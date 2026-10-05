"""The suite runs kb_tools from its source tree, which sits under no harness directory.

So for the session it stands up the installed layout — ``<tmp>/.claude/agents/kb_tools``,
a link to the package under test — and points ``install_location.current`` at
it before any test module is collected. In-process code reads that location;
a subprocess given ``current().agents_dir`` as its PYTHONPATH imports kb_tools
through the link and locates itself there for real. Nothing depends on where
the repository is checked out.
"""

import os
import shutil
import tempfile
from collections.abc import Iterator
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
    _patch.setenv("PATH", _path_without_graphviz(_harness_root / "path"))


def _path_without_graphviz(shadows: Path) -> str:
    """PATH with each directory holding ``dot`` replaced by links to everything else in it.

    For the processes tests spawn, which the in-process patch below cannot
    reach: a refresh or preflight run as a child must meet the same absent
    Graphviz the suite does, while finding pandoc, git and python where they were.
    """
    from kb_tools import dot

    directories = []
    for index, directory in enumerate(os.environ.get("PATH", "").split(os.pathsep)):
        if directory and (Path(directory) / dot.BINARY).exists():
            shadow = shadows / str(index)
            shadow.mkdir(parents=True)
            for entry in Path(directory).iterdir():
                if entry.name != dot.BINARY:
                    (shadow / entry.name).symlink_to(entry)
            directory = str(shadow)
        directories.append(directory)
    return os.pathsep.join(directories)


def pytest_unconfigure(config: pytest.Config) -> None:
    _patch.undo()
    if _harness_root is not None:
        shutil.rmtree(_harness_root)


@pytest.fixture(scope="session", autouse=True)
def no_graphviz() -> Iterator[None]:
    """The suite neither needs nor runs Graphviz: every in-process refresh draws placeholders.

    A test about a drawn sheet patches ``dot.to_svg`` instead; one about the
    seam patches what the seam calls.
    """
    from kb_tools import dot

    patch = pytest.MonkeyPatch()
    patch.setattr(dot, "BINARY", "kb-tools-tests-run-without-graphviz")
    yield
    patch.undo()


@pytest.fixture(autouse=True)
def no_reader_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts with no server or key named, so an operator's env never reaches a test's call."""
    from kb_tools.inference import liaison_tools

    for variable in (
        liaison_tools.BASE_URL_ENV,
        liaison_tools.MODEL_ENV,
        liaison_tools.KEY_FILE_ENV,
        liaison_tools.ALLOW_HTTP_ENV,
    ):
        monkeypatch.delenv(variable, raising=False)
