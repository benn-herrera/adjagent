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

from adjagent.install_base import PACKAGE_ROOT

_SCRIPT = PACKAGE_ROOT / "docdicer-tools" / "docdicer"

# A venv's `bin/python` that records each call's arguments as one line in the venv's `recorded`.
_STUB_VENV_PYTHON = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "${0%/*}/../recorded"
"""

# A `python3` that passes the version check and, for `-m venv ... DIR`, records its arguments as one
# line in `python3-calls` beside itself and builds DIR with the stub venv python.
_STUB_PYTHON3 = r"""#!/usr/bin/env bash
if [ "$1" = "-c" ]; then exit 0; fi
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  printf '%s\n' "$*" >> "${0%/*}/python3-calls"
  dir="${!#}"
  mkdir -p "${dir}/bin"
  cp "${0%/*}/venv-python" "${dir}/bin/python"
  exit 0
fi
exit 3
"""

_INSTALL_DOCDICER = "-m pip install git+https://github.com/benn-herrera/docdicer@v"


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
    _executable(tmp_path / "stubbin" / "venv-python", _STUB_VENV_PYTHON)
    return os.pathsep.join([str(tmp_path / "stubbin"), "/bin", "/usr/bin"])


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def test_with_no_venv_the_script_says_how_to_install_and_fails(tools: Path, tmp_path: Path) -> None:
    result = _run(tools, "--version", path=_stub_path(tmp_path))
    assert result.returncode != 0
    assert "--install" in result.stderr


def test_install_without_python3_names_a_remedy_and_fails(tools: Path, tmp_path: Path) -> None:
    bash_only = tmp_path / "bash-only"
    bash_only.mkdir()
    (bash_only / "bash").symlink_to(shutil.which("bash"))
    result = _run(tools, "--install", path=str(bash_only))
    assert result.returncode != 0
    assert "brew install python" in result.stdout + result.stderr


def test_install_with_no_venv_builds_one_with_current_pip_and_installs_docdicer(tools: Path, tmp_path: Path) -> None:
    result = _run(tools, "--install", path=_stub_path(tmp_path))
    assert result.returncode == 0, result.stderr
    assert _lines(tmp_path / "stubbin" / "python3-calls") == [f"-m venv --upgrade-deps {tools / '.venv'}"]
    recorded = _lines(tools / ".venv" / "recorded")
    assert len(recorded) == 1 and recorded[0].startswith(_INSTALL_DOCDICER)


def test_install_keeps_a_working_venv_and_upgrades_its_pip_before_docdicer(tools: Path, tmp_path: Path) -> None:
    path = _stub_path(tmp_path)
    _executable(tools / ".venv" / "bin" / "python", _STUB_VENV_PYTHON)
    marker = tools / ".venv" / "marker"
    marker.write_text("kept venv\n", encoding="utf-8")
    result = _run(tools, "--install", path=path)
    assert result.returncode == 0, result.stderr
    assert marker.exists()
    assert _lines(tmp_path / "stubbin" / "python3-calls") == []
    recorded = _lines(tools / ".venv" / "recorded")
    assert recorded[0].startswith("-c")
    assert recorded[1] == "-m pip install --upgrade pip"
    assert len(recorded) == 3 and recorded[2].startswith(_INSTALL_DOCDICER)


def test_install_rebuilds_a_venv_whose_python_no_longer_runs(tools: Path, tmp_path: Path) -> None:
    path = _stub_path(tmp_path)
    _executable(tools / ".venv" / "bin" / "python", "#!/usr/bin/env bash\nexit 1\n")
    marker = tools / ".venv" / "marker"
    marker.write_text("broken venv\n", encoding="utf-8")
    result = _run(tools, "--install", path=path)
    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    assert _lines(tmp_path / "stubbin" / "python3-calls") == [f"-m venv --upgrade-deps {tools / '.venv'}"]
    recorded = _lines(tools / ".venv" / "recorded")
    assert len(recorded) == 1 and recorded[0].startswith(_INSTALL_DOCDICER)


def test_arguments_pass_to_the_venvs_docdicer_unchanged(tools: Path, tmp_path: Path) -> None:
    _executable(tools / ".venv" / "bin" / "docdicer", '#!/usr/bin/env bash\nprintf "%s\\n" "$@"\n')
    result = _run(tools, "undice", "a", "b c", path=_stub_path(tmp_path))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["undice", "a", "b c"]
