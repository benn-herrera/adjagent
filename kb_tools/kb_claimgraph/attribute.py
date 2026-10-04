"""Stage D's narrowing: every edge candidate, classed and drafted. Mechanical throughout.

**The candidate set is narrowed mechanically, and a model adds to it only by
judging a pair a mechanical shortlist proposed** (:mod:`unmarked`).
What this module returns is one :class:`Candidate` per ordered pair, whatever
harvested it — a cross-reference anchor, a hand-written name
(:mod:`hand_named`), or a pair the unmarked-reference ask answered yes
(:mod:`unmarked`) — carrying the relations its class may be offered and the
draft a build with no reader writes. :mod:`classify` asks about each one.
Over stage B's cross-reference anchors, each end of a reference is attributed to
a claim where a rule settles it, and left open where none does:

* the **source** end. A reference sitting inside a claim-bearing block belongs
  to that block's claim; a reference inside a *proof* belongs to the claim that
  proof establishes (:func:`_proofs`); a reference anywhere else in a document's
  prose offers every claim that document hosts, there being no narrower rule to
  try. That last one is a fallback rather than a rule: it settles nothing about
  direction and nothing about which claim, and where the document happens to
  host one it narrows to that claim by arithmetic rather than by reading
  anything. **The node pass's verdict precedes all three** for a reference in
  readable prose (:mod:`prose`): a paragraph judged not a claim gives the
  reference no source and so no pair, and one judged a claim gives it that
  paragraph's claim alone. The fallback is what is left for prose nobody judged.
* the **target** end, in this order. A reference whose fragment names a block's
  own source label lands on that block's claim; a reference whose fragment names
  a block :data:`inventory.NOT_A_CLAIM_TARGET` classifies contributes no pair at
  all, the author having pointed at a site somebody judged to state no result; a
  reference whose label names a maths fence lands on the claim holding that
  equation — the block's, where a claim-bearing block holds it, and otherwise the
  node the equation was minted as; a reference into a document hosting exactly
  one claim lands on that claim, there being no other.
* where an end stays open the enumeration offers every claim it could be. Where
  **both** ends are settled *and the source end was settled by proof
  containment*, the candidate is drafted *supported by*; every other candidate
  is drafted *mention*.

**Why a mechanically-derived edge is now authored where it once was withheld.**
Three of the narrowings above used to be exclusions — an ``eqref`` contributed
nothing, a reference whose fragment named a section contributed nothing, and a
reference inside a proof was no more directed than one anywhere else — and each
rested on the same cost/benefit: a wrong edge is worse than a missing one, so
material a rule could not resolve with confidence was dropped rather than
guessed at. That calculus inverted, and the reason is what an edge *is* on this
path. A mechanical edge here is a **draft a later inference pass corrects**, not
a final assertion; the alternative to a rule that sometimes misfires is not a
correct rule but no rule and no result, and a claim recorded as depending on
nothing is itself a wrong answer, arrived at silently and prompting nobody to
revisit it. What stays unacceptable is being provably wrong inside a mechanical
constraint — an edge naming an id that does not exist, or one closing a cycle —
and both of those are checked below, before anything is written. The rulings
each narrowing replaced are kept beside it, because the question was reconsidered
rather than overlooked.

**A reference inside a proof is a dependency, and containment is what directs
it.** A proof establishes the claim it belongs to, so a claim-resolving
reference in a proof body says the proved claim rests on the referenced one.
This needs no model. The ruling it overturns is that an author's cross-reference
"carries no direction: a theorem citing a lemma is usually a dependency, a lemma
citing the theorem it motivates is not, and the markup is identical" — true of a
bare reference in prose, and false here, because the containment is part of the
markup too. Measured over the cross-references carried by the staged corpus's 27
claim-bearing maths papers, 39% of them sit inside a proof (``math.AP`` 0.65,
``math.DG`` 0.57, ``math.AG`` 0.54, ``math.PR`` 0.28, ``math.NT`` 0.26,
``math.ST`` 0.24), so this is the bulk of the material and not an edge case.

**Which claim a proof proves is stage B's reading, not this stage's.**
:class:`inventory.Proof` binds each proof block to the *blocks* it establishes —
by the opening run's own ``\\ref`` where the author wrote
``\\begin{proof}[Proof of Theorem \\ref{thm:main}]``, and by the block
*immediately* above where they wrote a bare ``\\begin{proof}``. That binding is
about blocks and lines and is knowable before any id exists, which is why it
lives there and why the off-graph endcap directs a ``\\cite`` through the same
reading rather than through a second one. What :func:`_proofs` does here is the
one thing that needs minted ids: map each subject block to the claim it carries.

What that binding misses, and it is the weaker of the two arms: a proof whose
document opens with it binds to nothing, so a section stating its result
elsewhere contributes no edge unless the opening run names it; a proof under a
remark, an example or a second proof binds to nothing, the block above stating
no claim; a result the author stated in ordinary prose rather than in a labelled
block is not a block at all, so the proof beneath it reads as following whatever
came before it and binds to nothing; and an author who wrote *Proof of Theorem 3*
as plain text rather than as a ``\\ref`` has named a subject this reads as naming
none. Where the opening run names a subject that resolves to no claim, the proof
gets no subject and adjacency is *not* tried behind it — the author said what is
being proved and it is not a node. One more is this stage's alone: a subject
block the tree names but no register entry carries — an undeclared claim — maps
to no node here and the proof binds to nothing. In every one of those cases the
references stay open pairs for the ask rather than becoming directed edges;
nothing is lost that was not already the ask's.

**An equation labelled inside a claim body is that claim's assertion.** The
ruling this replaces is that "an ``eqref`` anchor contributes nothing — it
targets an equation, and an equation is not a node", which is true of the
equation and does not follow for the reference: 232 of 791 claim-reaching
references in an earlier survey were of exactly this shape. The reference
resolves *through* the equation to the block it sits in.
:func:`_equation_claim` is the join, and it reads the label off the anchor's
third attribute because point 9 leaves an equation's ``\\label`` inside the maths
fence rather than as an addressable id — so an equation reference lands on its
document with an empty fragment, and the label is the whole of what says which
equation.

**An equation no block and no proof holds is a node of its own**, which is the
second half of that ruling reversed. What the old form said next — that a
reference whose equation sits in no claim-bearing block "still contributes
nothing" — described 2378 anchors across 43 of the corpus's 50 papers, and what
they contributed nothing *to* was a graph in which their target did not exist.
:mod:`equation` mints one per referenced equation nothing else holds, bounded by
the author's own cross-references, and :func:`_equation_claim` is where the
reference reaches it. **It is reachable there and nowhere else**: it is not in
:meth:`graph.AuthoredGraph.hosted_by`, so neither the prose source end nor the
sole-claim target end can offer one, and it carries no ``identifier``, so
:func:`_fragment_claim` cannot name one. The restriction is measured rather than
preferred — counting equation nodes as ordinary hosted claims cost 205 existing
sole-claim edges and manufactured 132 section references onto equations no
author pointed at. **And it is terminal**: the only reference that could run
*from* an equation is one sealed inside a maths fence, which reaches the tree as
no anchor at all, so nothing new can close a cycle.

**A reference into a document hosting exactly one claim lands on that claim**,
and it is what admits the section references the third narrowing used to drop.
**It has no source-end counterpart**, though the two agree on their output
wherever a document hosts one claim: the source end's prose fallback offers
every claim the document hosts and settles nothing, so a single-claim document
narrows it to one claim by arithmetic. Reading that coincidence as one rule read
at either end would be claiming a route settles the source end off code that
offers everything there. The ruling it replaces held that
"a reference to a document is not a reference to what the document establishes",
since the referent is the section and resolving it would *manufacture a claim
out of containment*; that objection stands wherever the target hosts several
claims, and there the reference is still ambiguous and still the ask's. It does
not stand where the document hosts one: nothing is manufactured, because there
is nothing else the reference could bear on. Measured over a seven-volume tree
at the declared graph, 104 of 159 resolving ``ref`` anchors are section
references, and dropping them took stage D from 15 sources / 29 pairs to 10 /
15. The narrowing's third argument — that its *cost* is k×m in exactly the place
discovery multiplies m — is unanswered and is paid: a section reference into a
multi-claim document offers every claim that document hosts.

**An anchor naming a block somebody classified as stating no result contributes
no pair.** A ``\\ref{def:thick}`` resolves to a *definition* and a
``\\ref{rmk:numevid}`` to a *remark* — the first a node kind SPEC.md rules out,
the second a block stage B classified as stating no result, and neither of them
something a claim node exists for. So :func:`_fragment_claim` finds nothing and
every route behind it answers with a claim the author did not point at — the
document's sole claim where it hosts one, and every claim it hosts where it
hosts several.
:data:`inventory.NOT_A_CLAIM_TARGET` is read at the target end and ends the
reference there. Two rules beside it already take that refusal on that ground: an
``\\eqref`` whose equation resolves to no claim returns ``()`` rather than falling
to the sole-claim route, and a proof whose opening run names a subject that is no
node binds to nothing rather than falling back to the block above it. In all
three the author said what they meant and what they meant is not in the graph.

**This is not one of the three reversed narrowings in a new place, and the
asymmetry is what decides it.** Those withheld *the relationship the corpus
states* because some fraction of them would be wrong, and left the graph
asserting the claims unrelated — a wrong answer arrived at silently. The
relationship this corpus states is claim → the block the author named, and there
is no node to record it against; what the refusal withholds is a *different*
relationship, one the author did not write, so no true statement is traded for
silence. A pair recorded here would also misstate the ``references`` class's own
contract, whose target is the claim the reference resolves to — and this
reference resolves to no claim.

**The refusal reaches every classified name but ``proof``, and what it removes
is candidates — never an edge.** Measured over the 53 built kb-roots, each name
against the same baseline of a run refusing nothing: the whole set removes 166
``references`` records and the 166 candidates they put to the model
(``assumption`` 84, ``definition`` 39, ``remark`` 23, and ``example``,
``notation``, ``problem`` none), **and leaves the 1000 settled edges untouched,
name for name and in combination**. ``proof`` stands outside on a different
ground from its zero: an anchor naming a proof block has a *better* answer
available than a refusal in the claims that proof establishes
(:class:`inventory.Proof` already binds them), so refusing it would spend a
route nobody has written yet.

**A per-anchor pair count is not an edge count, and reading one as the other is
what made ``remark`` look like the worse case.** :func:`narrow` collapses the
settled pairs into a dict keyed by ``(source, target)``, so an anchor naming a
non-claim-bearing block takes an edge away only where **no other anchor**
settles the same pair. Counted per anchor, ``remark`` contributes to 3 settled
pairs; those are 2 distinct edges, and each is settled independently by another
anchor — one through the identifier route off a claim-bearing block, one through
a plain section reference into the same single-claim document. Corpus-wide, not
one settled pair has its sole provenance in an anchor naming a block this
refusal reaches, so no ``depends`` edge moves and the route breakdown
:attr:`Attribution.routes` reports is unchanged.

**A name nobody has classified is outside this by construction** — 36 anchors
over the same corpus spell ``Hypothesis``, ``Setup``, ``PAR``, and the near
misses ``rremark``, ``defi`` and ``exa`` — and falls through exactly as it
always did: the refusal spends a judgement somebody made and never stands in for
one nobody made. Those anchors contribute to 2 settled pairs, and both of those
are co-settled too.

**The word before an anchor withholds a fallback's candidates, and only those.**
Where the page introduces a reference as *Section 3*, *Fig. 2* or *Remark 4*
(:func:`names_no_premise`) and the target end fell to the sole-claim route or to
every claim a multi-claim document hosts, the pairs are not opened: what the
author pointed at is a section or a figure, and the claims filed under it are the
fallback's stand-in for something no premise relation can hold. The fragment
refusal above is the same argument read off the target block; this reads it off
the page's word, for the anchor whose fragment names no block. It is a filter and
not a director: a pair containment settled is an edge whatever word precedes it,
so no ``depends`` edge moves, and a fragment or label naming the claim outranks
the word. Measured over the 54 staged kb-roots it removes 497 of 2238 candidate
pairs and 37 of 556 questions, ``section`` carrying most of it; 25 anchors whose
word names no premise reached the equation route — *Assumption (2.1)*, *Problem
(3)* — and keep their pairs.

The refusal these three replaced is unchanged in one place: **shared containment
in a directory contributes no candidate on its own**, filing being a placement
decision and not a dependency relation. Nothing above derives a candidate from
where a document sits; every one of them derives it from something the author
wrote.

**Leaf-prose references contribute candidates**, which is the ruling the corpus
forced: most of the tree's ``ref`` anchors sit in prose rather than inside a
block, and a rule confining candidates to block interiors would leave most
claims with nothing to select from.

**Where the prose's own document hosts no claim the end stays empty, and that
is an answer rather than a gap.** 360 of the 1789 anchors naming a claim-bearing
block sit in the prose of a document that states none — 293 of them before the
cleveref family was read at all, and the equation nodes moved the figure by
zero, :meth:`graph.AuthoredGraph.hosted_by` excluding them being precisely what
keeps a numbered formula from standing in for what a section says. What a
widening could attribute *from* was then measured document by document, and the
answer is mostly nothing: 212 of the 360 sit in a document holding no claim, no
proof and no equation; 63 hold an equation node, which the restriction above
refuses on its own measured grounds; 13 hold a proof bound to a claim; and
everything outside the document is containment in a directory, which the refusal
above already covers. The last 72 sit under a heading that names a claim —
``\\section{Proof of Theorem \\ref{thm:2}}`` reaches the tree as an anchor on the
H1 line — and 43 of those name only the claim the heading already names, which
is no pair, leaving 29 references and 28 pairs across 4 of 50 papers.

**That last case is a proof this stage cannot see, and it is not fixed here.** A
document whose heading says it proves a theorem *is* a proof; reading it as one
belongs beside :class:`inventory.Proof`'s two arms, where it would reach all 165
references the 28 such documents carry — and direct them, as proof containment
already directs — rather than the slice a prose fallback sees. Widening the
prose fallback to reach the same 29 would take the weaker half of that reading
and make the stronger one harder to add. **And the rest is the host
environment's base rate, visible in the text**: of the 324 outside that last
case, 85 sit in an ``overview.md`` and 31 more in a section organising the paper
— *Theorem 2 is proved in Section 6* — which names a result and asserts no
relationship between claims for the graph to carry.

**A pair containment cannot direct is recorded as a ``references`` edge, never
discarded.** The author wrote one claim's own identifier inside another claim's
text, in the formal notation LaTeX generated — *a second certificate, distinct
from the ``V`` of Theorem 2*, *not derivable from the bare cap-table dynamics
(Proposition 8(iii))*. What the narrowing cannot settle is the *direction of
dependence*; the fact that the source names the target is not in doubt and is
the whole content of the class. The notation settles that the relationship
exists and not whether it is a dependency, so a stage that recorded only
dependencies would discard every reference the markup cannot classify — and
leave the graph asserting the claims are unrelated, which is a wrong answer
arrived at silently.

Three properties keep it from being a weak ``depends``. It carries **no
acyclicity constraint**: two claims naming each other is the author's argument,
and the measured corpus contains exactly such a 2-cycle. It **enters no
solidity computation**, being carried on ``ClaimEntry.references`` rather than
``depends_on``, which is the tuple every scorer reads. And it **does not answer
the question**: the pair is still classified, because whether a naming is also
a dependency is exactly what the narrowing could not decide. A candidate
classified as a dependency is written as one and not also as a reference
(:func:`written`).

**Point 6 is satisfied by the check and not by abstention.** SPEC.md warns that
a consumer taking cross-references as dependency edges would import the author's
own cycles into a graph that must stay acyclic. That is a reason to check, and
the check runs here over the drafts before any question is asked and in
:mod:`classify` over the classified set before anything is written.

**A ring among the settled edges costs its own edges and not the build.** The
cycle proves that the edges on it cannot all be dependencies. It does not prove
that the corpus reasons circularly — four results whose proofs cite one another
are far more likely to be a single argument carried across several statements,
or proofs citing each other for symmetry, *the argument is as in Lemma 4*, which
containment reads as direction-bearing and which is not a dependency — and it
proves nothing whatever about the paper's other edges, so stopping the stage
discards a whole graph over one ring and leaves every claim in the paper
recorded as resting on nothing. Each edge on a ring is therefore recorded as a
``references`` edge (:func:`cycle_edges`), which is the class for a relationship
the corpus states and nothing can direct, and the rest of the settled edges
stand. Measured over a 50-paper arXiv sweep with no model reachable, three
papers carried such a ring — two 4-cycles and a 2-cycle — and each took its
entire graph down with it.

**Every edge on the ring is demoted, not a minimum feedback set.** Breaking one
edge per ring would leave the others asserted as dependencies, and a ring is
exactly where no evidence separates its members: each is a reference inside the
proof of the claim it runs from, read by one rule from one kind of markup.
Picking one by a sort key would be a discrimination nothing in the corpus
supports, and on a 2-cycle it is a coin flip reported as a finding. Demoting the
whole ring gives up only the direction claim — the half the cycle disproves —
and costs no relationship at all, the demoted edge being recorded rather than
dropped. This is what separates the ruling from the three the corpus reversed
above: those traded a fact for silence, and this trades a direction for a
weaker, true statement.

**A demoted pair is drafted *mention*, and classified like any other.** What the
ring refuses is the *set* of directions containment read, not any one reading,
so the draft gives up only the direction; the question of what each pair is
stays open and is asked.

**The class is a fact about the pair, never about its harvest.** A provenance
whose source end proof containment settled offers *supported by* and *mention*:
a proof of ``s`` citing ``t`` while ``t`` rests on ``s`` is circular unless it is
a mention. A target that is a minted equation node offers the same two: an edge
originating at a sink is provably wrong. Every other provenance offers all
three. Two provenances reaching one pair intersect what they offer
(:data:`OFFERED`), and every subset holds *supported by* and *mention*, so the
intersection is never empty and the draft is always among it.

**An empty candidate set is a legitimate output.** Claims with no candidate
carry no edges, and chains terminating on dependency-free foundational claims is
what SPEC's scoping describes rather than a gap to fill.

**The narrowing is not the ask's preamble, and a run that cannot ask still
runs it.** :func:`narrow` reads the tree, the authored graph and the inventory
and asks nothing of anybody, so the drafts are the corpus's answer and not a
model's. A run with no model reachable writes every candidate's draft.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .. import kb_pipeline
from ..kb_write import render
from . import equation_sites, hand_named, prose
from .graph import AuthoredGraph, ClaimNode
from .inventory import (
    NOT_A_CLAIM_TARGET,
    PROOF_ENVIRONMENT,
    Anchor,
    Block,
    Inventory,
    MathFence,
    by_document,
    hosting_block,
)
from .tree import Tree, strip_markers, unquote

#: How the three target-end rules are named in the build's own report, so a
#: reader of the log can tell how an edge arose without a marker on the edge.
BY_IDENTIFIER = "identifier"
BY_EQUATION = "equation"
BY_SOLE_CLAIM = "sole-claim"

#: The kinds of numbered thing a document's own structure prints — a sectioning
#: unit, a float, a footnote — as the page names them before a ``\\ref``,
#: case-folded, abbreviations included. **None of them is a result**, so no
#: premise relation can run to one, and an anchor the page introduces with one
#: of these words opens no candidate pair (:func:`names_no_premise`).
#:
#: **A fixed list, and it has to be.** The claim side of the vocabulary is the
#: corpus's own — its blocks' display names, classified by
#: :data:`inventory.CLAIM_BEARING` and :data:`inventory.NOT_CLAIM_BEARING` — but
#: these kinds are no display name: no ``\\newtheorem`` declares them, the reader
#: renders a section as a heading and a float without its number, and the tree
#: records the word nowhere but in the author's prose. What is listed is what
#: LaTeX numbers structurally and what the staged corpus writes before an anchor;
#: ``part``, ``paragraph``, ``item`` and ``line`` are left out, each being an
#: ordinary English word that also introduces a sub-item of a result.
STRUCTURAL_KINDS: frozenset[str] = frozenset(
    {"section", "subsection", "subsubsection", "chapter", "appendix", "figure", "table", "footnote"}
    | {"sec", "subsec", "ch", "chap", "app", "fig", "tab", "§", "§§"}
)


class Relation(StrEnum):
    """What a candidate's source is to its target: one meaning per member, mapped one to one onto classify's letters."""

    SUPPORTED_BY = "supported-by"
    IN_SUPPORT_OF = "in-support-of"
    MENTION = "mention"


class Harvest(StrEnum):
    """What found a candidate. Counted on the report, and read by nothing else."""

    REFERENCE = "reference"
    HAND_NAMED = "hand-named"
    UNMARKED = "unmarked"


class CandidateClass(StrEnum):
    """What one provenance of a pair is, read off facts :func:`narrow` holds. It does not travel past it."""

    PROOF_DIRECTED = "proof-directed"
    EQUATION_TARGET = "equation-target"
    CLAIM_TO_CLAIM = "claim-to-claim"


#: The relations each class may be offered. Every subset holds *supported by*
#: and *mention*, so intersecting two never empties, and the draft is always
#: offered.
OFFERED: Mapping[CandidateClass, frozenset[Relation]] = MappingProxyType(
    {
        CandidateClass.PROOF_DIRECTED: frozenset({Relation.SUPPORTED_BY, Relation.MENTION}),
        CandidateClass.EQUATION_TARGET: frozenset({Relation.SUPPORTED_BY, Relation.MENTION}),
        CandidateClass.CLAIM_TO_CLAIM: frozenset(Relation),
    }
)


def _class_of(*, directed: bool, target: ClaimNode) -> CandidateClass:
    """One provenance's class: proof containment first, then a sink target, then neither.

    A sink is a minted equation node (``target.equation``), never an ``eqref``
    that resolved *through* an equation to a block's or a proof's claim.
    """
    if directed:
        return CandidateClass.PROOF_DIRECTED
    if target.equation is not None:
        return CandidateClass.EQUATION_TARGET
    return CandidateClass.CLAIM_TO_CLAIM


@dataclass(frozen=True)
class Candidate:
    """One ordered pair, whatever harvested it: the source's text names the target.

    ``offered`` is in :class:`Relation`'s order. ``passages`` are the pair's
    own — the paragraph of each anchor or mention that produced it
    (:func:`_reference_line`), sorted and deduplicated.
    """

    source: ClaimNode
    target: ClaimNode
    offered: tuple[Relation, ...]
    draft: Relation
    passages: tuple[str, ...]
    harvests: frozenset[Harvest]

    @property
    def pair(self) -> tuple[str, str]:
        return (self.source.id, self.target.id)


class Written(StrEnum):
    """The register list a classified candidate lands in."""

    DEPENDS = "depends"
    REFERENCES = "references"


def written(candidate: Candidate, relation: Relation) -> tuple[Written, tuple[str, str]]:
    """The one record ``candidate`` classified as ``relation`` writes.

    *In support of* reverses the edge — the target rests on the source — and
    lands in the target's register entry. A dependency either way carries no
    ``references`` record beside it.
    """
    if relation is Relation.SUPPORTED_BY:
        return Written.DEPENDS, candidate.pair
    if relation is Relation.IN_SUPPORT_OF:
        return Written.DEPENDS, (candidate.target.id, candidate.source.id)
    return Written.REFERENCES, candidate.pair


# --- the mechanical narrowing ------------------------------------------------


def _claim_of(block: Block | None, hosted: Sequence[ClaimNode]) -> ClaimNode | None:
    """The claim a block carries, joined the way :func:`graph.read` bound it: by locator."""
    if block is None:
        return None
    return next((node for node in hosted if node.locator == block.display), None)


def _fragment_claim(anchor: Anchor, hosted: Sequence[ClaimNode]) -> ClaimNode | None:
    """The claim the anchor's fragment names, where it names one.

    Point 7 lands a rewritten anchor on the node that held its label, and stage
    B carries that label off the block's ``<span>``. Where the two agree the
    target is not a document but a claim. This is this package's whole reading
    of SPEC.md's cross-reference join (Corpus Invariants): the fragment is asked
    against the identifier the *target* declares, never against the author's own
    spelling, so ``\\label{bifurcation}`` on a theorem is as legal as
    ``\\label{thm:bif}``.
    """
    if not anchor.fragment:
        return None
    return next((node for node in hosted if node.identifier == anchor.fragment), None)


def _fragment_block(anchor: Anchor, blocks: Sequence[Block]) -> Block | None:
    """The block the anchor's fragment names, whether or not that block carries a claim.

    :func:`_fragment_claim`'s question asked of the page instead of the graph. A
    block stating no result is invisible to that join — it minted no node for a
    fragment to match — and it is exactly what the target end has to be able to
    see before it falls past the identifier route.
    """
    if not anchor.fragment:
        return None
    return next((block for block in blocks if block.identifier == anchor.fragment), None)


@dataclass(frozen=True)
class _Proof:
    """One proof block as this stage needs it: the claims it establishes.

    :class:`inventory.Proof` carries the same binding over *blocks*, which is
    what a pass running before the first id is minted can use. This is that
    binding with each subject block replaced by the claim it carries, and it is
    the whole of what this module adds to it.
    """

    subjects: tuple[ClaimNode, ...]
    head: frozenset[tuple[str, str]]

    def names(self, anchor: Anchor) -> bool:
        """Whether ``anchor`` is one of the run's: what is proved, not what it rests on."""
        return (anchor.href, anchor.label) in self.head


