"""A scripted stand-in for ``inference.call_chat`` for the driver suites, and nothing else.

Test-tree only. Nothing under ``kb_tools/`` imports this, and nothing shipped
into a consuming repository may: a consumer that installed a fake model would
be carrying a surface no entry point of theirs reaches.

The seam is ``call.Caller.transport``: :class:`FakeChat` takes the keyword
arguments ``call_chat`` takes and returns what it returns — the reply text and
how the request ended — so the driver's retry, re-ask and persistence run
exactly as they do over a live call. It writes no capture: what a capture holds
and how it is read are ``inference.liaison_tools``', exercised against the
loopback stub (``_chat_stub``).

It is a **combinator, not a fixture library**. A scenario is a function from the
call's context to a :class:`Response`, so a series composes in Python with
:func:`sequence`.

Content-shaped payloads are composed from the parsers' own markers and record
builders — :func:`stamped_leaf` from ``kb_write.render`` — never from sentinel
literals restated here: a test that is green against a shape nothing else
honours is proving nothing.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from kb_tools.inference import Outcome
from kb_tools.kb_driver import runlog
from kb_tools.kb_write import render


@dataclass(frozen=True)
class Context:
    """What a scenario gets to decide on: the call as composed, and which call it is."""

    system_prompt: str
    prompt: str
    capture_path: Path
    call_index: int  # 0-based within one fake

    @property
    def step(self) -> str:
        """``<seq>-<step label>``, read off the capture's name ``<seq>-<label>-a<attempt>.stream.jsonl``."""
        name = self.capture_path.name.removesuffix(runlog.CALL_STREAM_SUFFIX)
        return name.rpartition("-a")[0]

    def brief_text(self) -> str:
        """The composed brief, for a scenario that wants to answer what it was asked."""
        return self.prompt


@dataclass(frozen=True)
class Response:
    """What a scenario produces: the reply text, and how the request ended."""

    text: str = ""
    outcome: Outcome = Outcome.OK


Scenario = Callable[[Context], Response]


def clean(text: str = "ok") -> Scenario:
    """A request that completed with ``text`` as its reply."""

    def scenario(context: Context) -> Response:
        del context
        return Response(text=text)

    return scenario


def transport_die() -> Scenario:
    """A request that did not complete: retry territory."""

    def scenario(context: Context) -> Response:
        del context
        return Response(outcome=Outcome.TRANSPORT_FAILURE)

    return scenario


def sequence(*scenarios: Scenario) -> Scenario:
    """Answer differently on successive calls; the last one repeats."""
    if not scenarios:
        raise ValueError("sequence() needs at least one scenario")

    def scenario(context: Context) -> Response:
        return scenarios[min(context.call_index, len(scenarios) - 1)](context)

    return scenario


class FakeChat:
    """``call.Caller.transport`` that runs a scenario instead of a request."""

    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario
        self.seen: list[Context] = []

    @property
    def calls(self) -> int:
        """How many requests this fake has served."""
        return len(self.seen)

    def __call__(
        self, *, system_prompt: str, prompt: str, timeout_seconds: float, capture_path: Path
    ) -> tuple[str, Outcome]:
        del timeout_seconds
        context = Context(
            system_prompt=system_prompt, prompt=prompt, capture_path=capture_path, call_index=len(self.seen)
        )
        self.seen.append(context)
        response = self._scenario(context)
        return response.text, response.outcome


# --- the shapes a return carries --------------------------------------------


def stamped_leaf(document: str, *, claims: Sequence[str]) -> str:
    """One rendered leaf with its metadata block stamped in, and its body untouched.

    The one composer of a realistic distilled leaf, which the buildout suite
    stands a KB tree up with. The block itself is ``render``'s — the one
    composer of the shape the write op a real member calls already owns.
    """
    values = render.FrontmatterValues(kind="leaf", claims=tuple(claims))
    head, _, body = document.partition("\n")
    return "\n".join([head, "", render.render_frontmatter_block(values), body])
