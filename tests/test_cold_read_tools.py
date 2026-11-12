"""The shipped `cold-read.sh`, run as a consumer runs it: each case on a copy of the script placed in a
harness directory of its own project, under opencode the copy a real install ships, with stub `claude` and `opencode` first on the subprocess's PATH
and the session markers set only where the case sets them. No case makes a model call.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

from devpro import cli
from devpro.context import DEFAULT_FAMILY, build_render
from devpro.harness import Harness
from devpro.install_base import PACKAGE_ROOT
from devpro.loading import load
from devpro.render import filled_body, rendered_definitions

_SCRIPT = PACKAGE_ROOT / "development-tools" / "cold-read.sh"

_CLAUDE_COPY = Path(".claude/skills/devpro/skills/development/scripts")
_OPENCODE_COPY = Path(".opencode/plugins/devpro/skills/development/scripts")

# Records what the harness would have seen, into the directory STUB_RECORD names, then replies.
_STUB = """#!/usr/bin/env bash
printf '%s\\0' "$@" > "${STUB_RECORD}/argv"
pwd -P > "${STUB_RECORD}/cwd"
ls -ld . | cut -c1-10 > "${STUB_RECORD}/mode"
find . | sort > "${STUB_RECORD}/tree"
printf '%s' "${OPENCODE_CONFIG_CONTENT-unset}" > "${STUB_RECORD}/config"
if [[ -d .opencode ]]; then cp -R .opencode "${STUB_RECORD}/opencode-copy"; fi
cat > "${STUB_RECORD}/stdin"
printf '%s' "${STUB_STDERR:-}" >&2
printf '%s' "${STUB_STDOUT-the reply}"
exit "${STUB_EXIT:-0}"
"""

_NOT_LOADED = "--agent 'devpro:ghost' not found. Available agents: general-purpose, Explore"

# What the opencode fixture sets on the architect's record: a description whose colon and quotes a
# pattern match would mangle, and a model, which a real install leaves out.
_ARCHITECT_FIELDS = {"description": 'Architect: a "design" agent', "model": {"providerID": "prov", "id": "big-model"}}


def _place(tmp_path: Path, copy: Path) -> Path:
    """A project holding the script at `copy`: a copy of it under a claude plugin root, or the copy a real
    opencode install of devpro ships, its registry's architect record given `_ARCHITECT_FIELDS`."""
    project = tmp_path / "proj"
    if copy.parts[0] == ".claude":
        directory = project / copy
        directory.mkdir(parents=True)
        shutil.copy2(_SCRIPT, directory / "cold-read.sh")
        (project / _CLAUDE_COPY.parent.parent.parent / ".claude-plugin").mkdir()
        return directory / "cold-read.sh"
    project.mkdir()
    cli.main(["install", str(project), "--harness=opencode"])
    registry_path = project / _OPENCODE_COPY.parents[2] / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    next(record for record in registry["agents"] if record["id"] == "devpro-architect").update(_ARCHITECT_FIELDS)
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    return project / copy / "cold-read.sh"


def _rendered_body(name: str) -> str:
    """The text the opencode render of devpro writes below the banner of the definition `name`."""
    ctx = build_render(harness="opencode", plugin="devpro", family=DEFAULT_FAMILY, tier_spec=None, alias_spec=None)
    defn = next(defn for _, defn in rendered_definitions(ctx) if defn.name == name)
    return filled_body(defn, ctx) + "\n"


def _stubs(tmp_path: Path) -> Path:
    stubbin = tmp_path / "stubbin"
    stubbin.mkdir()
    for name in ("claude", "opencode"):
        (stubbin / name).write_text(_STUB, encoding="utf-8")
        (stubbin / name).chmod(0o755)
    return stubbin


def _tree(root: Path) -> set[Path]:
    return set(root.rglob("*"))