def _proofs(graph: AuthoredGraph, inventory: Inventory) -> Mapping[str, Mapping[int, _Proof]]:
    """Stage B's proof binding, by document and by the line each proof's label sits on.

    The subjects are mapped block by block through :func:`_claim_of`, which is
    the join ``graph.read`` itself made — so a subject block no register entry
    carries drops out here and the proof binds to nothing, exactly as one the
    tree never named would.
    """
    found: dict[str, dict[int, _Proof]] = {}
    for proof in inventory.proofs:
        hosted_by_document = {subject.document: graph.hosted_by(subject.document) for subject in proof.subjects}
        subjects = tuple(
            claim
            for subject in proof.subjects
            if (claim := _claim_of(subject, hosted_by_document[subject.document])) is not None
        )
        found.setdefault(proof.document, {})[proof.start] = _Proof(subjects=subjects, head=proof.head)
    return found


def _equation_claims(
    anchor: Anchor,
    fences: Sequence[MathFence],
    blocks: Sequence[Block],
    hosted: Sequence[ClaimNode],
    proofs: Mapping[int, _Proof],
    minted: ClaimNode | None,
) -> tuple[ClaimNode, ...] | None:
    """The claims an equation reference resolves through, or ``None`` for no equation reference.

    **The two empty answers are different and the caller acts on the
    difference.** ``None`` says the label names no fence in the document the
    anchor resolved to, so this is not an equation reference and the routes
    after it still apply. ``()`` says it *is* one and this cannot say which
    claim the equation belongs to — a proof binding to no subject, a
    claim-bearing block no register entry carries — and there the honest result
    is no pair at all. Collapsing the two would let an author's ``\\eqref`` land
    on whatever claim the target document happens to state alone, a claim they
    did not point at.

    **The residue is small and that is the point.** Measured over the staged
    corpus, 3 anchors take this refusal, because almost every equation the join
    meets now has a node or a proof behind it. Run the same ordering against a
    corpus with no equation nodes in it and the figure is 676 — which is what
    the refusal bounds, and what a build over a tree this row has not minted
    into would otherwise manufacture.

    The label is the anchor's own third attribute rather than its fragment,
    which point 9 leaves empty for an equation (:data:`tree.ANCHOR_RE`). **Where
    the equation is labelled is what decides**, and there are three cases:

    * inside a **claim-bearing block** — that block's claim holds it, an
      equation labelled inside a theorem body being that theorem's assertion;
    * inside a **proof** — the claims that proof establishes hold it, the
      equation being a step of their argument. The binding is
      :class:`inventory.Proof`'s, read here rather than derived a second time,
      and it is why such an equation needs no node of its own. A proof may
      establish several claims, and then the reference names several;
    * anywhere else — nothing holds it, and ``minted`` is the node the equation
      was given for exactly that reason (:mod:`equation`). It is reached here
      and nowhere else in this module.

    """
    fence = next((found for found in fences if anchor.label in found.labels), None)
    if fence is None:
        return None
    block = hosting_block(fence.start, blocks)
    if block is None:
        return (minted,) if minted is not None else ()
    if block.claim_bearing:
        held = _claim_of(block, hosted)
        return (held,) if held is not None else ()
    if block.environment.casefold() == PROOF_ENVIRONMENT:
        proof = proofs.get(block.start)
        return proof.subjects if proof is not None else ()
    return (minted,) if minted is not None else ()


