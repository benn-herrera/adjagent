"""The devpro package's own logic, each case checked against values the
renderer did not compute: the two map flags' grammar, the rendered model text,
the CLI's Render refusals, the frontmatter of each kind — an agent's and a
skill's against literal lines of the pre-1.0 render, a command's and a
document's as bare fixtures pinned to their render's shape — every rendered
definition extracting frontmatter-free, placeholder filling and refusal, overlay resolution
and stock, Definition refusals, the loader's refusal, the description's one line
and balanced code spans, the line cap, and the package's source invariants as
walks of its syntax trees.

The package is imported from the repository root, which `just test` puts on
PYTHONPATH.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
import inspect
import json
import re
import shutil
import subprocess
import sysconfig
import types
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

import devpro
import devpro.clauses
from devpro.agents_file import is_marker_line
from devpro.context import TIER_MAP_FLAG, Render, build_render, harnesses, parse_tier_map
from devpro.definition import Definition, SkillFile
from devpro.definitions import definitions_of, discover
from devpro.errors import InputError
from devpro.families.claude import FAMILY as CLAUDE_FAMILY
from devpro.families.qwen3 import FAMILY as QWEN3_FAMILY
from devpro.family import Family, Overlay
from devpro.harness import AgentFields, FrontmatterForm, Harness, HarnessFile, ShippedDefinition
from devpro.harnesses.claude import HARNESS as CLAUDE
from devpro.harnesses.mage import HARNESS as MAGE
from devpro.harnesses.opencode import HARNESS as OPENCODE
from devpro.loading import load
from devpro.plugin import Plugin
from devpro.plugins.devpro import PLUGIN as DEVPRO
from devpro.plugins.kbase import PLUGIN as KBASE
from devpro.render import (
    agent_fields,
    definitions,
    filled_body,
    filled_text,
    keyed_by_path,
    render_agents_file,
    render_all,
    render_definition,
    render_skill_file,
    write_renders,
)
from devpro.vocabulary import (
    ALL,
    TIERS,
    AgentsFileText,
    Anchor,
    HarnessText,
    Kind,
    OptionalHarnessText,
    PluginText,
    Tool,
    TuningText,
    hole,
    optional_reference,
    reference,
)
from devtools import render_diff
from tests._structure import (
    ARGUMENT_RULE,
    ASSIGNMENT_RULE,
    BODY_RULE,
    CALL_RULE,
    DEFINITION_CALL_RULE,
    DEFINITION_TOP_RULE,
    FILES_RULE,
    FUNCTION_RULE,
    IMPORT_RULE,
    TEXT_TOP_RULE,
    ClauseRoot,
    body_roots,
    carried_clauses,
    check_source,
    check_structure,
    clause_graph,
    kbase_skill_output_paths,
    repeated_clause_reaches,
)

_ALL_INHERIT = dict.fromkeys(("highest", "high", "medium", "low", "lowest"), "inherit")
_PACKAGE = Path(devpro.__file__).parent


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
        plugin=DEVPRO,
        family=CLAUDE_FAMILY,
        tier_map=dict(QWEN3_FAMILY.tiers),
        alias_map={"highest": "fable", "high": "opus", "medium": "sonnet", "low": "haiku", "lowest": "inherit"},
    )
    assert ctx.model("high") == "opus"
    assert ctx.model("lowest") == "inherit"


@pytest.mark.parametrize(
    "harness, text, expected",
    [(CLAUDE, "inherit", "inherit"), (OPENCODE, "inherit", ""), (OPENCODE, "default", "")],
)
def test_model_inherit_and_its_synonyms_render_the_harness_text(harness: Harness, text: str, expected: str) -> None:
    ctx = Render(harness=harness, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict.fromkeys(_ALL_INHERIT, text))
    assert ctx.model("medium") == expected


def test_opencode_reads_a_bare_tier_spec_as_the_whole_map() -> None:
    ctx = build_render(plugin="devpro", harness="opencode", family="claude", tier_spec="default", alias_spec=None)
    assert dict(ctx.tier_map) == dict.fromkeys(TIERS, "default")
    assert ctx.model("medium") == ""


def test_opencode_with_no_tier_spec_uses_its_default() -> None:
    ctx = build_render(plugin="devpro", harness="opencode", family="claude", tier_spec=None, alias_spec=None)
    assert dict(ctx.tier_map) == dict.fromkeys(TIERS, "default")
    assert ctx.model("medium") == ""


@pytest.mark.parametrize(
    "harness, spec, message",
    [
        ("claude", "default", "'default' is not a tier=value pair"),
        ("opencode", "default,high=omlx/X", "'default' is not a tier=value pair"),
        ("opencode", "", "'' is not a tier=value pair"),
    ],
)
def test_a_tier_spec_no_harness_reads_bare_is_refused(harness: str, spec: str, message: str) -> None:
    with pytest.raises(InputError) as caught:
        build_render(plugin="devpro", harness=harness, family="claude", tier_spec=spec, alias_spec=None)
    assert message in str(caught.value)


def test_build_render_refuses_a_model_outside_the_harness_shape() -> None:
    with pytest.raises(InputError) as caught:
        build_render(plugin="devpro", harness="claude", family="gemma-4", tier_spec=None, alias_spec=None)
    message = str(caught.value)
    assert "model 'gemma-4-31B-it' at tier highest" in message
    assert "--family" in message


@pytest.mark.parametrize("family", ["nonesuch", "templates/family/qwen3.toml", "qwen3.toml", "gemma_4"])
def test_build_render_refuses_a_family_that_is_not_a_name(family: str) -> None:
    with pytest.raises(InputError, match=re.escape("claude, gemma-4, qwen3")):
        build_render(plugin="devpro", harness="claude", family=family, tier_spec=None, alias_spec=None)


@pytest.mark.parametrize(
    "package, attribute",
    [("devpro.harnesses", "HARNESS"), ("devpro.families", "FAMILY"), ("devpro.plugins", "PLUGIN")],
)
def test_each_instance_is_named_as_its_module_loads(package: str, attribute: str) -> None:
    loaded = load(package, attribute)
    assert loaded
    assert {key: instance.name for key, instance in loaded.items()} == {key: key for key in loaded}


def test_load_refuses_a_module_without_the_attribute() -> None:
    with pytest.raises(InputError, match="'devpro.harnesses.claude' defines no FAMILY"):
        load("devpro.harnesses", "FAMILY")


def _security_reviewer() -> Definition:
    return Definition(
        name="security-reviewer",
        kind=Kind.AGENT,
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


def _claude_frontmatter(fields: AgentFields) -> tuple[str, ...]:
    form = CLAUDE.definition_form
    assert isinstance(form, FrontmatterForm)
    return form.agent(fields)


def test_claude_frontmatter_matches_the_pre_1_0_render() -> None:
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    assert _claude_frontmatter(agent_fields(_security_reviewer(), ctx)) == (
        "name: security-reviewer",
        _SECURITY_REVIEWER_DESCRIPTION,
        "model: opus",
        'color: "#DC2626"',
        "tools: Bash, Read, Grep, Glob, Write, Edit, WebSearch, WebFetch",
    )


_PYTHON_CODER_DESCRIPTION = 'description: "Python implementation specialist."'


def _python_coder() -> Definition:
    [defn] = [defn for _, defn in definitions() if defn.name == "python-coder"]
    return defn


def test_an_unrestricted_agent_frontmatter_matches_the_pre_1_0_render() -> None:
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    assert _claude_frontmatter(agent_fields(_python_coder(), ctx)) == (
        "name: python-coder",
        _PYTHON_CODER_DESCRIPTION,
        "model: opus",
        'color: "#3776AB"',
    )


_OPENCODE_PERMISSIONS = {
    "read": "allow",
    "grep": "allow",
    "glob": "allow",
    "list": "allow",
    "edit": "allow",
    "shell": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "subagent": "deny",
}

# A command and a document take no frontmatter value of their own, so each fixture is the least a
# definition of its kind can be: a name, a kind and a body. Each body does one thing — names the temp
# directory — so that the placeholder fill is observable.
_COMMAND = Definition(
    name="probe",
    kind=Kind.COMMAND,
    body=f"Write scratch output under {hole(HarnessText.PROJECT_TEMP_DIR)}.",
)
_DOCUMENT = Definition(
    name="note",
    kind=Kind.DOCUMENT,
    body=f"Keep a working draft under {hole(HarnessText.PROJECT_TEMP_DIR)}.",
)


@pytest.mark.parametrize(
    "defn, tier_map, expected",
    [
        (
            _security_reviewer(),
            _ALL_INHERIT,
            {
                "description": _security_reviewer().description,
                "mode": "subagent",
                "color": "#DC2626",
                "permission": _OPENCODE_PERMISSIONS,
            },
        ),
        (
            _python_coder(),
            dict.fromkeys(TIERS, "omlx/Qwen3.8-Flash-Next"),
            {
                "description": "Python implementation specialist.",
                "mode": "subagent",
                "model": {"providerID": "omlx", "id": "Qwen3.8-Flash-Next"},
                "color": "#3776AB",
            },
        ),
        (_DOCUMENT, _ALL_INHERIT, {"mode": "subagent", "hidden": True}),
    ],
    ids=["restricted-inherit", "unrestricted-pinned", "document"],
)
def test_an_opencode_agent_record_carries_the_pre_1_0_frontmatter_values(
    defn: Definition, tier_map: dict[str, str], expected: dict[str, object]
) -> None:
    """The registry record holds what opencode's frontmatter held before the plugin render: description,
    mode, the model split into provider and id where one renders, color, and a permission per governed key
    unless every tool is allowed. A document's record is a hidden subagent's."""
    ctx = Render(harness=OPENCODE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=tier_map)
    shipped = ShippedDefinition(
        name=defn.name,
        reference=f"devpro-{defn.name}",
        kind=defn.kind,
        path=str(defn.output_path),
        description=None,
        agent=agent_fields(defn, ctx) if defn.kind is Kind.AGENT else None,
    )
    registry = ctx.harness.definition_form
    assert isinstance(registry, HarnessFile)
    [record] = json.loads(registry.text("devpro", (shipped,)))["agents"]
    assert record == {"id": f"devpro-{defn.name}", "file": str(defn.output_path), **expected}


Discovered = tuple[tuple[str, Definition], ...]


@pytest.fixture(scope="module")
def discovered() -> Discovered:
    """Every definition the package discovers, with its module."""
    return definitions()


def _found(discovered: Discovered, path: str) -> tuple[str, Definition]:
    [found] = [(module, defn) for module, defn in discovered if defn.output_path == PurePosixPath(path)]
    return found


def test_a_command_renders_its_banner_straight_into_a_body_naming_the_harness_temp_dir() -> None:
    """A command carries no field lines, so its closing fence is the body's own first line: a blank
    line there opens the file with an empty paragraph. The body names the scratch directory the
    definition's placeholder stands for, filled as this harness spells it."""
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    lines = render_definition(_COMMAND, ctx, module="devpro.definitions.probe").split("\n")
    assert lines[0] == "---"
    assert lines[1].startswith("# !GENERATED! from devpro/definitions/probe.py — ")
    assert " tier=none member=none tier-map=" in lines[2]
    assert lines[3] == "---"
    body = "\n".join(lines[4:])
    assert not body.startswith("\n"), "a blank line after the closing fence opens the file with an empty paragraph"
    assert body.strip(), "the command renders no body"
    assert CLAUDE.text(HarnessText.PROJECT_TEMP_DIR) in body
    assert not re.search(r"@!hrn-[a-z0-9-]+!@", body), body