class _Run:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.record = tmp_path / "record"
        self.record.mkdir()
        self.stubbin = _stubs(tmp_path)
        self.loc = tmp_path / "loc"
        self.loc.mkdir()
        self.brief = tmp_path / "work" / "brief.md"
        self.brief.parent.mkdir()
        self.brief.write_bytes(b"What is the question?\nline two\n")

    def __call__(
        self, script: Path, *args: str, loc: Path | str | None = None, **extra: str
    ) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": os.pathsep.join([str(self.stubbin), "/bin", "/usr/bin"]),
            "HOME": os.environ["HOME"],
            "STUB_RECORD": str(self.record),
            **extra,
        }
        if loc is not None:
            env["DEVPRO_COLD_READ_DIR"] = str(loc)
        return subprocess.run(
            [str(script), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
        )

    def recorded(self, name: str) -> str:
        return (self.record / name).read_text(encoding="utf-8")

    def argv(self) -> list[str]:
        return self.recorded("argv").split("\0")[:-1]


@pytest.fixture
def run(tmp_path: Path) -> _Run:
    return _Run(tmp_path)


@pytest.fixture
def claude_script(tmp_path: Path) -> Path:
    return _place(tmp_path, _CLAUDE_COPY)


@pytest.fixture
def opencode_script(tmp_path: Path) -> Path:
    return _place(tmp_path, _OPENCODE_COPY)


def _refused_with_nothing_created(
    run: _Run, script: Path, loc: Path | str | None, *, says: str, agent: str = "devpro:architect"
) -> None:
    before = _tree(run.tmp_path)
    result = run(script, agent, str(run.brief), loc=loc)
    assert result.returncode == 1
    assert says in result.stderr
    assert _tree(run.tmp_path) == before
    assert not (run.record / "argv").exists()


def test_a_location_not_given_is_refused(run: _Run, claude_script: Path) -> None:
    _refused_with_nothing_created(run, claude_script, None, says="DEVPRO_COLD_READ_DIR is not set")


def test_a_location_that_is_not_a_directory_is_refused(run: _Run, claude_script: Path) -> None:
    (run.tmp_path / "file").write_text("x", encoding="utf-8")
    _refused_with_nothing_created(run, claude_script, run.tmp_path / "file", says="not a directory")


def test_a_location_inside_the_project_is_refused(run: _Run, claude_script: Path) -> None:
    inside = run.tmp_path / "proj" / "scratch"
    inside.mkdir()
    _refused_with_nothing_created(run, claude_script, inside, says="inside the project")


def test_an_instruction_file_above_the_location_is_refused_by_name(run: _Run, claude_script: Path) -> None:
    (run.tmp_path / "above").mkdir()
    (run.tmp_path / "above" / "AGENTS.md").write_text("x", encoding="utf-8")
    (run.tmp_path / "above" / "loc").mkdir()
    _refused_with_nothing_created(
        run, claude_script, run.tmp_path / "above" / "loc", says=str(run.tmp_path / "above" / "AGENTS.md")
    )


def test_the_users_own_claude_directory_above_the_location_is_exempt(run: _Run, claude_script: Path) -> None:
    home = Path(os.environ["HOME"])
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "CLAUDE.md").write_text("global", encoding="utf-8")
    (home / "loc").mkdir()
    result = run(claude_script, "devpro:architect", str(run.brief), loc=home / "loc")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("where", ["tools", "devpro/skills/development/scripts"])
def test_a_copy_under_no_claude_or_opencode_directory_refuses_naming_both(
    run: _Run, tmp_path: Path, where: str
) -> None:
    directory = tmp_path / where
    directory.mkdir(parents=True)
    shutil.copy2(_SCRIPT, directory / "cold-read.sh")
    result = run(directory / "cold-read.sh", "devpro:architect", str(run.brief), loc=run.loc)
    assert result.returncode == 1
    assert "claude" in result.stderr and "opencode" in result.stderr
    assert list(run.loc.iterdir()) == []


@pytest.mark.parametrize(
    ("copy", "marker", "refused"),
    [
        (_CLAUDE_COPY, {"OPENCODE_TERMINAL": "1"}, True),
        (_OPENCODE_COPY, {"CLAUDECODE": "1"}, True),
        (_CLAUDE_COPY, {"OPENCODE_TERMINAL": "1", "CLAUDECODE": "1"}, False),
        (_OPENCODE_COPY, {"OPENCODE_TERMINAL": "1", "CLAUDECODE": "1"}, False),
        (_CLAUDE_COPY, {}, False),
        (_OPENCODE_COPY, {}, False),
        (_CLAUDE_COPY, {"CLAUDECODE": "1"}, False),
        (_OPENCODE_COPY, {"OPENCODE_TERMINAL": "1"}, False),
    ],
)
def test_a_session_of_the_other_harness_is_refused(
    run: _Run, tmp_path: Path, copy: Path, marker: dict[str, str], refused: bool
) -> None:
    script = _place(tmp_path, copy)
    result = run(script, "devpro:architect", str(run.brief), loc=run.loc, **marker)
    if refused:
        assert result.returncode == 1
        assert ".claude" in result.stderr and ".opencode" in result.stderr
        assert list(run.loc.iterdir()) == []
    else:
        assert result.returncode == 0, result.stderr


