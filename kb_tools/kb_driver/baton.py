"""Relay batons — one per exit code, plus the unlisted-code fallback.

Every terminating invocation of the driver ends by printing a baton: the card
that tells the relaying session what to place in its message body, what to ask
the user, and what to run next. The exit-code vocabulary and the ASK / THEN RUN
content both live here and only here, so a config error at load time and a
completed build print their cards through the same call — the relay reads a
card, it never remembers a protocol.

The fallback is the load-bearing row: an unrecognized exit state is the one
place a session will otherwise improvise, and improvisation there is how a
stopped build gets narrated as a working one.

It is also the sole renderer of the **barrier record** — the file in the
run directory that is not a source a session summarizes but the message body it
pastes. ``barriers.py`` constructs the :class:`BarrierRecord`; this module emits
its bytes, exactly as ``BatonContext`` is constructed elsewhere and rendered
here. The record body and the baton are printed as two calls and stored as one
file, so the bytes at stdout and the bytes on disk cannot diverge.

Stateless leaf: no state, no I/O, and no import of another driver module. This
module renders text; the caller prints it (through ``runlog.relay``).
"""

import json
from dataclasses import dataclass

from .. import kb_util

# --- exit codes -------------------------------------------------------------
#
# Driver codes start at 10, leaving 1-9 to the existing kb_util/kb_pipeline
# ladder so a driver exit is never misread as a passed-through tool exit.

EXIT_OK = 0
EXIT_BARRIER = 10
EXIT_GATE_RED = 11
EXIT_TRANSPORT = 12
EXIT_CONFIG = 13
EXIT_ENVIRONMENT = 14
EXIT_INTERNAL = 15
EXIT_LOCKED = 16
#: A dispatched call did not answer its brief: a return that could not produce
#: the declared output shape, twice (``call.Caller``). A brief and a seat are
#: what it is a mismatch between, and neither exists on a row that invokes a
#: tool and reads an exit code — such a row's missing output is
#: :data:`EXIT_COVERAGE`.
EXIT_CONTRACT = 17
#: The run stopped where it was told to — ``--through``, or the point past
#: which ``--no-inference`` cannot go. Not a failure and not a completion: the
#: ledger is resumable and the stages past the bound are simply unwalked, so
#: neither EXIT_OK's "report completion" nor the fallback's "do not interpret
#: this" is a true card for it.
EXIT_BOUNDED = 18
#: A stage was refused its boundary: the stage's own declared output is not
#: there, so the ledger would not commit it (``kb_pipeline`` exit 6). The
#: refusal names the output and where it was looked for, and no answer supplies
#: it — which is why this is its own code rather than :data:`EXIT_CONTRACT`,
#: whose remedy is a brief or a seat that these rows do not have.
EXIT_COVERAGE = 19

#: The ladder, enumerated. It is a contract with whoever reads a driver exit —
#: "the registry may add codes; it may not remove these" — so it is named here
#: rather than reconstructed wherever something means to be exhaustive over it.
#: A suite asserting that every code is reachable is asking a question about a
#: set, and a set it derived itself would only ever agree with itself, which is
#: why this is spelled out rather than read off :data:`_BATONS`.
RUN_MODE_EXIT_CODES: tuple[int, ...] = (
    EXIT_OK,
    EXIT_BARRIER,
    EXIT_GATE_RED,
    EXIT_TRANSPORT,
    EXIT_CONFIG,
    EXIT_ENVIRONMENT,
    EXIT_INTERNAL,
    EXIT_LOCKED,
    EXIT_CONTRACT,
    EXIT_BOUNDED,
    EXIT_COVERAGE,
)

# The line prefix follows the existing [kb-build] / [preflight]
# convention: the checklist block stays the only thing matching `^\[[x* ]\] `,
# so a parser lifts a relayed render without knowing about the baton.
PREFIX = "[relay]"

_RULE = "-" * 63

# Rendered in place of an ASK the caller failed to supply. A blank ask is a
# driver defect; it must look like one rather than like "nothing to ask".
_MISSING_ASK = "(missing — read the barrier record and report it verbatim)"


