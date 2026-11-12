"""The install verb's target, driven through `main([...])`: which harness an install selects, where
ROOT and the project root land, the refusals that leave nothing behind, a plugin's agents file, and
the agents-file verb's harness inference.

The package is imported from the repository root, which `just test` puts on PYTHONPATH.
"""

import os
from pathlib import Path

import pytest

from devpro import cli
from devpro.errors import InputError
from devpro.harnesses.claude import HARNESS as CLAUDE
from devpro.harnesses.opencode import HARNESS as OPENCODE
from devpro.plugins.devpro import PLUGIN as DEVPRO
from devpro.render import render_agents_file

_UNCOMMITTED = ("?? devpro/x.py",)


def _committed() -> tuple[str, ...]:
    return ()


def _uncommitted() -> tuple[str, ...]:
    return _UNCOMMITTED


def _refused(argv: list[str], capsys: pytest.CaptureFixture[str]) -> str:
    """The stderr of a `main(argv)` that exits 2."""
    with pytest.raises(SystemExit) as exited:
        cli.main(argv)
    assert exited.value.code == 2
    return capsys.readouterr().err


def _paths(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))


def _claude_plugin(harness_dir: Path, plugin: str = "devpro") -> Path:
    """Where a claude install of `plugin` into `harness_dir` writes it."""
    return harness_dir / CLAUDE.bound(plugin).plugin_dir


def _opencode_plugin(harness_dir: Path, plugin: str = "devpro") -> Path:
    """Where an opencode install of `plugin` into `harness_dir` writes it."""
    return harness_dir / OPENCODE.bound(plugin).plugin_dir


def test_the_suite_runs_under_a_scratch_home(_home: Path) -> None:
    """The resolver reads the home directory on every install, so the suite must never see the real one."""
    pwd = pytest.importorskip("pwd")
    assert Path.home() == _home
    assert Path.home() != Path(pwd.getpwuid(os.getuid()).pw_dir)


def test_the_harness_flag_beats_a_harness_directory_in_the_target(tmp_path: Path) -> None:
    (tmp_path / ".opencode").mkdir()
    cli.main(["install", str(tmp_path), "--harness=claude"])
    assert (_claude_plugin(tmp_path / ".claude") / "agents").is_dir()
    assert _paths(tmp_path / ".opencode") == []


def test_the_one_harness_directory_in_the_target_selects_its_harness(tmp_path: Path) -> None:
    (tmp_path / ".opencode").mkdir()
    cli.main(["install", str(tmp_path)])
    assert (_opencode_plugin(tmp_path / ".opencode") / "agents").is_dir()
    assert not (tmp_path / ".claude").exists()


def test_two_harness_directories_in_the_target_are_refused(tmp_path: Path, capsys) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".opencode").mkdir()
    err = _refused(["install", str(tmp_path)], capsys)
    assert "--harness" in err and "'.claude'" in err and "'.opencode'" in err
    assert _paths(tmp_path) == [".claude", ".opencode"]


def test_a_harness_directory_target_is_the_harness_directory_under_its_parent_as_project_root(
    tmp_path: Path,
) -> None:
    """The kb install's project-root write — the runner file — lands beside the harness directory, not
    inside it, and the set and its MCP entry land in the plugin below it."""
    harness_dir = tmp_path / ".claude"
    harness_dir.mkdir()
    cli.main(["install", str(harness_dir), "--plugin=kbase"])
    plugin = _claude_plugin(harness_dir, "kbase")
    assert (plugin / "agents").is_dir() and (plugin / ".mcp.json").is_file()
    assert not (harness_dir / ".claude").exists()
    assert (tmp_path / "Makefile").is_file()


def test_a_mage_skills_target_installs_the_plugin_with_its_agents_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _committed)
    skills = tmp_path / "Mage/Skills"
    skills.mkdir(parents=True)
    cli.main(["install", str(skills)])
    plugin = skills / "devpro"
    assert (plugin / ".claude-plugin/plugin.json").is_file()
    assert (plugin / "CLAUDE.md").is_file()


@pytest.mark.parametrize(("cwd", "target"), [("proj/.claude/agents", ".."), ("proj", ".claude")])
@pytest.mark.parametrize("harness_args", [[], ["--harness=claude"]], ids=["detected", "flagged"])
def test_a_relative_target_is_matched_as_the_directory_it_names(
    tmp_path: Path, monkeypatch, cwd: str, target: str, harness_args: list[str]
) -> None:
    harness_dir = tmp_path / "proj/.claude"
    (harness_dir / "agents").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / cwd)
    cli.main(["install", target, *harness_args])
    assert (_claude_plugin(harness_dir) / "agents/python-coder.md").is_file()
    assert not (harness_dir / ".claude").exists()


