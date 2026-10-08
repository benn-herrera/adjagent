"""mad/design-topics/math-derivation: the design-debate topic for mathematical derivation construction."""

from adjagent.definition import Definition
from adjagent.section import Prose
from adjagent.sections.mad import ConditionalMarking, ConvergenceCriteria, FoundationalBasis, ReferenceValidation
from adjagent.vocabulary import Kind

_METHOD = r"""State the physical principle invoked at each step, the equations it produces, and the boundary
conditions that close it. Cite specific axioms or already-derived consequences for every non-trivial
assertion."""

_ATTACK_SURFACE = r"""### Attack Surface

Identify gaps, unjustified leaps, circular reasoning, sign errors, dimensional inconsistencies,
boundary condition violations, hidden empirical inputs, or implicit reliance on the answer being
known. Defend your own derivation against the same attacks."""

_CONVERGED = r"""- **(a) Algebraic convergence**: all active participants converge on the same closed-form derivation
  modulo algebraic equivalence. The derivation is the deliverable."""

_UNDER_DETERMINATION = r"""- **(c) Under-determination**: all active participants converge on the same statement of why the
  problem cannot be closed from the supplied axioms, and identify the specific additional axiom,
  principle, boundary condition, or empirical input required. The diagnostic statement is the
  deliverable."""

DEFINITIONS = (
    Definition(
        name="math-derivation",
        kind=Kind.DOCUMENT,
        folder="mad/design-topics",
        sections=(
            Prose("# TOPIC: Mathematical Derivation Construction"),
            FoundationalBasis(
                lead=(
                    "## Domain\n"
                    "Deep, technical mathematics related to physical phenomena from subatomic to cosmological scales."
                ),
                basis="the provided axiom set",
                imports="External results (GR, QED, SM constants, established theorems)",
                tail="A document specifying the axiom set will be provided alongside the open problem statement.",
            ),
            Prose("## Constructive Derivation, Adversarially Defended"),
            ConditionalMarking(
                lead=_METHOD,
                unit="step",
                gap="a result the framework asserts but does not derive in the supplied corpus",
                state="under-determination diagnosis",
            ),
            Prose(_ATTACK_SURFACE),
            ConvergenceCriteria(
                converged=_CONVERGED,
                result="numerical answer",
                paths="derivation paths",
                under_determined=(_UNDER_DETERMINATION,),
                divergence="distinct derivations producing different numerical predictions",
            ),
            Prose("## Numerical Validation"),
            ReferenceValidation(
                examples="a CODATA quantity, an engine fit value, an experimental measurement",
                construction="derivation",
                caveat="the reference may itself be empirical and the derivation may be predictive",
            ),
        ),
    ),
)
