"""Stage E — graph assembly. No new fact enters here.

Every value below is read off stage B's inventory or stage C's claims, or is
derived from a path. What this stage adds is arrangement: which register each
entry belongs in, what ``kind:`` each document carries, which documents declare
which claims, and where a Tier-2 marker goes.

**Two kinds of thing are arranged into one kind of entry.** A claim the author
marked as a block, and a referenced equation nothing in the graph holds
(:mod:`equation`) — the second is stage B's reading arranged, exactly like the
first, and both become ordinary ``clm-`` entries. Where they differ is the
marker: an equation has no line of prose to anchor one to, its position being
the ``\\label`` inside its maths fence, so it takes none and is not counted
toward the threshold that demands one of everything else.

**Ids do not exist yet**, and cannot: an insert op mints its own id and there is
no way to spell "depends on the third entry in this file". So a document record
and a marker record name their claims by **position in** :attr:`Plan.entries`,
which is the order pass 1 mints in and the order the minted ids come back in.
That binding is the whole reason the write path is four passes.

**No number is authored anywhere.** Every register entry's rigor is the pending
literal; there is no confidence, no fraction and no strength in this module or
downstream of it. Local rigor is hand-authored by a grading seat on a later
pass, and solidity is computed by refresh.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from .. import kb_index_lib, kb_schema
from ..kb_write import render
from . import endcap, equation
from .identify import Claim
from .inventory import Inventory
from .report import ClaimGraphError
from .tree import DECLARING_KINDS, Tree, document_kind

#: Where a domain's register lives. One per volume, because the citation gate
#: partitions register entries by the first path component.
REGISTER_FILENAME = "claim-quality.md"

#: Where the external works live: the KB root's own register, one file for the
#: whole corpus. Single-sourced in ``kb_index_lib`` and named here because this
#: is the module that decides an entry's home — the works are corpus-wide by
#: design, so they are the one entry kind not filed under a volume.
WORKS_REGISTER = kb_index_lib.WORKS_REGISTER

#: What a document with no author-marked block carries while no pass has read
#: its prose. It states the run's scope and not a finding about the document: a
#: reason asserting the document states no result would be a falsehood written
#: on the strength of a stage that did not run.
#:
#: **Also the resumption marker**, compared by identity in
#: :func:`conform.determination`, which is where what that costs is stated. It
#: is one of two reserved reason literals now; the other is
#: :data:`identify.UNANCHORED_REASON`, which is the same pattern for a run that
#: read a document and could anchor nothing in it.
#:
#: Defined in ``kb_index_lib`` and named here because this is the module that
#: writes it: the build pipeline's coverage check for claim discovery reads the
#: same literal, and it cannot import this package.
UNSCANNED_REASON = kb_index_lib.UNSCANNED_REASON


@dataclass(frozen=True)
class Entry:
    """One register entry to insert, in mint order.

    Two things are assembled into one of these and the difference is
    ``equation``: a claim the author marked as a block, and a referenced
    equation nothing else in the graph holds (:mod:`equation`). They share every
    other field because they become the same kind of node — an ordinary ``clm-``
    entry, minted by the same op into the same register.
    """

    register: str
    title: str
    rationale: str
    #: The document hosting it.
    document: str
    #: Where in that document it sits: a block's own display line, or — for an
    #: equation — its ``\\label``, which is inside the maths fence rather than on
    #: a line of prose.
    locator: str
    #: The equation's ``\\label`` where this entry stands for one, ``None`` where
    #: it stands for a claim-bearing block. **It is what says a Tier-2 marker
    #: does not apply**: the marker exists to make a claim's position
    #: recoverable, and an equation's position is its label — carried in the
    #: title, and findable in the document's own fence — so there is nothing for
    #: a marker to add and nowhere outside the maths to put one.
    equation: str | None = None


@dataclass(frozen=True)
class DocumentRecord:
    """One document's frontmatter: its kind, and what it declares."""

    path: str
    kind: str
    #: Positions in :attr:`Plan.entries` of the claims this document hosts.
    claims: tuple[int, ...] = ()
    no_claim: str | None = None


@dataclass(frozen=True)
class Marker:
    """One Tier-2 marker: a claim's id, anchored at its own display line."""

    document: str
    entry: int
    locator: str


@dataclass(frozen=True)
class Plan:
    """Everything the declared pass's write passes will land.

    No *internal* edge field: dependency attribution between claims of this
    corpus is the discovered pass's, and it runs over an authored graph rather
    than beside the writes that create one. The endcap's edges are here because
    they are not attribution: which works a claim rests on is a comparison of
    two positions stage B already recorded, so it is decided in this pass with
    everything else that is decided mechanically.
    """

    entries: tuple[Entry, ...] = ()
    documents: tuple[DocumentRecord, ...] = ()
    markers: tuple[Marker, ...] = ()
    works: tuple[endcap.CitedWork, ...] = ()
    #: ``(entry position, work id)`` — the off-graph edges, in entry order. The
    #: source is named by position for :class:`Marker`'s reason: no id exists
    #: for it until the first write pass mints one. The target needs no such
    #: indirection, a work's id being derived from its key rather than minted.
    rests_on: tuple[tuple[int, str], ...] = ()

    def registers(self) -> tuple[str, ...]:
        return tuple(sorted({entry.register for entry in self.entries}))


