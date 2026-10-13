"""The adjagent package's own logic, each case checked against values the
renderer did not compute: the two map flags' grammar, the rendered model text,
the CLI's Render refusals, the frontmatter of each kind against literal lines of
the pre-1.0 render, every rendered definition extracting frontmatter-free and every
participant extracting to the contract, placeholder filling and refusal, overlay
resolution and stock, Definition refusals, the loader's refusal, the line cap, and
the package's source invariants as walks of its syntax trees.

The package is imported from the repository root, which `just test` puts on
PYTHONPATH.
"""

import ast
import inspect
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path, PurePosixPath

import pytest

import adjagent
import adjagent.clauses
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
from adjagent.render import (
    agent_fields,
    definitions,
    filled_body,
    keyed_by_path,
    render_all,
    render_definition,
    write_renders,
)
from adjagent.vocabulary import ALL, Anchor, HarnessText, Kind, Tool, hole
from devtools import render_diff
from tests._structure import (
    ARGUMENT_RULE,
    ASSIGNMENT_RULE,
    BODY_RULE,
    CALL_RULE,
    DEFINITION_TOP_RULE,
    FUNCTION_RULE,
    IMPORT_RULE,
    TEXT_TOP_RULE,
    check_source,
    check_structure,
)

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
        body="body",
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


_PYTHON_CODER_DESCRIPTION = (
    'description: "Python implementation specialist. Writes idiomatic, readable Python — explicit over implicit, '
    "stdlib-first, no over-engineering. Covers type hints, async, testing, packaging, virtual environments, and "
    'common ecosystem tooling. Parallel-execution safe. Prefer over generalist-coder for any Python file '
    'modification or Python project task."'
)


@pytest.mark.parametrize(
    "ctx, expected",
    [
        (
            Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers)),
            ("name: python-coder", _PYTHON_CODER_DESCRIPTION, "model: opus", 'color: "#3776AB"'),
        ),
        (
            Render(harness=OPENCODE, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT),
            (_PYTHON_CODER_DESCRIPTION, 'color: "#3776AB"', "mode: subagent"),
        ),
    ],
    ids=["claude", "opencode"],
)
def test_an_unrestricted_agent_frontmatter_matches_the_pre_1_0_render(ctx: Render, expected: tuple[str, ...]) -> None:
    [defn] = [defn for _, defn in definitions() if defn.name == "python-coder"]
    assert ctx.harness.frontmatter(agent_fields(defn, ctx)) == expected


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


