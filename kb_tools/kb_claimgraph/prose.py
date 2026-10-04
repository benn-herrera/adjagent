"""The prose a leaf states outside its blocks, and where each reference in it stands.

**Readable prose** is every line of a leaf outside its headings and its
claim-bearing, ``proof`` and ``definition`` blocks. Those blocks are read
mechanically — a claim block is its own node, a proof binds to the claim it
establishes, a definition is out of the graph — and a heading states nothing,
so the node pass reads what is left, and reads it through
:func:`label.render` with the blocks as its excluded region. That render is the
one paragraph rule: it decides the unit a verdict covers, a yes-claim's span,
which references stage D drops, and a paragraph's identity in the node-pass
record, which is the 0-based line the paragraph begins on.

**An obligated paragraph** is a paragraph of readable prose holding at least one
cross-reference that resolves to a document. Every one of them is owed exactly
one verdict by the node pass.

**Where a reference stands** (:func:`standing`) joins the render to the
record's verdicts, and :func:`claim_of` joins a yes-verdict's paragraph to the
Tier-2 marker its claim carries there. A paragraph with no verdict, or a
defaulted one, is unjudged and keeps today's rules; a reference is dropped only
on a recorded not-a-claim verdict.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .. import kb_pipeline
from ..kb_write import render as compose
from . import label
from .inventory import DEFINITION_ENVIRONMENT, PROOF_ENVIRONMENT, Anchor, Block, Inventory
from .tree import Document, strip_markers


def excluded_lines(text: str, blocks: Iterable[Block]) -> frozenset[int]:
    """Every line of one leaf the node pass does not read as prose: its headings, and its blocks'.

    ``text`` is the leaf's marker-stripped body. A heading names a section and
    states nothing, so a leaf whose only readable text is its heading has
    nothing to read and is asked nothing.
    """
    return label.heading_lines(text) | frozenset(
        line
        for block in blocks
        if block.claim_bearing or block.environment.casefold() in (PROOF_ENVIRONMENT, DEFINITION_ENVIRONMENT)
        for line in range(block.start, block.end)
    )


@dataclass(frozen=True)
class Readable:
    """One leaf's readable prose, rendered, beside the bytes as they sit on disk."""

    document: str
    #: The document as it sits on disk, markers and all.
    text: str
    render: label.Render


def readable(document: Document, inventory: Inventory) -> Readable:
    """``document`` rendered over its marker-stripped body, its blocks excluded."""
    body = strip_markers(document.text)
    return Readable(
        document=document.path,
        text=document.text,
        render=label.render(
            body,
            fences=[fence for fence in inventory.fences if fence.document == document.path],
            excluded=excluded_lines(body, (block for block in inventory.blocks if block.document == document.path)),
        ),
    )


def obligated(leaf: Readable, inventory: Inventory) -> tuple[label.Paragraph, ...]:
    """The paragraphs of ``leaf``'s readable prose that hold a resolving reference, in document order."""
    holding = {
        found.start
        for anchor in inventory.anchors
        if anchor.document == leaf.document and anchor.target is not None
        if (found := leaf.render.paragraph_at(anchor.line)) is not None
    }
    return tuple(paragraph for paragraph in leaf.render.paragraphs if paragraph.start in holding)


class Standing(StrEnum):
    #: In an excluded block: the rules for blocks and proofs apply.
    OUTSIDE = "outside"
    CLAIM = "claim"
    NOT_A_CLAIM = "not-a-claim"
    #: In readable prose no recorded verdict covers, or one recorded as defaulted.
    UNJUDGED = "unjudged"


def standing(anchor: Anchor, leaf: Readable, entry: kb_pipeline.LeafEntry | None) -> Standing:
    """Where ``anchor`` stands, read off ``leaf``'s render and its record entry."""
    paragraph = leaf.render.paragraph_at(anchor.line)
    if paragraph is None:
        return Standing.OUTSIDE
    verdict = next(
        (verdict for verdict in (entry.verdicts if entry is not None else ()) if verdict.line == paragraph.start),
        None,
    )
    if verdict is None or verdict.judgement is kb_pipeline.Judgement.DEFAULTED:
        return Standing.UNJUDGED
    return Standing.CLAIM if verdict.judgement is kb_pipeline.Judgement.CLAIM else Standing.NOT_A_CLAIM


def claim_of(anchor: Anchor, leaf: Readable, hosted: Iterable[str]) -> str | None:
    """The claim of ``hosted`` whose Tier-2 marker sits in ``anchor``'s paragraph.

    Where a :attr:`Standing.CLAIM` paragraph's claim is: the marker is where the
    node is, which is KB fact, so the record does not repeat it.
    """
    paragraph = leaf.render.paragraph_at(anchor.line)
    if paragraph is None:
        return None
    return next((claim_id for claim_id in hosted if marks(leaf, paragraph, claim_id)), None)


def marks(leaf: Readable, paragraph: label.Paragraph, claim_id: str) -> bool:
    """Whether ``claim_id``'s Tier-2 marker sits in ``paragraph`` — the paragraph that claim was minted from."""
    lines = leaf.text.splitlines()
    marker = compose.render_tier2_marker(claim_id)
    return any(marker in lines[line] for line in paragraph.lines)
