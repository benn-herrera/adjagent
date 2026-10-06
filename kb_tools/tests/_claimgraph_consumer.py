"""The consuming repository the claim-graph suites build in.

A claim-graph consumer is stood up the way a consumer's is: the tree under
``kb-root/``, the package installed under ``.claude/agents/`` as a link, and the
real runner snippet imported by the line the installer writes, which is part of
the seeded spine ``kb_claimgraph`` requires.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from kb_tools import kb_util
from kb_tools.tests._stamped_kb import write_stamped_kb

_PACKAGE_ROOT = Path(kb_util.__file__).resolve().parent


def install_claimgraph_consumer(repo: Path, tree: Mapping[str, str]) -> Path:
    """A consuming repo at ``repo``: ``tree`` under ``kb-root/``, the installed package and the real runner targets.

    The tools resolve the repository root the way every tool in this toolchain
    does — a ``.git`` beside a ``kb-root/`` — so the marker is what makes this a
    repository to them, not a convenience of the fixture. The KB is stamped, as
    the seed that precedes every claim-graph stage leaves it.
    """
    write_stamped_kb(repo / "kb-root", tree)
    (repo / ".git").mkdir()
    (repo / "justfile").write_text("default:\n    @true\n", encoding="utf-8")
    installed = repo / ".claude" / "agents"
    installed.mkdir(parents=True)
    os.symlink(_PACKAGE_ROOT, installed / _PACKAGE_ROOT.name)
    kb_util.install_targets(repo, "just")
    return repo
