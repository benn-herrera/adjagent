"""mad/design-topics/*: the design-topic documents a design referee hands its seats, one per domain.

A paragraph the topics carry alike is a constant here, or a slot constant filled where each topic uses
it.
"""

from adjagent import clauses
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

# imports is plural-headed, to agree with the `are` that follows it.
_EXTERNAL_AUTHORITY = """Build only on {basis} — the exclusive source of foundational truth for this construction. {imports} are legitimate context and never load-bearing on their own: an appeal to one must be justified against the problem at hand."""

_MARK_CONDITIONAL = (
    """Mark any {unit} that depends on {gap}. A marked {unit} is conditional and surfaces as a candidate for {state}."""
)

_TERMINAL_STATES = """A successful debate terminates in one of these states:"""

_MULTIPATH_CONVERGENCE = """- **(b) Multi-path convergence**: participants reach the same {result} via demonstrably independent {paths}. Both paths are preserved in the deliverable as mutually reinforcing confirmations of the same {result}. This is a strong-positive outcome."""

# record is "" or a phrase opening with a space.
_UNRESOLVED_DIVERGENCE = """- **({letter}) Unresolved divergence**: participants remain at {divergence} after the round cap. All candidates are documented{record} and preserved for human arbitration."""

# Heading-less: each topic names the value its own way.
_REFERENCE_VALUE = """Where the problem has a known reference value (e.g., {examples}), participants may compute their {construction}'s prediction and compare. A {construction} that disagrees with the reference is not automatically wrong — {caveat} — but the disagreement must be acknowledged and explained.

A reference value MUST NOT be load-bearing in the {construction} itself. It may be used at the end for validation, and its role must be stated explicitly."""