@pytest.mark.skipif(shutil.which("sed") is None, reason="extraction needs sed")
@pytest.mark.parametrize("ctx", _HARNESS_RENDERS, ids=lambda ctx: ctx.harness.name)
def test_every_rendered_definition_extracts_frontmatter_free(tmp_path: Path, ctx: Render) -> None:
    """The definitions' own extraction command, run over every rendered file under agents/: it exits
    0, leaves no banner, and the frontmatter block plus what it printed is the file byte for byte."""
    write_renders(tmp_path, render_all(ctx))
    rendered = sorted((tmp_path / "agents").rglob("*.md"))
    assert len(rendered) > 20
    for path in rendered:
        done = subprocess.run(["sed", "1,/^---$/d", str(path)], capture_output=True, text=True, check=False)
        assert done.returncode == 0, done.stderr
        assert "!GENERATED!" not in done.stdout, path
        text = path.read_text(encoding="utf-8")
        between = text.removeprefix("---\n").split("\n---\n", 1)[0]
        assert text == "---\n" + between + "\n---\n" + done.stdout, path
        if path == tmp_path / _CONTRACT_PATH:
            assert done.stdout.lstrip("\n").split("\n", 1)[0] == _CONTRACT_FIRST_LINE


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
def test_a_harness_text_placeholder_fills_with_the_harness_string(
    part: HarnessText, harness: Harness, expected: str
) -> None:
    defn = Definition(name="probe", kind=Kind.COMMAND, body=f"see {hole(part)}/x")
    ctx = Render(harness=harness, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    assert filled_body(defn, ctx) == f"see {expected}/x"


@pytest.mark.parametrize("placeholder", ["@!hrn.agents-file!@", "@!hrn-nonesuch!@", "@!fam-gap!@", "@!gap-aversion!@"])
def test_an_unknown_placeholder_is_refused_at_render(placeholder: str) -> None:
    defn = Definition(name="probe", kind=Kind.COMMAND, body=f"before {placeholder} after")
    ctx = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    with pytest.raises(InputError, match=re.escape(f"definition 'probe': unknown placeholder {placeholder}")):
        filled_body(defn, ctx)


@pytest.mark.parametrize("part", list(HarnessText), ids=lambda part: part.name)
def test_the_text_module_spells_each_harness_placeholder_as_the_renderer_fills_it(part: HarnessText) -> None:
    assert getattr(adjagent.clauses, part.name) == hole(part)


_TUNED = Family(
    "tuned",
    {"highest": "big", "high": "big", "medium": "mid", "low": "small", "lowest": "small"},
    overlays={Anchor.GAP_AVERSION: Overlay(text="family-wide", members={"mid": "for mid"})},
)


def _with_family_text(*, family: Family, tier: str, body: str) -> str:
    defn = Definition(name="probe", description="a probe", tools=ALL, tier=tier, body=body)
    ctx = Render(harness=CLAUDE, family=family, tier_map=dict(family.tiers))
    return render_definition(defn, ctx, module="adjagent.definitions.probe").split("---\n\n", 1)[1]


_GAP = hole(Anchor.GAP_AVERSION)
_ASK = hole(Anchor.ASK_VS_STIPULATE)


@pytest.mark.parametrize(
    "family, tier, body, rendered",
    [
        (_TUNED, "medium", f"before\n\n{_GAP}\n\nafter", "before\n\nfor mid\n\nafter\n"),
        (_TUNED, "high", f"before\n\n{_GAP}\n\nafter", "before\n\nfamily-wide\n\nafter\n"),
        (_TUNED, "medium", f"before\n\n{_ASK}\n\nafter", "before\n\nafter\n"),
        (CLAUDE_FAMILY, "medium", f"before\n\n{_GAP}\n\nafter", "before\n\nafter\n"),
        (CLAUDE_FAMILY, "medium", f"{_GAP}\n\nafter", "after\n"),
        (CLAUDE_FAMILY, "medium", f"before\n\n{_GAP}", "before\n"),
        (CLAUDE_FAMILY, "medium", f"before\n\n{_GAP}\n\n{_ASK}\n\nafter", "before\n\nafter\n"),
        (_TUNED, "medium", f"before\n\n{_GAP}\n\n{_ASK}\n\nafter", "before\n\nfor mid\n\nafter\n"),
    ],
)
def test_family_text_renders_the_seats_overlay_or_leaves_no_empty_paragraph(
    family: Family, tier: str, body: str, rendered: str
) -> None:
    assert _with_family_text(family=family, tier=tier, body=body) == rendered


def test_stock_excludes_the_overridden_tier() -> None:
    ctx = Render(harness=CLAUDE, family=_TUNED, tier_map=dict(_TUNED.tiers))
    assert ctx.stock == ("highest", "high", "low", "lowest")


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"tools": ()}, "tools must be ALL"),
        ({"body": ""}, "body must be"),
        ({"body": "edge newline\n"}, "body must be"),
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
    fields = {"name": "probe", "description": "a probe", "tools": ALL, "tier": "high", "body": "ok"}
    with pytest.raises(InputError, match="definition 'probe'") as caught:
        Definition(**{**fields, **changes})
    assert message in str(caught.value)


def test_output_paths_not_names_are_unique() -> None:
    command = Definition(name="probe", kind=Kind.COMMAND, body="x")
    document = Definition(name="probe", kind=Kind.DOCUMENT, folder="nested", body="x")
    paths = [defn.output_path for _, defn in keyed_by_path([("m.a", (command,)), ("m.b", (document,))])]
    assert paths == [PurePosixPath("agents/nested/probe.md"), PurePosixPath("commands/probe.md")]
    with pytest.raises(InputError, match=re.escape("'commands/probe.md' is produced by both m.a and m.b")):
        keyed_by_path([("m.a", (command,)), ("m.b", (command,))])


def test_discovery_refuses_a_module_without_definitions() -> None:
    with pytest.raises(InputError, match="'adjagent.definitions.probe' defines no DEFINITIONS"):
        definitions_of("adjagent.definitions.probe", None)


# Source invariants, over every module of the package.