def test_a_document_renders_no_field_of_its_own() -> None:
    """A document declares no frontmatter value, so between the fences stands the banner alone."""
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    lines = render_definition(_DOCUMENT, ctx, module="devpro.definitions.probe").split("\n")
    assert lines[0] == "---"
    assert lines[1].startswith("# !GENERATED! from devpro/definitions/probe.py — ")
    assert " tier=none member=none tier-map=" in lines[2]
    assert lines[3] == "---"


@pytest.mark.skipif(shutil.which("sed") is None, reason="extraction needs sed")
def test_every_rendered_definition_extracts_frontmatter_free(tmp_path: Path) -> None:
    """The definitions' own extraction command, run over every rendered file under agents/: it exits
    0, leaves no banner, and the frontmatter block plus what it printed is the file byte for byte."""
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
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


def _skill(**changes: object) -> Definition:
    """A skill named `probe` with one reference, its required description filled, overridable."""
    fields = {
        "name": "probe",
        "kind": Kind.SKILL,
        "description": "Use when the user asks about the knowledge base.",
        "body": "Route the request to the reference it asks for.",
        "files": (SkillFile(path="references/reading.md", body="Read a claim before you cite it."),),
    }
    return Definition(**{**fields, **changes})


def test_a_skill_renders_a_directory_two_fields_and_a_comment_bannered_reference() -> None:
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    defn = _skill()
    assert defn.output_path == PurePosixPath("skills/probe/SKILL.md")
    assert defn.output_paths == (
        PurePosixPath("skills/probe/SKILL.md"),
        PurePosixPath("skills/probe/references/reading.md"),
    )
    lines = render_definition(defn, ctx, module="devpro.definitions.probe").split("\n")
    assert lines[0] == "---"
    assert lines[1].startswith("# !GENERATED! from devpro/definitions/probe.py — ")
    assert " tier=none member=none " in lines[2]
    assert lines[3:6] == [
        "name: probe",
        'description: "Use when the user asks about the knowledge base."',
        "---",
    ]
    assert lines[6:] == ["", "Route the request to the reference it asks for.", ""]
    reference = render_skill_file(defn, defn.files[0], ctx, module="devpro.definitions.probe").split("\n")
    assert reference[0].startswith("<!-- !GENERATED! from devpro/definitions/probe.py — ")
    assert reference[0].endswith(" -->")
    assert reference[1].startswith("<!-- !TUNING! family=")
    assert reference[1].endswith(" -->")
    assert reference[2:] == ["", "Read a claim before you cite it.", ""]


_OPENCODE_RENDER = Render(harness=OPENCODE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)


@pytest.mark.parametrize(
    "defn",
    [_security_reviewer(), _DOCUMENT, _COMMAND, _skill()],
    ids=lambda defn: defn.kind.value,
)
def test_an_opencode_definition_opens_with_the_comment_banner_and_no_frontmatter(defn: Definition) -> None:
    """Every kind opens with the two banner lines as HTML comments and the blank line after them, and
    what follows is the filled body entire: the registry, not the file, carries its metadata."""
    lines = render_definition(defn, _OPENCODE_RENDER, module="devpro.definitions.probe").split("\n")
    assert lines[0].startswith("<!-- !GENERATED! from devpro/definitions/probe.py — ")
    assert lines[0].endswith(" -->")
    assert lines[1].startswith("<!-- !TUNING! family=") and lines[1].endswith(" -->")
    assert lines[2] == ""
    assert "\n".join(lines[3:]) == filled_body(defn, _OPENCODE_RENDER) + "\n"


def test_every_opencode_output_but_the_registry_holds_the_comment_banner_and_then_only_its_body() -> None:
    """Over the whole render, each file opens with the two comment banner lines and a blank line, and
    no frontmatter fence or second banner follows; the registry is the one other output."""
    renders = dict(render_all(_OPENCODE_RENDER))
    assert renders.pop(PurePosixPath("registry.json"))
    assert len(renders) > 20
    for path, text in renders.items():
        generated, tuning, blank, body = text.split("\n", 3)
        assert generated.startswith("<!-- !GENERATED! ") and tuning.startswith("<!-- !TUNING! "), path
        assert blank == "" and not body.startswith("---\n") and "<!-- !GENERATED!" not in body, path


