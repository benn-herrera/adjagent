"""The adjagent package's own logic, each case checked against values the
renderer did not compute: the two map flags' grammar, the rendered model text,
the CLI's Render refusals, the frontmatter of each kind against literal lines of
the pre-1.0 render, guest extraction leaving exactly a definition's body and every
participant extracting to the contract, overlay resolution and stock, Definition,
Prose and section-field refusals, the loader's refusal, explain's format, and the
package's source invariants as walks of its syntax trees.

The package is imported from the repository root, which `just test` puts on
PYTHONPATH.
"""

import ast
import dataclasses
import re
import sys
from pathlib import Path, PurePosixPath

import pytest

import adjagent
from adjagent.cli import main
from adjagent.context import TIER_MAP_FLAG, Render, build_render, parse_tier_map
from adjagent.definition import Definition
from adjagent.definitions import definitions_of
from adjagent.errors import InputError
from adjagent.families.claude import FAMILY as CLAUDE_FAMILY
from adjagent.families.qwen3 import FAMILY as QWEN3_FAMILY
from adjagent.family import Family, Overlay
from adjagent.harness import Harness
from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.harnesses.opencode import HARNESS as OPENCODE
from adjagent.loading import load
from adjagent.render import agent_fields, definitions, keyed_by_path, render_definition
from adjagent.section import FamilyText, OwnText, Prose, Section
from adjagent.sections.liaison import Liaison
from adjagent.sections.mad import ConvergenceCriteria, Mode
from adjagent.vocabulary import ALL, Anchor, HarnessText, Kind, Tool

_ALL_INHERIT = dict.fromkeys(("highest", "high", "medium", "low", "lowest"), "inherit")
_PACKAGE = Path(adjagent.__file__).parent


@pytest.mark.parametrize(
    "spec, expected",
    [
        (
            "highest=a,high=b,medium=c,low=d,lowest=e",
            {"highest": "a", "high": "b", "medium": "c", "low": "d", "lowest": "e"},
        ),
        (
            "lowest=e,low=d,medium=c,high=b,highest=a",
            {"highest": "a", "high": "b", "medium": "c", "low": "d", "lowest": "e"},
        ),
        (
            "all=haiku,high=opus",
            {"highest": "haiku", "high": "opus", "medium": "haiku", "low": "haiku", "lowest": "haiku"},
        ),
        (
            "high=opus,all=haiku",
            {"highest": "haiku", "high": "opus", "medium": "haiku", "low": "haiku", "lowest": "haiku"},
        ),
    ],
)
def test_parse_tier_map_is_total_in_tier_order(spec: str, expected: dict[str, str]) -> None:
    parsed = parse_tier_map(spec, flag=TIER_MAP_FLAG)
    assert parsed == expected
    assert list(parsed) == ["highest", "high", "medium", "low", "lowest"]


@pytest.mark.parametrize(
    "spec, message",
    [
        ("high=opus", "names no value for highest, medium, low, lowest"),
        ("all=x,middle=y", "'middle=y' names no tier"),
        ("all=x,high=y,high=z", "duplicate key 'high'"),
        ("all=x,high", "'high' is not a tier=value pair"),
        ("all=x,high=a=b", "'high=a=b' is not a tier=value pair"),
        ("all=x,high=two words", "contains whitespace inside a tier or a value"),
    ],
)
def test_parse_tier_map_refusals(spec: str, message: str) -> None:
    with pytest.raises(InputError, match=re.escape(f"{TIER_MAP_FLAG}: ")) as caught:
        parse_tier_map(spec, flag=TIER_MAP_FLAG)
    assert message in str(caught.value)


def test_model_alias_wins_over_member() -> None:
    ctx = Render(
        harness=CLAUDE,
        family=CLAUDE_FAMILY,
        tier_map=dict(QWEN3_FAMILY.tiers),
        alias_map={"highest": "fable", "high": "opus", "medium": "sonnet", "low": "haiku", "lowest": "inherit"},
    )
    assert ctx.model("high") == "opus"
    assert ctx.model("lowest") == "inherit"


