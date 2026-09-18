"""The document tree, read off ``kb-root/`` — this package's sole input.

No ``.tex``, no pandoc AST, no bibliography, no intermediate the front end
happened to keep. Everything the claim graph is built from is read here, and a
fact the tree does not carry is a fact this package does not have.

Three readings live here because more than one stage needs each of them: the
document set with its two link relations (the down-link spine and the up-links
that invert it), the blockquote-prefix strip every scan over an
author-distinguished block runs first, and the marker strip that separates
authored content from the metadata an earlier pass appended to it. Each is read
once and shared, the way :mod:`kb_tools.kb_docgraph.walk` and
:mod:`kb_tools.kb_docgraph.text` are.
"""

import posixpath
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .. import kb_index_lib, kb_links
from ..kb_write import render

#: An id the marker composers accept, used only to read back the opening token
#: each of them writes in front of it.
_MARKER_PROBE = "clm-aaaaaa"


def _opener(marker: str) -> str:
    return marker[: marker.index(_MARKER_PROBE)].rstrip()


#: What each marker the write API writes into an authored document opens with,
#: read off the module that composes them rather than re-typed here.
MARKER_OPENERS: tuple[str, ...] = (
    _opener(render.render_id_marker(_MARKER_PROBE)),
    _opener(render.render_tier2_marker(_MARKER_PROBE)),
)

#: Those two and the frontmatter block's opener: every metadata artifact the
#: write API inserts into an authored document, which is the set point 14's
#: cleanliness check reads.
METADATA_OPENERS: tuple[str, ...] = (render.FRONTMATTER_OPENER, *MARKER_OPENERS)

#: One marker where it sits, with the space that separates it from the content
#: it follows. **A Tier-2 marker is appended to the end of the line it marks,
#: never written on a line of its own**: a comment alone on a line is a
#: block-level element and splits the paragraph or blockquote it lands in. So a
#: line carrying one is authored content *plus* a marker, and a scan reading
#: that content removes the marker rather than dropping the line — which is what
#: lets a pass re-scan a tree an earlier pass has already written to.
_MARKER_RE = re.compile("|".join(rf"[ \t]*{re.escape(opener)}.*?-->" for opener in MARKER_OPENERS))


def strip_markers(text: str) -> str:
    """``text`` with every marker the write API appended to a line removed."""
    return _MARKER_RE.sub("", text)


#: One line's leading blockquote markers — indent, ``>``, optional space, once
#: per nesting level. The same shape the write API strips before matching a
#: locator, so a span this package reads out of a quoted block is a span that
#: API can find again.
BLOCKQUOTE_PREFIX = re.compile(r"^(?:[ \t]{0,3}>[ \t]?)+")

#: A rewritten cross-reference, as point 7 renders one. The form it matches is
#: SPEC.md's, under Corpus Invariants' cross-reference join, which is also where
#: the identifier a reference resolves against is stated: this pattern reads a
#: contract rather than being one. All three attributes, in the order the
#: contract states them.
#:
#: **The third is read because an equation reference carries its target nowhere
#: else.** ``data-reference`` is the author's own ``\label``, and it rides every
#: anchor whether or not the fragment does — which for an ``eqref`` is the whole
#: of what says *which* equation, point 9 leaving an equation's label inside the
#: maths fence rather than as an id, so the anchor resolves to its document with
#: an empty fragment. Measured over the staged corpus: 717 of 717 ``eqref``
#: anchors carry no fragment, and 1945 of 1945 anchors carry this attribute.
#:
#: **The type is read as whatever the attribute holds, and a narrower class was
#: the defect.** ``([a-z]+)`` matched ``ref`` and ``eqref`` and refused both
#: spellings pandoc gives the cleveref family — ``ref+label`` for ``\cref`` and
#: ``\autoref``, ``ref+Label`` for ``\Cref`` — so references the trees carried
#: were read as none. SPEC.md's cross-reference join says only that the type is
#: the referencing macro's own kind and enumerates no vocabulary, so a class
#: that enumerates one is a second contract, and the next spelling defeats it
#: the same way this one was defeated.
#:
#: **A cleveref anchor is handed downstream under its own type**, and nothing
#: downstream reads the type to pick a route any more. A cleveref command names
#: whatever its label names and says which nowhere, so calling one an ``eqref``
#: would have asserted about every ``\cref`` to a theorem a thing that is true
#: of few of them, and flattening it to ``ref`` would erase the one fact
#: separating a cleveref equation reference from an author's own ``\ref{eq:8}``
#: — two populations a later pass has to count apart. What the pass-through once
#: cost was that a cleveref naming an equation took the identifier route and
#: reached nothing; :func:`attribute._target_end` now tries the identifier route
#: and falls back to the label-to-fence join for every type alike, so ordering
#: decides what typing used to, and the cost is paid off.
#:
#: Matched over the blockquote-stripped text because the reader wraps a long tag
#: across lines and the continuation line carries the quote prefix, which would
#: break a match that read the raw bytes.
ANCHOR_RE = re.compile(r'<a\s+href="([^"]*)"\s+data-reference-type="([^"]+)"\s+data-reference="([^"]*)"', re.DOTALL)