def _modules(*subpaths: str) -> list[tuple[str, ast.Module]]:
    """Every module under each subpath of the package (a directory or one file), or the whole package."""
    roots = [_PACKAGE.joinpath(*sub.split("/")) for sub in subpaths] or [_PACKAGE]
    files = sorted({path for root in roots for path in ([root] if root.is_file() else root.rglob("*.py"))})
    return [
        (path.relative_to(_PACKAGE.parent).as_posix(), ast.parse(path.read_text(encoding="utf-8"))) for path in files
    ]


def _imported(tree: ast.Module) -> list[str]:
    """Every module an import statement names, a relative import as under adjagent, and each name a
    from-import takes as a possible submodule (`from adjagent import clauses` names `adjagent.clauses`)."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = f"adjagent.{node.module}" if node.level else node.module
            names += [module, *(f"{module}.{alias.name}" for alias in node.names)]
    return names


def test_no_composed_text_is_rescanned() -> None:
    """No text is re-formatted or re-substituted, and the one pattern substitution is the body fill.
    A definition module's `.format` is outside this walk: check_structure admits it only on one of
    that module's string literals, which holds no composed text."""
    offenders = []
    substitutions = []
    for path, tree in _modules():
        if path.startswith("adjagent/definitions/"):
            continue
        for top in tree.body:
            scope = getattr(top, "name", "<module>")
            for node in ast.walk(top):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                owner = node.func.value.id if isinstance(node.func.value, ast.Name) else None
                attr = node.func.attr
                if (attr == "replace" and owner != "dataclasses") or attr in ("format", "format_map"):
                    offenders.append(f"{path}:{node.lineno} .{attr}(")
                elif attr in ("sub", "subn"):
                    substitutions.append(f"{path}:{scope} .{attr}(")
    assert offenders == []
    assert substitutions == ["adjagent/render.py:filled_body .sub("]


def test_definitions_and_text_reach_nothing_outside_their_arguments() -> None:
    banned = {"os", "sys", "subprocess", "time", "random"}
    offenders = []
    for path, tree in _modules("definitions", "clauses.py"):
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


_DEFINITION_PATHS = sorted(path for path in (_PACKAGE / "definitions").glob("*.py") if not path.stem.startswith("_"))


def test_the_definition_modules_and_the_text_module_hold_their_structure() -> None:
    violations = check_structure([*_DEFINITION_PATHS, _PACKAGE / "clauses.py"])
    assert violations == [], "\n".join(violations)


_DEFINITION_HEAD = "from adjagent import clauses\nfrom adjagent.definition import Definition\n"


def _definitions_of_body(body: str, *, head: str = "") -> str:
    """A definition-module source whose one Definition has `body` as its body= source text."""
    return f'{_DEFINITION_HEAD}{head}DEFINITIONS = (Definition(name="p", kind=Kind.COMMAND, body={body}),)\n'


@pytest.mark.parametrize(
    "source, line, rule",
    [
        (f'{_DEFINITION_HEAD}_N = len("x")\n', 3, ASSIGNMENT_RULE),
        (f'{_DEFINITION_HEAD}_D = {{"a": "b"}}\n', 3, ASSIGNMENT_RULE),
        (f'{_DEFINITION_HEAD}_T = ("a", _X)\n', 3, ASSIGNMENT_RULE),
        (f'{_DEFINITION_HEAD}_C = "".join(x for x in "ab")\n', 3, ASSIGNMENT_RULE),
        (f'{_DEFINITION_HEAD}_F = f"{{clauses.DISSENT}}"\n', 3, ASSIGNMENT_RULE),
        (_definitions_of_body('f"{clauses.dissent(x=clauses.other())}"'), 3, ARGUMENT_RULE),
        (_definitions_of_body('f"{_S.format(x=_V)}"', head='_S = "{x}"\n_V = f"{_S}"\n'), 5, ""),
        (_definitions_of_body("f\"{_F.format(x='a')}\"", head='_A = "a"\n_F = f"{_A} {{x}}"\n'), 5, CALL_RULE),
        (_definitions_of_body('f"{len(_S)}"', head='_S = "s"\n'), 4, CALL_RULE),
        (_definitions_of_body('f"{_S.upper()}"', head='_S = "s"\n'), 4, CALL_RULE),
        (_definitions_of_body('f"{clauses.x(**_K)}"'), 3, ARGUMENT_RULE),
        (_definitions_of_body('f"{_S if _S else _S}"', head='_S = "s"\n'), 4, BODY_RULE),
        (
            f'{_DEFINITION_HEAD}DEFINITIONS = (Definition(name="p", description=clauses.f(), body="b"),)\n',
            3,
            CALL_RULE,
        ),
        (f"{_DEFINITION_HEAD}def helper():\n    pass\n", 3, DEFINITION_TOP_RULE),
        (f"{_DEFINITION_HEAD}DEFINITIONS = (_ONE,)\n", 3, DEFINITION_TOP_RULE),
        ("from adjagent.clauses import X\n", 1, IMPORT_RULE),
        ("from adjagent import clauses as c\n", 1, IMPORT_RULE),
        ("import adjagent.clauses\n", 1, IMPORT_RULE),
    ],
)
def test_check_structure_refuses_a_definition_module_off_its_rules(source: str, line: int, rule: str) -> None:
    expected = [f"m.py:{line}: {rule}"] if rule else []
    assert check_source(source, where="m.py", text_module=False) == expected


