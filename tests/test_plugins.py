"""Plugins in the render: each plugin renders under each harness with every template filled and every
reference closed, membership is validated against discovery and is exactly what a render ships, an
out-of-plugin reference refuses while an optional one drops its paragraph, and the agents file carries
the paragraphs only its plugin's definitions back."""

from __future__ import annotations

import dataclasses
import re
from typing import cast

import pytest

from adjagent.context import Render, build_render, harness_named, plugin_named
from adjagent.definition import Definition
from adjagent.errors import InputError
from adjagent.families.claude import FAMILY as CLAUDE_FAMILY
from adjagent.harness import PLUGIN_MANIFEST, Harness
from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.harnesses.opencode import HARNESS as OPENCODE
from adjagent.loading import load
from adjagent.plugin import Plugin
from adjagent.plugins.devpro import PLUGIN as DEVPRO
from adjagent.plugins.kbase import PLUGIN as KBASE
from adjagent.render import definitions, filled_body, render_agents_file, render_all, rendered_definitions
from adjagent.vocabulary import Kind, optional_reference, reference

_PLUGINS = sorted(cast(dict[str, Plugin], load("adjagent.plugins", "PLUGIN")))
_HARNESSES = sorted(cast(dict[str, Harness], load("adjagent.harnesses", "HARNESS")))
_PAIRS = [(plugin, harness) for plugin in _PLUGINS for harness in _HARNESSES]


@pytest.mark.parametrize("plugin, harness", _PAIRS)
def test_every_plugin_renders_under_every_harness_with_nothing_left_unfilled(plugin: str, harness: str) -> None:
    """A plain reference outside the plugin refuses the render, so this is also the closure test of
    each plugin: one such reference fails it, naming the citing definition."""
    ctx = build_render(harness=harness, plugin=plugin, family="claude", tier_spec=None, alias_spec=None)
    texts = [text for _, text in render_all(ctx)]
    texts.append(render_agents_file(harness_named(harness), plugin_named(plugin), scope="x"))
    leaks = [match for text in texts for match in re.findall(r"\{plugin\}|@![a-z0-9.-]+!@", text)]
    assert leaks == []


@pytest.mark.parametrize("plugin, harness", _PAIRS)
def test_a_render_ships_exactly_its_plugins_members_less_what_the_harness_omits(plugin: str, harness: str) -> None:
    ctx = build_render(harness=harness, plugin=plugin, family="claude", tier_spec=None, alias_spec=None)
    discovered = {defn.name for _, defn in definitions()}
    expected = {name for name in discovered if ctx.plugin.ships(name)} - ctx.harness.omits
    assert {defn.name for _, defn in rendered_definitions(ctx)} == expected
    assert expected
    assert ctx.harness.omits == ({"adjagent"} if harness == "mage" else set())


def test_a_plugin_naming_an_undiscovered_definition_refuses_every_render(monkeypatch: pytest.MonkeyPatch) -> None:
    misspelt = Plugin(name="probe", include=frozenset({"python-coder", "pyhton-coder"}))
    monkeypatch.setattr("adjagent.context.plugins", lambda: {"devpro": DEVPRO, "probe": misspelt})
    with pytest.raises(InputError, match=re.escape("plugin 'probe' names no discovered definition: pyhton-coder")):
        build_render(harness="claude", plugin="devpro", family="claude", tier_spec=None, alias_spec=None)


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"name": "probe"}, "give exactly one of include and exclude"),
        ({"name": "probe", "include": frozenset(), "exclude": frozenset()}, "give exactly one of include and exclude"),
        ({"name": "Probe", "include": frozenset()}, "name is not a strict-kebab identifier"),
        ({"name": "probe", "exclude": frozenset({"Bad_name"})}, "a stated definition name is not"),
    ],
)
def test_a_plugin_of_the_wrong_shape_is_refused(fields: dict, message: str) -> None:
    with pytest.raises(InputError, match=re.escape(message)):
        Plugin(**fields)


