"""A synthetic ``inference.Invoker`` for the driver suites, and nothing else.

Test-tree only. Nothing under ``kb_tools/`` imports this, and nothing shipped
into a consuming repository may: a consumer that installed a fake model would
be carrying a surface no entry point of theirs reaches.

The seam sits **below** stream parsing. A scenario's response is emitted as
stream-json lines and read back through ``inference.invoke``, so a case here
goes through the same capture, the same watchdog and the same classifier a live
call goes through. Scenarios that end badly end badly the same way: :func:`stall`
blocks until the watchdog kills it, and :func:`cli_rejection` emits nothing at
all so the zero-event classifier fires for the reason it fires in production.

It is a **combinator, not a fixture library**. A scenario is a function from the
call's context to a :class:`Response`, so a capped series composes in Python
with :func:`sequence` instead of accumulating static JSON files that break on
every schema change.

Content-shaped payloads are composed from the parsers' own markers and record
builders — :func:`verdict` from ``envelope.VERDICT_PREFIX``, :func:`stamped_leaf`
from ``kb_write.render`` — never from sentinel literals restated here: a test
that is green against a shape nothing else honours is proving nothing.
"""

import json
import signal
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kb_tools.kb_driver.envelope import VERDICT_PREFIX
from kb_tools.kb_write import render

DEFAULT_SESSION_ID = "fake-00000000"

# The placeholder an async dispatch returns before the work it started finishes
# — the observed text shape of the premature result.
WAITING_PLACEHOLDER = "I'm waiting for the agent to complete. You'll see the response once it returns."

SYNTHETIC_NOTE = "Synthetic content: this call was answered by a test double, not a model."


@dataclass(frozen=True)
class Context:
    """What a scenario gets to decide on: the call as composed, and which call it is."""

    argv: tuple[str, ...]
    cwd: Path
    brief_path: Path
    call_index: int  # 0-based within one invoker: the cap-loop round selector

    @property
    def step(self) -> str:
        """The step label, from the brief's filename ``briefs/<seq>-<step>.md``."""
        return self.brief_path.stem

    @property
    def agent(self) -> str | None:
        """The seat this call names, or None where the argv carries no ``--agent``."""
        argv = self.argv
        for index, token in enumerate(argv[:-1]):
            if token == "--agent":
                return argv[index + 1]
        return None

    def brief_text(self) -> str:
        """The composed brief, for a scenario that wants to answer what it was asked."""
        return self.brief_path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class Response:
    """What a scenario produces: lines to emit, how the process ends, and whether it wedges."""

    lines: tuple[str, ...] = ()
    exit_status: int = 0
    stderr: str = ""
    stall: bool = False  # after the lines, say nothing until killed


Scenario = Callable[[Context], Response]


# --- events -----------------------------------------------------------------


def init_event(*, session_id: str = DEFAULT_SESSION_ID, model: str = "fake", tools: Sequence[str] = ("Task",)) -> str:
    """A ``system``/``init`` event. ``tools`` spells the dispatch tool ``Task``; the wire
    name in a ``tool_use`` is ``Agent`` — the two do not agree, and no parse may assume they do."""
    return json.dumps(
        {"type": "system", "subtype": "init", "session_id": session_id, "model": model, "tools": list(tools)}
    )


def assistant_event(text: str, *, session_id: str = DEFAULT_SESSION_ID) -> str:
    """An ``assistant`` message event carrying one text block."""
    return json.dumps(
        {
            "type": "assistant",
            "session_id": session_id,
            "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
        }
    )


def result_event(
    text: str,
    *,
    subtype: str = "success",
    session_id: str = DEFAULT_SESSION_ID,
    num_turns: int = 2,
    duration_ms: int = 1000,
    total_cost_usd: float = 0.0,
) -> str:
    """A ``result`` event. Carries the cost and duration fields cadence extraction reads."""
    return json.dumps(
        {
            "type": "result",
            "subtype": subtype,
            "is_error": subtype != "success",
            "result": text,
            "session_id": session_id,
            "num_turns": num_turns,
            "duration_ms": duration_ms,
            "total_cost_usd": total_cost_usd,
        }
    )


# --- the shapes a return carries --------------------------------------------


def verdict(*, critical: int = 0, warning: int = 0, note: int = 0) -> str:
    """A reviewer return whose final line is the VERDICT the driver counts.

    ``critical`` above zero is what drives a capped series: composed with
    :func:`sequence` it scripts red-then-green, and held constant it runs a
    series to its cap and its escalation.
    """
    return "\n".join(
        ["# Findings", "", SYNTHETIC_NOTE, "", f"{VERDICT_PREFIX} critical={critical} warning={warning} note={note}"]
    )


