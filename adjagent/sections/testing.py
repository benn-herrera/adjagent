"""Testing: the three test layers and verification evidence, and the review-side test rule."""

from dataclasses import dataclass

from adjagent.context import Render
from adjagent.section import Part, Section

_LAYERS_LEAD = r"""**Testing** — three layers, each with a distinct purpose:"""

_BOUNDARY_CHECKS_LEAD = r"""*Runtime boundary checks*: at significant system boundaries — external API calls, user input parsing, database writes, IPC, and queue boundaries — implement lightweight contract and expectation checks. What makes one a boundary is what the check reads, not where the line sits: data your own code did not compute, or state another thread or process may have changed underneath you. A check over a value your own code just computed, or over a state the code that reaches it has already refused, restates the design instead of testing it. Apply these only when the change directly touches or creates such a boundary; a fix internal to a module does not require new boundary checks."""

_CHEAP_OVER_THOROUGH = (
    r"""Cheap is more important than thorough — a check that always runs beats one that gets disabled."""
)

_BOUNDARY_CHECK_CONSUMERS = r"""One implementation serves three consumers: production forensics, development diagnostics, and integration test signal."""

_UNIT_TEST_SCOPE = r"""Target logic and algorithms where the correct answer is independently verifiable — fiddly math, boundary conditions, state transitions. Do NOT write unit tests for log messages, exact call sequences, or code paths — that is a code checksum. A test that breaks on refactor but not on logic error is worse than no test."""

_COVERAGE_METRIC = r"""Coverage percentage is the wrong metric."""

_MOCKING_THRESHOLD = r"""If you need to mock five dependencies to test one function, fix the design first."""

_INTEGRATION_TESTS = r"""*Integration tests*: exercise the system with realistic or well-chosen synthetic inputs that hit edges and corners. Real data for its own sake is not the goal — use judgment on inputs. Run with maximum logging enabled — boundary check violations appear in output as additional signal."""

_INTEGRATION_ARTIFACT = r"""**Integration tests exercise the delivered artifact** through its public surface (the binary/API as shipped), never in-process calls to internals — those are unit/component tests, whatever the file is named. Never create dev-only entry points or test-only verbs to make testing easier; test the real surface, and if the real surface is untestable, that is a design defect to surface, not scaffold around. Dev-only switches (e.g. expensive validation such as heap checking under custom allocators) are a last resort and live behind a config-file setting, never an environment variable."""

_VERIFICATION_EVIDENCE = r"""**Verification evidence**: any verification a reported conclusion rests on must be repeatable and inspectable — a test, a runner-recipe invocation, or a preserved command with its captured output; never an ad-hoc sequence whose results live only in the conversation. Results that cannot be re-examined are not results. Where the project defines an evidence location, put it there (integration logs/artifacts included). Exploratory checks along the way are exempt: this binds the verifications you cite, not every look around."""

_TEST_REVIEW = r"""**Reviewing tests, name what to cut.** *Duplicate coverage*: a test pinning a behaviour another already pins through the same path, a unit re-proving a golden-file or parametrised case included — merge or delete, naming the survivor. *Performative units*: a test no logic error could fail — a constant compared to itself, a mock confirmed called with nothing checked of what it was given, a file confirmed to load with no further claim — delete. Propose a new test only for a stated invariant or acceptance criterion that no test exercises."""


@dataclass(frozen=True, kw_only=True)
class Testing(Section):
    """A coder's testing run: runtime boundary checks, unit tests, integration tests, the delivered
    artifact rule and verification evidence.

    architect states the boundary-check paragraph in its own words; an edit here does not reach it.
    """

    unit_tests: str
    """The unit-test paragraph: the framework text after `*Unit tests*: `."""

    unit_tests_closing: str
    """The unit-test paragraph: its last line, after the mocking rule."""

    integration_tests: str
    """The integration-test paragraph: the tooling text after the logging-signal sentence."""

    routing: str = "the logging system"
    """The boundary-check paragraph: `Route violations through <routing>.`"""

    coverage_metric: bool = False
    """Whether the unit-test paragraph states the coverage rule; a seat without it states none."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        boundary = (
            f"{_BOUNDARY_CHECKS_LEAD} Contract checks: are these inputs valid for this boundary? "
            f"Expectation checks: is the system in the expected state/thread/context? {_CHEAP_OVER_THOROUGH} "
            f"Route violations through {self.routing}. {_BOUNDARY_CHECK_CONSUMERS}"
        )
        scope = " ".join(
            (_UNIT_TEST_SCOPE, _COVERAGE_METRIC, _MOCKING_THRESHOLD)
            if self.coverage_metric
            else (_UNIT_TEST_SCOPE, _MOCKING_THRESHOLD)
        )
        return (
            ("", _LAYERS_LEAD),
            ("routing", boundary),
            (
                "unit_tests, coverage_metric, unit_tests_closing",
                f"*Unit tests*: {self.unit_tests}\n{scope}\n{self.unit_tests_closing}",
            ),
            ("integration_tests", f"{_INTEGRATION_TESTS} {self.integration_tests}"),
            ("", _INTEGRATION_ARTIFACT),
            ("", _VERIFICATION_EVIDENCE),
        )


@dataclass(frozen=True)
class WhenReviewing(Section):
    """The When Reviewing section: what to cut from a test suite under review."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (("", "## When Reviewing"), ("", _TEST_REVIEW))
