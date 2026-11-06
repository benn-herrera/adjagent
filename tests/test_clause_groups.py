"""Definitions that share an anchor clause form a group, and every member carries what its group's
table lists, unless an exemption states why not."""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

import adjagent
from adjagent import clauses
from tests._structure import carried_clauses

_DEFINITIONS = Path(adjagent.__file__).parent / "definitions"


@dataclass(frozen=True)
class Group:
    anchor: str
    members: tuple[str, ...]
    plain: tuple[str, ...]
    alternatives: tuple[tuple[str, str], ...] = ()


GROUPS = {
    "coders": Group(
        anchor="CODE_PRINCIPLES_CODER",
        members=(
            "c-coder",
            "cpp-coder",
            "generalist-coder",
            "go-coder",
            "lua-coder",
            "python-coder",
            "rust-coder",
            "shell-dsl-coder",
            "typescript-coder",
        ),
        plain=(
            "CODER_OUTPUT_FORMAT",
            "DISSENT",
            "INTEGRATION_ARTIFACT",
            "KEY_GUIDELINE",
            "NEW_PROJECT_SETUP",
            "PE_EXPANSION_BULLET",
            "PE_LEAD",
            "PE_SHARED_BULLETS",
            "PROJECT_DOCS_SETUP",
            "boundary_checks_lead",
            "dependency_vetting",
            "incumbent_search",
            "pe_declare_bullet",
            "pe_scope_creep_bullet",
            "verification_evidence",
            "BOUNDARY_CHECK_CONSUMERS_CODER",
            "MOCKING_THRESHOLD_GENERAL",
            "TESTING_LAYERS_CODER",
            "WHEN_REVIEWING_SECTION",
            "boundary_check_coder_body",
            "integration_logging_signal",
            "integration_tests_coder",
            "manual_over_large_dependency",
            "unit_test_scope_coder",
            "LOGGING_ABSTRACTION_NOTE",
            "ISSUE_TRACKER_HEALTH",
            "new_project_runner_recipes",
            "LOGS_NOT_STDOUT",
            "warnings_as_defects",
            "COVERAGE_METRIC",
            "heavy_logging_framework",
        ),
        alternatives=(
            ("build_system", "build_system_lead"),
            ("DATA_FORMATS", "DATA_FORMATS_SCOPE"),
            ("DEPENDENCIES_LEAD_PACKAGES", "DEPENDENCIES_LEAD_CRATES"),
        ),
    ),
    "platform-experts": Group(
        anchor="CODE_PRINCIPLES_PLATFORM",
        members=(
            "android-app-expert",
            "ios-app-expert",
            "linux-app-expert",
            "linux-kernel-driver-expert",
            "macos-app-expert",
            "web-app-expert",
            "windows-app-expert",
        ),
        plain=(
            "AUTHORING_STANDARDS_LEAD",
            "CODER_OUTPUT_FORMAT",
            "DISSENT",
            "INTEGRATION_ARTIFACT",
            "KEY_GUIDELINE",
            "LOGGING_ABSTRACTION_NOTE",
            "MOCKING_THRESHOLD_PLATFORM",
            "PE_EXPANSION_BULLET",
            "PE_LEAD",
            "PE_SHARED_BULLETS",
            "PLATFORM_TESTING_LEAD",
            "PROJECT_SETUP_PLATFORM",
            "WHEN_REVIEWING_SECTION",
            "boundary_checks_lead",
            "build_system",
            "dependency_vetting",
            "incumbent_search",
            "integration_logging_signal",
            "pe_declare_bullet",
            "pe_platform_adjacent",
            "pe_scope_creep_bullet",
            "platform_boundary_routing",
            "unit_test_scope",
            "verification_evidence",
            "STDLIB_FIRST_ALWAYS",
            "logging_backend_seam",
        ),
    ),
}

