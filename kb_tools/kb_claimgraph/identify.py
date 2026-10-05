"""Stage C — claim identification, split by whether the author marked the site.

**C-mech — block-hosted claims. Mechanical, with no inference at all.** For each
claim-bearing block stage B found, everything a register entry needs is already
on the page: the **title** is the display line's optional argument where the
author wrote one and the environment's own printed word and number where they
did not, the **locator** is the span carrying it, and the **host** is the file.
The first two come off the same span, which is why it is worth naming — a
block's title and the anchor that locates it cannot disagree, so the affordance
does not reduce inference here, it eliminates it.

**C-inf — the node pass over every leaf's readable prose, one paragraph at a
time.** The paragraphs asked about (:func:`asked_paragraphs`) are every
obligated paragraph, whatever its words, and every other paragraph of readable
prose (:mod:`prose`) holding a sentence that could open a claim
(:func:`_opens_a_claim`) — so markup and two-word labels are not asked. Each is
put as one letter ask (:mod:`ask`, :mod:`letters`); this module turns what came
back into verdicts and claims (:func:`judge`) and asks nothing itself.

**A yes mints one claim, and its span is its whole paragraph.** Its title is
derived, not generated: the paragraph's first sentence that could open a claim
(its first sentence where none could), as the page shows it
(:func:`~.inventory.page_text`), on one line, cut at a word boundary within
:data:`TITLE_MAX_CHARS`, and suffixed with the paragraph's position where the
leaf already carries that title. It is therefore the author's bytes, the same on
every run, and unique in its leaf — which is what ``write.land_leaf`` resumes by
and what a register entry is joined back to its site by.

**Every asked paragraph ends with exactly one verdict**: a claim, not a claim,
or defaulted with its cause — no offered letter after the one re-ask, or a yes
whose paragraph the write path cannot place. A default never stops the stage:
a defaulted paragraph is unjudged (:func:`prose.standing`), so its references
keep the rules for prose no reading reached, and the claim it might have been is
the paragraph's cost and nobody else's.

**Placement is the one check, and it is a comparison against the document**
(:func:`_placed`): the paragraph's slice must appear exactly once under the
op's own matching. Whether a paragraph *is* a claim is never checked.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from ..kb_pipeline import DefaultCause, Judgement, ParagraphVerdict
from ..kb_write import ops
from . import label, prose
from .inventory import Block, Inventory, MathFence, page_text
from .report import ClaimGraphError
from .tree import DECLARING_KINDS, Document, Tree, document_kind, strip_markers


@dataclass(frozen=True)
class Claim:
    """One identified claim, before an id exists for it.

    ``locator`` is the Tier-2 anchor a multi-claim host will carry — the claim's
    own display line, apt by construction rather than by selection.
    ``identifier`` is the source ``\\label`` where the block carried one; it is
    the corpus's own name for the site and is carried for a later stage's
    candidate resolution, never as a node id.
    """

    document: str
    title: str
    locator: str
    environment: str
    identifier: str | None


class CoverageError(ClaimGraphError):
    """A claim-bearing block was dropped or double-counted."""


def block_claims(inventory: Inventory) -> tuple[Claim, ...]:
    """C-mech: one claim per claim-bearing block, read off the display line.

    A block's title and display line are optional on the block record and
    required here, and the narrowing is safe because a block that yielded
    neither is not claim-bearing and so is not in ``claim_blocks()``: there is no
    title to author and no span to anchor, so it costs itself a claim and this
    pass never meets it. Where the author declared no optional argument the title
    is the environment's printed word and its number, which is what the line
    carries.
    """
    return tuple(
        Claim(
            document=block.document,
            title=block.title,
            locator=block.display,
            environment=block.environment,
            identifier=block.identifier,
        )
        for block in inventory.claim_blocks()
    )


def check_block_coverage(claims: Sequence[Claim], inventory: Inventory) -> None:
    """Every claim-bearing block is named by exactly one claim. A comparison, not a judgement.

    The block set and the claim set are two artifacts, and this compares them —
    a block may not be dropped and may not be double-counted. It is stated over
    ``(document, locator)`` because that pair is what a register entry will
    carry, so the check is over the identity the write actually lands.
    """
    blocks = [(block.document, block.display) for block in inventory.claim_blocks()]
    named = [(claim.document, claim.locator) for claim in claims]
    dropped = sorted(set(blocks) - set(named))
    doubled = sorted({pair for pair in named if named.count(pair) > 1})
    if dropped or doubled:
        raise CoverageError(
            "block-coverage",
            f"{len(dropped)} claim-bearing block(s) named by no claim and {len(doubled)} named twice: "
            f"dropped {dropped[:3]}, doubled {doubled[:3]}",
        )


def unmarked_documents(tree: Tree, inventory: Inventory) -> tuple[str, ...]:
    """Every leaf the author marked nothing in, as ``stage-C-identify`` counts them.

    Mechanical: the complement of stage B's hosting set, narrowed to the one
    kind a claim declaration is asked of. An index is asked for no declaration
    by anything, so a stage reading one for claims would have nowhere to put
    them. This is a report line and not C-inf's ask surface, which is the
    node-pass record's leaves.
    """
    hosting = inventory.hosting_documents()
    return tuple(
        path
        for path in sorted(tree.documents)
        if path not in hosting and document_kind(path, has_children=bool(tree.children[path])) in DECLARING_KINDS
    )


# --- C-inf: the leaf as the node pass reads it ---------------------------------


@dataclass(frozen=True)
class Reading:
    """One leaf, as C-inf reads it.

    ``text`` is the document as it sits on disk — the bytes
    ``mark-claim-in-leaf`` will match a locator against — so the pre-check and
    the op it pre-checks see the same haystack. ``body`` is what the ask is
    shown: that same text with the markers an earlier pass appended taken back
    off, since those are not the author's words. Both carry the same line count,
    so a fence extent names the same line in either.
    """

    document: str
    text: str
    body: str
    fences: tuple[MathFence, ...] = ()
    #: The claim-bearing blocks in this document. Their titles are this
    #: document's already, and no prose claim may share one.
    blocks: tuple[Block, ...] = ()
    #: The lines the render shows unlabelled: every heading, and every line of a
    #: claim-bearing, proof or definition block (:func:`prose.excluded_lines`).
    excluded: frozenset[int] = frozenset()
    #: The paragraphs holding a resolving reference (:func:`prose.obligated`).
    obligated: tuple[label.Paragraph, ...] = ()

    @property
    def render(self) -> label.Render:
        """The labelled render the ask shows and placement resolves against.

        Derived rather than stored, so there is one statement of what a label
        means: the prompt the seat reads and the spans placement cuts are the
        same computation over the same bytes, and neither can go stale against
        the other.
        """
        return label.render(self.body, fences=self.fences, excluded=self.excluded)


def reading_of(document: Document, inventory: Inventory) -> Reading:
    """One leaf's :class:`Reading`, off stage B's inventory."""
    leaf = prose.readable(document, inventory)
    body = strip_markers(document.text)
    return Reading(
        document=document.path,
        text=document.text,
        body=body,
        fences=tuple(fence for fence in inventory.fences if fence.document == document.path),
        blocks=tuple(block for block in inventory.claim_blocks() if block.document == document.path),
        excluded=prose.excluded_lines(body, (block for block in inventory.blocks if block.document == document.path)),
        obligated=prose.obligated(leaf, inventory),
    )


#: The fewest words a sentence must canonically carry to be a claim
#: **opening**. Measured: over 843 sentences of two built KBs, every folded
#: collision at three words or fewer was a structural label — ``proof``,
#: ``definition``, ``proposition`` — and folding merged no two distinct prose
#: sentences at any length.
MIN_OPENING_WORDS = 4


def _opens_a_claim(sentence: label.Sentence, fences: Sequence[MathFence]) -> bool:
    """Whether a sentence may be the sentence a result begins at.

    Two exclusions, and both are about what a *start* can be rather than what a
    claim can contain.

    The first is counted over
    :func:`~kb_tools.kb_write.ops.canonical_form` — the matcher's own fold,
    called rather than restated. It covers both of the exclusion's halves at
    once: a structural label comes down to one or two words, and a markup-only
    line comes down to none.

    The second is the equation: **a claim may contain one and may not be one.**
    Display-maths fences open mid-sentence throughout this corpus — the
    converter emits one flush against the prose it interrupts — so a paragraph
    crossing a fence is the ordinary way a result carrying its own equation is
    stated. What is refused is a result that *begins* inside the equation.
    """
    if len(ops.canonical_form(sentence.text).split()) < MIN_OPENING_WORDS:
        return False
    return not any(fence.start <= sentence.line < fence.end for fence in fences)


@dataclass(frozen=True)
class Asked:
    """One paragraph the node pass asks about."""

    paragraph: label.Paragraph
    span: label.Span
    #: 1-based, among every paragraph of the leaf's readable prose.
    position: int

    @property
    def name(self) -> str:
        """The paragraph's label range, which names it in its ask."""
        return self.span.locator

    @property
    def text(self) -> str:
        """The paragraph's sentences as the render shows them, one labelled line each."""
        return "\n".join(f"{sentence.label}: {sentence.text}" for sentence in self.span.sentences)