@dataclass(frozen=True)
class BatonContext:
    """Everything a baton can substitute. Absent fields render as placeholders."""

    #: The flags that reproduce this run — ``--config <path>``, the
    #: ``--source``/``--permission-mode`` set, or both. The resume line is a
    #: command the operator is told to run, so it carries what this run was
    #: launched with rather than the one door it might have used.
    invocation: str = ""
    pair: str = ""  # "<stage>.<kind>"
    question: str = ""  # the registry's question text, verbatim
    admissible: tuple[str, ...] = ()
    run_dir: str = ""
    detail: tuple[str, ...] = ()  # extra ASK lines: findings paths, the named key, …
    unconsumed_decisions: tuple[str, ...] = ()


@dataclass(frozen=True)
class BatonSpec:
    """One row of the baton table: what to ask, and what to run next."""

    ask: str
    then_run: tuple[str, ...]
    substitutes_answer: bool = False


# The resume names the directory this run's evidence is in, through the
# invocation it was launched with (`config.invocation` renders `--run-dir`
# wherever it is not the default).
_RESUME = f"{kb_util.DRIVER_INVOCATION} run {{invocation}}"
_DECIDE = (f"{_RESUME} \\", "    --decide {pair}=<answer>")

_BATONS: dict[int, BatonSpec] = {
    EXIT_OK: BatonSpec(
        ask="none",
        then_run=("nothing — report completion",),
    ),
    EXIT_BARRIER: BatonSpec(
        ask="{question}",
        then_run=_DECIDE,
        substitutes_answer=True,
    ),
    EXIT_GATE_RED: BatonSpec(
        ask="{question}",
        then_run=_DECIDE,
        substitutes_answer=True,
    ),
    EXIT_TRANSPORT: BatonSpec(
        ask="none — report and ask whether to retry",
        then_run=(f"{_RESUME}", "    (resume; position comes from the ledger)"),
    ),
    EXIT_CONFIG: BatonSpec(
        ask="none — report the named key and stop",
        then_run=("nothing until the config is fixed",),
    ),
    EXIT_ENVIRONMENT: BatonSpec(
        ask="none — relay the `restore:` lines as printed",
        then_run=("re-run after the restore",),
    ),
    EXIT_INTERNAL: BatonSpec(
        ask="none — report as a driver defect",
        then_run=("nothing; the run directory is the bug report: {run_dir}",),
    ),
    EXIT_LOCKED: BatonSpec(
        ask="none — report the live pid",
        then_run=("nothing while that run holds the lock — wait for it to end, or stop it first",),
    ),
    EXIT_CONTRACT: BatonSpec(
        ask="none — report the step and the validator's complaint",
        then_run=("nothing; this is a brief/worker contract mismatch",),
    ),
    # The resume line drops the bound because `config.invocation` never carried
    # it: this card's whole purpose is to name the run that goes past where the
    # last one stopped.
    EXIT_BOUNDED: BatonSpec(
        ask="none — report the stage the run stopped at and that the rest is unwalked",
        then_run=(f"{_RESUME}", "    (resume past the bound; position comes from the ledger)"),
    ),
    # The condition comes before the command, and deliberately: the resume is
    # the right act and it is the wrong act now, so a card leading with the line
    # gets run immediately, refused identically, and printed again.
    EXIT_COVERAGE: BatonSpec(
        ask=(
            "none — the stage was refused its boundary because its own declared output is not there; "
            "report that stage and the lines under this one, verbatim"
        ),
        then_run=(
            "nothing until that output stands. The stage is unrecorded, so once it does, this re-walks it:",
            f"    {_RESUME}",
        ),
    ),
}

_FALLBACK = BatonSpec(
    ask="report this output verbatim and stop; do not interpret it",
    then_run=("nothing",),
)

# The card for a code that *can* carry a registry barrier but did not.
#
# An answer-substituting code arrives one of two ways. One is a raised barrier:
# a registered pair, a question, admissible answers, and a record on disk. The
# other is a stage that failed mechanically — a build front end or a runner gate
# whose rc came back nonzero, or a row whose own check went red — which has none
# of those and no answer an operator could give (``ledger.py``: a red front end
# is a defect in the tool or its input).
#
# Which way a given code arrives is not fixed and is not asserted here: it
# follows from which ``barriers.BarrierSpec`` carries that code, and today no
# registered spec carries :data:`EXIT_GATE_RED`, so every red gate is the second
# kind. ``BatonContext.pair`` is what tells them apart at render time, because
# only a raised barrier ever sets it — a registry that gains a red-gate spec
# gets its question card back with no edit here.
#
# Rendering the barrier card for the second kind is what put a blank ask and a
# `--decide <stage>.<kind>=<answer>` resume in front of every operator whose
# build stopped on a failing stage.
_NO_BARRIER = BatonSpec(
    ask="none — report the failing stage and the lines under this one, verbatim",
    then_run=("nothing; a stage failed a mechanical check, which takes no answer — fix what it reports",),
)