@pytest.mark.parametrize(
    "subdir",
    ["../escape", "{tmp}/elsewhere", "nested/../../escape"],
    ids=["escaping", "absolute", "escaping-after-a-descent"],
)
def test_a_subdir_that_leaves_the_target_is_refused(tmp_path: Path, capsys, subdir: str) -> None:
    (tmp_path / "proj").mkdir()
    argv = ["install", str(tmp_path / "proj"), "--harness=claude", f"--subdir={subdir.format(tmp=tmp_path)}"]
    assert "must name a directory inside the target" in _refused(argv, capsys)
    assert _paths(tmp_path) == ["proj"]


def test_an_unexpanded_home_target_is_refused_naming_the_tilde(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert "'~' was not expanded" in _refused(["install", "~/proj", "--harness=claude"], capsys)
    assert _paths(tmp_path) == []


def test_an_install_naming_an_unknown_plugin_is_refused(tmp_path: Path, capsys) -> None:
    err = _refused(["install", str(tmp_path), "--plugin=nosuch", "--harness=claude"], capsys)
    assert "invalid choice" in err and "devpro" in err and "kbase" in err
    assert _paths(tmp_path) == []


def test_a_target_naming_no_harness_is_refused(tmp_path: Path, capsys) -> None:
    err = _refused(["install", str(tmp_path)], capsys)
    assert "--harness" in err and all(name in err for name in ("claude", "mage", "opencode"))
    assert _paths(tmp_path) == []


@pytest.mark.parametrize("name", ["claude-work", "my-opencode", "mage"])
def test_a_harness_name_in_the_target_path_selects_nothing(tmp_path: Path, capsys, name: str) -> None:
    target = tmp_path / name
    target.mkdir()
    assert "cannot tell the harness" in _refused(["install", str(target)], capsys)
    assert _paths(target) == []


def test_a_nonexistent_target_is_refused(tmp_path: Path, capsys) -> None:
    target = tmp_path / "absent"
    assert "install target" in _refused(["install", str(target), "--harness=claude"], capsys)
    assert not target.exists()


def test_a_refused_install_leaves_no_root_behind(tmp_path: Path, capsys) -> None:
    (tmp_path / "justfile").write_bytes(b"\xff\n")
    err = _refused(["install", str(tmp_path), "--plugin=kbase", "--harness=claude", "--subdir=nested/root"], capsys)
    assert "not readable UTF-8" in err
    assert _paths(tmp_path) == ["justfile"]


def test_a_mage_install_below_its_project_with_uncommitted_sources_writes_its_agents_file(
    tmp_path: Path, monkeypatch
) -> None:
    """A project install guards no live operator configuration, so the commit state refuses nothing."""
    monkeypatch.setattr(cli, "uncommitted_sources", _uncommitted)
    skills = tmp_path / "Mage/Skills"
    skills.mkdir(parents=True)
    cli.main(["install", str(skills)])
    assert (skills / "devpro/CLAUDE.md").is_file()


def test_a_mage_install_into_the_target_itself_writes_no_agents_file(tmp_path: Path, monkeypatch) -> None:
    """The slot render and mage-dist path: ROOT is the project root, so there is no agents file to
    install and the commit state is never read — an uncommitted tree would otherwise refuse."""
    monkeypatch.setattr(cli, "uncommitted_sources", _uncommitted)
    cli.main(["install", str(tmp_path), "--subdir=", "--harness=mage"])
    assert (tmp_path / ".claude-plugin/plugin.json").is_file()
    assert not (tmp_path / "CLAUDE.md").exists()


@pytest.mark.parametrize("harness", [[], ["--harness="]], ids=["absent", "empty"])
def test_the_agents_file_harness_is_inferred_from_a_user_directory(
    tmp_path: Path, monkeypatch, harness: list[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli, "uncommitted_sources", _committed)
    user_dir = tmp_path / ".claude"
    user_dir.mkdir()
    cli.main(["install-agents-file", str(user_dir), *harness])
    assert (user_dir / "CLAUDE.md").read_text(encoding="utf-8") == render_agents_file(CLAUDE, DEVPRO, scope="Global")


def test_an_agents_file_harness_given_as_a_positional_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _committed)
    project = tmp_path / "project"
    project.mkdir()
    assert "unrecognized arguments: claude" in _refused(["install-agents-file", str(project), "claude"], capsys)
    assert _paths(project) == []


def test_a_project_directory_without_a_harness_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    err = _refused(["install-agents-file", str(project)], capsys)
    assert "claude, opencode" in err and "just" not in err
    assert _paths(project) == []


@pytest.mark.parametrize(
    ("present", "harness_args", "root", "set_dir"),
    [
        ([".claude"], [], ".claude", f".claude/{CLAUDE.bound('devpro').plugin_dir}"),
        ([".config/opencode"], [], ".config/opencode", f".config/opencode/{OPENCODE.bound('devpro').plugin_dir}"),
        (
            [".claude", ".config/opencode"],
            ["--harness=opencode"],
            ".config/opencode",
            f".config/opencode/{OPENCODE.bound('devpro').plugin_dir}",
        ),
    ],
    ids=["claude", "opencode", "both-with-harness"],
)
def test_a_home_directory_target_installs_user_level_into_the_user_directory(
    _home: Path, present: list[str], harness_args: list[str], root: str, set_dir: str
) -> None:
    for directory in present:
        (_home / directory).mkdir(parents=True)
    cli.main(["install", str(_home), *harness_args])
    assert (_home / set_dir / "agents").is_dir()
    assert not (_home / root / ".claude").exists() and not (_home / root / ".opencode").exists()
    assert not (_home / set_dir / "hooks").exists() and not (_home / set_dir / "guardrail.ts").exists()
    assert all(_paths(_home / other) == [] for other in present if other != root)


def test_another_harness_s_user_directory_name_is_a_project_install(_home: Path) -> None:
    _home.mkdir()
    cli.main(["install", str(_home), "--harness=opencode", "--subdir=.claude"])
    assert (_opencode_plugin(_home / ".claude") / "guardrail.ts").is_file()


def test_a_home_directory_holding_both_user_directories_is_refused(_home: Path, capsys) -> None:
    (_home / ".claude").mkdir(parents=True)
    (_home / ".config/opencode").mkdir(parents=True)
    assert "--harness" in _refused(["install", str(_home)], capsys)
    assert _paths(_home) == [".claude", ".config", ".config/opencode"]


def test_a_claude_user_level_kb_install_writes_the_definitions_and_the_plugins_mcp_entry(_home: Path) -> None:
    """The plugin's own `.mcp.json` is inside the plugin, so a user-level kb install writes it; nothing
    else beside the definitions, and no user settings file."""
    root = _home / ".claude"
    root.mkdir(parents=True)
    cli.main(["install", str(root), "--plugin=kbase"])
    plugin = _claude_plugin(root, "kbase")
    assert (plugin / "agents").is_dir() and (plugin / "skills/kbase/SKILL.md").is_file()
    assert (plugin / ".mcp.json").is_file()
    absent = [
        f"{plugin.relative_to(root)}/hooks/guardrail.pl",
        f"{plugin.relative_to(root)}/skills/kbase/kb-tools",
        "CLAUDE.md",
        "settings.json",
    ]
    assert not any((root / path).exists() for path in absent)
    assert not any((_home / path).exists() for path in ["Makefile", ".mcp.json", ".claude.json"])


def test_an_opencode_user_level_kb_install_writes_no_guardrail_or_settings(_home: Path) -> None:
    root = _home / ".config/opencode"
    root.mkdir(parents=True)
    cli.main(["install", str(root), "--plugin=kbase"])
    plugin = _opencode_plugin(root, "kbase")
    assert (plugin / "skills/kbase/SKILL.md").is_file()
    assert not (plugin / "guardrail.ts").exists()
    assert not [path for path in _paths(_home) if Path(path).name in ("opencode.json", "opencode.jsonc")]


def test_the_agents_file_verb_into_a_user_directory_with_uncommitted_sources_writes_nothing(
    _home: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _uncommitted)
    (_home / ".claude").mkdir(parents=True)
    assert "uncommitted changes" in _refused(["install-agents-file", str(_home / ".claude")], capsys)
    assert _paths(_home) == [".claude"]


def test_the_agents_file_verb_into_a_user_directory_reads_the_commit_state_once(_home: Path, monkeypatch) -> None:
    reads: list[None] = []

    def counted() -> tuple[str, ...]:
        reads.append(None)
        return ()

    monkeypatch.setattr(cli, "uncommitted_sources", counted)
    (_home / ".claude").mkdir(parents=True)
    cli.main(["install-agents-file", str(_home / ".claude")])
    assert (_home / ".claude" / CLAUDE.agents_file).is_file()
    assert len(reads) == 1


def _failed_git_status() -> tuple[str, ...]:
    raise InputError("git status failed")


def test_a_failed_git_status_refuses_the_agents_file_into_a_user_directory_only(
    _home: Path, tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _failed_git_status)
    project = tmp_path / "project"
    project.mkdir()
    cli.main(["install-agents-file", str(project), "--harness=claude"])
    assert (project / "CLAUDE.md").is_file()
    (_home / ".claude").mkdir(parents=True)
    assert "git status failed" in _refused(["install-agents-file", str(_home / ".claude")], capsys)
    assert _paths(_home) == [".claude"]


def test_a_non_directory_above_the_install_directory_is_not_examined(tmp_path: Path, monkeypatch, capsys) -> None:
    """`.claude/skills` sits between the harness directory and the install directory: the operator's own,
    so the destination refusal does not name it and the install ends in the operating system's failure,
    reported as an error line."""
    monkeypatch.setattr(cli, "uncommitted_sources", _committed)
    harness_dir = tmp_path / ".claude"
    harness_dir.mkdir()
    (harness_dir / "skills").write_text("mine\n", encoding="utf-8")
    err = _refused(["install", str(tmp_path), "--harness=claude"], capsys)
    assert err.startswith("error: ") and str(harness_dir / "skills") in err
    assert "did not write" not in err
