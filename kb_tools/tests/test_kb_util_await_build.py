"""``kb_util await-build``: reading a detached build's console, and waiting on it.

The console log is composed from the producers' own renders — ``kb_pipeline``'s
status card and ``baton``'s relay card — so what the parse is checked against
is the format the driver really prints, not a transcription of it. The waiting
loop runs against a log the test grows and a liveness the test flips, through
the loop's ``sleep``: no clock and no process.
"""

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from kb_tools import kb_pipeline, kb_util
from kb_tools.kb_driver import baton, checklist

_NOISE = "[kb-driver] INFO run started"


def _card(recorded: int) -> list[str]:
    stages = set(kb_pipeline.STAGE_IDS[:recorded])
    return [kb_pipeline.status_line(stages), *kb_pipeline.checklist_lines(stages)]


_RELAY = baton.render(baton.EXIT_BOUNDED, baton.BatonContext(invocation="--source a.tex")).splitlines()
_ONE, _TWO = _card(1), _card(2)


def _log(*blocks: list[str], newline: str = "\n") -> str:
    return "".join(f"{line}{newline}" for block in blocks for line in block)


@pytest.mark.parametrize(
    ("text", "card", "relay"),
    [
        pytest.param(_log([_NOISE]), (), (), id="no-card-yet"),
        pytest.param(_log([_NOISE], _ONE), _ONE, (), id="one-card"),
        pytest.param(_log(_ONE, [_NOISE], _TWO), _TWO, (), id="newest-card-wins"),
        pytest.param(_log(_ONE, _RELAY), _ONE, _RELAY, id="card-then-relay"),
        pytest.param(_log(_ONE, _RELAY[:-1]), _ONE, (), id="relay-not-yet-closed"),
        pytest.param(_log(_ONE, _TWO[:-1]), _ONE, (), id="card-short-of-its-checklist"),
        pytest.param(_log(_ONE, _TWO)[:-3], _ONE, (), id="last-line-still-being-written"),
        pytest.param(_log(_ONE, _TWO, _RELAY, newline="\r\n"), _TWO, _RELAY, id="crlf"),
    ],
)
def test_the_console_yields_its_newest_whole_card_and_a_closed_relay(
    text: str, card: list[str], relay: list[str]
) -> None:
    tail = checklist.read_console(text)

    assert tail.card == tuple(card)
    assert tail.relay == tuple(relay)


_BETWEEN = ["artifact: out/a.json", '{"barrier": "x"}', "restore: kb-root/a.md"]


@pytest.mark.parametrize(
    ("newline", "blocks", "expected"),
    [
        pytest.param("\n", [[_NOISE], _ONE, _BETWEEN, _RELAY], [_ONE, _BETWEEN, _RELAY], id="card-lines-relay"),
        pytest.param("\n", [[_NOISE], _ONE, _BETWEEN], [_ONE], id="no-relay-card-alone"),
        pytest.param("\r\n", [_ONE, _BETWEEN, _RELAY], [_ONE, _BETWEEN, _RELAY], id="crlf"),
    ],
)
def test_the_span_runs_from_the_newest_card_through_the_relay_close(
    newline: str, blocks: list[list[str]], expected: list[list[str]]
) -> None:
    text = _log(*blocks, newline=newline)

    start, end = checklist.read_console(text).span

    assert text[start:end] == _log(*expected, newline=newline)


