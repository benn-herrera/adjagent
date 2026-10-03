"""Builds a module or session pays for once, and the copy each test receives instead.

A shared build is never handed to a test: :func:`copy_build` gives each test its
own copy under its own ``tmp_path``, ``symlinks=True`` because every claim-graph
consumer carries ``.claude/agents/kb_tools`` as a link to the package and a
plain copy would duplicate the package into it. Read-only is checked rather than
promised: :func:`held_unchanged` digests the build when it is handed over and
fails the run, naming the build, if anything under it differs when the scope
that built it ends.
"""

import hashlib
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def tree_digest(root: Path) -> dict[str, str]:
    """Every entry under ``root`` by relative path: a file's sha256, a link's target, a directory's mark."""
    digest: dict[str, str] = {}
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        here = Path(directory)
        for name in subdirectories + filenames:
            path = here / name
            relative = str(path.relative_to(root))
            if path.is_symlink():
                digest[relative] = f"link:{os.readlink(path)}"
            elif path.is_dir():
                digest[relative] = "dir"
            else:
                digest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


@contextmanager
def held_unchanged(root: Path, *, name: str) -> Iterator[Path]:
    """Yield ``root``; on exit, fail naming ``name`` and every changed path if anything under it changed."""
    before = tree_digest(root)
    yield root
    after = tree_digest(root)
    changed = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    assert not changed, f"shared build {name!r} was written to while shared: {changed}"


def copy_build(build: Path, target: Path) -> Path:
    """``target``, a copy of ``build`` this test may drive however it likes."""
    shutil.copytree(build, target, symlinks=True)
    return target