@pytest.mark.parametrize("harness, expected", [(CLAUDE, "inherit"), (OPENCODE, "")])
def test_model_inherit_renders_the_harness_text(harness: Harness, expected: str) -> None:
    ctx = Render(harness=harness, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    assert ctx.model("medium") == expected


def test_build_render_refuses_a_model_outside_the_harness_shape() -> None:
    with pytest.raises(InputError) as caught:
        build_render(harness="opencode", family="claude", tier_spec=None, alias_spec=None)
    message = str(caught.value)
    assert "model 'fable' at tier highest" in message
    assert "--family" in message


@pytest.mark.parametrize("family", ["nonesuch", "templates/family/qwen3.toml", "qwen3.toml", "gemma_4"])
def test_build_render_refuses_a_family_that_is_not_a_name(family: str) -> None:
    with pytest.raises(InputError, match=re.escape("claude, gemma-4, qwen3")):
        build_render(harness="claude", family=family, tier_spec=None, alias_spec=None)


@pytest.mark.parametrize("package, attribute", [("adjagent.harnesses", "HARNESS"), ("adjagent.families", "FAMILY")])
def test_each_instance_is_named_as_its_module_loads(package: str, attribute: str) -> None:
    loaded = load(package, attribute)
    assert loaded
    assert {key: instance.name for key, instance in loaded.items()} == {key: key for key in loaded}


def test_load_refuses_a_module_without_the_attribute() -> None:
    with pytest.raises(InputError, match="'adjagent.harnesses.claude' defines no FAMILY"):
        load("adjagent.harnesses", "FAMILY")


def _security_reviewer() -> Definition:
    return Definition(
        name="security-reviewer",
        description=(
            "Adversarial security review of code and designs. Identifies hazards, attack vectors, and the "
            "specific conditions that must hold to prevent exploitation. Does not prescribe design solutions — "
            "that is the architect's job. Review only, never modifies files."
        ),
        tools=(Tool.BASH, Tool.READ, Tool.GREP, Tool.GLOB, Tool.WRITE, Tool.EDIT, Tool.WEBSEARCH, Tool.WEBFETCH),
        tier="high",
        sections=(Prose("body"),),
        color="#DC2626",
    )


_SECURITY_REVIEWER_DESCRIPTION = (
    'description: "Adversarial security review of code and designs. Identifies hazards, attack vectors, and '
    "the specific conditions that must hold to prevent exploitation. Does not prescribe design solutions — "
    "that is the architect's job. Review only, never modifies files.\""
)


def test_claude_frontmatter_matches_the_pre_1_0_render() -> None:
    ctx = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    assert CLAUDE.frontmatter(agent_fields(_security_reviewer(), ctx)) == (
        "name: security-reviewer",
        _SECURITY_REVIEWER_DESCRIPTION,
        "model: opus",
        'color: "#DC2626"',
        "tools: Bash, Read, Grep, Glob, Write, Edit, WebSearch, WebFetch",
    )


def test_opencode_frontmatter_matches_the_pre_1_0_render() -> None:
    ctx = Render(harness=OPENCODE, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    assert OPENCODE.frontmatter(agent_fields(_security_reviewer(), ctx)) == (
        _SECURITY_REVIEWER_DESCRIPTION,
        'color: "#DC2626"',
        "permission:",
        "  read: allow",
        "  grep: allow",
        "  glob: allow",
        "  list: allow",
        "  edit: allow",
        "  bash: allow",
        "  webfetch: allow",
        "  websearch: allow",
        "  task: deny",
        "mode: subagent",
    )


# The first body line of the pre-1.0 render of agents/mad/participant-contract.md.
_CONTRACT_FIRST_LINE = (
    "You are an independent technical reviewer participating in a structured multi-model debate review "
    "process. The Referee has seated two or more participants for this run — each pinned to a different "
    "model, each working the same artifact independently. You will never see any other participant's full "
    "output, in any mode or any round; the structured alignment map produced by the Alignment Assessor is "
    "your only window onto their positions. You are not told how many other seats there are or which models "
    "fill them, and you do not need to know."
)
_CONTRACT_PATH = "agents/mad/participant-contract.md"

Discovered = tuple[tuple[str, Definition], ...]


@pytest.fixture(scope="module")
def discovered() -> Discovered:
    """Every definition the package discovers, with its module."""
    return definitions()


def _found(discovered: Discovered, path: str) -> tuple[str, Definition]:
    [found] = [(module, defn) for module, defn in discovered if defn.output_path == PurePosixPath(path)]
    return found


@pytest.mark.parametrize(
    "path, harness, after_banner",
    [
        (_CONTRACT_PATH, CLAUDE, ["---", ""]),
        (_CONTRACT_PATH, OPENCODE, ["mode: subagent", "disable: true", "---", ""]),
        ("commands/mad-review.md", CLAUDE, ["---", "@.claude/agents/mad-review-referee.md"]),
        ("commands/mad-review.md", OPENCODE, ["---", "@.opencode/agents/mad-review-referee.md"]),
    ],
)
def test_document_and_command_shapes_match_the_pre_1_0_render(
    discovered: Discovered, path: str, harness: Harness, after_banner: list[str]
) -> None:
    module, defn = _found(discovered, path)
    ctx = Render(harness=harness, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    lines = render_definition(defn, ctx, module=module).split("\n")
    assert lines[0] == "---"
    assert lines[1].startswith("# !GENERATED! from adjagent/definitions/")
    assert " seat=none member=none tier=" in lines[2]
    assert lines[3 : 3 + len(after_banner)] == after_banner


_HARNESS_RENDERS = [
    Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers)),
    Render(harness=OPENCODE, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT),
]


def _extracted(defn: Definition, ctx: Render, *, module: str) -> str:
    """What `sed '1,/^---$/d'` leaves of the rendered file: every line after the first `---` line past
    line 1, without leading or trailing blank lines."""
    lines = render_definition(defn, ctx, module=module).split("\n")
    return "\n".join(lines[lines.index("---", 1) + 1 :]).strip("\n")


@pytest.mark.parametrize("ctx", _HARNESS_RENDERS, ids=lambda ctx: ctx.harness.name)
def test_guest_extraction_leaves_exactly_the_body(discovered: Discovered, ctx: Render) -> None:
    extractable = [
        (module, defn)
        for module, defn in discovered
        if (defn.kind is Kind.AGENT and defn.folder == "") or defn.output_path == PurePosixPath(_CONTRACT_PATH)
    ]
    assert len(extractable) > 1
    for module, defn in extractable:
        seated = dataclasses.replace(ctx, seat=defn.tier)
        body = "\n\n".join(text for text in (section.render(seated) for section in defn.sections) if text)
        assert _extracted(defn, ctx, module=module) == body, defn.output_path
    module, contract = _found(discovered, _CONTRACT_PATH)
    assert _extracted(contract, ctx, module=module).split("\n", 1)[0] == _CONTRACT_FIRST_LINE


@pytest.mark.parametrize("ctx", _HARNESS_RENDERS, ids=lambda ctx: ctx.harness.name)
def test_every_participant_extracts_to_the_contract_document(discovered: Discovered, ctx: Render) -> None:
    module, contract = _found(discovered, _CONTRACT_PATH)
    expected = _extracted(contract, ctx, module=module)
    participants = [(module, defn) for module, defn in discovered if defn.name.startswith("mad-participant-")]
    assert expected and participants
    for module, defn in participants:
        assert _extracted(defn, ctx, module=module) == expected, defn.name


@pytest.mark.parametrize(
    "part, harness, expected",
    [
        (HarnessText.AGENTS_FILE, CLAUDE, "CLAUDE.md"),
        (HarnessText.AGENTS_FILE, OPENCODE, "AGENTS.md"),
        (HarnessText.PROJECT_HARNESS_DIR, CLAUDE, ".claude"),
        (HarnessText.PROJECT_HARNESS_DIR, OPENCODE, ".opencode"),
        (HarnessText.PROJECT_TEMP_DIR, CLAUDE, ".claude-temp"),
        (HarnessText.PROJECT_TEMP_DIR, OPENCODE, ".opencode-temp"),
        (HarnessText.USER_HARNESS_DIR, CLAUDE, "~/.claude"),
        (HarnessText.USER_HARNESS_DIR, OPENCODE, "~/.config/opencode"),
    ],
)
def test_prose_renders_a_harness_text_part(part: HarnessText, harness: Harness, expected: str) -> None:
    ctx = Render(harness=harness, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    assert Prose("see ", part, "/x").render(ctx) == f"see {expected}/x"


_TUNED = Family(
    "tuned",
    {"highest": "big", "high": "big", "medium": "mid", "low": "small", "lowest": "small"},
    overlays={Anchor.GAP_AVERSION: Overlay(text="family-wide", members={"mid": "for mid"})},
)


def _with_family_text(*, family: Family, tier: str, anchor: Anchor) -> str:
    defn = Definition(
        name="probe",
        description="a probe",
        tools=ALL,
        tier=tier,
        sections=(Prose("before"), FamilyText(anchor), Prose("after")),
    )
    ctx = Render(harness=CLAUDE, family=family, tier_map=dict(family.tiers))
    return render_definition(defn, ctx, module="adjagent.definitions.probe").split("---\n\n", 1)[1]


@pytest.mark.parametrize(
    "family, tier, anchor, body",
    [
        (_TUNED, "medium", Anchor.GAP_AVERSION, "before\n\nfor mid\n\nafter\n"),
        (_TUNED, "high", Anchor.GAP_AVERSION, "before\n\nfamily-wide\n\nafter\n"),
        (_TUNED, "medium", Anchor.ASK_VS_STIPULATE, "before\n\nafter\n"),
        (CLAUDE_FAMILY, "medium", Anchor.GAP_AVERSION, "before\n\nafter\n"),
    ],
)
def test_family_text_renders_the_seats_overlay_or_nothing(family: Family, tier: str, anchor: Anchor, body: str) -> None:
    assert _with_family_text(family=family, tier=tier, anchor=anchor) == body


def test_stock_excludes_the_overridden_tier() -> None:
    ctx = Render(harness=CLAUDE, family=_TUNED, tier_map=dict(_TUNED.tiers))
    assert ctx.stock == ("highest", "high", "low", "lowest")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"tools": ()}, "tools must be ALL"),
        ({"sections": ()}, "sections must be"),
        ({"sections": (Prose("ok"), "a bare string")}, "section 1 is a str"),
        ({"description": 'holds a "quote"'}, "description must be"),
        ({"tier": None}, "an agent requires tier"),
        ({"kind": Kind.DOCUMENT}, "a document takes no description, tools, tier"),
        (
            {"kind": Kind.COMMAND, "description": None, "tools": None, "tier": None, "color": "#000000"},
            "takes no color",
        ),
        ({"folder": "mad/Design"}, "folder 'mad/Design'"),
    ],
)
def test_definition_refusals(changes: dict, message: str) -> None:
    fields = {"name": "probe", "description": "a probe", "tools": ALL, "tier": "high", "sections": (Prose("ok"),)}
    with pytest.raises(InputError, match="definition 'probe'") as caught:
        Definition(**{**fields, **changes})
    assert message in str(caught.value)