@pytest.mark.parametrize("plugin, servers", [(DEVPRO, set()), (KBASE, {"kbase"})], ids=["devpro", "kbase"])
def test_the_opencode_registry_matches_the_render(plugin: Plugin, servers: set[str]) -> None:
    """`registry.json`'s agent, command and skill records are exactly the definitions the render ships, each
    id the plugin's name, a hyphen and the definition's name, each file one the render writes; its MCP
    server is present only where kbase ships."""
    ctx = Render(harness=OPENCODE, plugin=plugin, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    renders = dict(render_all(ctx))
    registry = json.loads(renders[PurePosixPath("registry.json")])
    records = [*registry["agents"], *registry["commands"], *registry["skills"]]
    shipped = {defn.name: str(defn.output_path) for _, defn in definitions() if plugin.ships(defn.name)}
    assert sorted((record["id"], record["file"]) for record in records) == sorted(
        (f"{plugin.name}-{name}", path) for name, path in shipped.items()
    )
    assert all(PurePosixPath(record["file"]) in renders for record in records)
    assert registry["plugin"] == plugin.name and registry["version"] == devpro.__version__
    assert set(registry["mcp"]) == servers


def test_render_all_emits_every_file_of_a_shipped_skill_and_the_plugin_drops_a_whole_definition() -> None:
    shipping = {path for path, _ in render_all(dataclasses.replace(_CLAUDE_RENDER, plugin=KBASE))}
    without = {path for path, _ in render_all(_CLAUDE_RENDER)}
    assert set(kbase_skill_output_paths()) <= shipping
    assert not any(path.parts[:2] == ("skills", "kbase") for path in without)


# mage's output is a Claude Code plugin directory: claude's vocabulary and one file of its own, the
# manifest.
_MAGE_RENDER = Render(harness=MAGE, plugin=KBASE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
_MAGE_MANIFEST = PurePosixPath(".claude-plugin/plugin.json")


def test_a_mage_render_writes_the_plugin_tree_straight_into_the_root(tmp_path: Path) -> None:
    """The installed directory is the plugin itself, so its manifest and its surfaces sit at the root:
    one grown under another directory is a tree Claude Code does not read."""
    written = {path.relative_to(tmp_path).as_posix() for path in write_renders(tmp_path, render_all(_MAGE_RENDER))}
    assert {"agents/python-coder.md", "skills/kbase/SKILL.md", str(_MAGE_MANIFEST)} <= written


def test_the_manifest_is_the_three_key_object_carrying_the_version() -> None:
    """The marketplace reads these three keys and nothing else, its version being the release's."""
    parsed = json.loads(dict(render_all(_MAGE_RENDER))[_MAGE_MANIFEST])
    assert parsed == {
        "name": "kbase",
        "version": devpro.__version__,
        "description": "Skills, agents, and MCP tools from the devpro project",
    }


def test_the_manifest_is_the_only_render_of_a_mage_plugin_carrying_the_version() -> None:
    """A bump republishes the manifest alone: a version in a definition or a skill file would churn a
    render slot on every release and say nothing a plugin manifest does not."""
    carriers = [
        path for path, text in render_all(_MAGE_RENDER) if path != _MAGE_MANIFEST and devpro.__version__ in text
    ]
    assert carriers == []


@pytest.mark.parametrize(
    "harness, tool_name",
    [(CLAUDE, "mcp__plugin_kbase_kbase__query"), (MAGE, "mcp_kbase_query"), (OPENCODE, "kbase_query")],
)
def test_the_kb_reading_reference_names_the_harness_mcp_tool(harness: Harness, tool_name: str) -> None:
    """The rendered instruction must name the callable the selected host actually exposes."""
    ctx = Render(harness=harness, plugin=KBASE, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    reference = dict(render_all(ctx))[PurePosixPath("skills/kbase/references/reading.md")]
    assert f"`{tool_name}`" in reference


def _user_install_paths() -> set[str]:
    """Each loaded harness's user plugin directory as the guide spells it, and the directory mage's plugin
    parent names, read from the profiles."""
    paths = set()
    for harness in harnesses().values():
        if harness.plugin_dir:
            paths.add(f"{harness.user_harness_dir}/{harness.plugin_dir.replace('{plugin}', '<plugin>')}/")
        if harness.plugin_parent_dir:
            paths.add(f"~/{harness.plugin_parent_dir}/")
    return paths


@pytest.mark.parametrize("harness", harnesses())
def test_the_guide_names_every_harness_install_path_under_every_harness(harness: str) -> None:
    ctx = build_render(plugin="devpro", harness=harness, family="claude", tier_spec=None, alias_spec=None)
    [text] = [text for path, text in render_all(ctx) if str(path).endswith("guide/references/installing.md")]
    assert [path for path in sorted(_user_install_paths()) if path not in text] == []


def _routed_references(router: str) -> set[str]:
    """The reference paths the router's tables route to, read off the table cells themselves."""
    routed = set()
    for line in router.split("\n"):
        if not line.startswith("|"):
            continue
        for cell in line.strip("|").split("|"):
            path = cell.strip().strip("`")
            if path.startswith("references/"):
                routed.add(path)
    return routed


_SKILLS_WITH_FILES = [defn for _, defn in definitions() if defn.kind is Kind.SKILL and defn.files]


@pytest.mark.parametrize("skill", _SKILLS_WITH_FILES, ids=lambda skill: skill.name)
def test_the_router_routes_to_every_reference_that_ships_and_no_other(skill: Definition) -> None:
    """A reference is read only when its route is reached and every route is a reference, so the two
    sets are one: a route naming a file the skill does not carry opens on nothing, and a file no route
    names is text no session ever reads."""
    routed = _routed_references(skill.body)
    assert routed == {file.path for file in skill.files}
    assert routed, "no route parsed from the table, so the comparison above would pass vacuously"


def test_filled_text_names_the_file_an_unknown_placeholder_stands_in() -> None:
    ctx = _CLAUDE_RENDER
    with pytest.raises(
        InputError,
        match=re.escape("skills/probe/references/reading.md: unknown placeholder @!hrn-nonesuch!@"),
    ):
        filled_text("before @!hrn-nonesuch!@ after", _skill(), ctx, where="skills/probe/references/reading.md")


@pytest.mark.parametrize(
    "path",
    ["references/Reading.md", "SKILL.md", "references/reading.markdown", "../reading.md", "references/"],
)
def test_a_skill_file_path_outside_its_contract_is_refused(path: str) -> None:
    with pytest.raises(InputError, match=re.escape(f"skill file '{path}': path is not kebab")):
        SkillFile(path=path, body="text")


def test_a_skill_file_body_follows_the_definition_body_rule() -> None:
    for body in ("", "  \n", "text\n", "\ntext"):
        with pytest.raises(InputError, match="body must be non-empty text with no leading or trailing newline"):
            SkillFile(path="references/reading.md", body=body)


@pytest.mark.parametrize(
    "part, harness, expected",
    [
        (HarnessText.AGENTS_FILE, CLAUDE, "CLAUDE.md"),
        (HarnessText.AGENTS_FILE, OPENCODE, "AGENTS.md"),
        (HarnessText.PROJECT_HARNESS_DIR, CLAUDE, ".claude"),
        (HarnessText.PROJECT_HARNESS_DIR, OPENCODE, ".opencode"),
        (HarnessText.PROJECT_TEMP_DIR, CLAUDE, ".claude-temp"),
        (HarnessText.PROJECT_TEMP_DIR, OPENCODE, ".opencode-temp"),
        (HarnessText.DISPLAY_NAME, CLAUDE, "claude code"),
        (HarnessText.DISPLAY_NAME, OPENCODE, "opencode"),
        (HarnessText.DISPLAY_NAME, MAGE, "mage"),
        (HarnessText.USER_HARNESS_DIR, CLAUDE, "~/.claude"),
        (HarnessText.USER_HARNESS_DIR, OPENCODE, "~/.config/opencode"),
        (HarnessText.MCP_TOOL_PREFIX, CLAUDE, "mcp__plugin_devpro_kbase__"),
        (HarnessText.MCP_TOOL_PREFIX, OPENCODE, "kbase_"),
    ],
)
def test_a_harness_text_placeholder_fills_with_the_harness_string(
    part: HarnessText, harness: Harness, expected: str
) -> None:
    defn = Definition(name="probe", kind=Kind.COMMAND, body=f"see {hole(part)}/x")
    ctx = Render(harness=harness, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    assert filled_body(defn, ctx) == f"see {expected}/x"


def test_a_harness_display_name_that_is_not_lowercase_is_refused() -> None:
    with pytest.raises(InputError, match=re.escape("harness 'claude': display_name is not lowercase")):
        dataclasses.replace(CLAUDE, display_name="Claude Code")


@pytest.mark.parametrize(
    "placeholder", ["@!hrn.agents-file!@", "@!hrn-nonesuch!@", "@!fam-gap!@", "@!ask-vs-stipulate!@"]
)
def test_an_unknown_placeholder_is_refused_at_render(placeholder: str) -> None:
    defn = Definition(name="probe", kind=Kind.COMMAND, body=f"before {placeholder} after")
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    with pytest.raises(InputError, match=re.escape(f"definition 'probe': unknown placeholder {placeholder}")):
        filled_body(defn, ctx)


@pytest.mark.parametrize("part", [*HarnessText, *OptionalHarnessText, *TuningText], ids=lambda part: part.name)
def test_the_text_module_spells_each_render_placeholder_as_the_renderer_fills_it(
    part: HarnessText | OptionalHarnessText | TuningText,
) -> None:
    assert getattr(devpro.clauses, part.name) == hole(part)


def test_the_text_module_spells_the_plugin_name_as_the_renderer_fills_it() -> None:
    assert devpro.clauses.PLUGIN_NAME == hole(PluginText.NAME)


def test_the_text_module_spells_a_reference_as_the_renderer_fills_it() -> None:
    assert devpro.clauses.ref(name="python-coder") == reference("python-coder")
    assert devpro.clauses.optional_ref(name="python-coder") == optional_reference("python-coder")


_PREFIXED = [CLAUDE, dataclasses.replace(CLAUDE, reference_prefix="x:")]


@pytest.mark.parametrize("harness", _PREFIXED, ids=["bare", "prefixed"])
def test_a_reference_in_a_body_and_a_description_fills_with_the_prefix_and_name(harness: Harness) -> None:
    ctx = Render(harness=harness, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    named = f"{ctx.bound_harness.reference_prefix}python-coder"
    agent = Definition(
        name="probe",
        kind=Kind.AGENT,
        description=f"Prefer over {reference('python-coder')}.",
        tools=ALL,
        tier="high",
        body=f"Hand it to `{reference('python-coder')}`.",
    )
    skill = _skill(description=f"Prefer over {reference('python-coder')}.")
    agent_text = render_definition(agent, ctx, module="devpro.definitions.probe")
    assert f'description: "Prefer over {named}."' in agent_text.split("\n")
    assert agent_text.endswith(f"Hand it to `{named}`.\n")
    assert f'description: "Prefer over {named}."' in render_definition(skill, ctx, module="m").split("\n")


@pytest.mark.parametrize("harness", _PREFIXED, ids=["bare", "prefixed"])
@pytest.mark.parametrize("field", ["body", "description"])
def test_a_reference_to_an_undiscovered_name_is_refused_naming_the_definition(harness: Harness, field: str) -> None:
    hole_text = reference("nonesuch")
    defn = Definition(name="probe", kind=Kind.AGENT, description="a probe", tools=ALL, tier="high", body="Own.")
    defn = dataclasses.replace(defn, **{field: f"see {hole_text}"})
    ctx = Render(harness=harness, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    with pytest.raises(InputError, match=re.escape("definition 'probe'")) as refused:
        render_definition(defn, ctx, module="m")
    assert f"unknown placeholder {hole_text}" in str(refused.value)


_NAMESPACED = [harness for harness in (CLAUDE, MAGE, OPENCODE) if harness.reference_prefix]


@pytest.mark.parametrize("harness", _NAMESPACED, ids=lambda harness: harness.name)
def test_a_reference_prefix_changes_nothing_but_the_reference_sites(harness: Harness) -> None:
    """Every rendered file, the agents file included, read with each prefix occurrence removed is the
    render of the same harness with the prefix empty, and that bare render spells the prefix nowhere: a
    prefix reaches no text but the references it is put before."""
    bare = dataclasses.replace(harness, reference_prefix="")
    prefix = harness.bound(DEVPRO.name).reference_prefix

    def rendered(each: Harness) -> dict[PurePosixPath, str]:
        ctx = Render(harness=each, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
        return {**dict(render_all(ctx)), PurePosixPath("<agents file>"): render_agents_file(each, DEVPRO, scope="x")}

    # The agents-file marker lines spell the project's name, which can equal the plugin's and so hold the
    # prefix without being a reference site.
    def off_marker(text: str) -> list[str]:
        return [line for line in text.split("\n") if not is_marker_line(line)]

    def unprefixed(text: str) -> str:
        return "\n".join(line if is_marker_line(line) else line.replace(prefix, "") for line in text.split("\n"))

    prefixed, plain = rendered(harness), rendered(bare)
    assert prefixed.keys() == plain.keys()
    assert {path: unprefixed(text) for path, text in prefixed.items()} == plain
    assert [path for path, text in plain.items() if any(prefix in line for line in off_marker(text))] == []
    assert any(prefix in line for text in prefixed.values() for line in off_marker(text))


_STEP_DOWN_BODY = f"before\n\nDefault: `{devpro.clauses.STEP_DOWN_MODEL}`, unless bound.\n\nafter"


@pytest.mark.parametrize(
    "harness, tier_spec, rendered",
    [
        ("claude", None, "before\n\nDefault: `sonnet`, unless bound.\n\nafter"),
        ("opencode", None, "before\n\nafter"),
        (
            "opencode",
            "all=omlx/Qwen3.8-Flash-Next",
            "before\n\nDefault: `omlx/Qwen3.8-Flash-Next`, unless bound.\n\nafter",
        ),
        ("mage", None, "before\n\nDefault: `sonnet`, unless bound.\n\nafter"),
        ("claude", "all=inherit", "before\n\nafter"),
    ],
)
def test_the_step_down_paragraph_names_the_pinned_medium_model_or_drops_whole(
    harness: str, tier_spec: str | None, rendered: str
) -> None:
    """The paragraph renders exactly where the render pins a model for the step-down tier; where that
    tier renders as inherit there is nothing to step down to, and the paragraph goes with its other text."""
    ctx = build_render(plugin="devpro", harness=harness, family="claude", tier_spec=tier_spec, alias_spec=None)
    assert filled_text(_STEP_DOWN_BODY, _skill(), ctx, where="skills/probe/SKILL.md") == rendered


def test_the_step_down_model_fills_a_skill_supporting_file_as_it_fills_skill_md() -> None:
    line = f"Step down to {devpro.clauses.STEP_DOWN_MODEL}."
    defn = _skill(body=line, files=(SkillFile(path="references/reading.md", body=line),))
    ctx = build_render(plugin="devpro", harness="claude", family="claude", tier_spec=None, alias_spec=None)
    rendered = render_skill_file(defn, defn.files[0], ctx, module="devpro.definitions.probe")
    assert rendered.endswith("\n\nStep down to sonnet.\n")


# A paragraph a tuning hole stands in is dropped whole where the value fills to nothing; a list or table
# in that paragraph would go with it.
_TUNING_HOLES = re.compile("|".join(re.escape(hole(part)) for part in TuningText))
_LIST_OR_TABLE_LINE = re.compile(r"^\s*(?:[-*] |\d+\. |\|)", re.MULTILINE)


def test_no_tuning_hole_shares_a_paragraph_with_a_list_or_table() -> None:
    every = [defn for _, entries in discover() for defn in entries]
    bodies = [(defn.name, defn.body) for defn in every]
    bodies += [(f"{defn.name}/{file.path}", file.body) for defn in every for file in defn.files]
    found = [
        f"{label}: {paragraph[:120]}"
        for label, body in bodies
        for paragraph in body.split("\n\n")
        if _TUNING_HOLES.search(paragraph) and _LIST_OR_TABLE_LINE.search(paragraph)
    ]
    assert found == [], "\n".join(found)


@pytest.mark.parametrize("path", ["agents/python-coder.md", "agents/web-app-expert.md"])
def test_a_coder_and_a_platform_expert_render_the_recipe_rule_under_claude_and_drop_it_under_opencode(
    discovered: Discovered, path: str
) -> None:
    """The paragraph is the harness's own: where the harness supplies one it stands as its own paragraph,
    and where it supplies none the paragraph goes whole, leaving no empty one behind."""
    _, coder = _found(discovered, path)
    paragraph = CLAUDE.recipe_rule
    under_claude = filled_body(
        coder, Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    )
    under_opencode = filled_body(
        coder, Render(harness=OPENCODE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT)
    )
    assert OPENCODE.recipe_rule == ""
    assert f"\n\n{paragraph}\n\n" in under_claude
    assert paragraph not in under_opencode
    assert "\n\n\n" not in under_opencode


def test_the_kbase_project_rule_paragraph_renders_under_mage_and_drops_under_claude() -> None:
    body = f"before\n\n{hole(OptionalHarnessText.KBASE_PROJECT_RULE)}\n\nafter"
    defn = Definition(name="probe", kind=Kind.COMMAND, body=body)
    under_mage = filled_body(defn, Render(harness=MAGE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT))
    under_claude = filled_body(defn, Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT))
    assert MAGE.kbase_project_rule
    assert under_mage == f"before\n\n{MAGE.kbase_project_rule}\n\nafter"
    assert under_claude == "before\n\nafter"


def test_a_paragraph_holding_an_optional_harness_text_the_harness_supplies_nothing_for_drops_whole() -> None:
    body = f"before\n\nThe rule is: {hole(OptionalHarnessText.RELOAD_RULE)}\n\nafter"
    defn = Definition(name="probe", kind=Kind.COMMAND, body=body)
    under_claude = filled_body(defn, Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT))
    under_mage = filled_body(defn, Render(harness=MAGE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT))
    assert MAGE.reload_rule == ""
    assert CLAUDE.reload_rule
    assert under_claude == f"before\n\nThe rule is: {CLAUDE.reload_rule}\n\nafter"
    assert under_mage == "before\n\nafter"


_TUNED = Family(
    "tuned",
    {"highest": "big", "high": "big", "medium": "mid", "low": "small", "lowest": "small"},
    overlays={Anchor.ASK_VS_STIPULATE: Overlay(text="family-wide", members={"mid": "for mid"})},
)


def _with_family_text(*, family: Family, tier: str, body: str) -> str:
    defn = Definition(name="probe", kind=Kind.AGENT, description="a probe", tools=ALL, tier=tier, body=body)
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=family, tier_map=dict(family.tiers))
    return render_definition(defn, ctx, module="devpro.definitions.probe").split("---\n\n", 1)[1]


_OVERLAY = hole(Anchor.ASK_VS_STIPULATE)


@pytest.mark.parametrize(
    "family, tier, body, rendered",
    [
        (_TUNED, "medium", f"before\n\n{_OVERLAY}\n\nafter", "before\n\nfor mid\n\nafter\n"),
        (_TUNED, "high", f"before\n\n{_OVERLAY}\n\nafter", "before\n\nfamily-wide\n\nafter\n"),
        (CLAUDE_FAMILY, "medium", f"before\n\n{_OVERLAY}\n\nafter", "before\n\nafter\n"),
        (CLAUDE_FAMILY, "medium", f"{_OVERLAY}\n\nafter", "after\n"),
        (CLAUDE_FAMILY, "medium", f"before\n\n{_OVERLAY}", "before\n"),
    ],
)
def test_family_text_renders_the_seats_overlay_or_leaves_no_empty_paragraph(
    family: Family, tier: str, body: str, rendered: str
) -> None:
    assert _with_family_text(family=family, tier=tier, body=body) == rendered


# Filled text is literal: what a fill puts into a body is never filled again. Each value below carries a
# hole the fill expands — to the harness's agents file name — so any second pass over filled text
# changes the output.
_BAIT = hole(HarnessText.AGENTS_FILE)
_BAITED_FAMILY = Family(
    "baited",
    {"highest": "big", "high": "big", "medium": f"mid{_BAIT}", "low": "small", "lowest": "small"},
    overlays={Anchor.ASK_VS_STIPULATE: Overlay(text=f"overlay {_BAIT}")},
)


def _clause_with_a_baited_harness_value() -> tuple[Definition, Render, str]:
    """A clause constant's own holes are filled once; the value one fills to stays as it is."""
    harness = dataclasses.replace(CLAUDE, project_temp_dir=f"temp{_BAIT}")
    clause = devpro.clauses.NEW_PROJECT_SETUP
    expected = clause.replace(hole(HarnessText.PROJECT_TEMP_DIR), f"temp{_BAIT}").replace(
        hole(HarnessText.PROJECT_HARNESS_DIR), CLAUDE.project_harness_dir
    )
    defn = Definition(name="probe", kind=Kind.COMMAND, body=clause)
    return defn, Render(harness=harness, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT), expected


def _baited_harness_text() -> tuple[Definition, Render, str]:
    harness = dataclasses.replace(CLAUDE, user_harness_dir=f"~/home{_BAIT}")
    defn = Definition(name="probe", kind=Kind.COMMAND, body=f"see {hole(HarnessText.USER_HARNESS_DIR)}")
    return (
        defn,
        Render(harness=harness, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT),
        f"see ~/home{_BAIT}",
    )


def _baited_optional_harness_text() -> tuple[Definition, Render, str]:
    harness = dataclasses.replace(CLAUDE, recipe_rule=f"rule {_BAIT}")
    defn = Definition(name="probe", kind=Kind.COMMAND, body=hole(OptionalHarnessText.RECIPE_RULE))
    return defn, Render(harness=harness, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT), f"rule {_BAIT}"


def _baited_family_overlay() -> tuple[Definition, Render, str]:
    defn = Definition(name="probe", kind=Kind.AGENT, description="a probe", tools=ALL, tier="high", body=_OVERLAY)
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=_BAITED_FAMILY, tier_map=dict(_BAITED_FAMILY.tiers))
    return defn, ctx, f"overlay {_BAIT}"


def _baited_scope_name() -> tuple[Definition, Render, str]:
    defn = Definition(name="probe", kind=Kind.AGENTS_FILE, body=f"# {hole(AgentsFileText.SCOPE_NAME)}")
    return (
        defn,
        Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=_ALL_INHERIT, scope=f"s{_BAIT}"),
        f"# s{_BAIT}",
    )


def _baited_step_down_model() -> tuple[Definition, Render, str]:
    """The family member the step-down tier pins carries the hole."""
    defn = _skill(body=f"use {hole(TuningText.STEP_DOWN_MODEL)}")
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=_BAITED_FAMILY, tier_map=dict(_BAITED_FAMILY.tiers))
    return defn, ctx, f"use mid{_BAIT}"


@pytest.mark.parametrize(
    "case",
    [
        _clause_with_a_baited_harness_value,
        _baited_harness_text,
        _baited_optional_harness_text,
        _baited_family_overlay,
        _baited_scope_name,
        _baited_step_down_model,
    ],
    ids=["clause", "harness-text", "optional-harness-text", "family-overlay", "scope-name", "step-down-model"],
)
def test_a_filled_value_carrying_a_hole_reaches_the_body_literally(case) -> None:
    defn, ctx, expected = case()
    filled = filled_body(defn, ctx)
    assert filled == expected
    assert _BAIT in filled


def test_stock_excludes_the_overridden_tier() -> None:
    ctx = Render(harness=CLAUDE, plugin=DEVPRO, family=_TUNED, tier_map=dict(_TUNED.tiers))
    assert ctx.stock == ("highest", "high", "low", "lowest")


_REFERENCE = SkillFile(path="references/reading.md", body="Read it.")


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
        ({"folder": "nested/Design"}, "folder 'nested/Design'"),
        ({"kind": Kind.SKILL, "description": None}, "a skill requires description"),
        (
            {"kind": Kind.SKILL, "description": "a probe", "tools": ALL, "tier": None},
            "a skill takes no tools",
        ),
        (
            {"kind": Kind.SKILL, "description": "a probe", "tools": None, "tier": None, "color": "#000000"},
            "a skill takes no color",
        ),
        (
            {"kind": Kind.SKILL, "description": "a probe", "tools": None, "tier": None, "folder": "sub"},
            "a skill takes no folder",
        ),
        (
            {
                "kind": Kind.SKILL,
                "description": "a probe",
                "tools": None,
                "tier": None,
                "files": (_REFERENCE, _REFERENCE),
            },
            "files names a path twice",
        ),
        (
            {"kind": Kind.COMMAND, "description": None, "tools": None, "tier": None, "files": (_REFERENCE,)},
            "a command takes no files",
        ),
    ],
)
def test_definition_refusals(changes: dict, message: str) -> None:
    fields = {"name": "probe", "kind": Kind.AGENT, "description": "a probe", "tools": ALL, "tier": "high", "body": "ok"}
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


