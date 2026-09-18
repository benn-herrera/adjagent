"""The authored claim graph, read back off the tree the passes before it wrote.

A pass that extends a graph has to read one first. Two authored artifacts hold
it and they are joined here rather than either being trusted alone:

* each document's ``claims:`` frontmatter, which is what the tier-1 coverage
  check reads and therefore the canonical statement of which document hosts
  which claim;
* each domain's register, which is where the id was minted and where its title
  lives.

**A claim is bound back to its block by title.** The declared pass reads a
block's title off its display line and writes that exact string as the register
entry's heading, so matching the two recovers which block a minted id came from
— and with it the locator a later stage needs to say *where in this document*
the claim sits.

**A prose claim has no block, and its marker is the only route back.** Claim
discovery mints a Tier-2 marker for every claim it identifies precisely so this
join has a second arm: the marker names the id and sits on the end of the line
its excerpt located to, so that line — its markers taken back off — *is* the
locator. Without it a prose claim's excerpt would exist only in the run's
scratch and every later stage would know the claim by path alone. The block join
runs first, because where a block carries the title the block's own display line
is the locator by construction.

**An equation node has neither, and its title is the route back.** A node minted
for a referenced equation (:mod:`equation`) sits in no block and takes no marker
— its ``\\label`` is inside a maths fence, which is a place no block-level
metadata may go — so both arms above answer ``None`` and the claim would come
back locatable only by path. The title is what carries the label
(:func:`kb_schema.equation_label`), so it is the third arm, and it runs
**first**: the title's shape is decisive, where the other two are lookups that
can miss for reasons of their own. The honest locator is the label itself, which
is the whole of what says *where in this document* an equation sits.

**Nothing here re-derives an id, a title or a host.** Every value is read off
the authored bytes; the only thing computed is the join.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .. import kb_index_lib, kb_schema
from ..kb_write import render
from .assemble import REGISTER_FILENAME
from .inventory import Inventory
from .report import ClaimGraphError
from .tree import BLOCKQUOTE_PREFIX, Tree, strip_markers


class GraphReadError(ClaimGraphError):
    """The authored graph does not join: an id is declared that no register mints."""


@dataclass(frozen=True)
class ClaimNode:
    """One minted claim, as the authored graph carries it."""

    id: str
    document: str
    title: str
    #: Where in its document the claim sits: the display line of the block it
    #: was read off, or — for a claim identified in prose — the line its Tier-2
    #: marker is appended to. ``None`` only where neither join answers.
    locator: str | None
    #: The source ``\\label`` on that block, where it carried one. This is what
    #: a cross-reference fragment names, and the only mechanical route from an
    #: anchor to a *particular* claim in a document hosting several.
    identifier: str | None
    #: The equation's own ``\\label`` where this node stands for a referenced
    #: equation (:mod:`equation`), and ``None`` for every other claim. It is the
    #: node's **only** route in: :func:`attribute._equation_claim` matches it
    #: against an anchor's ``data-reference``, and nothing else reaches it —
    #: which is why it is a field of its own rather than a second spelling of
    #: ``identifier``, a field :func:`attribute._fragment_claim` reads.
    equation: str | None = None


@dataclass(frozen=True)
class AuthoredGraph:
    """Every claim the tree declares, by id and by hosting document."""

    nodes: Mapping[str, ClaimNode]

    def hosted_by(self, document: str) -> tuple[ClaimNode, ...]:
        """The claims ``document`` hosts — **an equation node deliberately not among them.**

        This is the set two of stage D's fallbacks stand on: ``_source_end``
        offers every claim a document hosts when a prose reference belongs to no
        block, and ``_target_end`` lands a reference on a document's claim when
        it hosts exactly one. An equation node counted here would join both, and
        both readings are false of it — "the claim this prose belongs to" and
        "the one thing this document could be about" are statements about what a
        document *states*, and an equation node stands for a numbered formula
        that nothing claims.

        Measured over the 50-paper arXiv corpus, counting them cost **205
        existing sole-claim edges** (90 documents stopped hosting exactly one),
        **manufactured 132 section references** onto an equation no author
        pointed at (66 documents newly sole), and took the prose source end's
        k×m from 3434 to 7487. So the restriction is here, at the one accessor
        both fallbacks read, rather than as a condition each remembers.
        """
        return tuple(node for node in self.nodes.values() if node.document == document and node.equation is None)

    def equation_node(self, document: str, label: str) -> ClaimNode | None:
        """The node standing for the equation ``label`` names in ``document``, or ``None``.

        The whole of an equation node's reachability. Everything else asks
        :meth:`hosted_by`, which does not carry it.
        """
        return next(
            (node for node in self.nodes.values() if node.document == document and node.equation == label), None
        )

    def documents(self) -> frozenset[str]:
        return frozenset(node.document for node in self.nodes.values())


def _register_titles(kb_root: Path) -> dict[str, str]:
    """Every minted claim id in the KB, with the title its entry carries."""
    titles: dict[str, str] = {}
    for register in sorted(kb_root.rglob(REGISTER_FILENAME)):
        if set(register.relative_to(kb_root).parts[:-1]) & kb_index_lib.EXCLUDE_DIRS:
            continue
        for entry in kb_index_lib.parse_claim_quality_file(register, kb_root):
            titles[entry.id] = entry.title
    return titles


def marker_locator(text: str, claim_id: str) -> str | None:
    """The line carrying ``claim_id``'s Tier-2 marker, as a locator, or ``None``.

    The marker's own spelling is composed by the module that writes it rather
    than typed here, so a marker whose form moved is not silently unfindable.
    What comes back is that line's authored content — every marker taken off it,
    its blockquote prefix stripped, its whitespace collapsed — which is the form
    the write API matches a locator in.
    """
    marker = render.render_tier2_marker(claim_id)
    for line in text.splitlines():
        if marker in line:
            recovered = render.collapse_prose(BLOCKQUOTE_PREFIX.sub("", strip_markers(line)))
            return recovered or None
    return None


def read(tree: Tree, inventory: Inventory) -> AuthoredGraph:
    """Join the tree's declarations to the registers' entries, and to stage B's blocks."""
    titles = _register_titles(tree.root)

    blocks_by_document: dict[str, dict[str, tuple[str | None, str | None]]] = {}
    for block in inventory.claim_blocks():
        assert block.title is not None  # a block with neither title nor locator is not claim-bearing
        blocks_by_document.setdefault(block.document, {})[block.title] = (block.display, block.identifier)

    nodes: dict[str, ClaimNode] = {}
    for path in sorted(tree.documents):
        fields = kb_index_lib.parse_frontmatter(tree.documents[path].text) or {}
        for claim_id in fields.get("claims") or ():
            title = titles.get(claim_id)
            if title is None:
                raise GraphReadError(
                    "orphan-claim",
                    f"{path} declares {claim_id}, which no register in this KB mints. The declaration and "
                    f"the register disagree about what exists, and an edge authored over that disagreement "
                    f"would name a node with no entry",
                )
            label = kb_schema.equation_label(title)
            if label is not None:
                nodes[claim_id] = ClaimNode(
                    id=claim_id, document=path, title=title, locator=label, identifier=None, equation=label
                )
                continue
            locator, identifier = blocks_by_document.get(path, {}).get(title, (None, None))
            if locator is None:
                locator = marker_locator(tree.documents[path].text, claim_id)
            nodes[claim_id] = ClaimNode(id=claim_id, document=path, title=title, locator=locator, identifier=identifier)
    return AuthoredGraph(nodes=nodes)
