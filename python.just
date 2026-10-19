# Venv layout differs by OS: POSIX puts executables in .venv/bin, Windows in
# .venv/Scripts with .exe suffixes. Resolved here via just's os() builtin.

# PROJECT_ROOT defined by consumer before importing.
VENV := PROJECT_ROOT / ".venv"
PYBIN := if os() == "windows" { "Scripts" } else { "bin" }
EXE := if os() == "windows" { ".exe" } else { "" }
VENV_PYTHON := VENV / PYBIN / "python" + EXE

# Lazy: if the venv's python already exists this is a no-op; a half-built
# venv is repaired by deleting .venv and re-running.
# The tool versions are pinned on the install line, so a venv rebuild cannot
# silently change what `just format-python` and `just test` do; bumping one is
# an edit to that line, visible in the diff. `pip` stays unpinned: it installs,
# it does not produce output a change depends on.
_venv:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -x "{{VENV_PYTHON}}" ]]; then
        python3 -m venv "{{VENV}}"
        "{{VENV_PYTHON}}" -m pip install pip pytest==9.1.1 isort==9.0.2 black==26.5.1 flake8==7.4.1
    fi
