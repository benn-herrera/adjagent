# Venv layout differs by OS: POSIX puts executables in .venv/bin, Windows in
# .venv/Scripts with .exe suffixes. Resolved here via just's os() builtin.

# PROJECT_ROOT defined by consumer before importing.
VENV := PROJECT_ROOT / ".venv"
PYBIN := if os() == "windows" { "Scripts" } else { "bin" }
EXE := if os() == "windows" { ".exe" } else { "" }
VENV_PYTHON := VENV / PYBIN / "python" + EXE
TOOLS_RECORD := VENV / "tools.txt"

# Lazy: the venv is created when its python is absent. The tool list below is recorded in
# .venv/tools.txt after it installs; when the record is absent or differs from the list, the list
# is installed into the existing venv and recorded again, and when it matches this runs no pip.
# A half-built venv is repaired by deleting .venv and re-running.
# The tools are compatible-release ranges on the install line (`~=X.Y.Z`): a venv rebuild takes
# the newest patch release of each named minor and nothing newer, so maintenance fixes arrive
# while what `just format-python` and `just test` do holds; a minor or major bump is an edit to
# that line, visible in the diff. `pip` stays unpinned: it installs, it does not produce output a
# change depends on.
_venv:
    #!/usr/bin/env bash
    set -euo pipefail
    tools=("pytest~=8.4.2" "isort~=6.1.0" "black~=25.11.0" "flake8~=7.3.0" "setuptools~=82.0.1" "build~=1.4.4" "git+https://github.com/benn-herrera/docdicer@v0.7.1")
    if [[ ! -x "{{VENV_PYTHON}}" ]]; then
        # if /usr/bin/python3 is installed it is the crappy 3.9.6 from xcode command line tools
        # that is actually our minspec, so use it to ensure we're not using any features
        # beyond its ken
        [[ "$(uname)" == Darwin ]] && export PATH=/usr/bin/:${PATH} || true
        python3 -m venv "{{VENV}}"
        "{{VENV_PYTHON}}" -m pip install pip --upgrade
    fi
    if [[ "$(cat "{{TOOLS_RECORD}}" 2>/dev/null || true)" != "$(printf '%s\n' "${tools[@]}")" ]]; then
        "{{VENV_PYTHON}}" -m pip install "${tools[@]}"
        printf '%s\n' "${tools[@]}" > "{{TOOLS_RECORD}}"
    fi