DEFINITIONS = (
    Definition(
        name="architecture",
        kind=Kind.DOCUMENT,
        folder="mad/design-topics",
        body=f"""# TOPIC: Architecture Design

## Domain

Software architecture construction for difficult systems: package and module structure, abstraction
boundaries, layering, coupling, interface contracts, data flow, state ownership, and failure-mode
handling for problems that do not have a standard, well-trodden solution.
{_EXTERNAL_AUTHORITY.format(
    basis="the provided problem statement, requirements, and any invariant document",
    imports="Established patterns (*the way framework X does it*, *the canonical pattern for Y*)",
)}

This topic is for systems where the structural decisions are non-obvious — novel data flows,
cross-cutting concerns, hard performance/safety/portability constraints, or hybrid requirements that
resist any single off-the-shelf pattern. It is not for greenfield CRUD-shaped problems where the
answer is "the usual thing."

## Constructive Architecture, Adversarially Defended

The proposal must include, at minimum:

- **Module / package decomposition** with the responsibility of each unit stated in one sentence
- **Key abstractions and interface contracts** between units — what each interface carries, what it
  deliberately does not, and what behavioral guarantees it makes
- **Layering and dependency direction** — which units depend on which, and why the direction is
  consistent
- **Data flow and state ownership** — where each piece of state lives, who is allowed to mutate it,
  and how it crosses boundaries
- **Failure-mode handling** — where errors are produced, where they are handled, and where they
  cross system boundaries
- **Cost / capability accounting** for each non-trivial structural decision: what hard problem it
  solves, what cheaper structure was considered and rejected, and why the cheaper structure fails

{_MARK_CONDITIONAL.format(
    unit="decision",
    gap=(
        "a requirement the problem statement asserts but does not fully specify (e.g., implied performance "
        "bounds, unstated portability targets, undefined consistency guarantees)"
    ),
    state="under-determination diagnosis",
)}

### Attack Surface

Identify unjustified abstractions, hidden coupling, abstraction inversions, leaky contracts,
pattern-for-its-own-sake, premature configurability, structural complexity that does not pay rent,
separation-of-concerns violations disguised as helpers, and decisions that close doors the
requirements say must remain open. Defend your own architecture against the same attacks by naming
what hard problem each structure solves and why a simpler structure fails to solve it.

## Convergence Criteria

Architecture problems usually admit a small family of valid solutions rather than a single right
answer. Convergence here is about whether participants agree on the structure of the solution space
and on a specific point within it — or, when they do not, on a clear diagnosis of why.

{_TERMINAL_STATES}

- **(a) Structural convergence**: all active participants converge on the same module decomposition,
  the same key interface contracts, the same layering and dependency direction, and the same
  data/state ownership boundaries — modulo trivial naming or grouping differences. The architecture
  is the deliverable.
{_MULTIPATH_CONVERGENCE.format(
    result="structural decisions",
    paths=(
        "reasoning paths (different driving constraints invoked, different rejected alternatives, but the same "
        "final structure)"
    ),
)}
- **(c) Tradeoff under-determination**: all active participants converge on the same
  characterization of the design space — same Pareto frontier, same set of viable architectures,
  same axes of tradeoff (e.g., latency vs. flexibility, simplicity vs. extensibility) — but cannot
  select a single point on the frontier from the supplied requirements. The frontier
  characterization and the specific missing requirement that would close the choice are the
  deliverable.
- **(d) Constraint under-determination**: all active participants converge on the same diagnosis
  that the problem cannot be closed from the supplied requirements at all, and identify the specific
  missing constraint, invariant, capability target, or stakeholder decision required. The diagnostic
  statement is the deliverable.
{_UNRESOLVED_DIVERGENCE.format(
    letter="e",
    divergence="distinct architectures making different structural commitments",
    record=" with their cost/capability accounting",
)}

## What This Topic Is Not

- This is not architecture *review* of an existing system.
- This is not implementation-level design. Findings about magic strings, error-handling style, or
  local DRY belong in code review, not here.
- This is not a search for an elegant pattern. A pattern is justified only if it removes a harder
  complexity than it introduces.
- This is not greenfield boilerplate. Reserve this process for problems where the structural
  decisions are genuinely non-obvious and the cost of getting them wrong is high.

## How to Report Proposals and Findings

Tradeoff disagreements should be framed as "this choice optimizes axis X at cost to axis Y; the
requirements weigh X higher" — not as right/wrong.""",
    ),
    Definition(
        name="math-derivation",
        kind=Kind.DOCUMENT,
        folder="mad/design-topics",
        body=f"""# TOPIC: Mathematical Derivation Construction

## Domain
Deep, technical mathematics related to physical phenomena from subatomic to cosmological scales.
{_EXTERNAL_AUTHORITY.format(
    basis="the provided axiom set", imports="External results (GR, QED, SM constants, established theorems)"
)} A document specifying the axiom set will be provided alongside the open problem statement.

## Constructive Derivation, Adversarially Defended

State the physical principle invoked at each step, the equations it produces, and the boundary
conditions that close it. Cite specific axioms or already-derived consequences for every non-trivial
assertion.
{_MARK_CONDITIONAL.format(
    unit="step",
    gap="a result the framework asserts but does not derive in the supplied corpus",
    state="under-determination diagnosis",
)}

### Attack Surface

Identify gaps, unjustified leaps, circular reasoning, sign errors, dimensional inconsistencies,
boundary condition violations, hidden empirical inputs, or implicit reliance on the answer being
known. Defend your own derivation against the same attacks.

## Convergence Criteria

{_TERMINAL_STATES}

- **(a) Algebraic convergence**: all active participants converge on the same closed-form derivation
  modulo algebraic equivalence. The derivation is the deliverable.
{_MULTIPATH_CONVERGENCE.format(result="numerical answer", paths="derivation paths")}
- **(c) Under-determination**: all active participants converge on the same statement of why the
  problem cannot be closed from the supplied axioms, and identify the specific additional axiom,
  principle, boundary condition, or empirical input required. The diagnostic statement is the
  deliverable.
{_UNRESOLVED_DIVERGENCE.format(
    letter="d", divergence="distinct derivations producing different numerical predictions", record=""
)}

## Numerical Validation

{_REFERENCE_VALUE.format(
    examples="a CODATA quantity, an engine fit value, an experimental measurement",
    construction="derivation",
    caveat="the reference may itself be empirical and the derivation may be predictive",
)}""",
    ),
    Definition(
        name="ml-engineering",
        kind=Kind.DOCUMENT,
        folder="mad/design-topics",
        body=f"""# TOPIC: ML Engineering

## Domain

Complex problem solving, technique research, and exploration in machine learning systems —
particularly inference, training, sampling, attention, optimization, quantization, distillation, and
novel inference-time mechanics. The space includes designing new techniques, adapting published ones
to non-standard regimes, diagnosing model behavior, and exploring open questions where the answer is
not yet known and may require empirical validation to resolve.

{_EXTERNAL_AUTHORITY.format(
    basis="the problem statement and the context supplied with it",
    imports="Published papers, reference implementations, and established techniques",
)}

## Constructive Technique, Adversarially Defended

{clauses.ml_technique_deliverable(unit="proposal")}

{_MARK_CONDITIONAL.format(
    unit="step",
    gap="an empirical outcome the proposal does not yet have data for",
    state="empirical under-determination resolution",
)}

### Attack Surface

{clauses.ml_technique_attacks(lead="Identify")} Defend your own proposal by sharpening the mechanism, grounding the
justification more concretely, tightening the prediction, or proposing a more discriminating measurement.

## Convergence Criteria

The choice between viable techniques frequently depends on empirical outcomes that reasoning cannot
predetermine. Convergence here is about whether participants agree on the proposed technique and on
a path to validate it — or, when they do not, on a clear diagnosis of why.

{_TERMINAL_STATES}

- **(a) Mechanism convergence**: all active participants converge on the same proposed technique,
  the same hypothesized mechanism, the same predicted observable behavior, and the same measurement
  plan — modulo trivial reformulation. The technique specification is the deliverable.
{_MULTIPATH_CONVERGENCE.format(
    result="technique",
    paths=(
        "justification paths (different mechanism rationales, different prior-work invocations, but the same "
        "final specification and the same predicted observables)"
    ),
)}
- **(c) Empirical under-determination**: all active participants converge on the same
  characterization of the candidate space — same set of viable techniques, same hypothesized
  mechanism for each, same predicted distinguishing measurements — but cannot select among them
  without running the experiment that distinguishes them. The candidate set, the distinguishing
  experiment, and the decision criterion are the deliverable. **Running the experiment IS the
  resolution** — this outcome is productive, not a failure.
- **(d) Theoretical under-determination**: all active participants converge on the same diagnosis
  that the problem cannot be closed from the supplied context — missing baseline, missing prior
  measurement, missing model-behavior characterization, or missing constraint. The diagnostic
  statement is the deliverable.
{_UNRESOLVED_DIVERGENCE.format(
    letter="e",
    divergence="distinct techniques making different mechanism-level claims",
    record=" with their full triple (mechanism, justification, measurement)",
)}

## Empirical Validation and Reference Values

{_REFERENCE_VALUE.format(
    examples="a published baseline, a logprob match against a reference implementation, a benchmark score",
    construction="proposal",
    caveat="the reference may itself be specific to a regime that does not transfer",
)} It is also admissible as evidence that the regime is comparable.

When the resolution path is "run the experiment," the experiment specification must be concrete
enough that a human or downstream agent can execute it without reinterpreting the proposal: specify
the prompt set or dataset, the baseline configuration, the metric, the threshold for
accepting/rejecting the hypothesis, and the failure modes that would invalidate the experiment
itself.

## What This Topic Is Not

- This is not architecture design.
- This is not formal derivation.
- This is not implementation. Findings about specific code patterns, error handling, or local DRY
  belong in code review.
- This is not a place to reach for novelty. If a well-established technique solves the problem, the
  strongest proposal is "use the established technique, here is why its conditions transfer."
  Novelty is a cost, not a virtue.

## How to Report Proposals and Findings

In debate rounds, the specific element an attack or defense turns on is a tensor or operation in the
mechanism, a claim in the justification, a metric in the measurement plan, or a cost line in the
accounting.

Tradeoff and uncertainty disagreements should be framed as "this proposal optimizes for X (e.g.,
compute) at cost to Y (e.g., flexibility); the problem prioritizes X" — not as right/wrong. When the
disagreement reduces to "we won't know until we measure," that is the signal for empirical
under-determination convergence, not for continued argumentation.""",
    ),
)
