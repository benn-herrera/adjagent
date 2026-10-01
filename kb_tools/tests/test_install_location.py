"""Where kb_tools finds itself installed, and the harness-named paths that follow from it."""

from pathlib import Path

import pytest

from kb_tools import install_location, kb_util

_INSTALLED = ("agents", "kb_tools", "kb_util.py")


@pytest.mark.parametrize(
    ("harness", "scratch"),
    [(".claude", ".claude-temp"), (".opencode", ".opencode-temp")],
)
def test_the_harness_directory_decides_every_derived_path(tmp_path: Path, harness: str, scratch: str) -> None:
    project = tmp_path / "project"
    location = install_location.locate(project.joinpath(harness, *_INSTALLED))

    assert location.harness_dir == project / harness
    assert location.project_root == project
    assert location.agents_dir == project / harness / "agents"
    assert location.agents_relpath == f"{harness}/agents"
    assert location.scratch_dir == project / scratch


def test_the_nearest_harness_ancestor_wins(tmp_path: Path) -> None:
    """A project cloned inside another's ``.claude/`` is still its own project."""
    inner = tmp_path / ".claude" / "clone" / "project"

    location = install_location.locate(inner.joinpath(".opencode", *_INSTALLED))

    assert location.harness_dir == inner / ".opencode"


def test_a_path_under_no_harness_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(install_location.InstallLocationError, match="sits under no"):
        install_location.locate(tmp_path.joinpath("src", *_INSTALLED))


def test_a_harness_named_file_is_not_its_own_ancestor(tmp_path: Path) -> None:
    with pytest.raises(install_location.InstallLocationError):
        install_location.locate(tmp_path / ".claude")


def test_what_kb_util_spells_follows_an_opencode_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    location = install_location.locate(tmp_path.joinpath(".opencode", *_INSTALLED))
    monkeypatch.setattr(install_location, "current", lambda: location)

    assert kb_util.harness_dirname() == ".opencode"
    assert kb_util.scratch_dirname() == ".opencode-temp"
    assert kb_util.invocation() == "PYTHONPATH=.opencode/agents python3 -m kb_tools.kb_util"
    assert kb_util.driver_invocation() == "PYTHONPATH=.opencode/agents python3 -m kb_tools.kb_driver"
    assert kb_util.install_line("just") == "import? '.opencode/agents/kb_tools/runner-snippets/kb.just'"
    assert kb_util.install_line("make") == "-include .opencode/agents/kb_tools/runner-snippets/kb.mk"
