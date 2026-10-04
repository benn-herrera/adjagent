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


@pytest.fixture
def runner_gate() -> None:
    """Names a test whose claim-graph pipelines reach stage G through the consuming project's runner.

    A test taking it is exempt from :func:`claimgraph_gate_in_process`; it does nothing itself.
    """


@pytest.fixture
def claimgraph_gate_in_process(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stage G in-process for every claim-graph pipeline this test runs, unless it takes ``runner_gate``.

    Function-scoped, so a module- or session-scoped build a test requests is
    made before this applies and keeps the runner's real gate.
    """
    if "runner_gate" in request.fixturenames:
        return
    from kb_tools.kb_claimgraph import gate
    from kb_tools.tests._claimgraph_consumer import stage_g_in_process

    monkeypatch.setattr(gate, "run", stage_g_in_process)