def asked_paragraphs(reading: Reading) -> tuple[Asked, ...]:
    """The paragraphs of ``reading`` the node pass asks about, in document order.

    Every obligated paragraph, so every one carries a verdict; and every other
    one holding a sentence that could open a claim.
    """
    rendered = reading.render
    opening = {sentence.paragraph for sentence in rendered.sentences if _opens_a_claim(sentence, reading.fences)}
    opening |= {paragraph.index for paragraph in reading.obligated}
    return tuple(
        Asked(paragraph=paragraph, span=rendered.span_of(paragraph), position=position)
        for position, paragraph in enumerate(rendered.paragraphs, start=1)
        if paragraph.index in opening
    )


#: The longest a prose claim's title runs. A title labels the claim — a register
#: heading, an ask's claim line beside the statement itself — and
#: summarises nothing, so it needs to be short and no more.
TITLE_MAX_CHARS = 120


def _title(asked: Asked, fences: Sequence[MathFence], taken: set[str]) -> str:
    """The title a yes for ``asked`` mints under, given the titles its leaf already carries."""
    sentences = asked.span.sentences
    opener = next((sentence for sentence in sentences if _opens_a_claim(sentence, fences)), sentences[0])
    words = " ".join(page_text(opener.text).split())
    if len(words) > TITLE_MAX_CHARS:
        cut = words[:TITLE_MAX_CHARS]
        words = (cut.rsplit(" ", 1)[0] if " " in cut else cut[:-1]) + "…"
    if words and words not in taken:
        return words
    return f"{words} (¶{asked.position})".lstrip()


