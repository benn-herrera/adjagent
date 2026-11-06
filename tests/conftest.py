"""Fixtures every test runs under."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A home directory under `tmp_path`, created by the tests that use it. `HOME` names it for every
    test and every process a test starts, so nothing the suite runs reads or writes the operator's real
    home."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    return home