def test_await_build_prints_every_line_between_the_card_and_the_relay(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    build = _Build(tmp_path / "live", console=_log(_ONE, _BETWEEN, _RELAY), steps=[])

    code, out = _await(build, capsys, running=False)

    assert (code, out) == (kb_util.EXIT_BUILD_EXITED, [_state(kb_util.AWAIT_EXITED), *_ONE, *_BETWEEN, *_RELAY])


def test_a_card_carrying_the_note_line_is_whole() -> None:
    noted = [_TWO[0], "[kb-build] note: kb-root/ is not seeded yet", *_TWO[1:]]

    assert checklist.read_console(_log(_ONE, noted)).card == tuple(noted)


# ---------------------------------------------------------------------------
# The waiting loop
# ---------------------------------------------------------------------------


class _Build:
    """A detached build's live directory, moved along one step per poll."""

    def __init__(self, live: Path, *, console: str | None, steps: list[tuple[str, bool]]) -> None:
        self.live = live
        self.console = live / kb_util.BUILD_CONSOLE_FILENAME
        self.running = True
        self.steps = steps
        live.mkdir()
        if console is not None:
            self.console.write_text(console, encoding="utf-8")

    def alive(self, pid_file: Path) -> bool:
        assert pid_file == self.live / kb_util.BUILD_PID_FILENAME
        return self.running

    def sleep(self, seconds: float) -> None:
        assert self.steps, "the loop polled past the last step: it missed the change"
        appended, self.running = self.steps.pop(0)
        with self.console.open("a", encoding="utf-8") as log:
            log.write(appended)


def _await(build: _Build, capsys: pytest.CaptureFixture[str], *, running: bool = True) -> tuple[int, list[str]]:
    build.running = running
    code = kb_util.await_build(build.live, alive=build.alive, sleep=build.sleep)
    return code, capsys.readouterr().out.splitlines()


def _state(state: str) -> str:
    return f"{kb_util.OP_AWAIT_BUILD}: {state}"


def test_a_changed_card_returns_it_while_the_driver_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    build = _Build(tmp_path / "live", console=_log(_ONE), steps=[(_log([_NOISE]), True), (_log(_TWO), True)])

    code, out = _await(build, capsys)

    assert code == 0
    assert out == [_state(kb_util.AWAIT_CHANGED), *_TWO]
    assert build.steps == []


def test_a_first_card_is_a_change(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    build = _Build(tmp_path / "live", console=None, steps=[(_log([_NOISE], _ONE), True)])

    code, out = _await(build, capsys)

    assert (code, out) == (0, [_state(kb_util.AWAIT_CHANGED), *_ONE])


def test_a_relay_still_being_written_is_waited_out_until_the_driver_exits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    build = _Build(
        tmp_path / "live",
        console=_log(_ONE),
        steps=[(_log(_RELAY[:3]), True), (_log(_RELAY[3:]), True), ("", False)],
    )

    code, out = _await(build, capsys)

    assert code == kb_util.EXIT_BUILD_EXITED
    assert out == [_state(kb_util.AWAIT_EXITED), *_ONE, *_RELAY]


def test_a_driver_already_exited_is_reported_at_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    build = _Build(tmp_path / "live", console=_log(_ONE, _RELAY), steps=[])

    code, out = _await(build, capsys, running=False)

    assert (code, out) == (kb_util.EXIT_BUILD_EXITED, [_state(kb_util.AWAIT_EXITED), *_ONE, *_RELAY])


def test_a_driver_that_died_mid_relay_says_where_its_output_is(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    build = _Build(tmp_path / "live", console=_log(_ONE, _RELAY[:3]), steps=[])

    code, out = _await(build, capsys, running=False)

    assert code == kb_util.EXIT_BUILD_EXITED
    assert out[: len(_ONE) + 1] == [_state(kb_util.AWAIT_EXITED), *_ONE]
    assert str(build.console) in out[-1]


def test_no_driver_and_no_console_is_nothing_to_await(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    build = _Build(tmp_path / "live", console=None, steps=[])

    code, out = _await(build, capsys, running=False)

    assert code == kb_util.EXIT_NOTHING_TO_AWAIT
    assert out[0] == _state(kb_util.AWAIT_NOTHING)
    assert len(out) == 2


@pytest.mark.parametrize(
    ("write", "alive"),
    [
        pytest.param(lambda pid_file: pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8"), True, id="running"),
        pytest.param(lambda pid_file: None, False, id="no-file"),
        pytest.param(lambda pid_file: pid_file.write_text("", encoding="utf-8"), False, id="empty"),
        pytest.param(lambda pid_file: pid_file.write_text("0\n", encoding="utf-8"), False, id="process-group"),
    ],
)
def test_the_pid_file_names_a_running_driver_or_none(
    tmp_path: Path, write: Callable[[Path], object], alive: bool
) -> None:
    pid_file = tmp_path / kb_util.BUILD_PID_FILENAME
    write(pid_file)

    assert kb_util._driver_alive(pid_file) is alive