def _source_end(
    anchor: Anchor,
    blocks: Sequence[Block],
    hosted: Sequence[ClaimNode],
    proofs: Mapping[int, _Proof],
    judged: tuple[prose.Standing, ClaimNode | None],
) -> tuple[tuple[ClaimNode, ...], bool]:
    """The claims the reference may belong to, and whether containment settled it.

    **The node pass's verdict comes first** (``judged``, :func:`prose.standing`).
    A reference in prose judged not a claim has no source and yields no pair; one
    in a paragraph judged a claim has that paragraph's claim as its source and no
    other. Everywhere else — inside a block, or in prose nobody judged — the
    rules below apply.

    Settled means a *direction* was established, which only a proof does: the
    claim the proof establishes rests on what the proof draws on. A reference
    inside a claim-bearing block narrows the end to one claim and says nothing
    about which way the edge runs; a reference anywhere else falls back to every
    claim the document hosts, which narrows nothing and settles nothing — one
    claim out of that fallback is a document hosting one, not a rule that read
    anything.
    """
    standing, claim = judged
    if standing is prose.Standing.NOT_A_CLAIM:
        return (), False
    if standing is prose.Standing.CLAIM:
        return ((claim,) if claim is not None else ()), False
    if (anchor.hosting_environment or "").casefold() == PROOF_ENVIRONMENT:
        block = hosting_block(anchor.line, blocks)
        proof = proofs.get(block.start) if block is not None else None
        if proof is None or proof.names(anchor):
            return (), False
        return (proof.subjects, True) if proof.subjects else (tuple(hosted), False)
    inside = _claim_of(hosting_block(anchor.line, [found for found in blocks if found.claim_bearing]), hosted)
    return ((inside,), False) if inside is not None else (tuple(hosted), False)