#: A rewritten cross-reference whole, with the text it shows a reader inside it.
#: :data:`ANCHOR_RE` reads the *attributes* and stops at the third, which is all
#: a reading of what an anchor names needs; this is the other question — what the
#: page says where the anchor sits — and it is asked wherever an anchor's span
#: has to become a value a person reads.
ANCHOR_RENDERING_RE = re.compile(r"<a\s[^>]*>(?P<rendering>.*?)</a>", re.DOTALL)

#: The two type spellings whose ``data-reference`` is a *list* of labels.
#: Cleveref splits its own argument on the comma, so a label reaching one of
#: these can never contain one — while a ``\ref`` takes exactly one label that
#: may, and this corpus carries four of them (``\ref{cor: decay, hyper, unif}``).
#: That is why the split below is keyed on the type and not on the comma: a rule
#: reading the comma alone turns those four resolving anchors into dead
#: fragments.
CLEVEREF_REFERENCE_TYPES: frozenset[str] = frozenset({"ref+label", "ref+Label"})

_LABEL_SEPARATOR = ","


def anchor_labels(reference_type: str, label: str) -> tuple[str, ...]:
    """The labels one anchor names — several only where a cleveref named several.

    ``\\cref{a,b}`` names two targets and states two relationships, and pandoc
    emits it as one anchor. Every reading that asks what an anchor names has to
    split it the same way or the two disagree about the corpus, which is why
    this is a function here rather than a comprehension at each call site.

    **The split is a reading, not yet a resolution.** Point 7 rewrites an href
    against :attr:`kb_docgraph.outline.VolumeTree.label_paths`, which is keyed on
    single labels — so a multi-label anchor matches no key, keeps its href as the
    bare fragment ``#a,b``, and resolves to no document. The labels this yields
    therefore reach the narrowing carrying no target until that rewrite handles a
    list.
    """
    if reference_type not in CLEVEREF_REFERENCE_TYPES:
        return (label,)
    return tuple(found for part in label.split(_LABEL_SEPARATOR) if (found := part.strip())) or (label,)


def unquote(text: str) -> str:
    """``text`` with each line's blockquote markers removed, line count intact.

    Line-for-line, so an offset into the result names the same line of the
    original. Point 9's fence-inside-a-blockquote case is why this exists: a
    scanner that anchors on column zero misses eight of this corpus's fences,
    and an unclosed fence swallows everything after it.
    """
    return "\n".join(BLOCKQUOTE_PREFIX.sub("", line) for line in text.splitlines())


@dataclass(frozen=True)
class Document:
    """One document of the tree, by its kb-root-relative POSIX path."""

    path: str
    text: str

    @property
    def domain(self) -> str:
        """The first path component — the volume this document falls under.

        Empty for ``entry-point.md``, which falls under no volume. This is what
        the citation gate partitions register entries by and where each
        register file lands.
        """
        head, sep, _ = self.path.partition("/")
        return head if sep else ""

    @property
    def is_index(self) -> bool:
        return self.path.rsplit("/", 1)[-1] == kb_index_lib.INDEX_FILENAME

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()

    @property
    def heading(self) -> str | None:
        """The document's own H1 **as the words the page shows**, or ``None``.

        The **first** such line rather than the best one: the partition writes a
        document one heading, so a reader preferring a later match would be
        preferring something the author's own prose happened to spell.

        A heading is *rendered* LaTeX, so a section the author titled with a
        ``\\ref`` is titled with the anchor point 7 rewrote — attribute, href and
        all. :data:`ANCHOR_RENDERING_RE` takes that back to what a reader of the
        line sees, for :func:`inventory._readable`'s reason and with its
        consequence: a value carried into a register heading may not carry the
        markup that produced it, not least because the href inside it is
        relative to this document and the heading is read somewhere else.
        """
        for line in self.text.splitlines():
            if line.startswith("# "):
                shown = ANCHOR_RENDERING_RE.sub(r"\g<rendering>", strip_markers(line[2:]))
                return shown.strip() or None
        return None