def test_an_agents_file_has_no_output_path() -> None:
    defn = Definition(name="probe", kind=Kind.AGENTS_FILE, body="x")
    with pytest.raises(InputError, match="definition 'probe': an agents file has no output path"):
        defn.output_path


def test_discovery_refuses_a_module_without_definitions() -> None:
    with pytest.raises(InputError, match="'devpro.definitions.probe' defines no DEFINITIONS"):
        definitions_of("devpro.definitions.probe", None)


# Source invariants, over every module of the package.


def _modules(*subpaths: str) -> list[tuple[str, ast.Module]]:
    """Every module under each subpath of the package (a directory or one file), or the whole package."""
    roots = [_PACKAGE.joinpath(*sub.split("/")) for sub in subpaths] or [_PACKAGE]
    files = sorted({path for root in roots for path in ([root] if root.is_file() else root.rglob("*.py"))})
    return [
        (path.relative_to(_PACKAGE.parent).as_posix(), ast.parse(path.read_text(encoding="utf-8"))) for path in files
    ]


def _imported(tree: ast.Module) -> list[str]:
    """Every module an import statement names, a relative import as under devpro, and each name a
    from-import takes as a possible submodule (`from devpro import clauses` names `devpro.clauses`)."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = f"devpro.{node.module}" if node.level else node.module
            names += [module, *(f"{module}.{alias.name}" for alias in node.names)]
    return names


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


def _is_stdlib(module: str) -> bool:
    """Whether the top-level module resolves into the running interpreter's
    standard library: built in, frozen, or a file under its stdlib directory
    outside any site-packages."""
    spec = importlib.util.find_spec(module)
    if spec is None or spec.origin is None:
        return False
    if spec.origin in ("built-in", "frozen"):
        return True
    stdlib = Path(sysconfig.get_paths()["stdlib"]).resolve()
    origin = Path(spec.origin).resolve()
    return stdlib in origin.parents and "site-packages" not in origin.relative_to(stdlib).parts


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("__future__", True),
        ("ast", True),
        ("_thread", True),
        ("json", True),
        ("pytest", False),
        ("devpro", False),
        ("no_such_module_anywhere", False),
    ],
)
def test_is_stdlib_tells_the_standard_library_from_everything_else(module: str, expected: bool) -> None:
    assert _is_stdlib(module) is expected


def test_every_import_is_stdlib_or_the_package() -> None:
    offenders = [
        f"{path} imports {name}"
        for path, tree in _modules()
        for name in _imported(tree)
        if name.split(".")[0] != "devpro" and not _is_stdlib(name.split(".")[0])
    ]
    assert offenders == []


_DEFINITION_PATHS = sorted(path for path in (_PACKAGE / "definitions").glob("*.py") if not path.stem.startswith("_"))


def test_the_definition_modules_and_the_text_module_hold_their_structure() -> None:
    violations = check_structure([*_DEFINITION_PATHS, _PACKAGE / "clauses.py"])
    assert violations == [], "\n".join(violations)


def test_development_bodies_spell_each_term_through_its_constant() -> None:
    """A project binds a term by its exact spelling, so a body writing one out literally drifts from the
    constant every other mention renders from."""
    tree = ast.parse((_PACKAGE / "definitions" / "development.py").read_text(encoding="utf-8"))
    terms = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign) and node.targets[0].id.endswith("_TERM")
    }
    assert terms, "no *_TERM constant found, so the check below would pass vacuously"
    literals = [
        node
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        for keyword in call.keywords
        if keyword.arg == "body"
        for node in ast.walk(keyword.value)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    found = [
        f"a development.py body writes out {term} as {value!r}"
        for node in literals
        for term, value in terms.items()
        if value in node.value
    ]
    assert found == [], "\n".join(found)


_DEFINITION_HEAD = "from devpro import clauses\nfrom devpro.definition import Definition\n"


def _definitions_of_body(body: str, *, head: str = "") -> str:
    """A definition-module source whose one Definition has `body` as its body= source text."""
    return f'{_DEFINITION_HEAD}{head}DEFINITIONS = (Definition(name="p", kind=Kind.COMMAND, body={body}),)\n'


def _definitions_of_files(files: str) -> str:
    """A definition-module source whose one skill has `files` as its files= source text."""
    return f'{_DEFINITION_HEAD}DEFINITIONS = (Definition(name="p", kind=Kind.SKILL, files={files}),)\n'


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
        (_definitions_of_files('(SkillFile(path="references/r.md", body="b"),)'), 3, ""),
        (_definitions_of_files('(SkillFile(path="references/r.md", body=f"{clauses.dissent()}"),)'), 3, ""),
        (_definitions_of_files('(SkillFile(path=clauses.f(), body="b"),)'), 3, FILES_RULE),
        (_definitions_of_files("(SkillFile(path=_P, body='b'),)"), 3, FILES_RULE),
        (_definitions_of_files("(clauses.f(),)"), 3, CALL_RULE),
        (_definitions_of_files('(SkillFile(path="references/r.md", body=f"{len(_S)}"),)'), 3, CALL_RULE),
        (
            f'{_DEFINITION_HEAD}DEFINITIONS = (Definition(name="p", description=f"{{clauses.ref(name=\'x\')}}", body="b"),)\n',
            3,
            "",
        ),
        (
            f'{_DEFINITION_HEAD}DEFINITIONS = (Definition(name="p", description=f"{{len(_S)}}", body="b"),)\n',
            3,
            CALL_RULE,
        ),
        (f'{_DEFINITION_HEAD}DEFINITIONS = (Definition(name="p", tools=clauses.f(), body="b"),)\n', 3, CALL_RULE),
        (f'{_DEFINITION_HEAD}DEFINITIONS = (Definition("p", "b", kind=Kind.AGENT),)\n', 3, DEFINITION_CALL_RULE),
        (f"{_DEFINITION_HEAD}def helper():\n    pass\n", 3, DEFINITION_TOP_RULE),
        (f"{_DEFINITION_HEAD}DEFINITIONS = (_ONE,)\n", 3, DEFINITION_TOP_RULE),
        ("from devpro.clauses import X\n", 1, IMPORT_RULE),
        ("from devpro import clauses as c\n", 1, IMPORT_RULE),
        ("import devpro.clauses\n", 1, IMPORT_RULE),
    ],
)
def test_check_structure_refuses_a_definition_module_off_its_rules(source: str, line: int, rule: str) -> None:
    expected = [f"m.py:{line}: {rule}"] if rule else []
    assert check_source(source, where="m.py", text_module=False) == expected


@pytest.mark.parametrize(
    "source, rule",
    [
        ('_X = "a"\nY = f"{_X}"\ndef f(*, a, b="x", c=_X) -> str:\n    """doc"""\n    return f"{a}{b}{c}{Y}"\n', ""),
        ("from devpro.vocabulary import hole\n", TEXT_TOP_RULE),
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

_CLAUDE_RENDER = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
# The sweeps below read each plugin as it ships: its definitions and its own agents file, under claude.
_PLUGIN_RENDERS = tuple(
    Render(harness=CLAUDE, plugin=plugin, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    for plugin in load("devpro.plugins", "PLUGIN").values()
)
RENDERED_DEFINITION_LINE_CAP = 500  # a runaway guard, not a target; the 100-column wrap makes lines a fair size


def test_no_rendered_definition_exceeds_the_line_cap(discovered: Discovered) -> None:
    """A definition's own rendered body is capped whatever its kind; a supporting file is carried beside
    it, not its own output, and is not counted."""
    over = [
        f"{defn.output_path} renders at {count} lines after the banner; the cap is {RENDERED_DEFINITION_LINE_CAP}"
        for _, defn in discovered
        if (count := len(filled_body(defn, _CLAUDE_RENDER).splitlines())) > RENDERED_DEFINITION_LINE_CAP
    ]
    assert over == []


def test_every_description_is_one_line_with_balanced_code_spans(discovered: Discovered) -> None:
    """A description emits as `description: "…"` on one line, so a newline breaks the frontmatter block
    and an odd backtick count opens a code span that never closes, swallowing the rest of the line. The
    double quote is not checked here: `Definition` already refuses one at construction, which
    `test_definition_refusals` pins."""
    offenders = []
    for _, defn in discovered:
        description = defn.description
        if description is None:
            continue
        if "\n" in description:
            offenders.append(f"{defn.name}: description holds a newline")
        if description.count("`") % 2:
            offenders.append(f"{defn.name}: description has an unclosed code span")
    assert offenders == []


def _credited_text() -> types.SimpleNamespace:
    """The clauses module with every constant and function standing as a sentinel naming it; a
    constant that is a bare placeholder keeps its value, so prose around it is not credited to it."""
    standing: dict[str, object] = {}
    for name, value in vars(devpro.clauses).items():
        if isinstance(value, str) and not devpro.render.PLACEHOLDER.fullmatch(value):
            standing[name] = f"<<devpro.clauses.{name}>>"
        elif isinstance(value, str):
            standing[name] = value
        elif inspect.isfunction(value) and value.__module__ == devpro.clauses.__name__:
            standing[name] = lambda _sentinel=f"<<devpro.clauses.{name}()>>", **_: _sentinel
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


def _prose_unit_list(body: str) -> list[bytes]:
    """The paragraphs and list items of a body in order, each as devtools.render_diff collapses it; a
    heading, a table row and a line of a fenced block are not prose."""
    lines = render_diff.collapsed(body.encode("utf-8")).split(b"\n")
    return [line for line, kind in zip(lines, render_diff.line_kinds(lines)) if kind in ("item", "text")]


def _prose_units(body: str) -> set[bytes]:
    return set(_prose_unit_list(body))


def _outputs(defn: Definition, sentinel: Definition) -> list[tuple[str, str, str]]:
    """(label, the definition's own text, its credited twin's) for every file it renders: its output
    first, labelled by the path it renders to, then each supporting file."""
    if defn.kind is Kind.AGENTS_FILE:
        return [(defn.name, defn.body, sentinel.body)]
    pairs = [(str(defn.output_path), defn.body, sentinel.body)]
    assert len(defn.files) == len(sentinel.files)
    pairs += [
        (str(defn.file_output_path(file)), file.body, twin.body) for file, twin in zip(defn.files, sentinel.files)
    ]
    return pairs


def _in_plugin(defn: Definition, ctx: Render) -> bool:
    """Whether `ctx`'s plugin carries `defn`: a definition it ships, or the agents file every plugin has."""
    return defn.kind is Kind.AGENTS_FILE or ctx.plugin.ships(defn.name)