def test_output_paths_not_names_are_unique() -> None:
    command = Definition(name="probe", kind=Kind.COMMAND, sections=(Prose("x"),))
    document = Definition(name="probe", kind=Kind.DOCUMENT, folder="nested", sections=(Prose("x"),))
    paths = [defn.output_path for _, defn in keyed_by_path([("m.a", (command,)), ("m.b", (document,))])]
    assert paths == [PurePosixPath("agents/nested/probe.md"), PurePosixPath("commands/probe.md")]
    with pytest.raises(InputError, match=re.escape("'commands/probe.md' is produced by both m.a and m.b")):
        keyed_by_path([("m.a", (command,)), ("m.b", (command,))])


@pytest.mark.parametrize("parts", [(), ("",), ("edge newline\n",), ("\nedge newline",), (b"bytes",)])
def test_prose_refuses_empty_or_edge_newline_text(parts: tuple) -> None:
    with pytest.raises(InputError, match="prose section"):
        Prose(*parts)


_FIX_THE_FIELD = "This check enforces the rule; fix the field it names, not the check."


def test_own_text_has_only_lead_and_tail() -> None:
    with pytest.raises(AttributeError, match="only lead and tail, not 'closing'") as caught:
        OwnText.closing
    assert str(caught.value).endswith(_FIX_THE_FIELD)