@dataclass(frozen=True)
class ProseClaim:
    """One claim a yes mints, placed, before an id exists for it.

    ``excerpt`` is both the evidence and the Tier-2 locator: the tool's own
    slice of the document — the whole paragraph — and what
    ``mark-claim-in-leaf`` anchors the marker at. ``line`` is where it located,
    and ``locator`` is the paragraph's label range.
    """

    document: str
    title: str
    excerpt: str
    line: int
    locator: str


@dataclass(frozen=True)
class Identification:
    """One leaf's outcome: the claims it states, and a verdict for every paragraph asked about."""

    document: str
    claims: tuple[ProseClaim, ...] = ()
    verdicts: tuple[ParagraphVerdict, ...] = ()


def _placed(asked: Asked, title: str, reading: Reading) -> ProseClaim | None:
    """``asked``'s claim as the write path will land it, or ``None`` where its slice is not unique.

    The question asked is :func:`kb_tools.kb_write.ops.excerpt_lines`' — the
    matching ``mark-claim-in-leaf`` will itself run over these same bytes — and
    not a second implementation of it: a pre-check that disagrees with the op it
    pre-checks is worse than no pre-check. Each claim's slice is its own
    paragraph's and no two paragraphs share a line, so one claim's marker never
    moves another's slice and each is placed alone.
    """
    lines = ops.excerpt_lines(reading.text, asked.span.excerpt)
    if len(lines) != 1:
        return None
    return ProseClaim(
        document=reading.document, title=title, excerpt=asked.span.excerpt, line=lines[0], locator=asked.name
    )


def judge(reading: Reading, answers: Sequence[tuple[Asked, bool | None]]) -> Identification:
    """One leaf's verdicts and claims from its answers: per asked paragraph, whether it states a result.

    ``None`` is a paragraph whose ask came back with no offered letter. It, and
    a yes the write path cannot place, are recorded defaulted with their cause;
    every other answer is recorded as given.
    """
    taken = {block.title for block in reading.blocks if block.title is not None}
    verdicts: list[ParagraphVerdict] = []
    claims: list[ProseClaim] = []
    for asked, states_a_result in sorted(answers, key=lambda answer: answer[0].paragraph.start):
        line = asked.paragraph.start
        if states_a_result is None:
            verdicts.append(ParagraphVerdict(line=line, judgement=Judgement.DEFAULTED, cause=DefaultCause.NO_LETTER))
            continue
        if not states_a_result:
            verdicts.append(ParagraphVerdict(line=line, judgement=Judgement.NOT_A_CLAIM))
            continue
        title = _title(asked, reading.fences, taken)
        taken.add(title)
        claim = _placed(asked, title, reading)
        if claim is None:
            verdicts.append(ParagraphVerdict(line=line, judgement=Judgement.DEFAULTED, cause=DefaultCause.UNPLACEABLE))
            continue
        claims.append(claim)
        verdicts.append(ParagraphVerdict(line=line, judgement=Judgement.CLAIM))
    return Identification(document=reading.document, claims=tuple(claims), verdicts=tuple(verdicts))
