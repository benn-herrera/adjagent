"""The KB's advisory locks, shared with kbase: one write lock, and one build's run lock.

**The write lock** is an exclusive ``flock`` on the directory that holds
``kb-root/`` — the repository root, the same directory kbase locks, so a writer
from either toolchain excludes a writer from the other. A writer takes it before
it reads the KB and holds it until its last write; a second writer that cannot
take it within the wait gets :class:`LockBusy` and nothing is read or written.
Readers take no lock.

**The run lock** is an exclusive ``flock`` on ``<git dir>/kbase-build.lock``,
held by a running build for its whole life and recording the build's
state directory. While it is held and names one, a command that writes the KB is
refused (:func:`command_write_lock`); held but empty, the build is starting and
has not yet waited out the writers in flight (:func:`await_writers`), so a
writer may go ahead.

Both are the kernel's: released when the holding process exits, by any route,
``kill -9`` included. There is no stale lock to judge or clear; the run lock's
file is removed by its holder on the way out only so that it stands while held.

**Windows has no advisory lock.** Where ``fcntl`` is absent nothing is locked
and nothing reads as held: the only guard against a concurrent writer is the
read-then-compare check each write makes on the file it replaces, two writers
can still interleave across files, a running build is not observable, and one
writer at a time is the operator's to keep.

Stdlib only.
"""

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: see the module docstring
    fcntl = None  # type: ignore[assignment]

#: How long a writer waits for another writer — its read, its write, its
#: refresh and sheets — before it is turned away rather than left hanging.
WRITE_LOCK_WAIT = 30.0

#: How long a build waits for another build's run lock: long enough to ride
#: out one that is releasing, short enough that a running one refuses at once.
RUN_LOCK_WAIT = 2.0

RUN_LOCK_FILENAME = "kbase-build.lock"

_POLL = 0.005

#: Write locks this process holds, by locked directory, with their depth. A
#: command holds the lock around an op that takes it again; ``flock`` is per open
#: file description, so a second descriptor here would wait on the first.
_held_here: dict[Path, int] = {}


class LockBusy(Exception):
    """Another process held ``path``'s lock past the wait. Nothing was read or written; re-run unchanged."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"{path} is locked by another process")
        self.path = path


class BuildRunning(Exception):
    """A build holds the repository's run lock, recording ``state_dir``."""

    def __init__(self, state_dir: str) -> None:
        super().__init__(f"a build is running; its state-dir is {state_dir}")
        self.state_dir = state_dir


def _open(path: Path) -> int:
    if path.is_dir():
        return os.open(path, os.O_RDONLY)
    return os.open(path, os.O_RDWR | os.O_CREAT, 0o666)


def _try_exclusive(fd: int) -> bool:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _unlock(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)


def _still_at(fd: int, path: Path) -> bool:
    """Whether ``path`` still names ``fd``: a holder removing its lock file unlinks what a waiter opened."""
    try:
        at = os.stat(path)
    except FileNotFoundError:
        return False
    held = os.fstat(fd)
    return (at.st_dev, at.st_ino) == (held.st_dev, held.st_ino)


def _acquire(path: Path, wait: float) -> int:
    deadline = time.monotonic() + wait
    while True:
        fd = _open(path)
        if _try_exclusive(fd):
            if _still_at(fd, path):
                return fd
            _unlock(fd)
        os.close(fd)
        if time.monotonic() >= deadline:
            raise LockBusy(path)
        time.sleep(_POLL)


def _held(path: Path) -> bool:
    """Whether another holder has ``path``'s lock: a shared probe, refused only by an exclusive holder."""
    if fcntl is None:
        return False
    try:
        fd = os.open(path, os.O_RDONLY)
    except FileNotFoundError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