def _uncredited_shared_paragraphs(sources: dict[str, str]) -> list[str]:
    """Every prose unit two or more outputs of one plugin write out rather than take from a constant, a
    slot constant or a text function: the unit survives each one's credited render unchanged."""
    found: dict[str, None] = {}
    for ctx in _PLUGIN_RENDERS:
        written: dict[bytes, list[str]] = {}
        for module, source in sources.items():
            rendered = _source_definitions(source, module=module, credited=False)
            credited = _source_definitions(source, module=module, credited=True)
            assert len(rendered) == len(credited)
            for defn, sentinel in zip(rendered, credited):
                if not _in_plugin(defn, ctx):
                    continue
                for label, literal_body, credited_body in _outputs(defn, sentinel):
                    literal = _prose_units(filled_text(literal_body, defn, ctx, where=label)) & _prose_units(
                        filled_text(credited_body, sentinel, ctx, where=label)
                    )
                    for unit in literal:
                        written.setdefault(unit, []).append(label)
        found.update(
            (f"written out in {', '.join(written[unit])}: {unit.decode()[:120]}", None)
            for unit in sorted(written)
            if len(written[unit]) > 1
        )
    return list(found)


def test_a_paragraph_two_outputs_carry_has_one_source() -> None:
    sources = {f"devpro.definitions.{path.stem}": path.read_text(encoding="utf-8") for path in _DEFINITION_PATHS}
    found = _uncredited_shared_paragraphs(sources)
    assert found == [], "\n".join(found)


