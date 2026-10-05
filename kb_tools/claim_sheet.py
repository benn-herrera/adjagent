"""The claim-graph sheets: ``.index/`` in, DOT text out, SVG through the ``dot`` seam.

:func:`load` reads the index through :func:`kb_cmd.index.load` — nothing else of
it — plus the H1s of ``entry-point.md`` and each volume's ``index.md``, and the
two claim-graph build records beside ``kb-root/`` for each edge's provenance.
:func:`compose_sheet`, :func:`compose_digest` and :func:`compose_volume_sheet`
turn that into DOT text and touch neither the disk nor a binary, so composition
is testable without Graphviz. :func:`render` is the one write site, and refresh
its one caller.

**Every interpolated value passes through exactly one escaper**, chosen by where
it lands: :func:`_q` for a plain DOT string, :func:`_h` inside an HTML-like
label. Neither's output is handed to the other — a ``\\nabla`` that reached a
plain string unescaped would draw as a line break, and an ``&lt;`` escaped twice
draws as itself.

**Every iteration that reaches the text is sorted**, so the DOT is a pure
function of the index and the records: volumes by key with the KB-root bucket
last, nodes by id, edges by the ends as emitted and then relation.

Stdlib only.
"""

import html
import logging
import posixpath
import re
import textwrap
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from kb_tools import dot, kb_index_lib, kb_pipeline, kb_schema, kb_util
from kb_tools.kb_cmd import index as kb_index
from kb_tools.kb_survey.manifest import write_text_atomic

_log = logging.getLogger(__name__)

SHEET_FILENAME = "claim-graph.svg"
DIGEST_FILENAME = "claim-graph-digest.svg"

#: The ``kind`` of a node drawn for an edge end no record carries.
GHOST_KIND = "ghost"

#: The reader-facing provenance words, the only ones that reach a sheet.
CITED = "cited"
INFERRED = "inferred"
CUT = "cut"

#: The letters the two build records store, as ``kb_claimgraph.ask`` defines them: the unmarked
#: ask's "points at the candidate", and the classify ask's "supported by", which classify writes as
#: a ``depends`` edge in the pair's own direction. Copied rather than imported, because importing
#: ``kb_claimgraph`` from refresh's path closes a cycle through ``kb_claimgraph.gate``;
#: ``tests/test_claim_sheet.py`` holds them equal.
UNMARKED_POINTS_LETTER = "A"
CLASSIFY_DEPENDS_LETTER = "A"


@dataclass(frozen=True)
class Volume:
    """One cluster of the full sheet and one box of the digest; ``key`` is ``""`` for the KB-root bucket."""

    key: str
    title: str
    href: str


@dataclass(frozen=True)
class SheetNode:
    """A node as the sheets draw it.

    ``kind`` is the record's ``node_type``, except that a claim is ``block``,
    ``equation`` or ``prose`` and an edge end no record carries is
    :data:`GHOST_KIND`. ``href`` is relative to ``kb-root/``. ``volume_key`` is
    ``None`` for a ghost alone.
    """

    id: str
    kind: str
    band: str | None
    title: str
    href: str
    volume_key: str | None


@dataclass(frozen=True)
class SheetEdge:
    """One stroke, in record direction; two records differing only in ``context`` are one.

    ``provenance`` is :data:`CITED` or :data:`INFERRED` for ``depends``,
    :data:`CUT` for ``references`` (no other ``references`` edge is drawn, so
    none is loaded), and ``None`` for every other relation.
    """

    source: str
    target: str
    relation: str
    provenance: str | None


@dataclass(frozen=True)
class SheetInput:
    """Everything composition reads, built by :func:`load`."""

    kb_title: str
    volumes: tuple[Volume, ...]
    nodes: tuple[SheetNode, ...]
    edges: tuple[SheetEdge, ...]
    #: Claims other than equations whose kind was read from the title, no leaf citing them carrying a
    #: readable marker for them.
    claims_without_marker: int = 0


def multi_volume(sheet: SheetInput) -> bool:
    """Whether the digest and the per-volume sheets are drawn: two or more volumes hold nodes.

    The KB-root bucket is not a volume. With fewer, the full sheet alone says
    everything the other two would.
    """
    return len({node.volume_key for node in sheet.nodes if node.volume_key}) >= 2


# ---------------------------------------------------------------------------
# Style tables, each checked total over its vocabulary at import
# ---------------------------------------------------------------------------

_FRAME = "#333333"
_GHOST_FRAME = "#c0392b"


@dataclass(frozen=True)
class _NodeStyle:
    shape: str
    style: str
    penwidth: int
    fill: str | None  # None: filled by the node's build band
    meaning: str


