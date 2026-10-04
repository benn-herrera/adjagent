"""Call **policy**: transport retry, contract validation, the one re-ask, persistence.

The driver's half of one call. The transport is ``inference.call_chat`` — one
tool-less chat-completions request to the server the environment names — and
it is :attr:`Caller.transport`, injected, so a suite can stand a scripted reply
in its place. It classifies how a request ended and applies no policy. This
module is that policy, and owns everything downstream of the classification:

* **Retry.** A request that did not complete is retried on ``[retry]
  transport_attempts`` with ``backoff_seconds``; exhaustion is exit 12. An
  environment the transport refuses is exit 14 and is not retried: the fault is
  in the environment the run was launched in, and the same request fails the
  same way every time.
* **Contract validation — existence and structure only.** Declared artifacts
  exist and are non-empty, and a returned text the driver persists holds no
  line a passage may not: a heading, a list item, a table row, a code fence, a
  Markdown link or a ``.md`` path, any of which would corrupt the document the
  text is substituted into. Never content quality.
* **The one re-ask.** A contract failure re-asks the *same* step once — the
  same template, with the row's correction alternative chosen and the rejected
  lines quoted verbatim in it where there are any, the unchanged brief where
  there are none. A second failure is exit 17, naming the step and the
  complaint. It is not a barrier: no pre-supplied answer can resolve a step
  that cannot produce its declared output shape twice. The re-ask's words are
  the fragment's; this module supplies the lines and nothing else.
* **Persistence, one route plus its absence.** ``driver`` — the returned text
  *is* the artifact, and this module writes it to a contract path the model
  never chose, through a temp and a rename so the path never holds bytes nobody
  finished writing. ``—`` is a row that leaves nothing behind and must declare
  no artifact.

**The driver process never writes under ``kb-root/``.** Its writes from here
are the composed brief and the call's capture in the run directory, and the
driver-persisted artifact under the scratch layout root — the last held by a
boundary check rather than by convention.

**What this module deliberately does not do.** It parses what a return declares
and hands it back. It counts nothing about rounds, caps, or position, and it
selects no successor.

**Dependency note.** ``call`` depends on ``{inference, prompt_templates, runlog,
config}``. Naming an exit code additionally requires ``baton``, and executing a
row requires ``steps`` — both leaves, both imported for the reason
``ledger.py`` states for ``baton``: copying those constants here would be
exactly the drift single-sourcing exists to prevent. The atomic write is
``kb_survey.manifest.write_text_atomic``, the toolchain's own, imported for the
same reason — a second implementation of a write that must not tear is a second
thing to get right.

Stdlib only.
"""

import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .. import inference, kb_links, kb_pipeline
from ..kb_survey.manifest import write_text_atomic
from . import baton, prompt_templates, runlog, steps
from .config import DriverConfig

_log = runlog.logger("call")


class ParseError(ValueError):
    """A returned artifact does not carry its declared structure. Exit 17 after one re-ask.

    ``rejected_lines`` are the returned lines the structure check refused,
    verbatim — what the re-ask quotes back.
    """

    def __init__(self, complaint: str, *, rejected_lines: tuple[str, ...] = ()) -> None:
        super().__init__(complaint)
        self.rejected_lines = rejected_lines


#: The transport's shape: ``inference.call_chat``'s keyword arguments in, the
#: reply text and how the request ended out. :class:`ValueError` is an
#: environment it refuses.
Transport = Callable[..., tuple[str, inference.Outcome]]

# The re-ask's brief and captures carry this suffix. It belongs to the brief
# filename grammar, so it is `prompt_templates`' — named here only because this
# is where the second ask is labelled.
REASK_SUFFIX = prompt_templates.REASK_SUFFIX

# The units this module serves. Every other row in the step table is a
# driver-op or a gate, and neither makes a call.
CALL_UNITS = (steps.Unit.SINGLE,)

# The persistence route, plus the absence of one: a calling row may leave
# nothing behind at all. A route describes where an artifact comes from, so a
# row with no artifact has none — but it must then declare no artifact either,
# which `_check` asserts. `tool` belongs to rows that make no call.
CALL_WRITERS = (steps.Writer.NONE, steps.Writer.DRIVER)

#: The caller-supplied slot of a row's correction alternative: the rejected lines.
REJECTED_LINES_SLOT = "rejected-lines"

