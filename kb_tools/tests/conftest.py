"""The suite runs kb_tools from its source tree, which sits under no harness directory.

So for the session it stands up the installed layout — ``<tmp>/.claude/agents/kb_tools``,
a link to the package under test — and points ``install_location.current`` at
it before any test module is collected. In-process code reads that location;
a subprocess given ``current().agents_dir`` as its PYTHONPATH imports kb_tools
through the link and locates itself there for real. Nothing depends on where
the repository is checked out.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from kb_tools import install_location

_PACKAGE = Path(install_location.__file__).resolve().parent
_patch = pytest.MonkeyPatch()
_harness_root: Path | None = None


def pytest_configure(config: pytest.Config) -> None:
    global _harness_root
    _harness_root = Path(tempfile.mkdtemp(prefix="kb-tools-installed-"))
    agents = _harness_root / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / _PACKAGE.name).symlink_to(_PACKAGE, target_is_directory=True)
    location = install_location.locate(agents / _PACKAGE.name / "install_location.py")
    _patch.setattr(install_location, "current", lambda: location)


def pytest_unconfigure(config: pytest.Config) -> None:
    _patch.undo()
    if _harness_root is not None:
        shutil.rmtree(_harness_root)
