"""Every path argument of `kb-driver-fixture` and `stage-fixture` resolves one way.

An absolute path is used as given; a relative one resolves against the
directory `just` was invoked from, not against `kb-testing/` (where just runs
the recipe) nor the repository root (where `install` runs).

Each case invokes the recipes from a directory that is neither of those, with
`--justfile` naming this tree's justfile. Fixtures are throwaway repositories
under this repository's `.claude-temp/`; nothing under `test-data/transient/`
is touched, and `KB_DRIVER_LIVE_DIR` is redirected so a live build's pid file
cannot refuse the call.
"""

import shutil
import subprocess
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JUSTFILE = _REPO_ROOT / "kb-testing" / "justfile"
_SCRATCH = _REPO_ROOT / ".claude-temp" / "fixture-path-resolution-tests"
_CALLER = _SCRATCH / "caller"


@pytest.fixture(scope="module", autouse=True)
def _clean_scratch():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    _CALLER.mkdir(parents=True)
    yield
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def _just(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["just", "--justfile", str(_JUSTFILE), "--set", "KB_DRIVER_LIVE_DIR", str(_SCRATCH / "live"), *args],
        env=env,
        cwd=_CALLER,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _make_cleared_repo(root: Path, extra: dict[str, str] | None = None) -> Path:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    for key, value in (("user.email", "fixture@example.invalid"), ("user.name", "fixture"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    for name, text in {"paper.tex": "\\documentclass{article}\n", **(extra or {})}.items():
        (root / name).write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "sources")
    _git(root, "tag", "cleared")
    return root


@pytest.mark.parametrize("spelling", ["absolute", "relative"])
def test_stage_fixture_installs_into_the_named_directory(spelling: str) -> None:
    fixture = _make_cleared_repo(_SCRATCH / f"staged-{spelling}")
    arg = str(fixture) if spelling == "absolute" else f"../{fixture.name}"
    result = _just("stage-fixture", arg)
    assert result.returncode == 0, result.stderr
    assert (fixture / ".claude" / "agents" / "kb_tools" / "kb_util.py").is_file()


@pytest.mark.parametrize("spelling", ["absolute", "relative"])
def test_stage_fixture_names_the_resolved_directory_in_its_refusal(spelling: str) -> None:
    bare = _SCRATCH / f"bare-{spelling}"
    bare.mkdir()
    arg = str(bare) if spelling == "absolute" else f"../{bare.name}"
    result = _just("stage-fixture", arg)
    assert result.returncode != 0
    expected = str(bare) if spelling == "absolute" else f"{_CALLER}/../{bare.name}"
    assert f"error: {expected} is not a git repository" in result.stderr


@pytest.mark.parametrize("spelling", ["absolute", "relative"])
def test_kb_driver_fixture_resolves_dir_and_env_file_alike(spelling: str) -> None:
    bare = _SCRATCH / f"driver-bare-{spelling}"
    bare.mkdir()
    env_file = _SCRATCH / f"driver-{spelling}.env"
    env_file.write_text("X=1\n", encoding="utf-8")
    dir_arg, env_arg = (str(bare), str(env_file)) if spelling == "absolute" else (f"../{bare.name}", f"../{env_file.name}")
    result = _just("kb-driver-fixture", dir_arg, env_arg)
    # Past the env-file check, into staging, which refuses the bare directory by its resolved name.
    expected = str(bare) if spelling == "absolute" else f"{_CALLER}/../{bare.name}"
    assert f"error: {expected} is not a git repository" in result.stderr, result.stderr


@pytest.mark.parametrize("spelling", ["absolute", "relative"])
def test_kb_driver_fixture_names_the_resolved_env_file_in_its_refusal(spelling: str) -> None:
    missing = _SCRATCH / f"missing-{spelling}.env"
    arg = str(missing) if spelling == "absolute" else f"../{missing.name}"
    result = _just("kb-driver-fixture", str(_SCRATCH), arg)
    assert result.returncode != 0
    expected = str(missing) if spelling == "absolute" else f"{_CALLER}/../{missing.name}"
    assert f"error: env file {expected} is not a readable file." in result.stderr


_DOC = "\\documentclass{article}\n"
_SOURCE_FILES = {"a.tex": _DOC, "b.tex": _DOC, "notes.tex": "\\input{a}\n"}


def _launch(name: str, *flags: str) -> subprocess.CompletedProcess:
    fixture = _make_cleared_repo(_SCRATCH / name, _SOURCE_FILES)
    env_file = _SCRATCH / f"{name}.env"
    env_file.write_text("X=1\n", encoding="utf-8")
    # `--help` makes the detached driver print usage and exit, so no build runs.
    return _just("kb-driver-fixture", str(fixture), str(env_file), *flags, "--", "--help")


def _launched_sources(result: subprocess.CompletedProcess) -> str:
    assert result.returncode == 0, result.stderr
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("launched pid "))
    return line.split("(", 1)[1].rstrip(")")


def test_kb_driver_fixture_without_sources_flag_builds_every_documentclass_file() -> None:
    assert _launched_sources(_launch("sources-none")) == "--source a.tex --source b.tex --source paper.tex"


def test_kb_driver_fixture_sources_flag_replaces_the_list_in_the_order_given() -> None:
    assert _launched_sources(_launch("sources-subset", "--sources=b.tex,a.tex")) == "--source b.tex --source a.tex"


def test_kb_driver_fixture_sources_flag_composes_with_resume_in_either_order() -> None:
    for order in (("--resume", "--sources=a.tex"), ("--sources=a.tex", "--resume")):
        result = _launch(f"sources-resume-{order[0][2:8]}", *order)
        # Nothing was staged, so resume refuses at the ledger check, after the list was accepted.
        assert "has no `kb-build:` ledger commit" in result.stderr or "holds no installed kb_tools" in result.stderr, result.stderr


@pytest.mark.parametrize(
    ("name", "flag", "message"),
    [
        ("sources-missing", "--sources=a.tex,gone.tex", "--sources file gone.tex does not exist in"),
        ("sources-nodoc", "--sources=notes.tex", "--sources file notes.tex holds no \\documentclass"),
        ("sources-empty", "--sources=", "--sources names no file"),
        ("sources-dup", "--sources=a.tex,b.tex,a.tex", "--sources names a.tex more than once"),
    ],
)
def test_kb_driver_fixture_refuses_a_bad_sources_list(name: str, flag: str, message: str) -> None:
    result = _launch(name, flag)
    assert result.returncode != 0
    assert message in result.stderr, result.stderr


def test_kb_driver_fixture_env_file_under_home_reaches_the_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    # The driver is a stub standing in for the venv's python, so the launched
    # environment is observable without a build. `~` is expanded from HOME.
    home = _SCRATCH / "home"
    home.mkdir()
    env_file = home / "build.env"
    env_file.write_text("X=1\nAPI_BASE_URL=http://reader.invalid/v1\nMODEL=probe-model\n", encoding="utf-8")
    stub = _SCRATCH / "stub-python"
    stub.write_text('#!/usr/bin/env bash\nprintf \'seen:%s|%s|%s\\n\' "${X-}" "${API_BASE_URL-}" "${MODEL-}"\n', encoding="utf-8")
    stub.chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    fixture = _make_cleared_repo(_SCRATCH / "env-reach", _SOURCE_FILES)
    result = _just("--set", "VENV_PYTHON", str(stub), "kb-driver-fixture", str(fixture), "~/build.env")
    assert result.returncode == 0, result.stderr
    log = _SCRATCH / "live" / "console.log"
    for _ in range(50):
        if log.is_file() and "seen:" in log.read_text(encoding="utf-8"):
            break
        time.sleep(0.1)
    assert "seen:1|http://reader.invalid/v1|probe-model" in log.read_text(encoding="utf-8")