# What a passage may not hold, one pattern per construct, each matched within a
# line: a heading, a list item, a table row, a code fence, a Markdown link, a
# `.md` path.
_NOT_PROSE: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s{0,3}#{1,6}(?:\s|$)"),
    re.compile(r"^\s*(?:[-*+]|\d+[.)])\s"),
    re.compile(r"^\s*\|"),
    re.compile(r"^\s*(?:```|~~~)"),
    kb_links.LINK_RE,
    re.compile(r"\S\.md\b"),
)


@dataclass(frozen=True, kw_only=True)
class CallRequest:
    """One step's call, as the run loop composes it.

    ``outputs`` are the step's declared artifacts with every ``<...>`` segment
    already expanded — absolute paths, because whose cwd a relative one would
    be resolved against is exactly the ambiguity a contract check must not
    have. ``slots`` fill the template's ``@!dyn.…!@`` slots.
    """

    step: steps.Step
    seq: int
    slots: Mapping[str, str] = field(default_factory=dict)
    outputs: tuple[Path, ...] = ()


@dataclass(frozen=True, kw_only=True)
class CallOutcome:
    """What one step's call produced, and the driver exit that holds if it failed.

    ``exit_code`` is :data:`baton.EXIT_OK` when the step met its contract, and
    12, 14, or 17 otherwise. ``detail`` is the baton's extra ASK lines — for
    exit 17, the step and the validator's complaint; for exit 14, the refusal
    and the ``restore:`` line that card is printed to carry.
    """

    exit_code: int
    result_text: str = ""
    written: tuple[Path, ...] = ()
    attempts: int = 0
    detail: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.exit_code == baton.EXIT_OK


@dataclass(frozen=True, kw_only=True)
class _Ask:
    """One ask's transport history: the last request's reply, and how many requests that took."""

    text: str
    outcome: inference.Outcome
    capture_path: Path
    attempts: int