def stamped_leaf(document: str, *, claims: Sequence[str]) -> str:
    """One rendered leaf with its metadata block stamped in, and its body untouched.

    The one composer of a realistic distilled leaf, which the buildout suite
    stands a KB tree up with. The block itself is ``render``'s — the one
    composer of the shape the write op a real member calls already owns.
    """
    values = render.FrontmatterValues(kind="leaf", claims=tuple(claims))
    head, _, body = document.partition("\n")
    return "\n".join([head, "", render.render_frontmatter_block(values), body])


# --- scenarios --------------------------------------------------------------


def clean(result_text: str = "ok", *, session_id: str = DEFAULT_SESSION_ID) -> Scenario:
    """One ``init``, one answer, one ``result``, exit 0 — a call that behaved."""

    def scenario(context: Context) -> Response:
        del context
        return Response(
            lines=(
                init_event(session_id=session_id),
                assistant_event(result_text, session_id=session_id),
                result_event(result_text, session_id=session_id),
            )
        )

    return scenario


def premature_dispatch(
    result_text: str = "ok",
    *,
    placeholder: str = WAITING_PLACEHOLDER,
    session_id: str = DEFAULT_SESSION_ID,
) -> Scenario:
    """The async-dispatch shape: a premature ``result``, then a second ``init``/``result``.

    Exit 0 throughout — this is what a call that dispatched with
    ``run_in_background: true`` looks like, and reading only the first
    ``result`` would record it as work that finished before it started.
    """

    def scenario(context: Context) -> Response:
        del context
        return Response(
            lines=(
                init_event(session_id=session_id),
                assistant_event(placeholder, session_id=session_id),
                result_event(placeholder, session_id=session_id, num_turns=3),
                init_event(session_id=session_id),
                assistant_event(result_text, session_id=session_id),
                result_event(result_text, session_id=session_id),
            )
        )

    return scenario


def stall(*, lines: Sequence[str] | None = None) -> Scenario:
    """Emit an ``init`` (or the given lines) and then go silent until killed.

    The wedge the silence watchdog exists for: the process is alive, its pipe
    is open, and nothing is ever coming.
    """
    prefix = tuple(lines) if lines is not None else (init_event(),)

    def scenario(context: Context) -> Response:
        del context
        return Response(lines=prefix, stall=True)

    return scenario


def cli_rejection(
    stderr: str = "error: unknown option '--frobnicate-widget'\n",
    *,
    exit_status: int = 1,
) -> Scenario:
    """Nonzero exit with **zero** stream events: the CLI refused the argv."""

    def scenario(context: Context) -> Response:
        del context
        return Response(lines=(), exit_status=exit_status, stderr=stderr)

    return scenario


def transport_die(
    *,
    exit_status: int = 1,
    stderr: str = "",
    lines: Sequence[str] | None = None,
) -> Scenario:
    """Speak, then die nonzero: a mid-stream failure, which is retry territory."""
    prefix = tuple(lines) if lines is not None else (init_event(),)

    def scenario(context: Context) -> Response:
        del context
        return Response(lines=prefix, exit_status=exit_status, stderr=stderr)

    return scenario


def sequence(*scenarios: Scenario) -> Scenario:
    """Answer differently on successive calls; the last one repeats.

    This is how a cap loop is scripted: ``sequence(red, red, green)`` is a
    stage that goes green on its third round, with no state outside the
    invoker.
    """
    if not scenarios:
        raise ValueError("sequence() needs at least one scenario")

    def scenario(context: Context) -> Response:
        chosen = scenarios[min(context.call_index, len(scenarios) - 1)]
        return chosen(context)

    return scenario


# --- the seam ---------------------------------------------------------------


class FakeInvoker:
    """``inference.Invoker`` that runs a scenario instead of a process."""

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self._calls = 0

    @property
    def calls(self) -> int:
        """How many calls this invoker has served — the cap-loop round count, observable."""
        return self._calls

    def run(
        self,
        *,
        argv: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
        prompt_path: Path,
    ) -> "_FakeInvocation":
        del env  # a synthetic call has no environment to overlay
        # A scripted run still composes and persists a real brief; a scenario
        # that cannot see one is being handed a call that was never composed,
        # and the brief's own filename is what says which row it answers.
        assert prompt_path.is_file(), f"a scripted call still requires the composed brief on disk: {prompt_path}"

        context = Context(argv=tuple(argv), cwd=cwd, brief_path=prompt_path, call_index=self._calls)
        self._calls += 1
        return _FakeInvocation(self._scenario(context))


class _FakeInvocation:
    """A scenario's response, presented as a live call."""

    def __init__(self, response: Response) -> None:
        self._response = response
        self._killed = threading.Event()
        self._status = response.exit_status

    def lines(self) -> Iterator[str]:
        for line in self._response.lines:
            if self._killed.is_set():
                return
            yield line if line.endswith("\n") else line + "\n"
        if self._response.stall:
            self._killed.wait()

    def kill(self) -> None:
        self._killed.set()
        # What a process group killed by the watchdog reports back.
        self._status = -signal.SIGKILL

    def wait(self) -> int:
        return self._status

    def stderr_text(self) -> str:
        return self._response.stderr