def _target_end(
    anchor: Anchor,
    targets: Sequence[ClaimNode],
    fences: Sequence[MathFence],
    blocks: Sequence[Block],
    proofs: Mapping[int, _Proof],
    minted: ClaimNode | None,
) -> tuple[tuple[ClaimNode, ...], str | None]:
    """The claims the reference may name, and the rule that settled it where one did.

    **Ordering decides which route a reference takes, not its type.** This used
    to branch on ``reference_type == "eqref"``, which asked the referencing
    *macro* a question only the referenced *target* can answer: an author's own
    ``\\ref{eq:8}`` names an equation and was sent down the identifier route to
    reach nothing, and the cleveref family — whose type says nothing about what
    it names — could be sent down neither route without being wrong about most
    of the corpus. Trying the identifier route first and falling back to the
    label-to-fence join costs nothing and preserves that reading exactly: a
    ``\\cref`` to a theorem has a fragment, wins on the identifier route, and
    never reaches the equation join at all. Measured anchor by anchor over the
    staged corpus, 1789 take the identifier route before the reorder and the
    same 1789 take it after; no anchor left it.

    **The equation join comes before the sole-claim fallback, and it ends the
    reference either way.** Where the label names a fence this returns what that
    join found and stops — an empty answer included — because a reference that
    names an equation is not a reference to the document's sole claim, and
    passing it on would be manufacturing one. An equation node never reaches the
    fallback for a second reason as well: ``targets`` is
    :meth:`graph.AuthoredGraph.hosted_by`, which does not carry one, so
    ``len(targets) == 1`` can only be a claim the document states.

    **A fragment naming a block somebody classified as stating no result ends the
    reference, and ends it ahead of the equation join.** The fragment is the
    strongest evidence an anchor carries — point 7 lands it on the node that held
    the label — so where it names a block :data:`inventory.NOT_A_CLAIM_TARGET`
    classifies, what the author pointed at is known and is not a claim. Both
    routes behind it would answer with one the author did not point at, which is
    manufacturing a target rather than resolving a reference.
    """
    named = _fragment_claim(anchor, targets)
    if named is not None:
        return (named,), BY_IDENTIFIER
    stated = _fragment_block(anchor, blocks)
    if stated is not None and stated.environment.casefold() in NOT_A_CLAIM_TARGET:
        return (), None
    through = _equation_claims(anchor, fences, blocks, targets, proofs, minted)
    if through is not None:
        return (through, BY_EQUATION) if through else ((), None)
    if len(targets) == 1:
        return tuple(targets), BY_SOLE_CLAIM
    return tuple(targets), None