def _within(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _not_prose(text: str) -> tuple[str, ...]:
    """Every line of ``text`` holding a construct a passage may not, verbatim."""
    return tuple(line for line in text.splitlines() if any(pattern.search(line) for pattern in _NOT_PROSE))


@dataclass(frozen=True, kw_only=True)
class Caller:
    """The invariant half of a call: everything that does not change between steps.

    ``prompt_templates_dir`` is a parameter for the same reason
    ``prompt_templates.load`` takes one — composition is parameterized at its
    source — so a scenario can be composed against templates other than the
    installed set. It is the shelf the composer reads from, never
    ``paths.briefs``, which is where a *composed* brief then lands. ``sleep`` is
    the backoff clock, injected so the retry policy can be exercised without
    spending its own backoff.
    """

    config: DriverConfig
    repo_root: Path
    paths: runlog.RunPaths
    transport: Transport = inference.call_chat
    prompt_templates_dir: Path = prompt_templates.PROMPT_TEMPLATES_DIR
    sleep: Callable[[float], None] = time.sleep

    @property
    def scratch_root(self) -> Path:
        """The build-artifact layout root — the only place under the repo this module writes."""
        return self.repo_root / kb_pipeline.scratch_relroot()

    # --- the one entry point -------------------------------------------------

    def execute(self, request: CallRequest) -> CallOutcome:
        """Compose, call, validate, persist — under one retry policy and one re-ask.

        Returns rather than raises for every *pipeline* outcome. A boundary
        violation still raises :class:`runlog.BoundaryError` (exit 15): a step
        table and a template that disagree are a driver defect, not something a
        build can absorb.
        """
        step = request.step
        template, system = self._check(request)
        system_prompt = prompt_templates.render(system, slots={}, directory=self.prompt_templates_dir)
        brief_text = self._brief(request, template)
        _log.info(
            "call composed",
            extra={"context": {"step": step.id, "system": step.system, "writer": step.writer.value}},
        )

        attempts = 0
        complaint = ""
        rejected: tuple[str, ...] = ()
        for re_ask in (False, True):
            label = f"{step.id}{REASK_SUFFIX}" if re_ask else step.id
            text = self._brief(request, template, rejected=rejected) if re_ask else brief_text
            prompt_templates.persist(self.paths.briefs, seq=request.seq, step_id=label, text=text)

            try:
                ask = self._ask(request, system_prompt=system_prompt, prompt=text, label=label)
            except ValueError as refusal:
                return self._refused(request, refusal=refusal, attempts=attempts)
            attempts += ask.attempts
            if not ask.outcome.ok:
                return self._transport_failure(request, ask=ask, attempts=attempts)

            try:
                return self._accept(request, text=ask.text, attempts=attempts)
            except ParseError as exc:
                complaint, rejected = str(exc), exc.rejected_lines
                _log.warning(
                    "the return did not satisfy the step's output contract",
                    extra={
                        "context": {
                            "step": step.id,
                            "complaint": complaint,
                            "capture": str(ask.capture_path),
                            "re_ask": re_ask,
                        }
                    },
                )

        _log.error(
            "contract failure twice: the step cannot produce its declared output shape",
            extra={"context": {"step": step.id, "complaint": complaint}},
        )
        return CallOutcome(
            exit_code=baton.EXIT_CONTRACT,
            attempts=attempts,
            detail=(f"{step.id}: the declared output shape was not produced, twice", *complaint.splitlines()),
        )

    def _brief(self, request: CallRequest, template: str, *, rejected: tuple[str, ...] = ()) -> str:
        """The composed brief: the first ask's, or the re-ask's quoting ``rejected``.

        A row with a correction alternative fills it with nothing on the first
        ask and on a re-ask with no lines to quote, and with its chosen
        fragment, the lines in its slot, on a re-ask with some.
        """
        directory = self.prompt_templates_dir
        correction = request.step.correction
        if correction is None:
            return prompt_templates.render(template, slots=request.slots, directory=directory)
        slot, choice = correction
        if not rejected:
            return prompt_templates.render(
                template, slots=request.slots, alternatives={slot: None}, directory=directory
            )
        return prompt_templates.render(
            template,
            slots={**request.slots, REJECTED_LINES_SLOT: "\n".join(rejected)},
            alternatives={slot: choice},
            directory=directory,
        )

    # --- boundary checks -------------------------------------------------------

    def _check(self, request: CallRequest) -> tuple[str, str]:
        """The call boundary. Returns the template to compose and the system prompt's fragment."""
        step = request.step
        template = step.template or ""
        runlog.require(step.unit in CALL_UNITS, "this step makes no call", step=step.id, unit=step.unit.value)
        runlog.require(template, "a call step names no template", step=step.id)
        runlog.require(
            step.system in prompt_templates.FRAGMENTS,
            "a call step names no registered fragment as its system prompt",
            step=step.id,
            system=str(step.system),
        )
        runlog.require(
            step.writer in CALL_WRITERS,
            "a call step's writer is not a persistence route this module serves",
            step=step.id,
            writer=step.writer.value,
        )
        runlog.require(
            all(path.is_absolute() for path in request.outputs),
            "declared artifacts must be absolute paths",
            step=step.id,
            outputs=", ".join(str(path) for path in request.outputs),
        )
        if step.writer is steps.Writer.NONE:
            # A row taking no persistence route leaves nothing behind, so an
            # artifact declared for one would be an artifact nobody was asked to
            # write. No row in the table takes this branch today; it is the
            # table's own consistency rule rather than a live case.
            runlog.require(
                not request.outputs,
                "a call step that writes nothing must declare no artifact",
                step=step.id,
                outputs=", ".join(str(path) for path in request.outputs),
            )
        if step.writer is steps.Writer.DRIVER:
            # The driver-persists route persists the returned text, so there is
            # exactly one thing it can be persisted as.
            runlog.require(
                len(request.outputs) == 1,
                "the driver-persists route needs exactly one declared artifact",
                step=step.id,
                outputs=len(request.outputs),
            )
        assert step.system is not None  # required above
        return template, prompt_templates.FRAGMENTS[step.system]

    # --- transport, with the retry policy ------------------------------------

    def _backoff(self, attempt: int) -> float:
        """The pause before attempt ``attempt + 1``; the last configured value repeats."""
        pauses: Sequence[int] = self.config.retry.backoff_seconds
        return float(pauses[min(attempt - 1, len(pauses) - 1)]) if pauses else 0.0

    def _ask(self, request: CallRequest, *, system_prompt: str, prompt: str, label: str) -> _Ask:
        """One ask: requests up to the attempt budget, stopping at the first that completes.

        Raises the transport's :class:`ValueError` where it refuses the
        environment, which no retry changes.
        """
        step = request.step
        budget = self.config.retry.transport_attempts
        for attempt in range(1, budget + 1):
            capture_path = runlog.call_stream_path(self.paths, seq=request.seq, label=label, attempt=attempt)
            text, outcome = self.transport(
                system_prompt=system_prompt,
                prompt=prompt,
                timeout_seconds=self.config.timeouts.silence_seconds,
                capture_path=capture_path,
            )
            if outcome.ok or attempt == budget:
                return _Ask(text=text, outcome=outcome, capture_path=capture_path, attempts=attempt)
            pause = self._backoff(attempt)
            _log.warning(
                "the call died in transport; retrying",
                extra={
                    "context": {
                        "step": step.id,
                        "outcome": outcome.value,
                        "attempt": attempt,
                        "of": budget,
                        "backoff_seconds": pause,
                    }
                },
            )
            self.sleep(pause)

        raise runlog.BoundaryError(f"[retry] transport_attempts must be positive, got {budget}")

    def _refused(self, request: CallRequest, *, refusal: ValueError, attempts: int) -> CallOutcome:
        """The transport refused the environment: exit 14, not retried."""
        _log.error(
            "the call was refused before a request was made; not retried",
            extra={"context": {"step": request.step.id, "refusal": str(refusal)}},
        )
        return CallOutcome(
            exit_code=baton.EXIT_ENVIRONMENT,
            attempts=attempts,
            detail=(
                f"{request.step.id}: {refusal}",
                "restore: name the server in the environment this run is launched from, and re-run",
            ),
        )

    def _transport_failure(self, request: CallRequest, *, ask: _Ask, attempts: int) -> CallOutcome:
        """A call that never completed on any attempt: exit 12."""
        _log.error(
            "transport exhausted",
            extra={
                "context": {
                    "step": request.step.id,
                    "outcome": ask.outcome.value,
                    "attempts": ask.attempts,
                    "capture": str(ask.capture_path),
                }
            },
        )
        return CallOutcome(
            exit_code=baton.EXIT_TRANSPORT,
            attempts=attempts,
            detail=(
                f"{request.step.id}: {ask.outcome.value} after {ask.attempts} attempt(s)",
                f"last capture: {ask.capture_path}",
            ),
        )

    # --- contract validation and the persistence route -----------------------

    def _accept(self, request: CallRequest, *, text: str, attempts: int) -> CallOutcome:
        """Validate the return, persist it where the route says, and check the artifacts.

        Raises :class:`ParseError` — the one re-ask's trigger — for every way a
        return can fail its contract. **Every parse runs before any write**, so
        a malformed return never overwrites the artifact a resume would read.

        The structure check reads a model's answer, which is what earns it its
        place: the text is substituted whole into a document, so one of these
        lines corrupts it.
        """
        step = request.step
        if step.writer is steps.Writer.DRIVER and (faults := _not_prose(text)):
            raise ParseError(
                f"the returned text holds {len(faults)} line(s) a passage may not: a heading, list item, table "
                f"row, code fence, Markdown link or .md path",
                rejected_lines=faults,
            )
        written = (self._persist(request, text=text),) if step.writer is steps.Writer.DRIVER else ()
        self._check_artifacts(request)

        _log.info(
            "call met its contract",
            extra={
                "context": {
                    "step": step.id,
                    "attempts": attempts,
                    "artifacts": ", ".join(str(path) for path in request.outputs),
                    "driver_wrote": ", ".join(str(path) for path in written),
                }
            },
        )
        return CallOutcome(
            exit_code=baton.EXIT_OK,
            result_text=text,
            written=written,
            attempts=attempts,
        )

    def _persist(self, request: CallRequest, *, text: str) -> Path:
        """The driver-persists route: the returned text becomes the artifact.

        **The write is a temp and a rename, so the target name never holds a
        partial file.** Every reader of these paths asks presence and
        non-emptiness and nothing else — the contract check below, and the
        resume that skips a step whose artifacts are already there — so bytes a
        dying process left half-written would be read as work that finished. A
        rename is what makes the target either the previous file or the whole
        new one, with no third state for a reader to meet.
        """
        target = request.outputs[0]
        if not text.strip():
            raise ParseError(f"the returned text is empty, and it is the artifact this step declares ({target.name})")
        # The driver's writes are its run directory and the driver-persisted
        # artifacts under the scratch layout. KB content is the runner's and the
        # run loop's, and nothing here may reach it.
        runlog.require(
            _within(target, self.scratch_root),
            "the driver persists only under the scratch layout root",
            step=request.step.id,
            target=str(target),
            scratch_root=str(self.scratch_root),
        )
        write_text_atomic(text if text.endswith("\n") else text + "\n", target)
        _log.debug("driver persisted a returned text", extra={"context": {"artifact": str(target)}})
        return target

    def _check_artifacts(self, request: CallRequest) -> None:
        """Existence and non-emptiness of every declared artifact, whoever wrote it."""
        missing = [str(path) for path in request.outputs if not (path.is_file() and path.stat().st_size > 0)]
        if missing:
            raise ParseError(f"declared artifact(s) missing or empty: {', '.join(missing)}")