@pytest.mark.parametrize(
    "source, rule",
    [
        ('_X = "a"\nY = f"{_X}"\ndef f(*, a, b="x", c=_X) -> str:\n    """doc"""\n    return f"{a}{b}{c}{Y}"\n', ""),
        ("from adjagent.vocabulary import hole\n", TEXT_TOP_RULE),
        ("class C:\n    pass\n", TEXT_TOP_RULE),
        ('X = hole("a")\n', ASSIGNMENT_RULE),
        ('X = f"{g()}"\n', ASSIGNMENT_RULE),
        ('X = Y\nY = "y"\n', ASSIGNMENT_RULE),
        ('def f(a):\n    return f"{a}"\n', FUNCTION_RULE),
        ('def f(*, a, b, c, d):\n    return f"{a}{b}{c}{d}"\n', FUNCTION_RULE),
        ('def f(*args):\n    return "x"\n', FUNCTION_RULE),
        ("def f(*, a):\n    return g(a=a)\n", FUNCTION_RULE),
        ('def f(*, a):\n    return f"{g(a=a)}"\n', FUNCTION_RULE),
        ('def f(*, a):\n    b = a\n    return f"{b}"\n', FUNCTION_RULE),
        ('def f(*, a=g()):\n    return f"{a}"\n', FUNCTION_RULE),
        ('def f(*, a):\n    return f"{a!r}"\n', FUNCTION_RULE),
    ],
)
def test_check_structure_refuses_a_text_module_off_its_rules(source: str, rule: str) -> None:
    expected = [f"clauses.py:1: {rule}"] if rule else []
    assert check_source(source, where="clauses.py", text_module=True) == expected


# Shared text has one source: a paragraph two outputs carry is not written out in either.