#: Per record kind, the sheet kinds it draws as. A claim's three sub-kinds are
#: the only split; iterating this is the legend's kind order.
_NODE_STYLES: dict[str, dict[str, _NodeStyle]] = kb_schema.kind_table(
    {
        "claim": {
            "block": _NodeStyle("box", "filled,rounded", 2, None, "labelled block — theorem, lemma, … (bold frame)"),
            "equation": _NodeStyle("box", "filled", 1, None, "equation"),
            "prose": _NodeStyle("box", "filled,rounded", 1, None, "prose claim"),
        },
        "support": {"support": _NodeStyle("box", "filled,rounded,dashed", 1, None, "analytical support")},
        "experiment": {"experiment": _NodeStyle("component", "filled", 1, "#e8f4fd", "experiment")},
        "invariant": {"invariant": _NodeStyle("box", "filled", 2, "#d9d9d9", "structural invariant")},
        "axiom": {"axiom": _NodeStyle("box", "filled", 2, "#d9d9d9", "axiom")},
        "work": {"work": _NodeStyle("note", "filled", 1, "#f0e6ff", "external work")},
    },
    what="claim-sheet node styles",
)
_SHEET_KIND_STYLES: dict[str, _NodeStyle] = {
    sheet_kind: style for by_kind in _NODE_STYLES.values() for sheet_kind, style in by_kind.items()
}
_SHEET_KIND_ORDER: tuple[str, ...] = (*_SHEET_KIND_STYLES, GHOST_KIND)
_GHOST_MEANING = "an id no record carries"

#: How the digest counts a claim sub-kind; every record kind counts under
#: :func:`kb_schema.node_kind_plural`.
_CLAIM_PLURALS = {"block": "blocks", "equation": "equations", "prose": "prose"}


@dataclass(frozen=True)
class _EdgeStyle:
    word: str  # what the legend, the tooltips and the digest's counts call the stroke
    reverse: bool  # emitted target → source with dir=back, so the premise sits at the head
    premise: bool
    color: str
    extra: str
    glyph: str
    meaning: str


#: Per relation, the strokes it draws as, keyed by provenance. Iterating this is the legend's and the
#: counts' order.
_EDGE_STYLES: dict[str, dict[str | None, _EdgeStyle]] = {
    "depends": {
        CITED: _EdgeStyle(
            CITED, False, True, "#222222", "penwidth=1.2", "━━━▶", "depends, marked in the text; points to the premise"
        ),
        INFERRED: _EdgeStyle(
            INFERRED,
            False,
            True,
            "#2471a3",
            "style=dashed penwidth=1.3",
            "╍╍╍▶",
            "depends, found with no mark in the text; points to the premise",
        ),
    },
    "strengthens": {
        None: _EdgeStyle(
            "strengthens", True, True, "#1f6fb2", "style=dashed arrowtail=empty", "╍╍╍▷", "points to the claim lifted"
        )
    },
    "supports": {
        None: _EdgeStyle("supports", True, True, "#2e7d32", "arrowtail=empty", "━━━▷", "points to the claim lifted")
    },
    "rests-on": {
        None: _EdgeStyle(
            "rests-on", False, True, "#7d3c98", "style=dashed arrowhead=diamond", "╍╍╍◆", "points to the cited work"
        )
    },
    "references": {
        CUT: _EdgeStyle(
            CUT,
            False,
            False,
            "#c0392b",
            "style=dotted penwidth=1.2 arrowhead=open constraint=false",
            "┈┈┈▷",
            "a depends cut to break a circle; no premise",
        )
    },
}

_BAND_FILLS: dict[str, str] = {
    "ok-to-build": "#b7e4c0",
    "ok-with-caveats": "#e3f2b5",
    "input-only": "#ffe1a8",
    "do-not-build": "#ffb8a1",
    "refuted": "#e3a7c4",
    kb_schema.UNKNOWN_BAND_SLUG: "#eeeeee",
}
_BAND_LABELS: dict[str, str] = dict(kb_index.BUILD_BANDS)


def _require_total(table: Mapping[str, object], vocabulary: Iterable[str], *, what: str) -> None:
    """Raise unless ``table`` is keyed on exactly ``vocabulary`` — the edge and band analogue of ``kind_table``."""
    expected = set(vocabulary)
    if set(table) != expected:
        raise ValueError(
            f"{what}: not total over {sorted(expected)!r}; "
            f"handles no {sorted(expected - set(table))!r}, names unknown {sorted(set(table) - expected)!r}"
        )


_require_total(_EDGE_STYLES, kb_schema.EDGE_RELATIONS, what="claim-sheet edge styles")
_require_total(_BAND_FILLS, _BAND_LABELS, what="claim-sheet band fills")

_STROKE_ORDER: tuple[_EdgeStyle, ...] = tuple(
    style for relation in kb_schema.EDGE_RELATIONS for style in _EDGE_STYLES[relation].values()
)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

_H1_RE = re.compile(r"^# +(.+?)\s*$", re.MULTILINE)
_BLOCK_TITLE_RE = re.compile(
    r"^(Theorem|Proposition|Lemma|Corollary|Definition|Conjecture|Remark|Assumption|Axiom|Claim|Example)\b"
)
_PRINTED_NAME_RE = re.compile(r"^\S+(?: \S+)? \d+(?:\.\d+)*$")


