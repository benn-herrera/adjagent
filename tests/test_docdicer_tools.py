"""The shipped `docdicer` launcher, run as a consumer runs it: each case on a copy of the script in its
own directory, with a stub `python3` first on the subprocess's PATH, so no case reaches the network or
writes under `adjagent/`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from adjagent.install import PACKAGE_ROOT

_SCRIPT = PACKAGE_ROOT / "docdicer-tools" / "docdicer"

# A `python3` that passes the version check and, for `-m venv DIR`, builds a venv whose `bin/python`
# records its arguments one per line in `DIR/recorded`.
_STUB_PYTHON3 = """#!/bin/sh
if [ "$1" = "-c" ]; then exit 0; fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  printf '%s\\n' '#!/bin/sh' 'printf "%s\\n" "$@" > "${0%/*}/../recorded"' > "$3/bin/python"
  chmod +x "$3/bin/python"
  exit 0
fi
exit 3
"""


@pytest.fixture
def tools(tmp_path: Path) -> Path:
    """A copy of the launcher, executable, alone in its own directory."""
    directory = tmp_path / "tools"
    directory.mkdir()
    shutil.copy2(_SCRIPT, directory / "docdicer")
    return directory


def _executable(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _run(tools: Path, *args: str, path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(tools / "docdicer"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PATH": path},
        check=False,
    )


def _stub_path(tmp_path: Path) -> str:
    """PATH with the stub `python3` ahead of the system directories the script and stub need."""
    _executable(tmp_path / "stubbin" / "python3", _STUB_PYTHON3)
    return os.pathsep.join([str(tmp_path / "stubbin"), "/bin", "/usr/bin"])


def test_with_no_venv_the_script_says_how_to_install_and_fails(tools: Path, tmp_path: Path) -> None:
    result = _run(tools, "--version", path=_stub_path(tmp_path))
    assert result.returncode != 0
    assert "--install" in result.stderr


def test_install_without_python3_names_a_remedy_and_fails(tools: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _run(tools, "--install", path=str(empty))
    assert result.returncode != 0
    assert "brew install python" in result.stdout + result.stderr


def test_install_rebuilds_the_venv_and_installs_docdicer_into_it(tools: Path, tmp_path: Path) -> None:
    marker = tools / ".venv" / "marker"
    marker.parent.mkdir()
    marker.write_text("old venv\n", encoding="utf-8")
    result = _run(tools, "--install", path=_stub_path(tmp_path))
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    recorded = (tools / ".venv" / "recorded").read_text(encoding="utf-8").splitlines()
    assert recorded[:4] == ["-m", "pip", "install", "--upgrade"]
    assert len(recorded) == 5 and "docdicer" in recorded[4]


def test_arguments_pass_to_the_venvs_docdicer_unchanged(tools: Path, tmp_path: Path) -> None:
    _executable(tools / ".venv" / "bin" / "docdicer", '#!/bin/sh\nprintf "%s\\n" "$@"\n')
    result = _run(tools, "undice", "a", "b c", path=_stub_path(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["undice", "a", "b c"]