@dataclass(frozen=True)
class Tree:
    """The document set and the two relations point 5 says must invert."""

    root: Path
    documents: Mapping[str, Document]
    #: Down-link children, in the order each index lists them (point 4).
    children: Mapping[str, tuple[str, ...]]
    #: The up-link each non-root document opens with (point 3), by path.
    parents: Mapping[str, str]

    def domains(self) -> tuple[str, ...]:
        return tuple(sorted({doc.domain for doc in self.documents.values() if doc.domain}))


#: The closed ``kind:`` vocabulary, used as specified rather than collapsed.
#: All three are pure path shape: nothing about a document's own body enters
#: the label, because a document with children carries no body of its own.
KIND_ENTRY_POINT = "entry-point"
KIND_INDEX = "index"
KIND_LEAF = "leaf"

#: The kind that must declare its claims or their absence — what the tier-1
#: coverage check is keyed on. A set because its readers ask membership of a
#: ``kind:`` field that may hold anything.
DECLARING_KINDS: frozenset[str] = frozenset({KIND_LEAF})


def document_kind(path: str, *, has_children: bool) -> str:
    """The structural-position label of one document."""
    if path == kb_index_lib.ENTRY_POINT_FILENAME:
        return KIND_ENTRY_POINT
    return KIND_INDEX if has_children else KIND_LEAF


def resolve(source: str, target: str) -> str:
    """A link target spelled in ``source``, as a kb-root-relative path.

    Relative resolution is the only correct one: every reader of a KB link —
    the dead-link gate and the citation gate alike — resolves it against the
    file the link sits in, never against the KB root.
    """
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def _document_paths(kb_root: Path) -> list[str]:
    """Every ``.md`` the verifier's own walk sees, in path order.

    ``kb_index_lib.kb_files`` and not a walk of this package's own: the
    documents this package must stamp a ``kind:`` onto are the documents that
    walk will later demand one from, and two implementations of the exclusion
    rules is how the two sets start to differ.
    """
    return [path.relative_to(kb_root).as_posix() for path in kb_index_lib.kb_files(kb_root)]


def _links(document: Document) -> list[tuple[int, str]]:
    """Every markdown link in ``document`` that names another document, located.

    Code spans are neutralized first — an example inside a fence is
    documentation — through the same primitive the dead-link gate reads a link
    with, so the two see the same link set.
    """
    found = []
    for number, line in enumerate(kb_links.blank_fenced_lines(kb_links.strip_code(document.text)), start=1):
        for match in kb_links.LINK_RE.finditer(line):
            target = kb_links.strip_target(match.group(1))
            if target.startswith("#") or re.match(r"^[a-z][a-z0-9+.-]*:", target):
                continue
            path, _, _ = target.partition("#")
            if path.endswith(".md"):
                found.append((number, path))
    return found


def read(kb_root: Path) -> Tree:
    """Read the tree and both of its link relations. Asserts nothing; that is stage A's."""
    documents = {
        path: Document(path=path, text=(kb_root / path).read_text(encoding="utf-8"))
        for path in _document_paths(kb_root)
    }

    children: dict[str, tuple[str, ...]] = {}
    parents: dict[str, str] = {}
    for path, document in documents.items():
        links = _links(document)
        uplink = next((target for number, target in links if number == 1), None)
        first = next(iter(document.lines), "")
        if uplink is not None and kb_index_lib.UPLINK_MARKER in first:
            parents[path] = resolve(path, uplink)
        down = [resolve(path, target) for number, target in links if number != 1]
        children[path] = tuple(dict.fromkeys(down))

    return Tree(root=kb_root, documents=documents, children=children, parents=parents)
