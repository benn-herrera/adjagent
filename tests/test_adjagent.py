"""The adjagent package's own logic, each case checked against values the
renderer did not compute: the two map flags' grammar, the rendered model text,
the CLI's Render refusals, the frontmatter tools path against literal lines of
the pre-1.0 render, overlay resolution and stock, Definition and Prose refusals,
discovery's refusal, and explain's section headers.

The package is imported from the repository root, which `just test` puts on
PYTHONPATH.
"""

import re
from types import ModuleType

import pytest

from adjagent import family as families
from adjagent import harness as harnesses
from adjagent.cli import main
from adjagent.context import TIER_MAP_FLAG, Render, build_render, parse_tier_map
from adjagent.definition import ALL, Anchor, Definition, Tool
from adjagent.definitions import definitions_of
from adjagent.errors import InputError
from adjagent.family import Family, Overlay
from adjagent.render import agent_fields
from adjagent.section import Prose

_ALL_INHERIT = dict.fromkeys(("highest", "high", "medium", "low", "lowest"), "inherit")


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
        harness=harnesses.claude,
        family=families.claude,
        tier_map=dict(families.qwen3.tiers),
        alias_map={"highest": "fable", "high": "opus", "medium": "sonnet", "low": "haiku", "lowest": "inherit"},
    )
    assert ctx.model("high") == "opus"
    assert ctx.model("lowest") == "inherit"


@pytest.mark.parametrize("harness, expected", [(harnesses.claude, "inherit"), (harnesses.opencode, "")])
def test_model_inherit_renders_the_harness_text(harness: harnesses.Harness, expected: str) -> None:
    ctx = Render(harness=harness, family=families.claude, tier_map=_ALL_INHERIT)
    assert ctx.model("medium") == expected


def test_build_render_refuses_a_model_outside_the_harness_shape() -> None:
    with pytest.raises(InputError) as caught:
        build_render(harness="opencode", family="claude", tier_spec=None, alias_spec=None)
    message = str(caught.value)
    assert "model 'fable' at tier highest" in message
    assert "--family" in message


@pytest.mark.parametrize("family", ["nonesuch", "templates/family/qwen3.toml", "qwen3.toml"])
def test_build_render_refuses_a_family_that_is_not_a_name(family: str) -> None:
    with pytest.raises(InputError, match=re.escape("claude, gemma-4, qwen3")):
        build_render(harness="claude", family=family, tier_spec=None, alias_spec=None)


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
    ctx = Render(harness=harnesses.claude, family=families.claude, tier_map=dict(families.claude.tiers))
    assert harnesses.claude.frontmatter(agent_fields(_security_reviewer(), ctx)) == (
        "name: security-reviewer",
        _SECURITY_REVIEWER_DESCRIPTION,
        "model: opus",
        'color: "#DC2626"',
        "tools: Bash, Read, Grep, Glob, Write, Edit, WebSearch, WebFetch",
    )


def test_opencode_frontmatter_matches_the_pre_1_0_render() -> None:
    ctx = Render(harness=harnesses.opencode, family=families.claude, tier_map=_ALL_INHERIT)
    assert harnesses.opencode.frontmatter(agent_fields(_security_reviewer(), ctx)) == (
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


_TUNED = Family(
    "tuned",
    {"highest": "big", "high": "big", "medium": "mid", "low": "small", "lowest": "small"},
    overlays={Anchor.GAP_AVERSION: Overlay(text="family-wide", members={"mid": "for mid"})},
)


@pytest.mark.parametrize(
    "anchor, tier, expected",
    [
        (Anchor.GAP_AVERSION, "medium", "for mid"),
        (Anchor.GAP_AVERSION, "high", "family-wide"),
        (Anchor.GAP_AVERSION, None, "family-wide"),
        (Anchor.ASK_VS_STIPULATE, "medium", ""),
    ],
)
def test_overlay_member_scope_wins(anchor: Anchor, tier: str | None, expected: str) -> None:
    ctx = Render(harness=harnesses.claude, family=_TUNED, tier_map=dict(_TUNED.tiers))
    assert ctx.overlay(anchor, tier=tier) == expected


def test_stock_excludes_the_overridden_tier() -> None:
    ctx = Render(harness=harnesses.claude, family=_TUNED, tier_map=dict(_TUNED.tiers))
    assert ctx.stock == ("highest", "high", "low", "lowest")


@pytest.mark.parametrize(
    "changes",
    [
        {"tools": ()},
        {"sections": ()},
        {"sections": (Prose("ok"), "a bare string")},
        {"description": 'holds a "quote"'},
    ],
)
def test_definition_refusals(changes: dict) -> None:
    fields = {"name": "probe", "description": "a probe", "tools": ALL, "tier": "high", "sections": (Prose("ok"),)}
    with pytest.raises(InputError, match="definition 'probe'"):
        Definition(**{**fields, **changes})


@pytest.mark.parametrize("text", ["", "edge newline\n", "\nedge newline"])
def test_prose_refuses_empty_or_edge_newline_text(text: str) -> None:
    with pytest.raises(InputError, match="prose section"):
        Prose(text)


def test_discovery_refuses_a_module_without_definitions() -> None:
    with pytest.raises(InputError, match="'adjagent.definitions.probe' defines no DEFINITIONS"):
        definitions_of(ModuleType("adjagent.definitions.probe"))


def test_explain_heads_a_section_with_its_class_and_non_default_fields(capsys: pytest.CaptureFixture[str]) -> None:
    main(["explain", "python-coder"])
    lines = capsys.readouterr().out.splitlines()
    assert "[Testing profile=Profile(language='Python') coverage_metric=True]" in lines
    assert "[ParallelExecution]" in lines