EXEMPTIONS = {
    (
        "shell-dsl-coder",
        "LOGGING_ABSTRACTION_NOTE",
    ): "Shell has no logging facility to wrap; its diagnostic channel is a direct stderr write, so the predicate has no thin abstraction as subject.",
    (
        "shell-dsl-coder",
        "LOGS_NOT_STDOUT",
    ): 'shell_dsl_coder.py ("stdout is the data channel ... go to stderr") states the same rule in its own words.',
    (
        "shell-dsl-coder",
        "WHEN_REVIEWING_SECTION",
    ): "shell_dsl_coder.py already delivers its four review clauses; the clause would reach them twice.",
    (
        "shell-dsl-coder",
        "boundary_check_coder_body",
    ): "shell_dsl_coder.py's boundary paragraph states the contract and expectation checks in shell's own terms, and the clause embeds CHEAP_OVER_THOROUGH, which that paragraph already delivers.",
    (
        "shell-dsl-coder",
        "integration_logging_signal",
    ): "Shell has no log level to raise; a violated check already writes to stderr and ends the run.",
    (
        "shell-dsl-coder",
        "heavy_logging_framework",
    ): "Shell logging is a stderr write, and shell_dsl_coder.py already bars any prerequisite beyond coreutils and the project's declared tools.",
    (
        "rust-coder",
        "heavy_logging_framework",
    ): 'rust_coder.py ("`tracing` when spans/structured fields are genuinely needed ... Do not pull in the `tracing` ecosystem for a tool that needs three log lines") states the same rule in its own words.',
    (
        "python-coder",
        "LOGGING_ABSTRACTION_NOTE",
    ): "python_coder.py directs stdlib `logging` via `getLogger(__name__)` with handlers at the entry point, which already separates logger from backend; there is no wrapper to be the predicate's subject.",
    (
        "generalist-coder",
        "new_project_runner_recipes",
    ): "The clause's required language slot has no true value for a seat without a single language; NEW_PROJECT_SETUP's standard set covers it.",
    (
        "go-coder",
        "warnings_as_defects",
    ): "The Go compiler emits errors, never warnings; go_coder.py runs `go vet` and `staticcheck` before shipping, which fail on any finding.",
    (
        "web-app-expert",
        "logging_backend_seam",
    ): 'web_app_expert.py ("use a structured console wrapper ... accept a logger interface so callers can substitute their own") states the wrapper rule in its own words.',
    (
        "android-app-expert",
        "logging_backend_seam",
    ): 'android_app_expert.py ("use a thin wrapper over `android.util.Log`") states the same rule, unconditionally.',
    (
        "windows-app-expert",
        "logging_backend_seam",
    ): 'windows_app_expert.py ("Define a thin interface; the backend ... is swappable") states the same rule in its own words.',
}


def check_clause_groups(
    groups: dict[str, Group],
    exemptions: dict[tuple[str, str], str],
    carried: dict[str, set[str]],
    defined: set[str],
) -> list[str]:
    """Every way the tables and the definitions disagree, one message per finding, each naming the
    group, the definition and the clause."""
    messages = []
    member_group = {member: name for name, group in groups.items() for member in group.members}
    for name, group in groups.items():
        table_names = {group.anchor, *group.plain, *(clause for pair in group.alternatives for clause in pair)}
        for clause in sorted(table_names - defined):
            messages.append(f"{name}: clause {clause} is not defined in adjagent/clauses.py")
        carriers = {definition for definition, names in carried.items() if group.anchor in names}
        for definition in sorted(carriers - set(group.members)):
            messages.append(f"{name}: {definition} carries {group.anchor} but is not listed as a member")
        for definition in group.members:
            names = carried.get(definition, set())
            if group.anchor not in names:
                messages.append(f"{name}: {definition} is listed as a member but does not carry {group.anchor}")
            for clause in group.plain:
                if clause not in names and (definition, clause) not in exemptions:
                    messages.append(f"{name}: {definition} lacks {clause} and has no exemption")
            for pair in group.alternatives:
                if sum(clause in names for clause in pair) != 1:
                    messages.append(f"{name}: {definition} must carry exactly one of {pair[0]} and {pair[1]}")
    for definition, clause in sorted(exemptions):
        name = member_group.get(definition)
        if name is None:
            messages.append(f"-: {definition} is not a member, so its exemption from {clause} is stale")
        elif clause in carried.get(definition, set()):
            messages.append(f"{name}: {definition} carries {clause}, so its exemption is stale")
        elif clause not in groups[name].plain:
            messages.append(f"{name}: {definition} is exempt from {clause}, which is not a plain entry")
    return messages


def check_exemption_quotes(exemptions: dict[tuple[str, str], str], sources: dict[str, str]) -> list[str]:
    """Every quote in an exemption reason, written `module.py ("a ... b")`, that its module does not
    carry, one message each, naming the definition, the clause and the module or fragment. `sources`
    maps a module file name to its text; a fragment is the quote between ` ... ` markers, matched
    with whitespace collapsed."""
    messages = []
    collapsed = {module: " ".join(text.split()) for module, text in sources.items()}
    for (definition, clause), reason in sorted(exemptions.items()):
        for module, quote in re.findall(r'(\w+\.py) \("(.+?)"\)', reason):
            if module not in collapsed:
                messages.append(
                    f"{definition}: exemption from {clause} quotes {module}, which is not a definition module"
                )
                continue
            for fragment in quote.split(" ... "):
                if fragment not in collapsed[module]:
                    messages.append(f"{definition}: exemption from {clause} quotes {fragment!r}, absent from {module}")
    return messages