def register_for(document: str) -> str:
    """The register a claim hosted by ``document`` belongs in."""
    domain, _, _ = document.partition("/")
    return f"{domain}/{REGISTER_FILENAME}"


def _rationale(claim: Claim) -> str:
    return (
        f"Stated by the author as a labelled {claim.environment} block in {claim.document}; the title and "
        f"the locator are that block's own display line. Neither dependency attribution nor rigor "
        f"assessment has run over it."
    )


def _equation_rationale(found: equation.ReferencedEquation) -> str:
    return (
        f"A labelled equation in {found.document} that this corpus's own cross-references name and that no "
        f"claim-bearing block and no proof holds. The title carries the equation's own label, which is what "
        f"a cross-reference resolves through; the equation is a node so that those references reach "
        f"something, not because anybody read it as stating a result. Neither dependency attribution nor "
        f"rigor assessment has run over it."
    )


def _equation_entries(tree: Tree, inventory: Inventory) -> tuple[Entry, ...]:
    """One entry per referenced equation nothing else in the graph holds.

    The title is the hosting document's own H1 and the equation's own label —
    both the author's words, and the pair unique across the corpus. A document
    with no H1 is refused rather than titled from its path: the heading is the
    half of the title a reader recognizes the node by, and a node named after a
    file is one no reader can place.

    **The heading is normalised before it is composed in**, because this is the
    one title source whose words are an author's running prose rather than a
    display line: a heading carrying a non-breaking space comes back off the
    register as an ordinary one, and the mint-order proof — which compares the
    title asked for against the title landed — reads that as the wrong entry.
    :func:`render.collapse_prose` is the parser's own normalization applied at
    write time, which is what makes the comparison well-posed.
    """
    found: list[Entry] = []
    for referenced in equation.unheld(inventory):
        heading = tree.documents[referenced.document].heading
        if heading is not None:
            heading = render.collapse_prose(heading) or None
        if heading is None:
            raise ClaimGraphError(
                "equation-heading",
                f"{referenced.document} carries no H1, so the equation labelled {referenced.label!r} in it "
                f"has no title to be minted under. Every document of a conforming tree carries one",
            )
        found.append(
            Entry(
                register=register_for(referenced.document),
                title=kb_schema.equation_title(label=referenced.label, heading=heading),
                rationale=_equation_rationale(referenced),
                document=referenced.document,
                locator=referenced.label,
                equation=referenced.label,
            )
        )
    return tuple(found)


def assemble(tree: Tree, inventory: Inventory, claims: Sequence[Claim]) -> Plan:
    """Arrange the claims, the referenced equations and the tree into the write passes' inputs."""
    entries = tuple(
        Entry(
            register=register_for(claim.document),
            title=claim.title,
            rationale=_rationale(claim),
            document=claim.document,
            locator=claim.locator,
        )
        for claim in claims
    ) + _equation_entries(tree, inventory)

    hosted: dict[str, list[int]] = {}
    for position, entry in enumerate(entries):
        hosted.setdefault(entry.document, []).append(position)

    documents = []
    for path in sorted(tree.documents):
        positions = tuple(hosted.get(path, ()))
        kind = document_kind(path, has_children=bool(tree.children[path]))
        declares = kind in DECLARING_KINDS
        documents.append(
            DocumentRecord(
                path=path,
                kind=kind,
                claims=positions,
                no_claim=UNSCANNED_REASON if declares and not positions else None,
            )
        )

    # Counted over the block-hosted entries alone, at both ends of the rule: an
    # equation node takes no marker, so it may not push the document it lands in
    # over the threshold that demands one of everything else either.
    markable = {
        path: [position for position in positions if entries[position].equation is None]
        for path, positions in hosted.items()
    }
    markers = tuple(
        Marker(document=path, entry=position, locator=entries[position].locator)
        for path, positions in sorted(markable.items())
        if len(positions) > 1
        for position in positions
    )

    off_graph = endcap.scan(inventory)
    position_of = {(entry.document, entry.locator): position for position, entry in enumerate(entries)}
    rests_on = tuple(
        (position_of[site], work_id)
        for site, work_ids in off_graph.pairings.items()
        if site in position_of
        for work_id in work_ids
    )

    return Plan(
        entries=entries,
        documents=tuple(documents),
        markers=markers,
        # Only the works something rests on: a work cited nowhere a claim owns —
        # neither in a claim's own block nor in the proof establishing it — is a
        # citation in surrounding prose, and a node for it would assert a
        # dependency the corpus does not state.
        works=tuple(work for work in off_graph.works if any(work.id == wid for _, wid in rests_on)),
        rests_on=rests_on,
    )
