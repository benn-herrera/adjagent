"""Read-only comparison of a built KB against the author's hand-curated KB of the same corpus.

Invoked through `just measure-kb-roots` (kb-testing/justfile), which hands every
staged kb-root as a leading positional argument. The reference is the kb-root
under ``ModernCorpPristine/``, ours the one under ``ModernCorp/``; the rest are
ignored. Trailing ``--threshold <cosine>`` overrides the match threshold.

Produces, under ``.claude-temp/pristine-compare/`` at the repository root:
  claim-matches.tsv  every reference claim, its matched nodes of ours, score, both titles
  candidates.tsv     each reference claim's five best-scoring nodes of ours, matched or not
  edges.tsv          every reference `depends` edge, its recall class and, for a miss, the mark test
  summary.md         the headline figures

Writes nothing else.
"""

import math
import re
import sys
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path

from kb_tools import kb_index_lib
from kb_tools.kb_claimgraph import graph, inventory, prose, tree
from kb_tools.kb_claimgraph.shortlist import STOPWORDS, cosine
from kb_tools.kb_claimgraph.tree import strip_markers, unquote

OUT = Path(__file__).resolve().parents[2] / ".claude-temp" / "pristine-compare"
THRESHOLD = 0.30
TOP_K = 5

MARKER_RE = re.compile(r"<!-- claim-quality: (clm-[a-z0-9]+) -->")
HEADING_RE = re.compile(r"^#{1,6} ")
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[a-z]{2,}")