@pytest.mark.parametrize(
    "namespace, rule",
    [
        ({"__annotations__": {"tail": str | None}, "tail": OwnText.lead}, "field 'tail' is bound to OwnText.lead"),
        ({"__annotations__": {"lead": str}}, "field 'lead' is named for own text but not declared"),
        ({"__annotations__": {"variant": str}}, "no field is named 'variant'"),
        ({"__annotations__": {"words": Mode}, "words": Mode.field}, "takes Mode, which a section binds only as"),
    ],
)
def test_a_section_field_breaking_the_naming_rules_is_refused_at_class_definition(namespace: dict, rule: str) -> None:
    with pytest.raises(TypeError) as caught:
        type("Probe", (Section,), namespace)
    assert rule in str(caught.value)
    assert str(caught.value).endswith(_FIX_THE_FIELD)


def test_convergence_criteria_refuses_an_item_opening_with_another_letter() -> None:
    fields = {"converged": "- **(a)**", "result": "r", "paths": "p", "divergence": "d"}
    ConvergenceCriteria(**fields, under_determined=("- **(c) one", "- **(d) two"))
    with pytest.raises(InputError, match=re.escape("item 1 must open '- **(d)'")):
        ConvergenceCriteria(**fields, under_determined=("- **(c) one", "- **(e) two"))


def test_discovery_refuses_a_module_without_definitions() -> None:
    with pytest.raises(InputError, match="'adjagent.definitions.probe' defines no DEFINITIONS"):
        definitions_of("adjagent.definitions.probe", None)