def names_no_premise(word: str | None) -> bool:
    """Whether the word before an anchor names a kind no premise relation can hold.

    Two sources, one test. :data:`STRUCTURAL_KINDS` is the structure the page
    prints; :data:`inventory.NOT_A_CLAIM_TARGET` is the display names somebody
    classified as stating no result, which the target end already refuses when
    an anchor's fragment names such a block — read here off the word, for the
    anchor whose fragment names none. A plural is the singular's kind and a
    trailing stop marks an abbreviation, so *Sections* and *Fig.* read as
    *section* and *fig*.
    """
    if word is None:
        return False
    kind = word.casefold().rstrip(".")
    vocabulary = STRUCTURAL_KINDS | NOT_A_CLAIM_TARGET
    return kind in vocabulary or (kind.endswith("s") and kind[:-1] in vocabulary)


def _reference_line(tree: Tree, document: str, line: int) -> str:
    """The author's words around a reference — its whole paragraph, collapsed to one line.

    ``line`` is 0-based in the document's marker-stripped, unquoted numbering:
    an anchor's own line, or a hand-written mention's (:class:`hand_named.HandNamed`).

    **A paragraph rather than a physical line, because the wrap is pandoc's.**
    The built markdown is hard-wrapped near 72 columns, so a physical line is a
    unit the converter chose and not one the author wrote in: the anchor lands on
    whichever side of a wrap it fell on, and the word saying what the reference is
    doing there — *By*, *using*, *follows from* — sits on the line above as
    readily as on the anchor's own. Read line by line over the built ModernCorp
    tree, 0 of 22 values reaching the ask's passages carried any of by /
    from / follows from / using / via / in view of / applying / combining / rests
    on / since / because / building on, and some were markup alone — half an
    anchor tag, cut at a wrap. Read paragraph by paragraph, 15 of 19 carry one.

    The blank-line block is also the narrowest unit :attr:`Anchor.line` can name.
    A wrapped line holds parts of several sentences and a sentence runs across
    several lines, so a line number names a set of sentences rather than one, and
    an anchor carries no offset to narrow that set with.

    **No length bound, and that is measured rather than assumed.** Over the same
    tree's 243 anchors the paragraph runs to 2789 characters at its longest and
    2277 at the 99th percentile, and the longest ones are ordinary prose. The case
    a bound would be for — a display-maths fence flush against the prose, which
    this corpus writes with no blank line around it — sits at the median rather
    than in the tail (1223 characters against 1218). Ending the run at a fence was
    measured too: it changes no value's cue phrase, 15 of 19 either way, and
    leaves the evidence opening mid-sentence on the words after the fence, "with
    ``$`\\rho`$`` the discount rate" for a paragraph whose subject stood two fences
    above — the defect this function exists to avoid, paid for a second time.

    **Marker-stripped and unquoted before the block is found, not after.** This
    value is not read by this package: it becomes one of
    :attr:`Candidate.passages` and renders verbatim into the ask's
    reference-lines slot. A Tier-2 marker is
    appended to the end of the line its claim is located by, and this stage always
    runs over a tree two earlier passes have minted into — so an author who states
    a result by reference puts the anchor and the marker on one line, and the seat
    choosing a dependency direction would be reading the metadata alongside the
    prose. Unquoting first is what makes the boundary right inside a blockquote,
    where the blank line separating two quoted paragraphs is written ``>``: read
    quoted, that line is not blank and the run swallows the whole quote.
    """
    lines = unquote(strip_markers(tree.documents[document].text)).splitlines()
    if line >= len(lines):
        return ""
    start = line
    while start > 0 and lines[start - 1].strip():
        start -= 1
    end = line + 1
    while end < len(lines) and lines[end].strip():
        end += 1
    return render.collapse_prose(" ".join(lines[start:end]))