_FIXTURE_HEAD = (
    "from devpro import clauses\nfrom devpro.definition import Definition\nfrom devpro.vocabulary import Kind\n"
)
_SKILL_FIXTURE_HEAD = (
    "from devpro import clauses\nfrom devpro.definition import Definition, SkillFile\n"
    "from devpro.vocabulary import Kind\n"
)


def _fixture_module(*bodies: tuple[str, str], head: str = "") -> str:
    """A definition-module source of one command per (name, body source text)."""
    entries = "".join(f'Definition(name="{name}", kind=Kind.COMMAND, body={body}),' for name, body in bodies)
    return f"{_FIXTURE_HEAD}{head}DEFINITIONS = ({entries})\n"


def _skill_fixture_module(*file_bodies: str) -> str:
    """A definition-module source of one skill whose supporting files carry `file_bodies`."""
    names = ("one", "two", "three")
    entries = "".join(
        f'SkillFile(path="references/{names[index]}.md", body={body}),' for index, body in enumerate(file_bodies)
    )
    return (
        f'{_SKILL_FIXTURE_HEAD}DEFINITIONS = (Definition(name="s", kind=Kind.SKILL, description="a skill", '
        f'body="Own router.", files=({entries})),)\n'
    )


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


def test_a_paragraph_two_supporting_files_write_out_is_found() -> None:
    """A skill's references are outputs too: one of them pasting a paragraph another holds is the same
    defect, named by the path it renders to."""
    sources = {
        "fixture.skill": _skill_fixture_module(
            '"Written out twice."',
            'f"{clauses.DISSENT}\\n\\nWritten out twice."',
        )
    }
    assert _uncredited_shared_paragraphs(sources) == [
        "written out in skills/s/references/one.md, skills/s/references/two.md: Written out twice."
    ]