NAME_FORMS = {
    "proposition": r"(?:Proposition|Prop)",
    "theorem": r"(?:Theorem|Thm)",
    "corollary": r"(?:Corollary|Cor)",
    "lemma": r"Lemma",
    "conjecture": r"(?:Conjecture|Conj)",
    "definition": r"(?:Definition|Def)",
    "remark": r"Remark",
    "assumption": r"Assumption",
}
NAME_NUMBER_RE = re.compile(r"^\W*(" + "|".join(NAME_FORMS) + r")\s+([0-9A-Z][0-9.]*[a-z]?)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Span:
    """A half-open line range of one document: part of the text a claim is read from."""

    document: str
    start: int
    end: int


@dataclass(frozen=True)
class Claim:
    id: str
    title: str
    kind: str
    documents: tuple[str, ...]
    text: str
    spans: tuple[Span, ...] = ()
    printed: tuple[str, ...] = ()


def tokens(text: str) -> list[str]:
    plain = TAG_RE.sub(" ", strip_markers(text)).lower()
    return [word for word in WORD_RE.findall(plain) if word not in STOPWORDS]


def plain_text(text: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", unquote(strip_markers(text))).replace("*", "")).strip()


# --- the reference KB ----------------------------------------------------------


def hosting(documents: tree.Tree) -> dict[str, list[str]]:
    hosts: dict[str, list[str]] = {}
    for path, document in sorted(documents.documents.items()):
        for claim_id in (kb_index_lib.parse_frontmatter(document.text) or {}).get("claims") or ():
            hosts.setdefault(claim_id, []).append(path)
    return hosts


def reference_section(text: str, claim_id: str) -> str:
    """The claim's statement: from its marker to the next heading or marker, else the leaf's opening section."""
    lines = kb_index_lib.strip_frontmatter(text).splitlines()
    marker = f"<!-- claim-quality: {claim_id} -->"
    start = next((number + 1 for number, line in enumerate(lines) if marker in line), None)
    if start is None:
        start = next((number + 1 for number, line in enumerate(lines) if line.startswith("# ")), 0)
    end = start
    while end < len(lines) and not HEADING_RE.match(lines[end]) and not MARKER_RE.search(lines[end]):
        end += 1
    return "\n".join(lines[start:end])


def read_reference(kb_root: Path) -> tuple[dict[str, Claim], list[tuple[str, str]], Counter]:
    state = kb_index_lib.discover_kb(kb_root, diagnostic_stream=None)
    documents = tree.read(kb_root)
    hosts = hosting(documents)
    claims = {}
    for entry in state.claim_entries:
        docs = tuple(hosts.get(entry.id, ()))
        body = "\n".join(reference_section(documents.documents[doc].text, entry.id) for doc in docs)
        claims[entry.id] = Claim(id=entry.id, title=entry.title, kind="reference", documents=docs, text=body)
    relations = Counter((edge.relation, edge.target_kind) for entry in state.claim_entries for edge in entry.depends_on)
    edges = [
        (edge.source, edge.target)
        for entry in state.claim_entries
        for edge in entry.depends_on
        if edge.relation == "depends" and edge.target_kind == "claim"
    ]
    return claims, edges, relations


# --- our KB ----------------------------------------------------------------------


def read_ours(kb_root: Path) -> tuple[dict[str, Claim], set[tuple[str, str]], set[tuple[str, str]], list[inventory.Anchor]]:
    documents = tree.read(kb_root)
    sites = inventory.scan(documents)
    authored = graph.read(documents, sites)
    readable: dict[str, prose.Readable] = {}

    claims: dict[str, Claim] = {}
    for node in authored.nodes.values():
        lines = documents.documents[node.document].text.splitlines()
        blocks = [block for block in sites.claim_blocks() if block.document == node.document]
        block = next((found for found in blocks if found.display == node.locator), None)
        printed: tuple[str, ...] = ()
        if node.equation is not None:
            kind = "equation"
            fence = next(f for f in sites.fences if f.document == node.document and node.equation in f.labels)
            spans = (Span(node.document, fence.start, fence.end),)
        elif block is not None:
            kind = "block"
            spans = (Span(node.document, block.start, block.end),) + tuple(
                Span(proof.document, proof.start, proof.end)
                for proof in sites.proofs
                if any(subject.document == block.document and subject.start == block.start for subject in proof.subjects)
            )
            name = inventory._printed_name(block.display)
            printed = (plain_text(name).rstrip("."),) if name else ()
        else:
            kind = "prose"
            marker = f"<!-- claim-quality: {node.id} -->"
            line = next((n for n, text in enumerate(lines) if marker in text), None)
            if node.document not in readable:
                readable[node.document] = prose.readable(documents.documents[node.document], sites)
            paragraph = None if line is None else readable[node.document].render.paragraph_at(line)
            if paragraph is not None:
                spans = (Span(node.document, min(paragraph.lines), max(paragraph.lines) + 1),)
            else:
                spans = () if line is None else (Span(node.document, line, line + 1),)
        text = "\n".join(
            "\n".join(documents.documents[span.document].text.splitlines()[span.start : span.end]) for span in spans
        )
        claims[node.id] = Claim(
            id=node.id, title=node.title, kind=kind, documents=(node.document,), text=text, spans=spans, printed=printed
        )

    state = kb_index_lib.discover_kb(kb_root, diagnostic_stream=None)
    depends = {
        (edge.source, edge.target)
        for entry in state.claim_entries
        for edge in entry.depends_on
        if edge.relation == "depends" and edge.target_kind == "claim"
    }
    references = {(edge.source, edge.target) for entry in state.claim_entries for edge in entry.references}
    return claims, depends, references, list(sites.anchors)


# --- matching -----------------------------------------------------------------------


def vectors(documents: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    """Sublinear-tf, smoothed-idf, L2-normalised term vectors over one shared vocabulary."""
    frequency = Counter(term for words in documents.values() for term in set(words))
    count = len(documents)
    idf = {term: math.log((1 + count) / (1 + df)) + 1 for term, df in frequency.items()}
    out = {}
    for key, words in documents.items():
        weights = {term: (1 + math.log(tf)) * idf[term] for term, tf in Counter(words).items()}
        norm = math.sqrt(sum(value * value for value in weights.values())) or 1.0
        out[key] = {term: value / norm for term, value in weights.items()}
    return out


# --- edges ----------------------------------------------------------------------------


def reaches(edges: set[tuple[str, str]], sources: set[str], targets: set[str]) -> bool:
    following: dict[str, set[str]] = {}
    for source, target in edges:
        following.setdefault(source, set()).add(target)
    seen = set(sources)
    pending = deque(sources)
    while pending:
        for node in following.get(pending.popleft(), ()):
            if node in targets:
                return True
            if node not in seen:
                seen.add(node)
                pending.append(node)
    return False


def name_pattern(name: str) -> re.Pattern[str] | None:
    parsed = NAME_NUMBER_RE.match(name)
    if parsed is None:
        return None
    word, number = parsed.group(1).lower(), re.escape(parsed.group(2).rstrip("."))
    return re.compile(rf"\b{NAME_FORMS[word]}\.?\s*~?{number}(?![\d]|\.\d)", re.IGNORECASE)


def mark_test(
    *, a_nodes: list[Claim], b_nodes: list[Claim], b_reference: Claim, anchors: list[inventory.Anchor], texts: dict[str, list[str]]
) -> list[str]:
    """Every mark of B inside the text our pipeline reads for A's matched claims."""
    b_hosts = {doc for node in b_nodes for doc in node.documents}
    names = {name: "ours" for node in b_nodes for name in node.printed}
    names.setdefault(b_reference.title, "reference title")
    patterns = [(name, origin, found) for name, origin in names.items() if (found := name_pattern(name)) is not None]
    marks = []
    for a in a_nodes:
        for span in a.spans:
            for anchor in anchors:
                if anchor.document == span.document and span.start <= anchor.line < span.end and anchor.target in b_hosts:
                    marks.append(f"anchor {a.id}:{anchor.reference_type} -> {anchor.href}")
            body = plain_text("\n".join(texts[span.document][span.start : span.end]))
            for name, origin, pattern in patterns:
                hit = pattern.search(body)
                if hit is not None:
                    marks.append(f"name {a.id}: '{hit.group()}' ({origin}: {name})")
    return sorted(set(marks))




MISSES = ("references only", "nothing")
SWEEP = (0.20, 0.25, 0.30, 0.35, 0.40, 0.50)


def verdict(a: set[str], b: set[str], *, depends: set[tuple[str, str]], references: set[tuple[str, str]]) -> str:
    if not a or not b:
        return "endpoint unmatched (" + " and ".join(end for end, s in (("source", a), ("target", b)) if not s) + ")"
    if a & b:
        return "shared node"
    if any((x, y) in depends for x in a for y in b):
        return "depends"
    if any((y, x) in depends for x in a for y in b):
        return "depends reversed"
    if reaches(depends, a, b):
        return "depends path"
    if reaches(depends, b, a):
        return "depends path reversed"
    if any((x, y) in references or (y, x) in references for x in a for y in b):
        return "references only"
    return "nothing"


def recall(
    *,
    mapped: dict[str, set[str]],
    reference: dict[str, Claim],
    reference_edges: list[tuple[str, str]],
    ours: dict[str, Claim],
    depends: set[tuple[str, str]],
    references: set[tuple[str, str]],
    anchors: list[inventory.Anchor],
    texts: dict[str, list[str]],
) -> list[tuple[str, ...]]:
    rows = []
    for source, target in sorted(reference_edges):
        a, b = mapped[source], mapped[target]
        found = verdict(a, b, depends=depends, references=references)
        marks: list[str] = []
        split = ""
        if found in MISSES:
            marks = mark_test(
                a_nodes=[ours[x] for x in sorted(a)],
                b_nodes=[ours[y] for y in sorted(b)],
                b_reference=reference[target],
                anchors=anchors,
                texts=texts,
            )
            split = "marked" if marks else "unmarked — needs reading"
        rows.append(
            (
                source,
                reference[source].title,
                target,
                reference[target].title,
                found,
                split,
                "; ".join(marks),
                " ".join(sorted(a)),
                " ".join(sorted(b)),
                paper_scope(a, b, ours),
                document_level(a, b, ours=ours, depends=depends, references=references) if found in MISSES else "",
            )
        )
    return rows


def document_level(
    a: set[str], b: set[str], *, ours: dict[str, Claim], depends: set[tuple[str, str]], references: set[tuple[str, str]]
) -> str:
    """The claim-level verdict relaxed on B's side: any node of ours hosted where one of B's matches is hosted."""
    hosts = {ours[y].documents[0] for y in b}
    wide = {oid for oid, claim in ours.items() if claim.documents[0] in hosts} - a
    for relation, edges in (("depends", depends), ("references", references)):
        if any((x, y) in edges for x in a for y in wide):
            return relation
        if any((y, x) in edges for x in a for y in wide):
            return relation + " reversed"
    return "nothing"


def paper_scope(a: set[str], b: set[str], ours: dict[str, Claim]) -> str:
    """Whether some matched pair sits in one of our papers (top-level directory), where an anchor could join them."""
    if not a or not b:
        return ""
    papers = {ours[x].documents[0].split("/")[0] for x in a} & {ours[y].documents[0].split("/")[0] for y in b}
    return "same paper" if papers else "cross paper"


def tally(rows: list[tuple[str, ...]]) -> tuple[Counter, Counter]:
    return Counter(row[4].split(" (")[0] for row in rows), Counter(row[5] for row in rows if row[5])


def write_tsv(name: str, header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    body = ["\t".join(header)] + ["\t".join(cell.replace("\t", " ") for cell in row) for row in rows]
    (OUT / name).write_text("\n".join(body) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    threshold = THRESHOLD
    if "--threshold" in argv:
        index = argv.index("--threshold")
        threshold = float(argv[index + 1])
        argv = argv[:index] + argv[index + 2 :]
    OUT.mkdir(parents=True, exist_ok=True)
    roots = [Path(raw).resolve() for raw in argv]
    reference_root = next(root for root in roots if root.parent.name == "ModernCorpPristine")
    ours_root = next(root for root in roots if root.parent.name == "ModernCorp")

    reference, reference_edges, reference_relations = read_reference(reference_root)
    ours, depends, references, anchors = read_ours(ours_root)
    texts = {path: document.text.splitlines() for path, document in tree.read(ours_root).documents.items()}

    bags = {("r", key): tokens(c.title + "\n" + c.text) for key, c in reference.items()}
    bags |= {("o", key): tokens(c.title + "\n" + c.text) for key, c in ours.items()}
    vecs = vectors(bags)
    scored = {
        rid: sorted(((oid, cosine(vecs[("r", rid)], vecs[("o", oid)])) for oid in ours), key=lambda pair: -pair[1])
        for rid in sorted(reference, key=lambda key: reference[key].title)
    }

    def mapping(at: float) -> dict[str, set[str]]:
        return {rid: {oid for oid, score in pairs if score >= at} for rid, pairs in scored.items()}

    context = dict(
        reference=reference,
        reference_edges=reference_edges,
        ours=ours,
        depends=depends,
        references=references,
        anchors=anchors,
        texts=texts,
    )
    mapped = mapping(threshold)
    edge_rows = recall(mapped=mapped, **context)
    classes, split = tally(edge_rows)

    match_rows, candidate_rows = [], []
    for rid, pairs in scored.items():
        title = reference[rid].title
        kept = [(oid, score) for oid, score in pairs if score >= threshold]
        if not kept:
            match_rows.append((rid, title, "", "", "", "UNMATCHED", ""))
        for oid, score in kept:
            match_rows.append((rid, title, f"{score:.3f}", oid, ours[oid].kind, ours[oid].title, ours[oid].documents[0]))
        for rank, (oid, score) in enumerate(pairs[:TOP_K], start=1):
            candidate_rows.append(
                (rid, title, str(rank), f"{score:.3f}", oid, ours[oid].kind, ours[oid].title, ours[oid].documents[0])
            )

    write_tsv("claim-matches.tsv", ("ref_id", "ref_title", "score", "ours_id", "ours_kind", "ours_title", "ours_document"), match_rows)
    write_tsv(
        "candidates.tsv",
        ("ref_id", "ref_title", "rank", "score", "ours_id", "ours_kind", "ours_title", "ours_document"),
        candidate_rows,
    )
    write_tsv(
        "ours-nodes.tsv",
        ("ours_id", "kind", "document", "spans", "tokens", "title"),
        [
            (c.id, c.kind, c.documents[0], " ".join(f"{s.start}-{s.end}" for s in c.spans), str(len(bags[("o", c.id)])), c.title)
            for c in sorted(ours.values(), key=lambda c: (c.documents[0], c.id))
        ],
    )
    write_tsv(
        "edges.tsv",
        ("ref_source", "ref_source_title", "ref_target", "ref_target_title", "recall", "mark_split", "marks", "ours_sources", "ours_targets", "scope", "document_level"),
        edge_rows,
    )

    matched = [rid for rid, kept in mapped.items() if kept]
    kinds = Counter(c.kind for c in ours.values())
    fan = Counter(len(kept) for kept in mapped.values())
    ours_matched = {oid for kept in mapped.values() for oid in kept}
    volumes = Counter(
        (reference[rid].documents[0].split("/")[0] if reference[rid].documents else "?", ours[oid].documents[0].split("/")[0])
        for rid, kept in mapped.items()
        for oid in kept
    )
    top1 = sorted(pairs[0][1] for pairs in scored.values())

    sweep = []
    for at in SWEEP:
        at_classes, at_split = tally(recall(mapped=mapping(at), **context))
        sweep.append(
            f"| {at:.2f} | {sum(1 for kept in mapping(at).values() if kept)} | "
            + " | ".join(
                str(at_classes.get(name, 0))
                for name in ("depends", "depends reversed", "depends path", "depends path reversed", "shared node", "references only", "nothing", "endpoint unmatched")
            )
            + f" | {at_split.get('marked', 0)} |"
        )

    summary = [
        "# ModernCorpPristine (reference) vs ModernCorp (ours)",
        "",
        f"script: {Path(__file__).resolve()}",
        f"reference: {reference_root}",
        f"ours: {ours_root}",
        "",
        f"reference: {len(reference)} claims; depends-on relations {dict(sorted((f'{r}/{k}', n) for (r, k), n in reference_relations.items()))}",
        f"reference claim-to-claim depends edges: {len(reference_edges)}",
        f"ours: {len(ours)} claim nodes {dict(sorted(kinds.items()))}; depends {len(depends)}; references {len(references)}",
        "",
        f"## Claim matching — TF-IDF cosine over title+statement, threshold {threshold}",
        "",
        f"matched: {len(matched)} of {len(reference)}; unmatched {len(reference) - len(matched)}",
        f"matches per reference claim: {dict(sorted(fan.items()))}",
        f"distinct nodes of ours matched: {len(ours_matched)} ({dict(sorted(Counter(ours[o].kind for o in ours_matched).items()))})",
        f"best score per reference claim, sorted: {', '.join(f'{s:.2f}' for s in top1)}",
        "unmatched reference claims (best candidate in candidates.tsv):",
        *[f"  {rid}  {reference[rid].title}  (best {scored[rid][0][1]:.3f})" for rid, kept in mapped.items() if not kept],
        "",
        "matches by reference volume x our paper (top-level directory of each host document):",
        *[f"  {volume:<12} {paper:<55} {count}" for (volume, paper), count in sorted(volumes.items())],
        "",
        "## Edge recall over reference depends edges",
        "",
        *[f"  {name}: {count}" for name, count in classes.most_common()],
        "",
        "## Mechanical split of misses (references only + nothing)",
        "",
        *[f"  {name}: {count}" for name, count in split.most_common()],
        "",
        f"anchors of ours resolving to a document: {sum(1 for x in anchors if x.target)}; of them crossing papers: "
        f"{sum(1 for x in anchors if x.target and x.target.split('/')[0] != x.document.split('/')[0])}",
        "misses by paper scope (whether some matched pair shares one of our papers):",
        *[
            f"  {scope}: {count}"
            for scope, count in sorted(Counter(f"{row[9]}, {row[5]}" for row in edge_rows if row[5]).items())
        ],
        "",
        "misses re-read at document level (A's matches to any node hosted in a document hosting one of B's matches):",
        *[f"  {name}: {count}" for name, count in Counter(row[10] for row in edge_rows if row[5]).most_common()],
        "",
        "## Threshold sensitivity",
        "",
        "| threshold | matched | depends | reversed | path | path reversed | shared node | references only | nothing | endpoint unmatched | marked |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        *sweep,
        "",
    ]
    (OUT / "summary.md").write_text("\n".join(summary), encoding="utf-8")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
