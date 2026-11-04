"""The install verb's target, driven through `main([...])`: which harness an install selects, where
ROOT and the project root land, the refusals that leave nothing behind, a plugin's agents file, and
the agents-file verb's harness inference.

The package is imported from the repository root, which `just test` puts on PYTHONPATH.
"""

from pathlib import Path

import pytest

from adjagent import cli
from adjagent.harnesses.claude import HARNESS as CLAUDE
from adjagent.render import render_agents_file

_UNCOMMITTED = ("?? adjagent/x.py",)


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


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch) -> Path:
    """A home directory under `tmp_path`, created by the tests that use it: the resolver reads the home
    directory on every install, and no test reads the real one."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    return home


def test_the_harness_flag_beats_a_harness_directory_in_the_target(tmp_path: Path) -> None:
    (tmp_path / ".opencode").mkdir()
    cli.main(["install", str(tmp_path), "--harness=claude"])
    assert (tmp_path / ".claude/agents").is_dir()
    assert _paths(tmp_path / ".opencode") == []


def test_the_one_harness_directory_in_the_target_selects_its_harness(tmp_path: Path) -> None:
    (tmp_path / ".opencode").mkdir()
    cli.main(["install", str(tmp_path)])
    assert (tmp_path / ".opencode/agents").is_dir()
    assert not (tmp_path / ".claude").exists()


def test_two_harness_directories_in_the_target_are_refused(tmp_path: Path, capsys) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".opencode").mkdir()
    err = _refused(["install", str(tmp_path)], capsys)
    assert "--harness" in err and "'.claude'" in err and "'.opencode'" in err
    assert _paths(tmp_path) == [".claude", ".opencode"]


def test_a_harness_directory_target_is_root_under_its_parent_as_project_root(tmp_path: Path) -> None:
    """The kb install's project-root writes — the MCP entry and the runner file — land beside the
    harness directory, not inside it."""
    root = tmp_path / ".claude"
    root.mkdir()
    cli.main(["install", str(root), "--with-kb"])
    assert (root / "agents").is_dir()
    assert not (root / ".claude").exists()
    assert (tmp_path / ".mcp.json").is_file() and (tmp_path / "Makefile").is_file()


def test_a_mage_skills_target_installs_the_plugin_with_its_agents_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _committed)
    skills = tmp_path / "Mage/Skills"
    skills.mkdir(parents=True)
    cli.main(["install", str(skills)])
    plugin = skills / "adjagent"
    assert (plugin / ".claude-plugin/plugin.json").is_file()
    assert (plugin / "CLAUDE.md").is_file()


@pytest.mark.parametrize(("cwd", "target"), [("proj/.claude/agents", ".."), ("proj", ".claude")])
@pytest.mark.parametrize("harness_args", [[], ["--harness=claude"]], ids=["detected", "flagged"])
def test_a_relative_target_is_matched_as_the_directory_it_names(
    tmp_path: Path, monkeypatch, cwd: str, target: str, harness_args: list[str]
) -> None:
    root = tmp_path / "proj/.claude"
    (root / "agents").mkdir(parents=True)
    monkeypatch.chdir(tmp_path / cwd)
    cli.main(["install", target, *harness_args])
    assert (root / "agents/python-coder.md").is_file()
    assert not (root / ".claude").exists()


@pytest.mark.parametrize("subdir", ["../escape", "{tmp}/elsewhere"], ids=["escaping", "absolute"])
def test_a_subdir_outside_the_project_root_is_refused(tmp_path: Path, capsys, subdir: str) -> None:
    (tmp_path / "proj").mkdir()
    argv = ["install", str(tmp_path / "proj"), "--harness=claude", f"--subdir={subdir.format(tmp=tmp_path)}"]
    assert "not inside project root" in _refused(argv, capsys)
    assert _paths(tmp_path) == ["proj"]


def test_an_unexpanded_home_target_is_refused_naming_the_tilde(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert "'~' was not expanded" in _refused(["install", "~/proj", "--harness=claude"], capsys)
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
    err = _refused(["install", str(tmp_path), "--harness=claude", "--with-kb", "--subdir=nested/root"], capsys)
    assert "not readable UTF-8" in err
    assert _paths(tmp_path) == ["justfile"]


def test_a_mage_install_with_uncommitted_sources_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _uncommitted)
    skills = tmp_path / "Mage/Skills"
    skills.mkdir(parents=True)
    assert "uncommitted changes" in _refused(["install", str(skills)], capsys)
    assert _paths(skills) == []


def test_a_mage_install_into_the_target_itself_writes_no_agents_file(tmp_path: Path, monkeypatch) -> None:
    """The slot render and mage-dist path: ROOT is the project root, so there is no agents file to
    install and the commit state is never read — an uncommitted tree would otherwise refuse."""
    monkeypatch.setattr(cli, "uncommitted_sources", _uncommitted)
    cli.main(["install", str(tmp_path), "--subdir=", "--harness=mage"])
    assert (tmp_path / ".claude-plugin/plugin.json").is_file()
    assert not (tmp_path / "CLAUDE.md").exists()


@pytest.mark.parametrize("harness", [[], [""]], ids=["absent", "empty"])
def test_the_agents_file_harness_is_inferred_from_a_user_directory(
    tmp_path: Path, monkeypatch, harness: list[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(cli, "uncommitted_sources", _committed)
    user_dir = tmp_path / ".claude"
    user_dir.mkdir()
    cli.main(["install-agents-file", str(user_dir), *harness])
    assert (user_dir / "CLAUDE.md").read_text(encoding="utf-8") == render_agents_file(CLAUDE, scope="Global")


def test_a_project_directory_without_a_harness_is_refused(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    err = _refused(["install-agents-file", str(project)], capsys)
    assert "claude, opencode" in err and "just" not in err
    assert _paths(project) == []


@pytest.mark.parametrize(
    ("present", "harness_args", "root"),
    [
        ([".claude"], [], ".claude"),
        ([".config/opencode"], [], ".config/opencode"),
        ([".claude", ".config/opencode"], ["--harness=opencode"], ".config/opencode"),
    ],
    ids=["claude", "opencode", "both-with-harness"],
)
def test_a_home_directory_target_installs_user_level_into_the_user_directory(
    _home: Path, present: list[str], harness_args: list[str], root: str
) -> None:
    for directory in present:
        (_home / directory).mkdir(parents=True)
    cli.main(["install", str(_home), *harness_args])
    assert (_home / root / "agents").is_dir()
    assert not (_home / root / ".claude").exists() and not (_home / root / ".opencode").exists()
    assert not (_home / root / "hooks").exists() and not (_home / root / "plugins").exists()
    assert all(_paths(_home / other) == [] for other in present if other != root)


@pytest.mark.parametrize("in_home", ["", ".claude"], ids=["home", "user-directory"])
def test_a_user_directory_symlinked_out_of_home_installs_through_the_link(
    tmp_path: Path, _home: Path, in_home: str
) -> None:
    dotfiles = tmp_path / "dotfiles/claude"
    dotfiles.mkdir(parents=True)
    _home.mkdir()
    (_home / ".claude").symlink_to(dotfiles)
    cli.main(["install", str(_home / in_home)])
    assert (dotfiles / "agents").is_dir()
    assert not (dotfiles / "hooks").exists()


def test_another_harness_s_user_directory_name_is_a_project_install(_home: Path) -> None:
    _home.mkdir()
    cli.main(["install", str(_home), "--harness=opencode", "--subdir=.claude"])
    assert (_home / ".claude/plugins/guardrail.ts").is_file()


def test_a_home_directory_holding_both_user_directories_is_refused(_home: Path, capsys) -> None:
    (_home / ".claude").mkdir(parents=True)
    (_home / ".config/opencode").mkdir(parents=True)
    assert "--harness" in _refused(["install", str(_home)], capsys)
    assert _paths(_home) == [".claude", ".config", ".config/opencode"]


def test_a_claude_user_level_kb_install_writes_only_the_definitions(_home: Path) -> None:
    root = _home / ".claude"
    root.mkdir(parents=True)
    cli.main(["install", str(root), "--with-kb"])
    assert (root / "agents").is_dir() and (root / "skills/kbase/SKILL.md").is_file()
    absent = ["hooks/guardrail.pl", "skills/kbase/kb-tools", "CLAUDE.md", "settings.json"]
    assert not any((root / path).exists() for path in absent)
    assert not any((_home / path).exists() for path in ["Makefile", ".mcp.json", ".claude.json"])


def test_an_opencode_user_level_kb_install_writes_no_plugin_or_settings(_home: Path) -> None:
    root = _home / ".config/opencode"
    root.mkdir(parents=True)
    cli.main(["install", str(root), "--with-kb"])
    assert (root / "skills/kbase/SKILL.md").is_file()
    assert not (root / "plugins/guardrail.ts").exists()
    assert not [path for path in _paths(_home) if Path(path).name in ("opencode.json", "opencode.jsonc")]


def test_the_global_agents_file_flag_installs_the_agents_file_at_a_user_level_root(_home: Path, monkeypatch) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _committed)
    root = _home / ".claude"
    root.mkdir(parents=True)
    cli.main(["install", str(root), "--install-global-agents-file"])
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == render_agents_file(CLAUDE, scope="Global")


def test_the_global_agents_file_flag_with_uncommitted_sources_writes_nothing(_home: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "uncommitted_sources", _uncommitted)
    (_home / ".claude").mkdir(parents=True)
    assert "uncommitted changes" in _refused(["install", str(_home), "--install-global-agents-file"], capsys)
    assert _paths(_home) == [".claude"]


def test_the_global_agents_file_flag_is_ignored_on_a_project_install(tmp_path: Path, _home: Path, monkeypatch) -> None:
    """The commit state is never read, so the injected uncommitted sources refuse nothing."""
    monkeypatch.setattr(cli, "uncommitted_sources", _uncommitted)
    _home.mkdir()
    flagged, plain = tmp_path / "flagged", tmp_path / "plain"
    for project in (flagged, plain):
        project.mkdir()
    cli.main(["install", str(flagged), "--harness=claude", "--install-global-agents-file"])
    cli.main(["install", str(plain), "--harness=claude"])
    assert _paths(flagged) == _paths(plain)
    assert _paths(_home) == []
