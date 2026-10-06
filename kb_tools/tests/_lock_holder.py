"""A second process holding a ``flock`` lock, for tests about exclusion.

The child is stdlib only and imports nothing from ``kb_tools``: it stands for
any holder — another kb_tools writer, a driver, a kbase build — and needs no
PYTHONPATH. It takes the exclusive lock on a directory or on a file it creates,
writes ``content`` into a file where one is given, reports ``held`` and keeps
the lock until its stdin closes or it is killed.
"""

import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_HOLDER = """
import fcntl, os, sys
path = sys.argv[1]
if os.path.isdir(path):
    fd = os.open(path, os.O_RDONLY)
else:
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
fcntl.flock(fd, fcntl.LOCK_EX)
if len(sys.argv) > 2:
    with open(fd, "w", encoding="utf-8", closefd=False) as stream:
        stream.truncate(0)
        stream.write(sys.argv[2])
print("held", flush=True)
sys.stdin.read()
"""


@contextmanager
def held(path: Path, *, content: str | None = None) -> Iterator[subprocess.Popen]:
    """Hold ``path``'s lock in a child process for the block; the child is the yielded process."""
    argv = [sys.executable, "-c", _HOLDER, str(path)]
    if content is not None:
        argv.append(content)
    child = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "held"
        yield child
    finally:
        child.stdin.close()  # type: ignore[union-attr]
        child.wait(timeout=10)
        child.stdout.close()  # type: ignore[union-attr]