@pytest.mark.parametrize(
    "plugin, shipped, unshipped",
    [(DEVPRO, "python-coder", "kbase"), (KBASE, "kbase", "go-coder")],
    ids=["by-exclusion", "by-enumeration"],
)
def test_ships_reads_the_set_the_plugin_states(plugin: Plugin, shipped: str, unshipped: str) -> None:
    assert plugin.ships(shipped)
    assert not plugin.ships(unshipped)


def test_a_render_whose_plugin_is_replaced_binds_its_harness_to_the_new_plugin() -> None:
    devpro = Render(harness=CLAUDE, plugin=DEVPRO, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    assert (devpro.bound_harness.plugin_dir, devpro.bound_harness.reference_prefix) == ("skills/devpro", "devpro:")
    kbase = dataclasses.replace(devpro, plugin=KBASE)
    assert kbase.harness is CLAUDE
    assert (kbase.bound_harness.plugin_dir, kbase.bound_harness.reference_prefix) == ("skills/kbase", "kbase:")
    manifest = next(file for file in kbase.bound_harness.rendered_files if file.path == PLUGIN_MANIFEST.path)
    assert manifest.marker == '"name": "kbase"'


def test_binding_fills_the_guardrail_registration_marker_and_leaves_other_braces() -> None:
    assert CLAUDE.guardrail is not None
    registration = dataclasses.replace(CLAUDE.guardrail.registration, marker='{"plugin": "{plugin}"}')
    probe = dataclasses.replace(CLAUDE, guardrail=dataclasses.replace(CLAUDE.guardrail, registration=registration))
    bound = probe.bound(KBASE.name).guardrail
    assert bound is not None
    assert bound.registration.marker == '{"plugin": "kbase"}'


_PAIR = Plugin(name="pair", include=frozenset({"python-coder", "architect"}))
_PAIR_RENDER = Render(harness=CLAUDE, plugin=_PAIR, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))


def test_a_plain_reference_outside_the_shipped_set_refuses_naming_the_site_and_the_referent() -> None:
    defn = Definition(name="probe", kind=Kind.COMMAND, body=f"Hand it to {reference('tech-writer')}.")
    with pytest.raises(InputError, match=re.escape("definition 'probe': references 'tech-writer', which")):
        filled_body(defn, _PAIR_RENDER)


def test_an_optional_reference_fills_where_its_referent_ships_and_drops_its_paragraph_where_not() -> None:
    body = (
        f"Before.\n\nAsk {optional_reference('architect')} first.\n\n"
        f"Then {optional_reference('tech-writer')}, and more.\n\nAfter."
    )
    defn = Definition(name="probe", kind=Kind.COMMAND, body=body)
    assert filled_body(defn, _PAIR_RENDER) == "Before.\n\nAsk pair:architect first.\n\nAfter."


def _paragraphs(text: str) -> list[str]:
    return text.split("\n\n")


@pytest.mark.parametrize("plugin", [DEVPRO, KBASE], ids=lambda plugin: plugin.name)
@pytest.mark.parametrize("harness", [CLAUDE, OPENCODE], ids=lambda harness: harness.name)
def test_each_plugins_agents_file_carries_the_development_bullet(harness: Harness, plugin: Plugin) -> None:
    text = render_agents_file(harness, plugin, scope="x")
    development = f"{harness.bound(plugin.name).reference_prefix}development"
    assert f"load the `{development}` skill" in text


def _unprefixed_text(plugin: Plugin) -> str:
    """The plugin's claude agents file, its reference prefix and its begin marker's plugin word removed."""
    text = render_agents_file(CLAUDE, plugin, scope="x").replace(f"vvv-adjagent {plugin.name} ", "vvv-adjagent ")
    return text.replace(CLAUDE.bound(plugin.name).reference_prefix, "")


def test_the_two_agents_files_are_equal_but_for_the_plugin_name() -> None:
    assert _unprefixed_text(DEVPRO) == _unprefixed_text(KBASE)
