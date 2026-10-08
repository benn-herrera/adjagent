"""Testing: boundary checks, unit and integration test scope, verification
evidence, and the review-side test rule."""

from typing import Literal


# architect.tmpl.md's `Runtime boundary validation` invariant states this whole
# paragraph in its own words and in must-voice — this chunk, the two check
# questions, cheap-over-thorough, the routing rule and the consumer triple. A
# chunk edit does not reach it.
def boundary_checks_lead(
    *, boundaries: str = "external API calls, user input parsing, database writes, IPC, and queue boundaries"
) -> str:
    return rf"""*Runtime boundary checks*: at significant system boundaries — {boundaries} — implement lightweight contract and expectation checks. What makes one a boundary is what the check reads, not where the line sits: data your own code did not compute, or state another thread or process may have changed underneath you. A check over a value your own code just computed, or over a state the code that reaches it has already refused, restates the design instead of testing it. Apply these only when the change directly touches or creates such a boundary; a fix internal to a module does not require new boundary checks."""


CHEAP_OVER_THOROUGH = (
    r"""Cheap is more important than thorough — a check that always runs beats one that gets disabled."""
)


def boundary_check_coder_body(*, expectation: str = "state/thread/context", routing: str = "the logging system") -> str:
    return rf"""Contract checks: are these inputs valid for this boundary? Expectation checks: is the system in the expected {expectation}? {CHEAP_OVER_THOROUGH} Route violations through {routing}."""


# A second home for the consumer triple, deliberately: platform-testing-lead
# leads with the sink, for a seat whose logger is already chosen; this one
# leads with the count, which is what stops a coder seat building three
# diagnostic paths. Merging them is a wording ruling, not an extraction.
BOUNDARY_CHECK_CONSUMERS_CODER = r"""One implementation serves three consumers: production forensics, development diagnostics, and integration test signal."""


# NOT shell-dsl-coder, the one implementing seat that takes boundary-checks-lead
# without this: a recipe legitimately drives docker, git, jq, curl and a cloud
# CLI, so a mock count read as evidence of coupling fires on the normal case
# there.
def mocking_threshold(*, variant: Literal["general"]) -> str:
    texts = {
        "general": r"""If you need to mock five dependencies to test one function, fix the design first.""",
    }
    return texts[variant]


# A second home for the rule unit-test-scope states, on the same split
# boundary-check-consumers-coder records: a platform expert is warned off its
# refactor-fragile artifact, a coder seat off call sequences and code paths.
def unit_test_scope_coder(*, examples: str = "fiddly math, boundary conditions, state transitions") -> str:
    return rf"""Target logic and algorithms where the correct answer is independently verifiable — {examples}. Do NOT write unit tests for log messages, exact call sequences, or code paths — that is a code checksum. A test that breaks on refactor but not on logic error is worse than no test."""


# Deliberately not folded into unit-test-scope-coder above: go-coder and
# rust-coder state no coverage rule, and folding it in would add one to them.
COVERAGE_METRIC = r"""Coverage percentage is the wrong metric."""

# Review-side counterpart of unit-test-scope and unit-test-scope-coder: what to
# cut from a suite, not what to write into one. The checksum class (log
# messages, call sequences) stays with those chunks and architect.tmpl.md's
# unit-test item; this one adds only what they do not name. Observed: the owner
# typing this instruction into review briefs by hand across several sprints.
TEST_REVIEW = r"""**Reviewing tests, name what to cut.** *Duplicate coverage*: a test pinning a behaviour another already pins through the same path, a unit re-proving a golden-file or parametrised case included — merge or delete, naming the survivor. *Performative units*: a test no logic error could fail — a constant compared to itself, a mock confirmed called with nothing checked of what it was given, a file confirmed to load with no further claim — delete. Propose a new test only for a stated invariant or acceptance criterion that no test exercises."""


# The coders' and platform experts' When Reviewing section. body is its content
# without the heading, for a seat that reviews under a section of its own
# (shell-dsl-coder's Review Function); section expands body, so a rule added
# there reaches both.
def when_reviewing(*, variant: Literal["section", "body"]) -> str:
    if variant == "section":
        return "## When Reviewing\n\n" + when_reviewing(variant="body")
    return TEST_REVIEW


def integration_logging_signal(*, sink: str, level: str = "logging") -> str:
    return rf"""Run with {level} enabled — boundary check violations appear in {sink} as additional signal."""


def integration_tests_coder(*, subject: str = "exercise the system") -> str:
    return rf"""*Integration tests*: {subject} with realistic or well-chosen synthetic inputs that hit edges and corners. Real data for its own sake is not the goal — use judgment on inputs. {integration_logging_signal(level='maximum logging', sink='output')}"""


INTEGRATION_ARTIFACT = r"""**Integration tests exercise the delivered artifact** through its public surface (the binary/API as shipped), never in-process calls to internals — those are unit/component tests, whatever the file is named. Never create dev-only entry points or test-only verbs to make testing easier; test the real surface, and if the real surface is untestable, that is a design defect to surface, not scaffold around. Dev-only switches (e.g. expensive validation such as heap checking under custom allocators) are a last resort and live behind a config-file setting, never an environment variable."""


# Both arguments exist for architect, which has no Bash: it runs nothing, so
# neither the default forms nor the default evidence location is reachable for
# it. Every other consumer takes both defaults.
def verification_evidence(
    *,
    forms: str = "a test, a runner-recipe invocation, or a preserved command with its captured output",
    where: str = "Where the project defines an evidence location, put it there (integration logs/artifacts included).",
) -> str:
    return rf"""**Verification evidence**: any verification a reported conclusion rests on must be repeatable and inspectable — {forms}; never an ad-hoc sequence whose results live only in the conversation. Results that cannot be re-examined are not results. {where} Exploratory checks along the way are exempt: this binds the verifications you cite, not every look around."""
