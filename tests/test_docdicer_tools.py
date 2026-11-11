"""The shipped `docdicer` launcher, run as a consumer runs it: each case on a copy of the script in its
own directory, with a stub `python3` first on the subprocess's PATH, so no case reaches the network or
writes under `adjagent/`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from adjagent.install_base import PACKAGE_ROOT

_SCRIPT = PACKAGE_ROOT / "docdicer-tools" / "docdicer"

_VERSION = re.search(r"^VERSION=(\S+)$", _SCRIPT.read_text(encoding="utf-8"), re.MULTILINE).group(1)

# Each stub fails the step `STUB_FAIL` names: `version-check`, `venv` or `pip`. Each install step
# prints a line on stdout, so install output the launcher lets reach stdout shows there.

# A `python3` that records each call's arguments as one line in `python3-calls` beside itself. For
# `-m venv ... DIR` it builds DIR with the stub venv python (before failing, where told to, so a
# launcher that went on would reach docdicer).
_STUB_PYTHON3 = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "${0%/*}/python3-calls"
if [ "$1" = "-c" ]; then
  [ "${STUB_FAIL:-}" != version-check ]
  exit
fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  echo "stub venv output"
  dir="${!#}"
  mkdir -p "${dir}/bin"
  cp "${0%/*}/venv-python" "${dir}/bin/python"
  [ "${STUB_FAIL:-}" != venv ]
  exit
fi
exit 3
"""

# A venv's `bin/python` that records each call's arguments as one line in the venv's `recorded`.
# `-m pip install <url>` installs the stub docdicer reporting the version the URL's `@v` names.
_STUB_VENV_PYTHON = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "${0%/*}/../recorded"
if [ "$1" = "-m" ] && [ "$2" = "pip" ] && [ "$3" = "install" ]; then
  echo "stub pip output"
  [ "${STUB_FAIL:-}" != pip ] || exit 1
  cp "${STUB_DIR}/docdicer" "${0%/*}/docdicer"
  url="${!#}"
  printf '%s\n' "${url##*@v}" > "${0%/*}/docdicer-version"
fi
"""

# A docdicer that prints the version in `docdicer-version` beside it for `--version`, and its
# arguments one per line otherwise.
_STUB_DOCDICER = r"""#!/usr/bin/env bash
if [ "$*" = "--version" ]; then cat "${0%/*}/docdicer-version"; exit 0; fi
printf '%s\n' "$@"
"""

_ARGS = ("undice", "a", "b c")
_INSTALL_PINNED = f"-m pip install git+https://github.com/benn-herrera/docdicer@v{_VERSION}"


@pytest.fixture
def tools(tmp_path: Path) -> Path:
    """A copy of the launcher, executable, alone in its own directory."""
    directory = tmp_path / "tools"
    directory.mkdir()
    shutil.copy2(_SCRIPT, directory / "docdicer")
    return directory


@pytest.fixture
def stubbin(tmp_path: Path) -> Path:
    directory = tmp_path / "stubbin"
    _executable(directory / "python3", _STUB_PYTHON3)
    _executable(directory / "venv-python", _STUB_VENV_PYTHON)
    _executable(directory / "docdicer", _STUB_DOCDICER)
    return directory


def _executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _run(tools: Path, stubbin: Path, *, fail: str = "") -> subprocess.CompletedProcess[str]:
    """Run the launcher with `_ARGS`, the stubs ahead of the system directories on PATH."""
    return subprocess.run(
        [str(tools / "docdicer"), *_ARGS],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            **os.environ,
            "PATH": os.pathsep.join([str(stubbin), "/bin", "/usr/bin"]),
            "STUB_DIR": str(stubbin),
            "STUB_FAIL": fail,
        },
        stdin=subprocess.DEVNULL,
        timeout=60,
        check=False,
    )


def _plant_venv(tools: Path, stubbin: Path, *, docdicer_version: str) -> None:
    """A working venv holding a docdicer that reports `docdicer_version`."""
    venv_bin = tools / ".venv" / "bin"
    _executable(venv_bin / "python", _STUB_VENV_PYTHON)
    shutil.copy2(stubbin / "docdicer", venv_bin / "docdicer")
    (venv_bin / "docdicer-version").write_text(f"{docdicer_version}\n", encoding="utf-8")


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _built_venv(stubbin: Path, tools: Path) -> bool:
    return f"-m venv --upgrade-deps {tools / '.venv'}" in _lines(stubbin / "python3-calls")


def _installed_pinned(tools: Path) -> bool:
    return _INSTALL_PINNED in _lines(tools / ".venv" / "recorded")


def test_with_no_venv_the_launcher_builds_one_installs_docdicer_and_runs_it(tools: Path, stubbin: Path) -> None:
    result = _run(tools, stubbin)
    assert result.returncode == 0, result.stderr
    assert _built_venv(stubbin, tools)
    assert _installed_pinned(tools)
    assert result.stdout.splitlines() == list(_ARGS)


@pytest.mark.parametrize("fail", ["version-check", "venv"])
def test_without_a_usable_python3_the_launcher_fails_and_runs_no_docdicer(
    tools: Path, stubbin: Path, fail: str
) -> None:
    result = _run(tools, stubbin, fail=fail)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "python3 3.9" in result.stderr


def test_a_failed_venv_build_leaves_no_venv(tools: Path, stubbin: Path) -> None:
    _run(tools, stubbin, fail="venv")
    assert not (tools / ".venv").exists()


def test_arguments_pass_to_the_venvs_docdicer_unchanged(tools: Path, stubbin: Path) -> None:
    _plant_venv(tools, stubbin, docdicer_version=_VERSION)
    result = _run(tools, stubbin)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == list(_ARGS)
    assert _lines(stubbin / "python3-calls") == []
    assert not any(line.startswith("-m pip") for line in _lines(tools / ".venv" / "recorded"))


def test_a_docdicer_reporting_another_version_gets_the_pinned_one_installed(tools: Path, stubbin: Path) -> None:
    _plant_venv(tools, stubbin, docdicer_version="0.0.0")
    result = _run(tools, stubbin)
    assert result.returncode == 0, result.stderr
    assert not _built_venv(stubbin, tools)
    assert _installed_pinned(tools)
    assert result.stdout.splitlines() == list(_ARGS)


def test_a_venv_whose_python_does_not_run_is_rebuilt(tools: Path, stubbin: Path) -> None:
    _executable(tools / ".venv" / "bin" / "python", "#!/usr/bin/env bash\nexit 1\n")
    marker = tools / ".venv" / "marker"
    marker.write_text("broken venv\n", encoding="utf-8")
    result = _run(tools, stubbin)
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert _built_venv(stubbin, tools)
    assert _installed_pinned(tools)
    assert result.stdout.splitlines() == list(_ARGS)


def test_a_failed_pip_install_fails_the_launcher_and_runs_no_docdicer(tools: Path, stubbin: Path) -> None:
    _plant_venv(tools, stubbin, docdicer_version="0.0.0")
    result = _run(tools, stubbin, fail="pip")
    assert result.returncode != 0
    assert result.stdout == ""