# The enumerated codes, for the completeness guard.
CODES: tuple[int, ...] = tuple(sorted(_BATONS))


def render(exit_code: int, context: BatonContext | None = None) -> str:
    """Render the relay baton for ``exit_code``; unlisted codes get the fallback.

    An answer-substituting code reached without a barrier pair gets
    :data:`_NO_BARRIER` instead of its own row — see that constant.
    """
    ctx = context if context is not None else BatonContext()
    spec = _BATONS.get(exit_code, _FALLBACK)
    if spec.substitutes_answer and not ctx.pair:
        spec = _NO_BARRIER
    fields = {
        "invocation": ctx.invocation or "<the flags this run was launched with>",
        "pair": ctx.pair or "<stage>.<kind>",
        "question": ctx.question,
        "run_dir": ctx.run_dir or "<run-dir>",
    }

    lines = [
        _RULE,
        "PLACE IN YOUR MESSAGE BODY, VERBATIM:",
        "  everything above this block",
        "ASK THE USER:",
        f"  {spec.ask.format(**fields) or _MISSING_ASK}",
    ]
    lines += [f"  {line}" for line in ctx.detail]
    if ctx.admissible:
        lines += ["ADMISSIBLE ANSWERS:", f"  {' | '.join(ctx.admissible)}"]
    if ctx.unconsumed_decisions:
        # An operator resuming past an already-recorded gate must learn
        # that their answer did nothing.
        lines += ["UNCONSUMED --decide (never raised in this run):"]
        lines += [f"  {spec_text}" for spec_text in ctx.unconsumed_decisions]
    lines.append("THEN RUN, WITH THE ANSWER SUBSTITUTED:" if spec.substitutes_answer else "THEN RUN:")
    lines += [f"  {line.format(**fields)}" for line in spec.then_run]
    lines.append(_RULE)

    return "\n".join(f"{PREFIX} {line}".rstrip() for line in lines)


# --- the barrier record -----------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class BarrierRecord:
    """One raised barrier, as ``barriers.py`` constructs it for this module to render.

    ``render`` is the **complete** verbatim stdout of ``show-status`` — the
    status line, any advisory, and the checklist block. Trimming it re-creates
    the paraphrase failure the render exists to prevent, so nothing here trims
    it.
    """

    stage: str
    kind: str
    question: str
    answers: tuple[str, ...] = ()
    artifacts: tuple[str, ...] = ()
    run_dir: str = ""
    exit_code: int = EXIT_BARRIER
    render: str = ""
    unconsumed_decisions: tuple[str, ...] = ()

    @property
    def pair(self) -> str:
        return f"{self.stage}.{self.kind}"


def render_record(record: BarrierRecord) -> str:
    """Render the record body: the whole display, the ask, the paths, the JSON object.

    The baton is deliberately **not** appended here. Every terminal path leaves
    through ``cli.main``, which prints the baton for the code being returned;
    the caller writes this body followed by that same baton to
    ``barriers/<stage>-<kind>.md``, so the file and the terminal carry the same
    bytes with the baton rendered exactly once in each.
    """
    lines = [
        record.render.rstrip("\n"),
        "",
        f"# Barrier: {record.stage} / {record.kind}",
        "",
        f"**Question**: {record.question}",
        "",
        f"**Admissible answers**: {' | '.join(record.answers)}",
        "",
    ]
    if record.artifacts:
        lines += [f"**Artifact**: {artifact}" for artifact in record.artifacts]
        lines.append("")

    payload = {
        "stage": record.stage,
        "kind": record.kind,
        "answers": list(record.answers),
        "artifacts": list(record.artifacts),
        "run_dir": record.run_dir,
        "exit_code": record.exit_code,
        "unconsumed_decisions": list(record.unconsumed_decisions),
    }
    lines += ["```json", json.dumps(payload, ensure_ascii=False), "```"]
    return "\n".join(lines) + "\n"