def test_explain_heads_each_section_and_each_field_supplied_paragraph(capsys: pytest.CaptureFixture[str]) -> None:
    main(["explain", "python-coder"])
    lines = capsys.readouterr().out.splitlines()
    data_formats = lines.index("[DataFormats libraries='`tomllib` (stdlib, 3.11+) for reading TOML.']")
    assert lines[data_formats + 1] == "  ‹libraries›"
    assert lines[data_formats + 2].startswith("**Data formats**: the right tool for the job decides.")
    principles = lines.index("[CorePrinciples baseline='PEP 8 is the baseline that applies when the project states…]")
    assert lines[principles + 1] == "## Core Principles"
    assert lines.index("  ‹baseline›") > principles
    parallel = lines.index("[ParallelExecution]")
    assert lines[parallel + 1] == "## Parallel Execution"


# Source invariants, over every module of the package.


def _modules(*subpackages: str) -> list[tuple[str, ast.Module]]:
    roots = [_PACKAGE.joinpath(*sub.split("/")) for sub in subpackages] or [_PACKAGE]
    files = sorted({path for root in roots for path in root.rglob("*.py")})
    return [
        (path.relative_to(_PACKAGE.parent).as_posix(), ast.parse(path.read_text(encoding="utf-8"))) for path in files
    ]


def _imported(tree: ast.Module) -> list[str]:
    """Every module an import statement names, a relative import as under adjagent."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(f"adjagent.{node.module}" if node.level else node.module)
    return names


@pytest.mark.parametrize("value_type, module", [(Mode, "sections/mad.py"), (Liaison, "sections/liaison.py")])
def test_every_value_type_term_is_read_by_two_or_more_sections(value_type: type, module: str) -> None:
    readers: dict[str, set[str]] = {spec.name: set() for spec in dataclasses.fields(value_type)}
    tree = ast.parse(_PACKAGE.joinpath(module).read_text(encoding="utf-8"))
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        for node in ast.walk(cls):
            owner = node.value if isinstance(node, ast.Attribute) else None
            if (
                isinstance(owner, ast.Attribute)
                and owner.attr == "mode"
                and isinstance(owner.value, ast.Name)
                and owner.value.id == "self"
                and node.attr in readers
            ):
                readers[node.attr].add(cls.name)
    assert {term: sorted(classes) for term, classes in readers.items() if len(classes) < 2} == {}


def test_no_composed_text_is_rescanned() -> None:
    offenders = []
    for path, tree in _modules():
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            owner = node.func.value.id if isinstance(node.func.value, ast.Name) else None
            attr = node.func.attr
            if (
                (attr == "replace" and owner != "dataclasses")
                or attr in ("format", "format_map")
                or (owner == "re" and attr in ("sub", "subn"))
            ):
                offenders.append(f"{path}:{node.lineno} .{attr}(")
    assert offenders == []


def test_sections_and_definitions_reach_nothing_outside_their_arguments() -> None:
    banned = {"os", "sys", "subprocess", "time", "random"}
    offenders = []
    for path, tree in _modules("sections", "definitions"):
        offenders += [f"{path} imports {name}" for name in _imported(tree) if name.split(".")[0] in banned]
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                if called == "open":
                    offenders.append(f"{path}:{node.lineno} calls open")
    assert offenders == []


def test_every_import_is_at_module_level() -> None:
    offenders = [
        f"{path}:{node.lineno}"
        for path, tree in _modules()
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in tree.body
    ]
    assert offenders == []


def test_every_import_is_stdlib_or_the_package() -> None:
    offenders = [
        f"{path} imports {name}"
        for path, tree in _modules()
        for name in _imported(tree)
        if name.split(".")[0] not in sys.stdlib_module_names and name.split(".")[0] != "adjagent"
    ]
    assert offenders == []


def test_the_import_graph_is_acyclic() -> None:
    def module_name(path: str) -> str:
        parts = PurePosixPath(path).with_suffix("").parts
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)

    graph = {
        module_name(path): {name for name in _imported(tree) if name.startswith("adjagent")}
        for path, tree in _modules()
    }
    done: set[str] = set()

    def visit(module: str, trail: tuple[str, ...]) -> None:
        assert module not in trail, f"import cycle: {' -> '.join((*trail, module))}"
        if module not in done:
            for target in sorted(graph.get(module, ())):
                visit(target, (*trail, module))
            done.add(module)

    for module in sorted(graph):
        visit(module, ())