def cycle_edges(edges: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """Every edge lying on a cycle, sorted. Removing them all leaves an acyclic set.

    An edge is on a cycle exactly when its target reaches its source again, so
    this is a property of the edge set alone — no tie-break key, no iteration
    order, and two runs over one corpus name the same edges. What remains is the
    condensation of the graph, which is acyclic by construction rather than by a
    check afterward.
    """
    following: dict[str, set[str]] = {}
    for source, target in edges:
        following.setdefault(source, set()).add(target)

    def reaches(start: str) -> set[str]:
        reached: set[str] = set()
        pending = [start]
        while pending:
            for node in following.get(pending.pop(), ()):
                if node not in reached:
                    reached.add(node)
                    pending.append(node)
        return reached

    onward = {target: reaches(target) for _, target in edges}
    return tuple(sorted({(source, target) for source, target in edges if source in onward[target]}))


@dataclass(frozen=True)
class Attribution:
    """What the narrowing produced: every candidate, classed and drafted.

    ``candidates`` is one per ordered pair, sorted by it, a pair two harvests
    reach merged into one (:class:`Candidate`).

    ``routes`` counts the pairs drafted *supported by* by the target-end rule
    that resolved each, which is what the build's own log carries in place of a
    marker on the edge: an edge authored here is an ordinary ``depends`` edge and
    nothing in the KB distinguishes it from one a person wrote. ``demoted`` is
    out of it, those pairs being drafted *mention*.

    ``demoted`` is the pairs containment settled that a ring took the direction
    off — carried separately only so the report can name them.

    ``word_dropped`` is the pairs an anchor would have opened had the word
    before it not named a kind no premise relation can hold
    (:func:`names_no_premise`), less any pair that is a candidate anyway. They
    are no candidate: the author pointed at a section or a figure, and the
    claims it hosts are what the fallback routes offered in its place.

    ``own_equations`` is the pairs some harvest reached from a claim to an
    equation node whose fence lies inside that claim's own body
    (:func:`equation_sites.own_equations`). They are no candidate: the claim
    states that equation, so the pair is no dependency in either direction and
    no reference.
    """

    candidates: tuple[Candidate, ...]
    routes: Mapping[str, int]
    demoted: tuple[tuple[str, str], ...] = ()
    word_dropped: tuple[tuple[str, str], ...] = ()
    own_equations: tuple[tuple[str, str], ...] = ()

    def _drafted(self, kind: Written) -> tuple[tuple[str, str], ...]:
        records = (written(candidate, candidate.draft) for candidate in self.candidates)
        return tuple(sorted({pair for written_as, pair in records if written_as is kind}))

    @property
    def edges(self) -> tuple[tuple[str, str], ...]:
        """The ``depends`` edges the drafts write: what a build with no reader records."""
        return self._drafted(Written.DEPENDS)

    @property
    def references(self) -> tuple[tuple[str, str], ...]:
        """The ``references`` records the drafts write."""
        return self._drafted(Written.REFERENCES)


@dataclass
class _Reached:
    """One pair's provenances as the narrowing meets them, before they merge into a :class:`Candidate`."""

    offered: frozenset[Relation]
    passages: set[str]
    harvests: set[Harvest]


def narrow(
    tree: Tree,
    graph: AuthoredGraph,
    inventory: Inventory,
    record: kb_pipeline.NodePassRecord | None = None,
    unmarked: Iterable[tuple[str, str]] = (),
) -> Attribution:
    """Every edge candidate the corpus states, classed and drafted.

    Deterministic and total: nothing is sampled and nothing is dropped
    silently. Three harvests: stage B's anchors, read end by end,
    :func:`hand_named.harvest`, and ``unmarked``. A pair any of them reaches is
    one candidate, unless it is a claim and one of its own equations
    (:attr:`Attribution.own_equations`).

    ``record`` is the node pass's, whose verdicts decide the source end of a
    reference in readable prose (:func:`_source_end`). ``None`` is a record
    judging nothing, every such reference unjudged.

    ``unmarked`` is the ordered pairs the unmarked-reference ask answered yes
    (:func:`unmarked.found`). Each is classed as an undirected provenance of
    its pair, drafted *mention*, and its passage is the source claim's own
    body (:func:`hand_named.bodies`) — a prose claim's paragraph, a block
    claim's block — the yes having been about that claim's text.
    """
    blocks = by_document(inventory.blocks)
    fences = by_document(inventory.fences)
    proofs = _proofs(graph, inventory)
    readable: dict[str, prose.Readable] = {}
    passages: dict[tuple[str, int], str] = {}

    def judged(anchor: Anchor) -> tuple[prose.Standing, ClaimNode | None]:
        if anchor.document not in readable:
            readable[anchor.document] = prose.readable(tree.documents[anchor.document], inventory)
        leaf = readable[anchor.document]
        standing = prose.standing(anchor, leaf, None if record is None else record.leaves.get(anchor.document))
        if standing is not prose.Standing.CLAIM:
            return standing, None
        claim = prose.claim_of(anchor, leaf, (node.id for node in graph.hosted_by(anchor.document)))
        return standing, None if claim is None else graph.nodes[claim]

    settled: dict[tuple[str, str], str] = {}
    reached: dict[tuple[str, str], _Reached] = {}
    unopened: set[tuple[str, str]] = set()

    def passage_at(document: str, line: int) -> str:
        if (document, line) not in passages:
            passages[(document, line)] = _reference_line(tree, document, line)
        return passages[(document, line)]

    def reach(pair: tuple[str, str], *, offered: frozenset[Relation], passage: str | None, harvest: Harvest) -> None:
        found = reached.setdefault(pair, _Reached(offered=offered, passages=set(), harvests=set()))
        found.offered &= offered
        found.harvests.add(harvest)
        if passage is not None:
            found.passages.add(passage)

    for anchor in inventory.anchors:
        if anchor.target is None:
            continue
        targets = graph.hosted_by(anchor.target)
        # An equation node is not in `targets` and is the only thing 144 of this
        # corpus's documents hold, so a bail on the hosted set alone would drop
        # every reference into one of them before the join that resolves it ran.
        minted = graph.equation_node(anchor.target, anchor.label)
        if not targets and minted is None:
            continue

        to_ends, route = _target_end(
            anchor,
            targets,
            fences.get(anchor.target, ()),
            blocks.get(anchor.target, ()),
            proofs.get(anchor.target, {}),
            minted,
        )
        if not to_ends:
            continue
        from_ends, directed = _source_end(
            anchor,
            blocks.get(anchor.document, ()),
            graph.hosted_by(anchor.document),
            proofs.get(anchor.document, {}),
            judged(anchor),
        )
        # The word before the anchor filters what a fallback route opened and
        # never what containment settles, and it gives way to a fragment or a
        # label that named the claim itself.
        unheld = route not in (BY_IDENTIFIER, BY_EQUATION) and names_no_premise(anchor.preceding_word)

        for source in from_ends:
            for target in to_ends:
                if source.id == target.id:
                    continue
                pair = (source.id, target.id)
                if directed and route is not None:
                    settled.setdefault(pair, route)
                elif unheld:
                    unopened.add(pair)
                    continue
                offered = OFFERED[_class_of(directed=directed, target=target)]
                reach(
                    pair, offered=offered, passage=passage_at(anchor.document, anchor.line), harvest=Harvest.REFERENCE
                )

    for found in hand_named.harvest(tree, graph, inventory):
        offered = OFFERED[_class_of(directed=False, target=graph.nodes[found.target])]
        reach(
            (found.source, found.target),
            offered=offered,
            passage=passage_at(found.document, found.line),
            harvest=Harvest.HAND_NAMED,
        )

    yeses = tuple(unmarked)
    if yeses:
        # The yes was about the source claim's own text, so that text is its
        # passage. A claim no body reaches is shown to classification by its
        # title (`classify.statements`) and gets no passage here.
        own_text: dict[str, str] = {}
        for node, _, _, body in hand_named.bodies(tree, graph, inventory):
            own_text.setdefault(node.id, render.collapse_prose(body))
        for source, target in yeses:
            offered = OFFERED[_class_of(directed=False, target=graph.nodes[target])]
            reach((source, target), offered=offered, passage=own_text.get(source), harvest=Harvest.UNMARKED)

    stated = equation_sites.own_equations(tree, graph, inventory).intersection(reached)
    demoted = cycle_edges(sorted(settled))
    on_ring = set(demoted)
    routes: dict[str, int] = {}
    for pair, name in settled.items():
        if pair not in on_ring:
            routes[name] = routes.get(name, 0) + 1

    candidates = tuple(
        Candidate(
            source=graph.nodes[pair[0]],
            target=graph.nodes[pair[1]],
            offered=tuple(relation for relation in Relation if relation in found.offered),
            draft=Relation.SUPPORTED_BY if pair in settled and pair not in on_ring else Relation.MENTION,
            passages=tuple(sorted(found.passages)),
            harvests=frozenset(found.harvests),
        )
        for pair, found in sorted(reached.items())
        if pair not in stated
    )
    return Attribution(
        candidates=candidates,
        routes=routes,
        demoted=demoted,
        word_dropped=tuple(sorted(unopened - set(reached))),
        own_equations=tuple(sorted(stated)),
    )