_CLAUDE_RENDER = Render(harness=CLAUDE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
RENDERED_DEFINITION_LINE_CAP = 500  # a runaway guard, not a target; the 100-column wrap makes lines a fair size


def test_no_rendered_agent_definition_exceeds_the_line_cap(discovered: Discovered) -> None:
    over = [
        f"{defn.output_path} renders at {count} lines after the banner; the cap is {RENDERED_DEFINITION_LINE_CAP}"
        for _, defn in discovered
        if defn.output_path.parts[0] == "agents"
        and (count := len(filled_body(defn, _CLAUDE_RENDER).splitlines())) > RENDERED_DEFINITION_LINE_CAP
    ]
    assert over == []


def _credited_text() -> types.SimpleNamespace:
    """The clauses module with every constant and function standing as a sentinel naming it; a
    constant that is a bare placeholder keeps its value, so prose around it is not credited to it."""
    standing: dict[str, object] = {}
    for name, value in vars(adjagent.clauses).items():
        if isinstance(value, str) and not re.fullmatch(r"@![a-z0-9-]+!@", value):
            standing[name] = f"<<adjagent.clauses.{name}>>"
        elif isinstance(value, str):
            standing[name] = value
        elif inspect.isfunction(value) and value.__module__ == adjagent.clauses.__name__:
            standing[name] = lambda _sentinel=f"<<adjagent.clauses.{name}()>>", **_: _sentinel
    return types.SimpleNamespace(**standing)


def _source_definitions(source: str, *, module: str, credited: bool) -> tuple[Definition, ...]:
    """DEFINITIONS as the module's source builds them; credited, with each of the module's string
    constants and everything it reaches through `clauses` standing as a sentinel naming it."""
    tree = ast.parse(source)
    namespace: dict[str, object] = {"__name__": module}
    if credited:
        namespace["clauses"] = _credited_text()
        body = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and any(alias.name == "clauses" for alias in node.names):
                continue
            target = node.targets[0].id if isinstance(node, ast.Assign) else ""
            if target and target != "DEFINITIONS":
                node = ast.copy_location(ast.Assign(targets=node.targets, value=ast.Constant(f"<<{target}>>")), node)
            body.append(node)
        tree.body = body
        ast.fix_missing_locations(tree)
    exec(compile(tree, module, "exec"), namespace)
    return namespace["DEFINITIONS"]


def _prose_units(body: str) -> set[bytes]:
    """The paragraphs and list items of a body, each as devtools.render_diff collapses it; a heading,
    a table row and a line of a fenced block are not prose."""
    units: set[bytes] = set()
    fence: bytes | None = None
    for line in render_diff.collapsed(body.encode("utf-8")).split(b"\n"):
        if fence is not None:
            closing = render_diff.FENCE_CLOSE.fullmatch(line)
            if closing and closing[1][:1] == fence[:1] and len(closing[1]) >= len(fence):
                fence = None
        elif opening := render_diff.FENCE_OPEN.fullmatch(line):
            fence = opening[1] or opening[2]
        elif line.strip() and not render_diff.HEADING.match(line) and not line.lstrip().startswith(b"|"):
            units.add(line)
    return units


def _uncredited_shared_paragraphs(sources: dict[str, str]) -> list[str]:
    """Every prose unit two or more outputs write out rather than take from a constant, a slot constant
    or a text function: the unit survives each one's credited render unchanged."""
    written: dict[bytes, list[str]] = {}
    for module, source in sources.items():
        rendered = _source_definitions(source, module=module, credited=False)
        credited = _source_definitions(source, module=module, credited=True)
        for defn, sentinel in zip(rendered, credited, strict=True):
            literal = _prose_units(filled_body(defn, _CLAUDE_RENDER)) & _prose_units(
                filled_body(sentinel, _CLAUDE_RENDER)
            )
            label = defn.name if defn.kind is Kind.AGENTS_FILE else str(defn.output_path)
            for unit in literal:
                written.setdefault(unit, []).append(label)
    return [
        f"written out in {', '.join(written[unit])}: {unit.decode()[:120]}"
        for unit in sorted(written)
        if len(written[unit]) > 1
    ]


def test_a_paragraph_two_outputs_carry_has_one_source() -> None:
    sources = {f"adjagent.definitions.{path.stem}": path.read_text(encoding="utf-8") for path in _DEFINITION_PATHS}
    found = _uncredited_shared_paragraphs(sources)
    assert found == [], "\n".join(found)


_FIXTURE_HEAD = (
    "from adjagent import clauses\nfrom adjagent.definition import Definition\nfrom adjagent.vocabulary import Kind\n"
)


def _fixture_module(*bodies: tuple[str, str], head: str = "") -> str:
    """A definition-module source of one command per (name, body source text)."""
    entries = "".join(f'Definition(name="{name}", kind=Kind.COMMAND, body={body}),' for name, body in bodies)
    return f"{_FIXTURE_HEAD}{head}DEFINITIONS = ({entries})\n"


def test_a_paragraph_written_out_in_two_outputs_is_found_and_a_constant_is_not() -> None:
    sources = {
        "fixture.a": _fixture_module(("a", 'f"Own a.\\n\\nWritten out twice.\\n\\n{clauses.DISSENT}"')),
        "fixture.b": _fixture_module(("b", 'f"Written out twice.\\n\\n{clauses.DISSENT}\\n\\nOwn b."')),
        "fixture.group": _fixture_module(
            ("c", "f\"{_SHARED}\\n\\n{_SLOT.format(word='one')}\""),
            ("d", "f\"{_SLOT.format(word='one')}\\n\\n{_SHARED}\""),
            ("e", '"Written out in one module twice."'),
            ("f", '"Written out in one module twice."'),
            head='_SHARED = "Shared through a constant."\n_SLOT = "A slot holding {word}."\n',
        ),
    }
    assert _uncredited_shared_paragraphs(sources) == [
        "written out in commands/e.md, commands/f.md: Written out in one module twice.",
        "written out in commands/a.md, commands/b.md: Written out twice.",
    ]


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
