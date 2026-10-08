"""`stage-fixture --family=<name>` supplies the tier alias map the claude harness needs.

A non-claude family renders its tier member on the model line, which the claude
harness accepts only as a Claude alias; the staging recipes append a default
`--model-pin-tier-alias-map` unless the caller passed one. The fixture is a
throwaway repository under this repository's `.claude-temp/`; nothing under
`test-data/transient/` is touched.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JUSTFILE = _REPO_ROOT / "kb-testing" / "justfile"
_SCRATCH = _REPO_ROOT / ".claude-temp" / "stage-tier-alias-map-tests"

# architect renders the high tier, biz-dev-strategist the medium one.
_HIGH_AGENT = "architect.md"


@pytest.fixture(scope="module", autouse=True)
def _clean_scratch():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    _SCRATCH.mkdir(parents=True)
    yield
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _stage(name: str, *flags: str) -> tuple[subprocess.CompletedProcess, Path]:
    fixture = _SCRATCH / name
    fixture.mkdir()
    _git(fixture, "init", "-q")
    for key, value in (("user.email", "fixture@example.invalid"), ("user.name", "fixture"), ("commit.gpgsign", "false")):
        _git(fixture, "config", key, value)
    (fixture / "paper.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-qm", "sources")
    _git(fixture, "tag", "cleared")
    result = subprocess.run(
        ["just", "--justfile", str(_JUSTFILE), "--set", "KB_DRIVER_LIVE_DIR", str(_SCRATCH / "live"), "stage-fixture", str(fixture), *flags],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result, fixture


def _model(fixture: Path) -> str:
    text = (fixture / ".claude" / "agents" / _HIGH_AGENT).read_text(encoding="utf-8")
    return next(ln for ln in text.splitlines() if ln.startswith("model:"))


def test_family_without_an_alias_map_stages_with_the_default_map() -> None:
    result, fixture = _stage("family-default", "--family=qwen3")
    assert result.returncode == 0, result.stderr
    assert _model(fixture) == "model: opus"


def test_a_callers_own_alias_map_is_kept() -> None:
    result, fixture = _stage("family-own-map", "--family=qwen3", "--model-pin-tier-alias-map=all=sonnet")
    assert result.returncode == 0, result.stderr
    assert _model(fixture) == "model: sonnet"
