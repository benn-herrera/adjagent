"""The Graphviz seam: its version parse, its missing-binary message, and its nonzero-exit failure.

No case here runs Graphviz: the binary is pointed at a name not on PATH, or
the lookup finds it and ``subprocess.run`` answers in its place.
"""

import subprocess

import pytest

from kb_tools import dot

MISSING_MESSAGE = (
    "Graphviz `dot` is not on PATH. This toolchain draws the claim-graph sheets by invoking it and does not "
    "install or vendor it — install Graphviz (https://graphviz.org/download/) and re-run."
)


def _answering(monkeypatch: pytest.MonkeyPatch, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
    """The binary found on PATH, and ``subprocess.run`` answering for it."""

    def run(argv, **_kwargs):
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(dot.shutil, "which", lambda name: f"/graphviz/bin/{name}")
    monkeypatch.setattr(dot.subprocess, "run", run)


@pytest.mark.parametrize("call", [dot.version, lambda: dot.to_svg("digraph {}")], ids=["version", "to_svg"])
def test_a_missing_binary_is_named_with_its_install_page(monkeypatch: pytest.MonkeyPatch, call) -> None:
    monkeypatch.setattr(dot, "BINARY", "kb-tools-no-such-graphviz-binary")

    with pytest.raises(dot.DotMissingError) as raised:
        call()

    assert str(raised.value) == MISSING_MESSAGE.replace("`dot`", "`kb-tools-no-such-graphviz-binary`")


def test_the_message_names_dot_when_dot_is_the_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact text a report relays, with the real binary name in it."""

    def absent(*_args, **_kwargs):
        raise FileNotFoundError(dot.BINARY)

    monkeypatch.setattr(dot, "BINARY", "dot")
    monkeypatch.setattr(dot.shutil, "which", lambda name: f"/graphviz/bin/{name}")
    monkeypatch.setattr(dot.subprocess, "run", absent)

    with pytest.raises(dot.DotMissingError) as raised:
        dot.version()

    assert str(raised.value) == MISSING_MESSAGE


def test_the_version_is_read_off_the_banner_on_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    _answering(monkeypatch, stderr="dot - graphviz version 16.1.0 (20260904.0139)\n")

    assert dot.version() == "16.1.0"


def test_an_unrecognised_banner_is_a_dot_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _answering(monkeypatch, stderr="something else\n")

    with pytest.raises(dot.DotError, match="unrecognized"):
        dot.version()


def test_a_refused_graph_is_a_dot_error_carrying_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    _answering(monkeypatch, returncode=1, stderr="Error: <stdin>: syntax error in line 1\n")

    with pytest.raises(dot.DotError) as raised:
        dot.to_svg("digraph {")

    assert not isinstance(raised.value, dot.DotMissingError)
    assert "exited 1" in str(raised.value)
    assert "syntax error in line 1" in str(raised.value)


def test_stderr_at_exit_zero_is_logged_and_the_svg_returned(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _answering(monkeypatch, stdout="<svg/>", stderr="Warning: a font\n")

    assert dot.to_svg("digraph {}") == "<svg/>"
    assert "Warning: a font" in caplog.text