@contextmanager
def write_lock(repo_root: Path, wait: float | None = None) -> Iterator[None]:
    """Hold the KB write lock of the repository at ``repo_root``; :class:`LockBusy` past ``wait``.

    ``wait`` defaults to :data:`WRITE_LOCK_WAIT`. Re-entrant within this
    process, so an op taking it under a command that already holds it runs on.
    Without ``fcntl`` it holds nothing and opens nothing.
    """
    if fcntl is None:
        yield
        return
    path = Path(repo_root).resolve()
    if path in _held_here:
        _held_here[path] += 1
        try:
            yield
        finally:
            _held_here[path] -= 1
        return
    fd = _acquire(path, WRITE_LOCK_WAIT if wait is None else wait)
    _held_here[path] = 1
    try:
        yield
    finally:
        del _held_here[path]
        _unlock(fd)
        os.close(fd)


@contextmanager
def command_write_lock(repo_root: Path, wait: float | None = None) -> Iterator[None]:
    """The write lock as a command that writes the KB holds it: refused while a build runs.

    The build is probed before the wait, so a running one refuses at once, and
    again once the lock is held, for a build that started during the wait — its
    own wait for writers may have ended before this one took the lock.
    :class:`BuildRunning` or :class:`LockBusy`; nothing is read or written on either.
    """
    _refuse_running_build(repo_root)
    with write_lock(repo_root, wait):
        _refuse_running_build(repo_root)
        yield


def _refuse_running_build(repo_root: Path) -> None:
    state_dir = running_build(repo_root)
    if state_dir is not None:
        raise BuildRunning(state_dir)


def await_writers(repo_root: Path) -> None:
    """Wait out a writer already holding the write lock: take it once and let it go. :class:`LockBusy` past the wait."""
    with write_lock(repo_root):
        pass


def run_lock_path(repo_root: Path) -> Path:
    """``<git dir>/kbase-build.lock``. A ``.git`` file's ``gitdir:`` is followed — a linked worktree's own git dir.

    Read rather than asked of git, so a writer that checks for a build never
    needs git; a relative ``gitdir:`` is relative to ``repo_root``.
    """
    repo = Path(repo_root)
    git_dir = repo / ".git"
    try:
        text = git_dir.read_text(encoding="utf-8")
    except OSError:
        return git_dir / RUN_LOCK_FILENAME
    key, sep, target = text.strip().partition(":")
    if sep and key == "gitdir":
        git_dir = repo / target.strip()
    return git_dir / RUN_LOCK_FILENAME


@dataclass
class RunLock:
    """A held run lock. :meth:`release` removes the file, then lets the lock go.

    Removing first is what keeps a waiter from locking a file its holder then
    unlinks (:func:`_still_at`). Without ``fcntl`` there is no file and no
    descriptor (``_fd`` is ``None``), and releasing does nothing.
    """

    path: Path
    _fd: int | None

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            self.path.unlink(missing_ok=True)
        finally:
            _unlock(self._fd)
            os.close(self._fd)


def take_run_lock(repo_root: Path, state_dir: Path) -> RunLock:
    """Take the repository's run lock and record ``state_dir`` in it.

    A holder that kept it past :data:`RUN_LOCK_WAIT` is :class:`BuildRunning`
    where its file names a state dir, and :class:`LockBusy` where it does not yet
    — it is starting, or has just released. Without ``fcntl`` nothing is taken
    or recorded, and no file is opened.
    """
    path = run_lock_path(repo_root)
    if fcntl is None:
        return RunLock(path, None)
    try:
        fd = _acquire(path, RUN_LOCK_WAIT)
    except LockBusy:
        holder = _recorded_state_dir(path)
        if holder:
            raise BuildRunning(holder) from None
        raise
    try:
        with open(fd, "w", encoding="utf-8", closefd=False) as stream:
            stream.truncate(0)
            stream.write(str(state_dir))
        os.fsync(fd)
    except OSError:
        RunLock(path, fd).release()
        raise
    return RunLock(path, fd)


def running_build(repo_root: Path) -> str | None:
    """The state dir a held run lock records; ``None`` where none is held or it records none yet. Never waits."""
    path = run_lock_path(repo_root)
    if not _held(path):
        return None
    return _recorded_state_dir(path) or None


def _recorded_state_dir(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