# A prompt delivers each shared span once: no clause reached twice, no paragraph written twice.

_CLAUSE_GRAPH = clause_graph((_PACKAGE / "clauses.py").read_text(encoding="utf-8"))
_HARNESS_STRINGS = {hole(part) for part in (*HarnessText, *PluginText)}
# A reference names one definition, like a harness string names one directory and the plugin name one
# plugin: a sentence's word, not a span a prompt could deliver twice.
_SENTENCE_HOLES = frozenset(
    name for name, value in vars(devpro.clauses).items() if isinstance(value, str) and value in _HARNESS_STRINGS
) | {devpro.clauses.ref.__name__, devpro.clauses.optional_ref.__name__}


@dataclass(frozen=True)
class _PromptOutput:
    """One rendered file: its label, its text filled under the claude render, and the clause roots its
    body names. `loads` marks a command's or skill's own body, whose `@` lines can load another
    output; `path` is None for the agents file, which no `@` line can name."""

    label: str
    path: PurePosixPath | None
    text: str
    roots: tuple[ClauseRoot, ...]
    loads: bool


def _prompts(sources: dict[str, str]) -> list[list[_PromptOutput]]:
    """Every prompt of every plugin: an output with that plugin's installed agents file, and for a command
    or skill body each output of the plugin an `@` line of it names, transitively; the agents file's own
    output is a prompt alone."""
    prompts = []
    for ctx in _PLUGIN_RENDERS:
        outputs = []
        for module, source in sources.items():
            roots = body_roots(source, _CLAUSE_GRAPH)
            for defn in _source_definitions(source, module=module, credited=False):
                if not _in_plugin(defn, ctx):
                    continue
                keys = (None, *(file.path for file in defn.files))
                defn_outputs = _outputs(defn, defn)
                assert len(keys) == len(defn_outputs)
                for key, (label, body, _) in zip(keys, defn_outputs):
                    outputs.append(
                        _PromptOutput(
                            label=label,
                            path=None if defn.kind is Kind.AGENTS_FILE else PurePosixPath(label),
                            text=filled_text(body, defn, ctx, where=label),
                            roots=roots[defn.name, key],
                            loads=key is None and defn.kind in (Kind.COMMAND, Kind.SKILL),
                        )
                    )
        agents_file = [output for output in outputs if output.path is None]
        prompts += [
            [output, *(_loaded(output, outputs) if output.loads else ()), *(agents_file if output.path else ())]
            for output in outputs
        ]
    return prompts