def _real_carried() -> dict[str, set[str]]:
    carried: dict[str, set[str]] = {}
    for path in sorted(_DEFINITIONS.glob("*.py")):
        carried |= carried_clauses(path.read_text(encoding="utf-8"))
    return carried


def test_every_member_carries_what_its_group_carries() -> None:
    defined = {name for name in vars(clauses) if not name.startswith("_")}
    assert check_clause_groups(GROUPS, EXEMPTIONS, _real_carried(), defined) == []


_GROUP = Group(anchor="ANCHOR", members=("one", "two"), plain=("PLAIN",), alternatives=(("LEFT", "RIGHT"),))
_DEFINED = {"ANCHOR", "PLAIN", "LEFT", "RIGHT"}
_CARRIED = {"one": {"ANCHOR", "PLAIN", "LEFT"}, "two": {"ANCHOR", "PLAIN", "RIGHT"}}


@pytest.mark.parametrize(
    ("carried", "exemptions", "defined", "expected"),
    [
        pytest.param(
            {**_CARRIED, "two": {"ANCHOR", "LEFT"}}, {}, _DEFINED, "two lacks PLAIN and has no exemption", id="lacks"
        ),
        pytest.param(
            {**_CARRIED, "two": {"ANCHOR", "PLAIN", "LEFT", "RIGHT"}},
            {},
            _DEFINED,
            "two must carry exactly one of LEFT and RIGHT",
            id="both",
        ),
        pytest.param(
            {**_CARRIED, "two": {"ANCHOR", "PLAIN"}},
            {},
            _DEFINED,
            "two must carry exactly one of LEFT and RIGHT",
            id="neither",
        ),
        pytest.param(_CARRIED, {("two", "PLAIN"): "r"}, _DEFINED, "two carries PLAIN, so its exemption", id="stale"),
        pytest.param(
            {**_CARRIED, "two": {"PLAIN", "RIGHT"}},
            {},
            _DEFINED,
            "two is listed as a member but does not carry ANCHOR",
            id="no-anchor",
        ),
        pytest.param(
            {**_CARRIED, "two": {"PLAIN", "RIGHT"}},
            {("two", "ANCHOR"): "r"},
            _DEFINED,
            "ANCHOR, which is not a plain entry",
            id="anchor-exempt",
        ),
        pytest.param(
            {**_CARRIED, "three": {"ANCHOR"}}, {}, _DEFINED, "three carries ANCHOR but is not listed", id="unlisted"
        ),
        pytest.param(_CARRIED, {}, _DEFINED - {"PLAIN"}, "clause PLAIN is not defined", id="undefined"),
        pytest.param(_CARRIED, {("two", "LEFT"): "r"}, _DEFINED, "LEFT, which is not a plain entry", id="not-plain"),
        pytest.param(_CARRIED, {("three", "PLAIN"): "r"}, _DEFINED, "three is not a member", id="not-member"),
    ],
)
def test_the_check_reports_each_disagreement(
    carried: dict[str, set[str]], exemptions: dict[tuple[str, str], str], defined: set[str], expected: str
) -> None:
    messages = check_clause_groups({"g": _GROUP}, exemptions, carried, defined)
    assert any(expected in message for message in messages), messages


def test_the_check_is_silent_on_agreement() -> None:
    assert check_clause_groups({"g": _GROUP}, {}, _CARRIED, _DEFINED) == []


def test_every_exemption_quote_occurs_in_its_definition_module() -> None:
    sources = {path.name: path.read_text(encoding="utf-8") for path in _DEFINITIONS.glob("*.py")}
    assert check_exemption_quotes(EXEMPTIONS, sources) == []


def test_an_exemption_quote_absent_from_its_module_is_reported() -> None:
    exemptions = {("d", "C"): 'm.py ("stdout is the data ... go to stderr")'}
    messages = check_exemption_quotes(exemptions, {"m.py": "stdout is the data channel; output go to stdout"})
    assert len(messages) == 1
    assert "d" in messages[0] and "C" in messages[0] and "go to stderr" in messages[0]


def test_an_exemption_quote_from_an_unknown_module_is_reported() -> None:
    messages = check_exemption_quotes({("d", "C"): 'gone.py ("x")'}, {"m.py": "x"})
    assert len(messages) == 1
    assert "gone.py" in messages[0]


def test_an_exemption_quote_spanning_a_line_break_is_found() -> None:
    exemptions = {("d", "C"): 'm.py ("stdout is the data ... go to stderr")'}
    assert check_exemption_quotes(exemptions, {"m.py": "stdout is the\n    data channel; all\n  go to stderr"}) == []