def _h1(path: Path) -> str | None:
    """The first ``# `` heading of the document at ``path``, metadata block excluded; ``None`` without one."""
    if not path.is_file():
        return None
    found = _H1_RE.search(kb_index_lib.strip_frontmatter(path.read_text(encoding="utf-8")))
    return found.group(1) if found else None


_QUOTE_PREFIX_RE = re.compile(r"^[ \t]*(?:>[ \t]?)+")
_MATH_FENCE_RE = re.compile(r"^(`{3,}|~{3,})[ \t]*math\b")
#: A labelled block's first line: its bold name, which carries the source's ``\\label`` as a ``<span id>`` around
#: it where the source gave one.
_BLOCK_LABEL_RE = re.compile(r"^(?:<span\b[^>]*>)?\*\*")


def _title_kind(title: str) -> str:
    """A claim's kind from its title alone: the fallback where no leaf marker places it.

    A block titled with the author's argument rather than its printed name
    reads as prose, and costs a frame weight.
    """
    if kb_schema.equation_label(title) is not None:
        return "equation"
    if _BLOCK_TITLE_RE.match(title) or _PRINTED_NAME_RE.match(title):
        return "block"
    return "prose"


def _marker_kind(text: str, claim_id: str) -> str | None:
    """A claim's kind from where its Tier-2 marker sits in a leaf's body; ``None`` where no marker names it.

    Inside a ``math`` fence it is an equation; in a blockquote whose first line
    opens with a bold label, a block; anywhere else, prose.
    """
    offset = next((at for at, ids in kb_index_lib.tier2_markers(text) if claim_id in ids), None)
    if offset is None:
        return None
    lines = text.split("\n")
    at = text.count("\n", 0, offset)
    fence = None
    for line in lines[:at]:
        bare = _QUOTE_PREFIX_RE.sub("", line).strip()
        if fence is None:
            opened = _MATH_FENCE_RE.match(bare)
            fence = opened.group(1) if opened else None
        elif bare.startswith(fence) and not bare.strip(fence[0]):
            fence = None
    if fence is not None:
        return "equation"
    if _QUOTE_PREFIX_RE.match(lines[at]):
        start = at
        while start > 0 and _QUOTE_PREFIX_RE.match(lines[start - 1]):
            start -= 1
        quoted = (_QUOTE_PREFIX_RE.sub("", line).strip() for line in lines[start : at + 1])
        if _BLOCK_LABEL_RE.match(next((line for line in quoted if line), "")):
            return "block"
    return "prose"


