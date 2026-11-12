"""Opencode's plugin entry, `index.ts`, run under `bun` against a stub plugin context over a real opencode
install of `kbase`, whose registry gains a command record, a model and a permission map: what it
registers is what the registry lists, with each body's banner stripped; an edited body and a dropped record take effect on the
reload its watcher triggers; a command reads its body when it runs; and its cleanup closes the watcher.
A user-level install, which ships no guardrail beside the entry, registers the same way and hooks nothing.
A missing `bun` fails rather than skips, as in `tests/test_guardrail.py`.
"""

from __future__ import annotations

import functools
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from devpro import cli
from devpro.context import DEFAULT_FAMILY, build_render
from devpro.harnesses.opencode import HARNESS as OPENCODE
from devpro.plugins.kbase import PLUGIN as KBASE
from devpro.render import filled_body, render_definition, rendered_definitions

_RUNNER = Path(__file__).parent / "opencode_entry_runner.ts"


@functools.cache
def _banner_lines() -> int:
    """How many lines the opencode render writes above a definition's body."""
    ctx = build_render(harness=OPENCODE.name, plugin=KBASE.name, family=DEFAULT_FAMILY, tier_spec=None, alias_spec=None)
    module, defn = rendered_definitions(ctx)[0]
    text = render_definition(defn, ctx, module=module)
    return text[: len(text) - len(filled_body(defn, ctx) + "\n")].count("\n")


def _banner(text: str) -> str:
    return "".join(text.splitlines(keepends=True)[: _banner_lines()])


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[len(_banner(text)) :]


def _installed(target: Path, *, harness_dir: Path) -> tuple[Path, dict]:
    """A real opencode install of kbase into `target`, whose harness directory is `harness_dir`: its
    plugin directory and its registry."""
    if shutil.which("bun") is None:
        pytest.fail("bun is not on PATH: the opencode entry cannot run without it")
    cli.main(["install", str(target), f"--plugin={KBASE.name}", "--harness=opencode"])
    plugin = harness_dir / OPENCODE.bound(KBASE.name).plugin_dir
    return plugin, json.loads((plugin / "registry.json").read_text(encoding="utf-8"))


def _add_probe_command(plugin: Path, registry: dict, *, banner: str) -> Path:
    """Plant a command body and its record in `registry`, returning the body's path."""
    command_path = plugin / "commands/probe.md"
    command_path.parent.mkdir()
    command_path.write_text(f"{banner}Old command.\n", encoding="utf-8")
    registry["commands"] = [{"id": "kbase-probe", "file": "commands/probe.md", "description": "A probe"}]
    return command_path


def _run_entry(plugin: Path, *, directory: Path, writes: list[dict], command: dict) -> dict:
    """The runner's output for the entry installed in `plugin`."""
    done = subprocess.run(
        ["bun", str(_RUNNER)],
        input=json.dumps(
            {
                "entry": str(plugin / OPENCODE.entry_resource),
                "directory": str(directory),
                "writes": writes,
                "command": command,
            }
        ),
        capture_output=True,
        encoding="utf-8",
        # A watcher the entry's cleanup left open keeps the runner from exiting.
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_opencode_entry_registers_and_reloads_what_the_plugin_holds(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    plugin, registry = _installed(project, harness_dir=project / OPENCODE.project_harness_dir)
    registry_path = plugin / "registry.json"
    edited, removed, *_ = registry["agents"]
    banner = _banner((plugin / edited["file"]).read_text(encoding="utf-8"))

    command_path = _add_probe_command(plugin, registry, banner=banner)
    edited["model"] = {"providerID": "omlx", "id": "Qwen3.8-Flash-Next"}
    edited["permission"] = {"read": "allow", "shell": "deny", "subagent": "deny"}
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    without_removed = {**registry, "agents": [a for a in registry["agents"] if a["id"] != removed["id"]]}
    bodies = {record["id"]: _body(plugin / record["file"]) for record in registry["agents"] + registry["skills"]}

    out = _run_entry(
        plugin,
        directory=project,
        writes=[
            {"path": str(plugin / edited["file"]), "text": f"{banner}New body.\n"},
            {"path": str(registry_path), "text": json.dumps(without_removed)},
        ],
        command={"name": "kbase-probe", "path": str(command_path), "text": f"{banner}New command.\n", "user": "go"},
    )
    first, after_edit, after_removal = out["states"]

    assert out["id"] == KBASE.name
    assert out["hooks"] == ["execute.before"]
    assert set(first["agents"]) == {a["id"] for a in registry["agents"]}
    assert set(first["skills"]) == {s["id"] for s in registry["skills"]}
    assert first["commands"] == {"kbase-probe": "A probe"}
    assert first["mcp"] == registry["mcp"] != {}
    for record in registry["agents"]:
        assert first["agents"][record["id"]]["system"] == bodies[record["id"]]
    for record in registry["skills"]:
        registered = first["skills"][record["id"]]
        assert registered["content"] == bodies[record["id"]]
        assert registered["path"] == str(plugin / record["file"])
    assert first["agents"][edited["id"]]["model"] == {"providerID": "omlx", "id": "Qwen3.8-Flash-Next"}
    assert first["agents"][edited["id"]]["permissions"][-3:] == [
        {"action": "read", "resource": "*", "effect": "allow"},
        {"action": "shell", "resource": "*", "effect": "deny"},
        {"action": "subagent", "resource": "*", "effect": "deny"},
    ]

    assert after_edit["agents"][edited["id"]]["system"] == "New body.\n"
    assert set(after_removal["agents"]) == set(first["agents"]) - {removed["id"]}
    assert out["prompts"] == ["Old command.\n\ngo", "New command.\n\ngo"]


def test_a_user_level_opencode_entry_with_no_guardrail_beside_it_registers_and_hooks_nothing(tmp_path: Path) -> None:
    OPENCODE.user_dir.mkdir(parents=True)
    plugin, registry = _installed(OPENCODE.user_dir, harness_dir=OPENCODE.user_dir)
    assert not (plugin / "guardrail.ts").exists()
    banner = _banner((plugin / registry["agents"][0]["file"]).read_text(encoding="utf-8"))
    command_path = _add_probe_command(plugin, registry, banner=banner)
    (plugin / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()

    out = _run_entry(
        plugin,
        directory=project,
        writes=[],
        command={"name": "kbase-probe", "path": str(command_path), "text": f"{banner}New command.\n", "user": "go"},
    )

    assert out["hooks"] == []
    (registered,) = out["states"]
    assert set(registered["agents"]) == {a["id"] for a in registry["agents"]}
    assert set(registered["skills"]) == {s["id"] for s in registry["skills"]}
    assert registered["commands"] == {"kbase-probe": "A probe"}
    assert registered["mcp"] == registry["mcp"] != {}