def _loaded(output: _PromptOutput, outputs: list[_PromptOutput]) -> list[_PromptOutput]:
    """The outputs `output`'s `@` lines name, and those named by the `@` lines of each such output that
    loads, transitively, each once in first-reached order and never `output` itself. A line names an
    output when its path ends in the output's."""
    reached: list[_PromptOutput] = []
    pending = [output]
    while pending:
        current = pending.pop(0)
        named = [PurePosixPath(line[1:].strip()).parts for line in current.text.splitlines() if line.startswith("@")]
        for parts in named:
            for target in outputs:
                if target.path is None or parts[-len(target.path.parts) :] != target.path.parts:
                    continue
                if target is output or target in reached:
                    continue
                reached.append(target)
                if target.loads:
                    pending.append(target)
    return reached


def _double_clause_deliveries(sources: dict[str, str]) -> list[str]:
    """Each clause a prompt reaches twice, named with the prompt and both chains that reach it."""
    found = []
    for prompt in _prompts(sources):
        rooted = [(output.label, output.roots) for output in prompt]
        for node, *reaches in repeated_clause_reaches(_CLAUSE_GRAPH, rooted, uncounted=_SENTENCE_HOLES):
            paths = " | ".join(f"{label}: {' → '.join(chain)}" for label, chain in reaches)
            found.append(f"{prompt[0].label}: {node} reached twice — {paths}")
    return found


def _double_paragraphs(sources: dict[str, str]) -> list[str]:
    """Each prose unit a prompt carries twice, named with the prompt."""
    found = []
    for prompt in _prompts(sources):
        counts = Counter(unit for output in prompt for unit in _prose_unit_list(output.text))
        found += [
            f"{prompt[0].label}: written twice: {unit.decode()[:120]}" for unit, count in counts.items() if count > 1
        ]
    return found


@pytest.mark.parametrize("check", [_double_clause_deliveries, _double_paragraphs])
def test_no_prompt_delivers_a_span_twice(check: Callable[[dict[str, str]], list[str]]) -> None:
    sources = {f"devpro.definitions.{path.stem}": path.read_text(encoding="utf-8") for path in _DEFINITION_PATHS}
    assert sum(prompt[0].path is None for prompt in _prompts(sources)) == len(_PLUGIN_RENDERS)
    found = check(sources)
    assert found == [], "\n".join(found)


def test_a_paragraph_the_agents_file_and_an_agent_both_write_is_refused() -> None:
    source = (
        f"{_FIXTURE_HEAD}from devpro.vocabulary import ALL\n"
        "DEFINITIONS = (\n"
        'Definition(name="f", kind=Kind.AGENTS_FILE, body="Written in both.\\n\\nOwn file text."),\n'
        'Definition(name="a", kind=Kind.AGENT, description="an agent", tools=ALL, tier="high", '
        'body="Own agent text.\\n\\nWritten in both."),\n'
        ")\n"
    )
    assert _double_paragraphs({"fixture.both": source}) == ["agents/a.md: written twice: Written in both."]


def _chain_output(name: str, *loads: str) -> _PromptOutput:
    text = "\n".join(f"@commands/{target}.md" for target in loads)
    return _PromptOutput(
        label=f"commands/{name}.md", path=PurePosixPath(f"commands/{name}.md"), text=text, roots=(), loads=True
    )


def test_loaded_follows_at_lines_transitively() -> None:
    a, b, c = _chain_output("a", "b"), _chain_output("b", "c"), _chain_output("c")
    assert _loaded(a, [a, b, c]) == [b, c]


def test_loaded_terminates_on_a_cycle() -> None:
    a, b = _chain_output("a", "b"), _chain_output("b", "a")
    assert _loaded(a, [a, b]) == [b]


def test_a_clause_a_composite_already_delivers_is_refused_with_both_paths() -> None:
    sources = {
        "fixture.a": _fixture_module(("a", 'f"{clauses.CODE_PRINCIPLES_CODER}\\n\\n{clauses.MACHINE_GUARANTEES}"'))
    }
    assert _double_clause_deliveries(sources) == [
        "commands/a.md: MACHINE_GUARANTEES reached twice — "
        "commands/a.md: CODE_PRINCIPLES_CODER → MACHINE_GUARANTEES_CODER → MACHINE_GUARANTEES | "
        "commands/a.md: MACHINE_GUARANTEES"
    ]


def test_a_clause_passed_to_a_parameter_interpolated_twice_is_refused() -> None:
    sources = {"fixture.a": _fixture_module(("a", 'f"{clauses.kb_orientation_docs(when=clauses.DISSENT)}"'))}
    assert _double_clause_deliveries(sources) == [
        "commands/a.md: DISSENT reached twice — commands/a.md: DISSENT | commands/a.md: DISSENT"
    ]


def test_carried_clauses_maps_each_definition_to_the_clauses_its_call_names() -> None:
    source = (
        f"{_SKILL_FIXTURE_HEAD}DEFINITIONS = ("
        'Definition(name="c", kind=Kind.COMMAND, body=f"{clauses.kb_orientation_docs(when=clauses.DISSENT)}"),'
        'Definition(name="s", kind=Kind.SKILL, description="a skill", body="Own router.", '
        'files=(SkillFile(path="references/one.md", body=clauses.MACHINE_GUARANTEES),)),'
        ")\n"
    )
    assert carried_clauses(source) == {"c": {"kb_orientation_docs", "DISSENT"}, "s": {"MACHINE_GUARANTEES"}}


@pytest.mark.parametrize("walk", [carried_clauses, lambda source: body_roots(source, _CLAUSE_GRAPH)])
def test_a_definition_name_that_is_not_a_literal_is_refused_alike(walk: Callable[[str], object]) -> None:
    source = f'{_FIXTURE_HEAD}_NAME = "a"\nDEFINITIONS = (Definition(name=_NAME, kind=Kind.COMMAND, body="Own."),)\n'
    with pytest.raises(ValueError, match="name= is not a string literal"):
        walk(source)


@pytest.mark.parametrize(
    "call, expected",
    [
        (
            "clauses.machine_guarantees()",
            [
                "commands/a.md: MACHINE_GUARANTEES_FRAME reached twice — "
                "commands/a.md: machine_guarantees → MACHINE_GUARANTEES_FRAME | "
                "commands/a.md: MACHINE_GUARANTEES_FRAME"
            ],
        ),
        ("clauses.machine_guarantees(frame=clauses.DISSENT)", []),
    ],
)
def test_a_default_delivers_its_constant_only_where_the_call_passes_none(call: str, expected: list[str]) -> None:
    sources = {"fixture.a": _fixture_module(("a", f'f"{{{call}}}\\n\\n{{clauses.MACHINE_GUARANTEES_FRAME}}"'))}
    assert _double_clause_deliveries(sources) == expected


def test_a_command_repeating_a_clause_the_output_it_loads_carries_is_refused() -> None:
    source = (
        f"{_FIXTURE_HEAD}from devpro.vocabulary import ALL\n"
        "DEFINITIONS = (\n"
        'Definition(name="a", kind=Kind.AGENT, description="an agent", tools=ALL, tier="high", '
        'body=f"Own agent text.\\n\\n{clauses.DISSENT}"),\n'
        'Definition(name="c", kind=Kind.COMMAND, '
        'body=f"@{clauses.PROJECT_HARNESS_DIR}/agents/a.md\\n\\n{clauses.DISSENT}"),\n'
        ")\n"
    )
    sources = {"fixture.loading": source}
    assert _double_clause_deliveries(sources) == [
        "commands/c.md: DISSENT reached twice — commands/c.md: DISSENT | agents/a.md: DISSENT"
    ]
    assert _double_paragraphs(sources) == [f"commands/c.md: written twice: {devpro.clauses.DISSENT[:120]}"]


def test_a_paragraph_one_output_writes_twice_is_refused() -> None:
    sources = {"fixture.a": _fixture_module(("a", '"Written twice.\\n\\nOwn.\\n\\nWritten twice."'))}
    assert _double_paragraphs(sources) == ["commands/a.md: written twice: Written twice."]


def test_a_thematic_break_written_twice_is_not_a_paragraph() -> None:
    sources = {"fixture.a": _fixture_module(("a", '"Own.\\n\\n---\\n\\nMore.\\n\\n---\\n\\nLast."'))}
    assert _double_paragraphs(sources) == []


def test_the_import_graph_is_acyclic() -> None:
    def module_name(path: str) -> str:
        parts = PurePosixPath(path).with_suffix("").parts
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)

    graph = {
        module_name(path): {name for name in _imported(tree) if name.startswith("devpro")} for path, tree in _modules()
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
