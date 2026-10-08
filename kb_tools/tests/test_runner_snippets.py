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
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from kb_tools import install_location
from kb_tools.tests._stamped_kb import write_stamped_kb

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
    """A consuming repo, its KB stamped and otherwise empty, carrying the include lines its installed toolchain wrote."""
    write_stamped_kb(root / "kb-root")
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


_STUB_DRIVER = """\
import os, sys, time
from pathlib import Path
run_dir = Path(sys.argv[sys.argv.index("--run-dir") + 1])
(run_dir / "card").write_text("card\\n")
print("stub-driver cwd=" + os.getcwd() + " argv=" + " ".join(sys.argv[1:]), flush=True)
time.sleep(60)
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _consumer_with_snippets(root: Path) -> Path:
    """A consumer whose installed ``agents/kb_tools/`` is a real directory holding
    the real snippets, copied as an install copies them. The snippets set
    PYTHONPATH to their own install location, so anything a recipe is to run
    in place of the real tools has to live there. Returns that ``kb_tools``."""
    kb_tools = root / ".claude" / "agents" / "kb_tools"
    snippets = kb_tools / "runner-snippets"
    snippets.mkdir(parents=True)
    for name in ("kb.just", "kb.mk"):
        shutil.copy(_AGENTS_SURFACE / "kb_tools" / "runner-snippets" / name, snippets / name)
    (root / "justfile").write_text("import? '.claude/agents/kb_tools/runner-snippets/kb.just'\n")
    (root / "Makefile").write_text("-include .claude/agents/kb_tools/runner-snippets/kb.mk\n")
    return kb_tools


@pytest.fixture
def build_consumer(tmp_path: Path) -> Iterator[Path]:
    """The consumer with a stub ``kb_driver`` that writes a card and sleeps."""
    root = tmp_path / "consumer"
    kb_tools = _consumer_with_snippets(root)
    (kb_tools / "__init__.py").write_text("")
    (kb_tools / "kb_driver.py").write_text(_STUB_DRIVER)
    yield root
    pid_file = root / ".claude-temp" / "kb-driver-live" / "driver.pid"
    if pid_file.exists() and _alive(int(pid_file.read_text())):
        os.kill(int(pid_file.read_text()), signal.SIGKILL)


@pytest.fixture
def await_consumer(tmp_path: Path) -> Path:
    """The consumer with the real ``kb_tools`` linked beside its copied snippets
    (``__file__`` keeps the linked path, so the tools still locate the
    consumer's ``.claude-temp``), and a live dir holding a console log and the
    pid of a process that has exited."""
    root = tmp_path / "consumer"
    kb_tools = _consumer_with_snippets(root)
    for entry in (_AGENTS_SURFACE / "kb_tools").iterdir():
        if entry.name != "runner-snippets":
            (kb_tools / entry.name).symlink_to(entry)
    live = root / ".claude-temp" / "kb-driver-live"
    live.mkdir(parents=True)
    (live / "console.log").write_text("no card here\n")
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    (live / "driver.pid").write_text(f"{gone.pid}\n")
    return root


def _build_args(runner: str, *sources: str, flags: str = "") -> list[str]:
    if runner == "just":
        return [runner, "kb-build", *sources, *flags.split()]
    return [runner, "kb-build", f"SOURCES={' '.join(sources)}", *([f"DRIVER_FLAGS={flags}"] if flags else [])]


def _run(args: list[str], root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=root, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("runner", _RUNNERS)
def test_kb_build_launches_detached_refuses_a_second_and_kill_ends_it(runner: str, build_consumer: Path) -> None:
    live = build_consumer / ".claude-temp" / "kb-driver-live"

    launched = _run(_build_args(runner, "a.tex", "b.tex"), build_consumer)

    assert launched.returncode == 0, launched.stdout + launched.stderr
    pid = int((live / "driver.pid").read_text())
    assert _alive(pid)
    assert f"launched pid {pid}" in launched.stdout
    assert str(live / "console.log") in launched.stdout
    assert f"then: {runner} kb-build-await" in launched.stdout
    deadline = time.monotonic() + 10
    while "stub-driver" not in (live / "console.log").read_text() and time.monotonic() < deadline:
        time.sleep(0.1)
    console = (live / "console.log").read_text()
    assert f"cwd={build_consumer.resolve()}" in console
    assert f"argv=run --source a.tex --source b.tex --run-dir {live}/runs" in console
    assert (live / "runs" / "card").is_file()

    second = _run(_build_args(runner, "a.tex"), build_consumer)

    assert second.returncode != 0
    assert str(pid) in second.stderr
    assert _alive(pid)

    killed = _run([runner, "kb-build-kill"], build_consumer)

    assert killed.returncode == 0, killed.stdout + killed.stderr
    assert str(pid) in killed.stdout
    assert not _alive(pid)
    assert (live / "driver.pid").is_file()


@pytest.mark.parametrize("runner", _RUNNERS)
def test_kb_build_passes_driver_flags_after_the_sources(runner: str, build_consumer: Path) -> None:
    live = build_consumer / ".claude-temp" / "kb-driver-live"

    launched = _run(_build_args(runner, "a.tex", "b.tex", flags="--no-inference --decide s.k=yes"), build_consumer)

    assert launched.returncode == 0, launched.stdout + launched.stderr
    deadline = time.monotonic() + 10
    while "stub-driver" not in (live / "console.log").read_text() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert (
        f"argv=run --source a.tex --source b.tex --no-inference --decide s.k=yes --run-dir {live}/runs"
        in (live / "console.log").read_text()
    )


@pytest.mark.parametrize("runner", _RUNNERS)
def test_kb_build_await_passes_the_op_output_and_exit_code_through(runner: str, await_consumer: Path) -> None:
    """``make`` reports any failed recipe as 2, so only ``just`` can carry the op's own code."""
    done = _run([runner, "kb-build-await"], await_consumer)

    assert "await-build: exited" in done.stdout
    assert done.returncode == (3 if runner == "just" else 2)