def test_a_brief_starting_with_a_dash_is_refused_for_opencode_only(
    run: _Run, tmp_path: Path, opencode_script: Path
) -> None:
    run.brief.write_bytes(b"--version\nand more\n")
    result = run(opencode_script, "devpro:architect", str(run.brief), loc=run.loc)
    assert result.returncode == 1
    assert "starts with '-'" in result.stderr
    assert not (run.record / "argv").exists()
    claude_script = _place(tmp_path / "other", _CLAUDE_COPY)
    assert run(claude_script, "devpro:architect", str(run.brief), loc=run.loc).returncode == 0


def test_wrong_argument_counts_exit_two(run: _Run, claude_script: Path) -> None:
    assert run(claude_script, "devpro:architect", loc=run.loc).returncode == 2


def test_claude_reads_the_brief_on_stdin_with_no_tools_from_an_empty_run_directory(
    run: _Run, claude_script: Path
) -> None:
    result = run(claude_script, "devpro:architect", str(run.brief), loc=run.loc)
    assert result.returncode == 0, result.stderr
    plugin_root = claude_script.resolve().parents[3]
    assert (plugin_root / ".claude-plugin").is_dir()
    assert run.argv() == [
        "-p", "--tools", "", "--plugin-dir", str(plugin_root), "--agent", "devpro:architect",
        "--no-session-persistence",
    ]  # fmt: skip
    assert run.recorded("stdin") == run.brief.read_text(encoding="utf-8")
    assert run.recorded("mode").strip() == "drwx------"
    cwd = Path(run.recorded("cwd").strip())
    assert cwd.parent == run.loc.resolve()
    assert run.recorded("tree").splitlines() == ["."]
    output = run.brief.parent / "brief-devpro-architect.md"
    assert output.read_text(encoding="utf-8") == "the reply"
    assert result.stdout == f"{output}\n"
    assert list(run.loc.iterdir()) == []


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ({"DEVPRO_COLD_READ_MODEL": "opus"}, ["--model", "opus"]),
        ({"DEVPRO_COLD_READ_MODEL": ""}, []),
        ({}, []),
    ],
    ids=["set", "empty", "unset"],
)
@pytest.mark.parametrize("copy", [_CLAUDE_COPY, _OPENCODE_COPY])
def test_the_model_variable_adds_model_to_the_harness_call_only_when_set_and_not_empty(
    run: _Run, tmp_path: Path, copy: Path, model: dict[str, str], expected: list[str]
) -> None:
    script = _place(tmp_path, copy)
    result = run(script, "devpro:architect", str(run.brief), loc=run.loc, **model)
    assert result.returncode == 0, result.stderr
    argv = run.argv()
    assert argv.count("--model") == len(expected) // 2
    if expected:
        at = argv.index("--model")
        assert argv[at : at + 2] == expected
        if copy == _OPENCODE_COPY:
            assert argv[-1] == run.brief.read_text(encoding="utf-8").rstrip("\n"), "the message stays last"


def test_a_third_argument_names_the_output(run: _Run, claude_script: Path) -> None:
    out = run.tmp_path / "elsewhere.txt"
    result = run(claude_script, "devpro:architect", str(run.brief), str(out), loc=run.loc)
    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{out}\n"
    assert out.read_text(encoding="utf-8") == "the reply"
    assert not (run.brief.parent / "brief-devpro-architect.md").exists()


def test_claude_not_loading_the_agent_is_reported_with_its_list_and_keeps_no_output(
    run: _Run, claude_script: Path
) -> None:
    result = run(claude_script, "devpro:ghost", str(run.brief), loc=run.loc, STUB_EXIT="1", STUB_STDERR=_NOT_LOADED)
    assert result.returncode == 1
    assert "did not load devpro:ghost" in result.stderr
    assert "Available agents: general-purpose, Explore" in result.stderr
    assert "trust" not in result.stderr
    assert not (run.brief.parent / "brief-devpro-ghost.md").exists()
    assert list(run.loc.iterdir()) == []


