"""The KB write lock and the build's run lock, against a second process holding them.

``flock`` belongs to an open file description, so every holder here is another
process (``_lock_holder``), never a thread of this one.
"""

import os
import time
from pathlib import Path

import pytest

from kb_tools import kb_lock
from kb_tools.tests import _lock_holder

pytestmark = pytest.mark.skipif(kb_lock.fcntl is None, reason="no advisory lock without fcntl (Windows)")


def _repo(root: Path) -> Path:
    (root / ".git").mkdir(parents=True)
    (root / "kb-root").mkdir()
    return root


def test_a_held_write_lock_turns_a_second_writer_away(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    with _lock_holder.held(repo):
        started = time.monotonic()
        with pytest.raises(kb_lock.LockBusy) as excinfo:
            with kb_lock.write_lock(repo, wait=0.1):
                pytest.fail("a held write lock must not be taken")
        assert time.monotonic() - started >= 0.1
    assert excinfo.value.path == repo.resolve()


@pytest.mark.parametrize("ending", ["exit", "kill -9"])
def test_the_write_lock_goes_with_its_holder_however_it_ends(tmp_path: Path, ending: str) -> None:
    repo = _repo(tmp_path / "repo")
    with _lock_holder.held(repo) as child:
        if ending == "kill -9":
            child.kill()
        else:
            child.stdin.close()
        child.wait(timeout=10)
        with kb_lock.write_lock(repo, wait=0.5):
            pass


def test_the_write_lock_re_enters_within_one_process_and_is_let_go_by_the_outermost(tmp_path: Path) -> None:
    """A command holds the lock around an op that takes it again; the op must not wait on its own command."""
    repo = _repo(tmp_path / "repo")
    with kb_lock.write_lock(repo, wait=0.1):
        with kb_lock.write_lock(repo, wait=0.1):
            pass
        assert kb_lock._held(repo)
    assert not kb_lock._held(repo)


def test_take_run_lock_records_the_state_dir_and_running_build_reads_it_back(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    state_dir = tmp_path / "runs" / "run-1"
    held = kb_lock.take_run_lock(repo, state_dir)
    try:
        assert held.path == repo / ".git" / kb_lock.RUN_LOCK_FILENAME
        assert held.path.read_text(encoding="utf-8") == str(state_dir)
        assert kb_lock.running_build(repo) == str(state_dir)
    finally:
        held.release()
    assert not held.path.exists()
    assert kb_lock.running_build(repo) is None


def test_a_second_build_is_refused_naming_the_running_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    with _lock_holder.held(kb_lock.run_lock_path(repo), content="/state/of/the/other"):
        assert kb_lock.running_build(repo) == "/state/of/the/other"
        with pytest.raises(kb_lock.BuildRunning) as excinfo:
            kb_lock.take_run_lock(repo, tmp_path / "mine")
    assert excinfo.value.state_dir == "/state/of/the/other"


def test_a_held_but_empty_run_lock_reports_no_build_and_busies_a_second_build(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    with _lock_holder.held(kb_lock.run_lock_path(repo), content=""):
        assert kb_lock.running_build(repo) is None
        with pytest.raises(kb_lock.LockBusy):
            kb_lock.take_run_lock(repo, tmp_path / "mine")


def test_a_run_lock_file_nobody_holds_is_no_build(tmp_path: Path) -> None:
    """A file left by a killed holder records a state dir, but the lock went with the process."""
    repo = _repo(tmp_path / "repo")
    with _lock_holder.held(kb_lock.run_lock_path(repo), content="/state/of/the/dead") as child:
        child.kill()
        child.wait(timeout=10)
        assert kb_lock.run_lock_path(repo).read_text(encoding="utf-8") == "/state/of/the/dead"
        assert kb_lock.running_build(repo) is None
        held = kb_lock.take_run_lock(repo, tmp_path / "next")
        held.release()


def test_command_write_lock_refuses_while_a_build_runs(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    with _lock_holder.held(kb_lock.run_lock_path(repo), content="/state/of/the/build"):
        with pytest.raises(kb_lock.BuildRunning):
            with kb_lock.command_write_lock(repo, wait=0.1):
                pytest.fail("a command must not write while a build runs")
        with kb_lock.write_lock(repo, wait=0.1):
            pass


def test_await_writers_waits_out_a_writer_and_leaves_the_lock_free(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo")
    with _lock_holder.held(repo) as child:
        child.stdin.close()
        kb_lock.await_writers(repo)
    assert not kb_lock._held(repo)


@pytest.mark.parametrize(
    ("gitdir", "expected"),
    [
        ("gitdir: ../main/.git/worktrees/wt", "main/.git/worktrees/wt"),
        ("gitdir: {abs}/main/.git/worktrees/wt\n", "main/.git/worktrees/wt"),
    ],
    ids=["relative", "absolute"],
)
def test_run_lock_path_follows_a_dot_git_file(tmp_path: Path, gitdir: str, expected: str) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(gitdir.format(abs=tmp_path), encoding="utf-8")
    path = kb_lock.run_lock_path(worktree)
    assert os.path.normpath(path) == os.path.normpath(tmp_path / expected / kb_lock.RUN_LOCK_FILENAME)