def _leaf_bodies(kb_root: Path, paths: Iterable[str]) -> dict[str, str]:
    """Each readable leaf among ``paths``, metadata block excluded; a leaf that cannot be read is left out."""
    bodies = {}
    for path in sorted(set(paths)):
        try:
            bodies[path] = kb_index_lib.strip_frontmatter((kb_root / path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
    return bodies


def _claim_kinds(kb_root: Path, index: kb_index.Index) -> tuple[dict[str, str], int]:
    """Each claim's kind, from its marker in the first leaf citing it that carries one, else from its title.

    Returns the kinds and how many claims other than equations fell back to the title.
    """
    leaves = {claim.id: [citation.leaf_path for citation in index.cited_by(claim.id)] for claim in index.all_claims}
    bodies = _leaf_bodies(kb_root, (path for paths in leaves.values() for path in paths))
    kinds = {}
    fallbacks = 0
    for claim in index.all_claims:
        found = (_marker_kind(bodies[path], claim.id) for path in leaves[claim.id] if path in bodies)
        kind = next((kind for kind in found if kind is not None), None)
        if kind is None:
            kind = _title_kind(claim.title)
            # An equation never carries a marker, so its title is its rule rather than a fallback.
            if kb_schema.equation_label(claim.title) is None:
                fallbacks += 1
        kinds[claim.id] = kind
    return kinds, fallbacks


def _lettered(entries: Mapping[tuple[str, str], kb_pipeline.CandidateEntry], letter: str) -> set[tuple[str, str]]:
    return {pair for pair, entry in entries.items() if entry.letter == letter}


def load(kb_root: Path) -> SheetInput:
    """Read the sheets' input: ``kb_root``'s ``.index/``, the H1s that title it, the build records beside it.

    A ``depends`` edge whose pair the unmarked record answered "points" is
    inferred, every other one cited. A ``references`` row is drawn only where
    the classification record chose ``depends`` for its pair — a ``depends``
    cut to break a cycle. Absent records leave every ``depends`` cited and
    draw no ``references``. A record that does not read raises its own
    ``kb_pipeline`` error.
    """
    index = kb_index.load(kb_root / kb_util.INDEX_DIRNAME)
    repo_root = kb_root.parent
    unmarked = kb_pipeline.read_unmarked(repo_root)
    classification = kb_pipeline.read_classification(repo_root)
    inferred = _lettered(unmarked.pairs, UNMARKED_POINTS_LETTER) if unmarked else set()
    cut = _lettered(classification.candidates, CLASSIFY_DEPENDS_LETTER) if classification else set()

    claim_kinds, fallbacks = _claim_kinds(kb_root, index)
    nodes = {
        record.id: SheetNode(
            id=record.id,
            kind=claim_kinds.get(record.id, record.node_type),
            band=record.build_band if isinstance(record, (kb_index.Claim, kb_index.SupportNode)) else None,
            title=record.title,
            href=record.canonical_path + (f"#{record.canonical_anchor}" if record.canonical_anchor else ""),
            volume_key=kb_index_lib.node_domain(record.canonical_path),
        )
        for record in index.all_nodes
    }
    edges = []
    for source, target, relation in sorted({(e.source, e.target, e.relation) for e in index.all_depends_on_edges}):
        provenance = None
        if relation == "depends":
            provenance = INFERRED if (source, target) in inferred else CITED
        elif relation == "references":
            if (source, target) not in cut:
                continue
            provenance = CUT
        edges.append(SheetEdge(source, target, relation, provenance))
    ghosts = {end for edge in edges for end in (edge.source, edge.target)} - set(nodes)
    for ghost in ghosts:
        nodes[ghost] = SheetNode(id=ghost, kind=GHOST_KIND, band=None, title="", href="", volume_key=None)

    keys = {node.volume_key for node in nodes.values() if node.volume_key is not None}
    root_title = _h1(kb_root / kb_index_lib.ENTRY_POINT_FILENAME) or kb_util.KB_DIRNAME
    volumes = [
        Volume(key, _h1(kb_root / key / kb_index_lib.INDEX_FILENAME) or key, f"{key}/{kb_index_lib.INDEX_FILENAME}")
        for key in sorted(keys - {""})
    ]
    if "" in keys:
        volumes.append(Volume("", root_title, kb_index_lib.ENTRY_POINT_FILENAME))
    return SheetInput(
        kb_title=root_title,
        volumes=tuple(volumes),
        nodes=tuple(nodes[node_id] for node_id in sorted(nodes)),
        edges=tuple(edges),
        claims_without_marker=fallbacks,
    )


# ---------------------------------------------------------------------------
# Escaping and text
# ---------------------------------------------------------------------------


def _q(*lines: str) -> str:
    """A plain DOT string: each line with ``\\`` and ``"`` escaped, joined by DOT's ``\\n`` line break."""
    return '"' + "\\n".join(line.replace("\\", "\\\\").replace('"', '\\"') for line in lines) + '"'


def _h(text: str) -> str:
    """Text or an attribute value inside an HTML-like label, where backslashes are literal."""
    return html.escape(text, quote=True)


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _collapsed(title: str) -> str:
    return " ".join(title.split())


def _display_title(title: str) -> str:
    """The title as a box shows it: link text for links, maths without its fence, no emphasis or code marks."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)
    text = re.sub(r"\$`([^`]*)`\$", r"\1", text)
    return _collapsed(re.sub(r"[*`]", "", text))


def _tooltip(node: SheetNode) -> str:
    classes = f"{node.kind}, {_BAND_LABELS[node.band]}" if node.band is not None else node.kind
    return f"{node.id} [{classes}] {_collapsed(node.title)}"


def _label_lines(node: SheetNode) -> list[str]:
    wrapped = textwrap.wrap(_display_title(node.title), width=28)
    if len(wrapped) > 3:
        wrapped = [*wrapped[:2], wrapped[2][:27] + "…"]
    return [node.id, *wrapped]


def _relative(href: str, base: str) -> str:
    """``href``, relative to ``kb-root/``, made relative to the directory ``base`` names (``""``: kb-root itself)."""
    if not base or not href:
        return href
    path, mark, anchor = href.partition("#")
    return posixpath.relpath(path, base) + mark + anchor


# ---------------------------------------------------------------------------
# Graph structure every composition shares
# ---------------------------------------------------------------------------


def _style(edge: SheetEdge) -> _EdgeStyle:
    return _EDGE_STYLES[edge.relation][edge.provenance]


def _edge_ends(edges: Iterable[SheetEdge]) -> set[str]:
    """Every id some edge touches — a node outside this set is unattached."""
    return {end for edge in edges for end in (edge.source, edge.target)}


def _emitted(edge: SheetEdge) -> tuple[str, str]:
    """The edge's (tail, head) as written into the DOT, the premise always at the head."""
    return (edge.target, edge.source) if _style(edge).reverse else (edge.source, edge.target)


def _reduced(edges: Iterable[SheetEdge]) -> list[SheetEdge]:
    """``edges`` less each ``depends`` edge whose target its source still reaches through the ``depends`` kept.

    Taken one edge at a time against what is kept so far, so no reachability is
    lost even where the ``depends`` set holds a cycle. No other relation takes
    part, as a route or as a stroke to drop.
    """
    edges = sorted(edges, key=lambda edge: (edge.source, edge.target, edge.relation))
    following: dict[str, set[str]] = {}
    for edge in edges:
        if edge.relation == "depends":
            following.setdefault(edge.source, set()).add(edge.target)

    def reaches(start: str, goal: str) -> bool:
        seen, pending = {start}, [start]
        while pending:
            for node in following.get(pending.pop(), ()):
                if node == goal:
                    return True
                if node not in seen:
                    seen.add(node)
                    pending.append(node)
        return False

    kept = []
    for edge in edges:
        if edge.relation == "depends":
            following[edge.source].discard(edge.target)
            if reaches(edge.source, edge.target):
                continue
            following[edge.source].add(edge.target)
        kept.append(edge)
    return kept


def _members(sheet: SheetInput, key: str) -> list[SheetNode]:
    return [node for node in sheet.nodes if node.volume_key == key]


def _stroke_counts(edges: Iterable[SheetEdge]) -> str:
    """``3 cited · 1 inferred · 1 rests-on``: the strokes by the word each is drawn as, in legend order."""
    counts = Counter(_style(edge).word for edge in edges)
    return " · ".join(f"{counts[style.word]} {style.word}" for style in _STROKE_ORDER if counts[style.word])


@dataclass(frozen=True)
class _Bundle:
    tail: int
    head: int
    premise: bool
    edges: tuple[SheetEdge, ...]


def _bundles(sheet: SheetInput) -> list[_Bundle]:
    """Edges crossing between two buckets, one bundle per ordered pair and premise-ness, ghost ends excluded."""
    bucket = {v.key: k for k, v in enumerate(sheet.volumes)}
    bucket_of = {node.id: bucket[node.volume_key] for node in sheet.nodes if node.volume_key is not None}
    grouped: dict[tuple[int, int, bool], list[SheetEdge]] = {}
    for edge in sheet.edges:
        tail, head = _emitted(edge)
        if tail not in bucket_of or head not in bucket_of or bucket_of[tail] == bucket_of[head]:
            continue
        grouped.setdefault((bucket_of[tail], bucket_of[head], _style(edge).premise), []).append(edge)
    # Premise bundles before the dotted one for a pair.
    order = sorted(grouped, key=lambda key: (key[0], key[1], not key[2]))
    return [_Bundle(t, h, p, tuple(grouped[(t, h, p)])) for t, h, p in order]


def _legend(rows: list[str]) -> str | None:
    """The legend node's statement, or ``None`` where there is nothing to explain."""
    if not rows:
        return None
    body = "".join(f"<tr>{row}</tr>" for row in rows)
    return (
        'legend [shape=plaintext label=<<table border="1" cellborder="0" cellspacing="2" cellpadding="3" '
        f'color="#999999"><tr><td colspan="2" align="left"><b>legend</b></td></tr>{body}</table>>]'
    )


def _stroke_rows(edges: Iterable[SheetEdge]) -> list[str]:
    drawn = {_style(edge).word for edge in edges}
    return [
        f'<td><font color="{_h(style.color)}"><b>{_h(style.glyph)}</b></font></td>'
        f'<td align="left">{_h(style.word)} — {_h(style.meaning)}</td>'
        for style in _STROKE_ORDER
        if style.word in drawn
    ]


def _sheet_link(*, label: str, href: str, rank: str) -> list[str]:
    """The plaintext node one root sheet links to the other by, kept to the first or last rank."""
    return [
        f'  "sheet-link" [shape=plaintext fontsize=10 fontcolor="#1f6fb2" label={_q(label)} href={_q(href)}]',
        f'  {{ rank={rank}; "sheet-link" }}',
    ]


# ---------------------------------------------------------------------------
# The sheets of claims: the full sheet and one per volume
# ---------------------------------------------------------------------------


def _node_statement(node: SheetNode, base: str) -> str:
    style = _SHEET_KIND_STYLES[node.kind]
    fill = style.fill if style.fill is not None else _BAND_FILLS[node.band]
    return (
        f"{_q(node.id)} [shape={style.shape} style={_q(style.style)} penwidth={style.penwidth} "
        f"fillcolor={_q(fill)} label={_q(*_label_lines(node))} href={_q(_relative(node.href, base))} "
        f"tooltip={_q(_tooltip(node))}]"
    )


def _ghost_statement(node: SheetNode) -> str:
    return (
        f'{_q(node.id)} [shape=box style="dashed" penwidth=1 color={_q(_GHOST_FRAME)} label={_q(node.id)} '
        f"tooltip={_q(f'{node.id} — no record carries this id')}]"
    )


def _unattached_table(nodes: list[SheetNode], base: str) -> str:
    rows = "".join(
        f'<tr><td align="left" href="{_h(_relative(node.href, base))}" tooltip="{_h(_tooltip(node))}">'
        f"{_h(node.id)} — {_h(_cut(_display_title(node.title), 48))}</td></tr>"
        for node in nodes
    )
    return (
        '<table border="0" cellborder="0" cellspacing="0" cellpadding="1">'
        f'<tr><td align="left"><b>unattached ({len(nodes)})</b></td></tr>{rows}</table>'
    )


def _edge_statement(edge: SheetEdge) -> str:
    style = _style(edge)
    tail, head = _emitted(edge)
    direction = "dir=back " if style.reverse else ""
    word = style.word if style.word == edge.relation else f"{edge.relation}, {style.word}"
    tooltip = f"{edge.source} → {edge.target} ({word})"
    return f"{_q(tail)} -> {_q(head)} [{direction}color={_q(style.color)} {style.extra} tooltip={_q(tooltip)}]"


def _kind_swatch(kind: str) -> str:
    if kind == GHOST_KIND:
        return f'<td border="1" color="{_GHOST_FRAME}" style="dashed">{_h(kind)}</td>'
    style = _SHEET_KIND_STYLES[kind]
    dashed = ' style="dashed"' if "dashed" in style.style.split(",") else ""
    return (
        f'<td bgcolor="{_h(style.fill or "#ffffff")}" border="{style.penwidth}" color="{_FRAME}"{dashed}>'
        f"{_h(kind)}</td>"
    )


def _claims_legend_rows(drawn: list[SheetNode], edges: list[SheetEdge]) -> list[str]:
    kinds = {node.kind for node in drawn}
    rows = [
        f'{_kind_swatch(kind)}<td align="left">'
        f"{_h(_GHOST_MEANING if kind == GHOST_KIND else _SHEET_KIND_STYLES[kind].meaning)}</td>"
        for kind in _SHEET_KIND_ORDER
        if kind in kinds
    ]
    bands = {node.band for node in drawn}
    rows += [
        f'<td bgcolor="{_h(_BAND_FILLS[slug])}" border="1" color="{_FRAME}"> </td><td align="left">{_h(label)}</td>'
        for slug, label in kb_index.BUILD_BANDS
        if slug in bands
    ]
    return rows + _stroke_rows(edges)


def _cluster(k: int, *, title: str, subtitle: str, body: list[str]) -> list[str]:
    return [
        f"  subgraph cluster_{k} {{",
        '    graph [style="rounded" color="#888888" bgcolor="#fafafa" labeljust=l fontsize=12 '
        f'label=<<b>{_h(title)}</b><br/><font point-size="9">{_h(subtitle)}</font>>]',
        *body,
        "  }",
    ]


def _own_cluster(sheet: SheetInput, k: int, volume: Volume, connected: set[str], base: str) -> list[str]:
    members = _members(sheet, volume.key)
    unattached = [node for node in members if node.id not in connected]
    body = [f"    {_node_statement(node, base)}" for node in members if node.id in connected]
    if unattached:
        body.append(f'    "unattached_{k}" [shape=plaintext fontsize=8 label=<{_unattached_table(unattached, base)}>]')
    subtitle = f"{_count(len(members), 'node')} · {len(unattached)} unattached"
    return _cluster(k, title=volume.title, subtitle=subtitle, body=body)


def _claims_graph(
    sheet: SheetInput, *, name: str, title: str, clusters: list[str], drawn: list[SheetNode], edges: list[SheetEdge]
) -> list[str]:
    """Everything a sheet of claims holds but its clusters and links: header, ghosts, strokes, legend."""
    lines = [
        f"digraph {_q(name)} {{",
        '  graph [rankdir=TB newrank=true nodesep=0.25 ranksep=0.5 pad=0.3 fontname="Helvetica" '
        f"outputorder=edgesfirst labelloc=t label=<<b>{_h(title)}</b>>]",
        f'  node [fontname="Helvetica" fontsize=9 margin="0.08,0.04" color="{_FRAME}"]',
        "  edge [arrowsize=0.7]",
        *clusters,
    ]
    lines += [f"  {_ghost_statement(node)}" for node in drawn if node.kind == GHOST_KIND]
    lines += [f"  {_edge_statement(edge)}" for edge in sorted(edges, key=lambda e: (*_emitted(e), e.relation))]
    legend = _legend(_claims_legend_rows(drawn, edges))
    if legend is not None:
        lines.append(f"  {legend}")
    return lines


def compose_sheet(sheet: SheetInput) -> str:
    """The full sheet as DOT text: one cluster per bucket holding nodes, every drawn edge, unattached tables."""
    connected = _edge_ends(sheet.edges)
    clusters = []
    for k, volume in enumerate(sheet.volumes):
        if _members(sheet, volume.key):
            clusters += _own_cluster(sheet, k, volume, connected, "")
    lines = _claims_graph(
        sheet,
        name="claim-graph",
        title=sheet.kb_title,
        clusters=clusters,
        drawn=[node for node in sheet.nodes if node.id in connected],
        edges=_reduced(sheet.edges),
    )
    if multi_volume(sheet):
        lines += _sheet_link(label="volume digest →", href=DIGEST_FILENAME, rank="min")
    lines.append("}")
    return "\n".join(lines) + "\n"


def compose_volume_sheet(sheet: SheetInput, key: str) -> str:
    """One volume's sheet as DOT text: its nodes, their one-hop neighbours by volume, the edges touching it.

    Written at ``<key>/claim-graph.svg``, so every ``href`` is relative to that
    directory.
    """
    member_ids = {node.id for node in _members(sheet, key)}
    edges = [edge for edge in sheet.edges if edge.source in member_ids or edge.target in member_ids]
    connected = _edge_ends(edges)
    neighbours = connected - member_ids
    clusters = []
    for k, volume in enumerate(sheet.volumes):
        if volume.key == key:
            clusters += _own_cluster(sheet, k, volume, connected, key)
            continue
        near = [node for node in _members(sheet, volume.key) if node.id in neighbours]
        if near:
            body = [f"    {_node_statement(node, key)}" for node in near]
            clusters += _cluster(k, title=volume.title, subtitle=_count(len(near), "neighbour"), body=body)
    volume = next(volume for volume in sheet.volumes if volume.key == key)
    lines = _claims_graph(
        sheet,
        name="claim-graph",
        title=volume.title,
        clusters=clusters,
        drawn=[node for node in sheet.nodes if node.id in connected],
        edges=_reduced(edges),
    )
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The digest
# ---------------------------------------------------------------------------


def _plural(kind: str) -> str:
    return _CLAIM_PLURALS.get(kind) or kb_schema.node_kind_plural(kind)


def _volume_table(sheet: SheetInput, volume: Volume, connected: set[str]) -> str:
    members = _members(sheet, volume.key)
    member_ids = {node.id for node in members}
    kinds = Counter(node.kind for node in members)
    within = _stroke_counts(edge for edge in sheet.edges if edge.source in member_ids and edge.target in member_ids)
    by_kind = ", ".join(f"{kinds[kind]} {_plural(kind)}" for kind in _SHEET_KIND_ORDER if kinds[kind])
    rows = [
        f"<b>{_h(_cut(volume.title, 44))}</b>",
        _h(_count(len(members), "node") + (f": {by_kind}" if by_kind else "")),
        _h(f"{sum(1 for node in members if node.id not in connected)} unattached"),
    ]
    if within:
        rows.append(_h(f"within: {within}"))
    cells = "".join(f'<tr><td align="left">{row}</td></tr>' for row in rows)
    if volume.key:
        sheet_href = f"{volume.key}/{SHEET_FILENAME}"
        cells += f'<tr><td align="left" href="{_h(sheet_href)}"><font color="#1f6fb2">claim graph →</font></td></tr>'
    return (
        '<table border="1" cellborder="0" cellspacing="0" cellpadding="3" color="#888888" bgcolor="#fafafa">'
        f"{cells}</table>"
    )


def _bundle_statement(bundle: _Bundle) -> str:
    ends = f'"v_{bundle.tail}" -> "v_{bundle.head}"'
    label = _q(_stroke_counts(bundle.edges))
    if not bundle.premise:
        style = _EDGE_STYLES["references"][CUT]
        return f"{ends} [label={label} color={_q(style.color)} {style.extra}]"
    return f'{ends} [label={label} penwidth={min(1 + len(bundle.edges) / 4, 6):.1f} color="#222222"]'


def compose_digest(sheet: SheetInput) -> str:
    """The digest as DOT text: one box per volume, one bundle per pair of volumes edges cross between."""
    connected = _edge_ends(sheet.edges)
    lines = [
        'digraph "claim-graph-digest" {',
        '  graph [rankdir=LR nodesep=0.5 ranksep=1.2 pad=0.3 fontname="Helvetica"]',
        '  node [shape=plaintext fontname="Helvetica" fontsize=10]',
        '  edge [fontname="Helvetica" fontsize=9 arrowsize=0.8]',
    ]
    lines += [
        f'  "v_{k}" [href={_q(volume.href)} label=<{_volume_table(sheet, volume, connected)}>]'
        for k, volume in enumerate(sheet.volumes)
    ]
    bundles = _bundles(sheet)
    lines += [f"  {_bundle_statement(bundle)}" for bundle in bundles]
    legend = _legend(_stroke_rows(edge for bundle in bundles for edge in bundle.edges))
    if legend is not None:
        lines.append(f"  {legend}")
    lines += _sheet_link(label="← full claim graph", href=SHEET_FILENAME, rank="max")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Rendering — the one write site
# ---------------------------------------------------------------------------

_SVG_SIZE_RE = re.compile(r'<svg width="[^"]*" height="[^"]*"')


@dataclass(frozen=True)
class Outcome:
    """What :func:`render` did: ``failed`` decides refresh's exit, ``lines`` are its report, in print order."""

    failed: bool
    lines: tuple[str, ...]


def fit(svg: str) -> str:
    """``svg`` with its fixed point size replaced by ``width="100%"``, so the viewBox scales to the viewer.

    The SVG is another program's output, so a size attribute it no longer writes
    is logged and the SVG kept as it came rather than refused.
    """
    fitted, replaced = _SVG_SIZE_RE.subn('<svg width="100%"', svg, count=1)
    if not replaced:
        _log.warning("claim sheet: the SVG carries no fixed width and height to replace; written unscaled")
    return fitted


def _sheet_summary(sheet: SheetInput) -> str:
    connected = _edge_ends(sheet.edges)
    real = [node for node in sheet.nodes if node.kind != GHOST_KIND]
    return (
        f"{_count(len(real), 'node')}, {_count(len(_reduced(sheet.edges)), 'edge')} drawn of {len(sheet.edges)}, "
        f"{sum(1 for node in real if node.id not in connected)} unattached, "
        f"{_count(len(sheet.nodes) - len(real), 'ghost id')}"
    )


def _volume_summary(sheet: SheetInput, key: str) -> str:
    member_ids = {node.id for node in _members(sheet, key)}
    edges = [edge for edge in sheet.edges if edge.source in member_ids or edge.target in member_ids]
    neighbours = _edge_ends(edges) - member_ids
    return (
        f"{_count(len(member_ids), 'node')}, {_count(len(neighbours), 'neighbour')}, "
        f"{_count(len(_reduced(edges)), 'edge')} drawn"
    )


def _digest_summary(sheet: SheetInput) -> str:
    return f"{_count(len(sheet.volumes), 'volume')}, {_count(len(_bundles(sheet)), 'bundle')}"


def _sheets(sheet: SheetInput) -> list[tuple[str, str, str]]:
    """Each sheet :func:`multi_volume` calls for: its path under ``kb-root/``, its DOT text, its report summary."""
    sheets = [(SHEET_FILENAME, compose_sheet(sheet), _sheet_summary(sheet))]
    if multi_volume(sheet):
        sheets.append((DIGEST_FILENAME, compose_digest(sheet), _digest_summary(sheet)))
        sheets += [
            (f"{volume.key}/{SHEET_FILENAME}", compose_volume_sheet(sheet, volume.key), _volume_summary(sheet, volume.key))
            for volume in sheet.volumes
            if volume.key
        ]
    return sheets


def _placeholder_svg() -> str:
    """What stands where a sheet would be when ``dot`` is absent: the seam's notice, centred, scaling to the viewer."""
    reason, remedy = (html.escape(line, quote=False) for line in dot.ABSENT_NOTICE)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 800 120" '
        'font-family="Helvetica, Arial, sans-serif" text-anchor="middle">\n'
        '<rect x="1" y="1" width="798" height="118" rx="8" fill="#fafafa" stroke="#999999"/>\n'
        f'<text x="400" y="54" font-size="15" fill="#333333">{reason}</text>\n'
        f'<a href="{html.escape(dot.INSTALL_URL)}"><text x="400" y="82" font-size="14" fill="#1f6fb2">'
        f"{remedy}</text></a>\n"
        "</svg>\n"
    )


#: Fixed bytes, so a refresh without ``dot`` leaves a placeholder byte-identical.
PLACEHOLDER_SVG = _placeholder_svg()


def _placeholders(kb_root: Path, names: list[str], missing: dot.DotMissingError) -> Outcome:
    """Stand a placeholder where no sheet exists yet; keep any sheet, real or placeholder, that does."""
    lines = []
    for name in names:
        path = kb_root / name
        if path.is_file():
            lines.append(f"[refresh-sheet] Kept {name}.")
        else:
            write_text_atomic(PLACEHOLDER_SVG, path)
            lines.append(f"[refresh-sheet] Placeholder {name}.")
    lines.append(f"[refresh-sheet] NOTE {missing}")
    return Outcome(failed=False, lines=tuple(lines))


def _notes(sheet: SheetInput) -> list[str]:
    if not sheet.claims_without_marker:
        return []
    return [
        f"[refresh-sheet] NOTE {_count(sheet.claims_without_marker, 'claim')} without a readable marker; "
        f"kind read from the title."
    ]


def render(kb_root: Path) -> Outcome:
    """Draw every sheet beside ``kb_root``'s ``.index/``, writing each only where its bytes changed.

    Every sheet is drawn before any is written, so a refused graph writes
    nothing. Without ``dot`` none is drawn, and that is no failure: a
    placeholder stands where no sheet exists, and an existing sheet is kept. A
    build record that does not read fails the render, naming the record.
    """
    try:
        sheet = load(kb_root)
    except (kb_pipeline.UnmarkedRecordError, kb_pipeline.ClassificationRecordError) as unreadable:
        return Outcome(failed=True, lines=(f"FAIL: [refresh-sheet] {unreadable}",))
    sheets = _sheets(sheet)
    notes = _notes(sheet)
    drawn = []
    for name, composed, summary in sheets:
        try:
            drawn.append((name, fit(dot.to_svg(composed)), summary))
        except dot.DotMissingError as missing:
            placeholders = _placeholders(kb_root, [name for name, _, _ in sheets], missing)
            return Outcome(failed=False, lines=(*placeholders.lines, *notes))
        except dot.DotError as refused:
            return Outcome(failed=True, lines=(f"FAIL: [refresh-sheet] drawing {name}: {refused}",))
    lines = []
    for name, svg, summary in drawn:
        path = kb_root / name
        if path.is_file() and path.read_text(encoding="utf-8") == svg:
            verb = "Unchanged"
        else:
            write_text_atomic(svg, path)
            verb = "Wrote"
        lines.append(f"[refresh-sheet] {verb} {name}: {summary}.")
    return Outcome(failed=False, lines=(*lines, *notes))