@pytest.mark.parametrize(
    ("name", "fields"),
    [
        ("architect", 'description: "Architect: a \\"design\\" agent"\nmodel: "prov/big-model"\n'),
        ("python-coder", None),
    ],
)
def test_opencode_gets_the_brief_as_its_message_and_an_agent_file_composed_from_its_registry_record(
    run: _Run, opencode_script: Path, name: str, fields: str | None
) -> None:
    """`fields` is the frontmatter above `mode`; None is the record's own description and no model."""
    if fields is None:
        registry = json.loads((opencode_script.parents[3] / "registry.json").read_text(encoding="utf-8"))
        record = next(record for record in registry["agents"] if record["id"] == f"devpro-{name}")
        fields = f"description: {json.dumps(record['description'])}\n"
    composed = f'---\n{fields}mode: subagent\npermission:\n  "*": deny\n---\n{_rendered_body(name)}'
    result = run(opencode_script, f"devpro:{name}", str(run.brief), loc=run.loc)
    assert result.returncode == 0, result.stderr
    assert run.argv() == [
        "run", "--archived", "--agent", f"devpro-{name}", "What is the question?\nline two",
    ]  # fmt: skip
    assert "--auto" not in run.argv()
    assert run.recorded("config") == "unset"
    assert run.recorded("stdin") == ""
    assert run.recorded("mode").strip() == "drwx------"
    assert Path(run.recorded("cwd").strip()).parent == run.loc.resolve()
    assert run.recorded("tree").splitlines() == [
        ".", "./.opencode", "./.opencode/agents", f"./.opencode/agents/devpro-{name}.md",
    ]  # fmt: skip
    copy = run.record / "opencode-copy" / "agents" / f"devpro-{name}.md"
    assert copy.read_text(encoding="utf-8") == composed
    assert (run.brief.parent / f"brief-devpro-{name}.md").read_text(encoding="utf-8") == "the reply"
    assert list(run.loc.iterdir()) == []


def test_an_agent_with_no_registry_record_is_refused_by_name(run: _Run, opencode_script: Path) -> None:
    _refused_with_nothing_created(
        run,
        opencode_script,
        run.loc,
        says="no registry record for devpro-ghost",
        agent="devpro:ghost",
    )


def test_an_opencode_copy_with_no_registry_above_it_is_refused(run: _Run, tmp_path: Path) -> None:
    directory = tmp_path / "proj" / _OPENCODE_COPY
    directory.mkdir(parents=True)
    shutil.copy2(_SCRIPT, directory / "cold-read.sh")
    _refused_with_nothing_created(run, directory / "cold-read.sh", run.loc, says="no registry.json above this script")


@pytest.mark.parametrize("copy", [_CLAUDE_COPY, _OPENCODE_COPY])
def test_a_failing_harness_removes_the_run_directory_and_the_output(run: _Run, tmp_path: Path, copy: Path) -> None:
    script = _place(tmp_path, copy)
    result = run(script, "devpro:architect", str(run.brief), loc=run.loc, STUB_EXIT="3", STUB_STDERR="boom")
    assert result.returncode == 1
    assert "boom" in result.stderr
    assert list(run.loc.iterdir()) == []
    assert not (run.brief.parent / "brief-devpro-architect.md").exists()


def _harnesses() -> dict[str, Harness]:
    loaded = cast(dict[str, Harness], load("devpro.harnesses", "HARNESS"))
    return {name: harness.bound("devpro") for name, harness in loaded.items()}


def test_the_scripts_harness_directory_names_are_the_profiles() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    harnesses = _harnesses()
    claude = re.search(r'^readonly CLAUDE_DIR="([^"]+)"$', source, re.MULTILINE)
    opencode = re.search(r'^readonly OPENCODE_DIR="([^"]+)"$', source, re.MULTILINE)
    assert claude and opencode
    assert claude.group(1) == harnesses["claude"].project_harness_dir
    assert opencode.group(1) == harnesses["opencode"].project_harness_dir


def test_every_harnesss_agents_file_is_an_instruction_name() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    block = re.search(r"^readonly INSTRUCTION_NAMES=\(([^)]*)\)", source, re.MULTILINE)
    assert block
    names = block.group(1).split()
    for harness in _harnesses().values():
        assert harness.agents_file in names
