"""Tests for the installed runner fragments themselves — ``runner-snippets/``.

The delivered artifact is a justfile fragment and a Makefile fragment, so these
cases drive the real ``just`` and ``make`` over them, in a scratch consuming
repo whose ``<harness-dir>/agents`` symlinks to this repository's agents surface,
with the include lines written by the installed ``install-targets`` itself. That
is the shape the fragments document; anything less exercises a copy of the
recipe rather than the recipe.

The property under test is ``kb-verify``'s composite contract: both verifiers
of the standard check run, and the target carries the worst outcome — a report
covering one verifier's faults sends whoever reads it after half of the
problem. The citation-grammar check is build-time only and is not among them.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from kb_tools import install_location

_AGENTS_SURFACE = Path(__file__).resolve().parent.parent.parent

# Each verifier's mark ON STDOUT. verify_md_links puts its per-file findings on
# stdout and only its summary banner on stderr, so these are what "one report
# covers both" means to whoever reads it.
_RED_MARKS = ("[broken intra]", "[claim-quality] FAIL")

_RUNNERS = [
    pytest.param(
        runner,
        marks=pytest.mark.skipif(shutil.which(runner) is None, reason=f"needs {runner} on PATH"),
    )
    for runner in ("just", "make")
]


def _installed_env(root: Path, harness: str) -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": str(root / harness / "agents"), "PYTHONDONTWRITEBYTECODE": "1"}


def _consumer(root: Path, harness: str = ".claude") -> Path:
    """A consuming repo carrying the include lines its installed toolchain wrote."""
    (root / "kb-root").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    (root / harness).mkdir()
    (root / harness / "agents").symlink_to(_AGENTS_SURFACE, target_is_directory=True)
    for runner in ("just", "make"):
        subprocess.run(
            [sys.executable, "-m", "kb_tools.kb_util", "install-targets", "--runner", runner],
            cwd=root,
            env=_installed_env(root, harness),
            check=True,
            capture_output=True,
        )
    return root


def _verify(runner: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([runner, "kb-verify"], cwd=root, capture_output=True, text=True)


@pytest.fixture
def all_red(tmp_path: Path) -> Path:
    """A KB that fails both: a broken link, a file with no frontmatter, and no
    ``.index/`` at all. The same link is a citation resolving to nothing, which
    only the build-time check reports."""
    root = _consumer(tmp_path / "consumer")
    (root / "kb-root" / "x.md").write_text("[a](missing.md)\n", encoding="utf-8")
    return root


@pytest.fixture(params=install_location.HARNESS_DIRNAMES)
def green(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """The same shape with an empty KB, refreshed so the ``.index/`` spine the
    metadata verifier requires exists, under each harness directory. Nothing
    here needs ``init``: that verb runs preflight over a *consuming project's*
    whole state, which is a different contract from the one under test."""
    root = _consumer(tmp_path / "consumer", request.param)
    subprocess.run(
        [sys.executable, "-m", "kb_tools.refresh_kb_metadata"],
        cwd=root,
        env=_installed_env(root, request.param),
        check=True,
        capture_output=True,
    )
    return root


@pytest.mark.parametrize("runner", _RUNNERS)
def test_kb_verify_reports_both_verifiers_in_one_round_and_no_citation_check(runner: str, all_red: Path) -> None:
    """Two plain recipe lines stop at the first failure, and both runners do."""
    done = _verify(runner, all_red)

    assert done.returncode != 0
    assert [mark for mark in _RED_MARKS if mark not in done.stdout] == []
    assert "[citations]" not in done.stdout + done.stderr


@pytest.mark.parametrize("runner", _RUNNERS)
def test_kb_verify_is_green_when_every_verifier_is(runner: str, green: Path) -> None:
    """Collecting the rcs must not make the gate unpassable.

    Under either harness directory: the include line the installer wrote, the
    fragment's own location, and each tool's located install have to agree for
    either verifier to run at all.
    """
    done = _verify(runner, green)

    assert done.returncode == 0, done.stdout + done.stderr
