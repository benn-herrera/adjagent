"""The typed barrier registry, answer resolution, and the record's construction.

A barrier is an **exit, never a prompt**: the driver never reads stdin from
a human and never blocks on one. A raise persists a record, prints the render
and its baton, and ends the process. The answer arrives on the *next*
invocation, through one of two doors with one vocabulary — the
``[barriers.<stage>.<kind>]`` config tables and the repeatable
``--decide <stage>.<kind>=<answer>[:<free text>]``.

What lives here:

* **The registry** — one :class:`BarrierSpec` per ``(stage, kind)``, carrying
  the admissible answers, the exit code that holds when the barrier is not
  resolved, and the question text the record renders verbatim. Every admissible
  answer continues the run; a barrier stops it by going unanswered, which is the
  only way it stops. Raise sites reference registry members, never string
  literals; :data:`REGISTRY` is the authority. **No wildcards** — a wildcard
  reintroduces the prose topic-matching the typed registry exists to kill.
* **Resolution** — :class:`Resolver`, which applies ``--decide``'s precedence
  over config, consumes each answer at most once per run (a second raise of the
  same pair is an automatic stop even if config answers it), and reports the
  ``--decide`` values whose pair was never raised.
* **The record's construction** — :func:`record` builds the
  :class:`baton.BarrierRecord`. ``baton.py`` renders it; the split is
  deliberate, and it is the same one ``BatonContext`` already has.

What does not live here: raising decisions of its own. Whether a scope line is
an expansion, whether a cap is spent, whether a gate was reached — those are
the run loop's readings of formats it parsed. This module only says what a
barrier is, what answers it takes, and what happened to the one supplied.

**Reachability, whole.** Every registered pair must have a raise site in
``steps.py``. The registry below carries every pair, the step
table holds rows for every stage, and every one of those pairs is raised by
one of them — so the unit tests assert both directions over the **whole**
registry rather than over a cut: no raise site names an unregistered pair, and
no registered pair is an escalation class nothing can reach.

Stdlib only.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from . import baton, runlog
from .config import Decision

_log = runlog.logger("barriers")

# --- the answer vocabulary ---------------------------------------------------
#
# Every answer token in the registry, named once. `config._ANSWER_RE` fixes the
# form (lowercase, hyphens); these fix the words, so a raise site comparing
# against one cannot drift from the set the config validator admits.

ANSWER_JUST = "just"
ANSWER_MAKE = "make"

# --- the pairs, named -------------------------------------------------------

#: Raised where the spine seed needs a runner file and this repository carries
#: neither. It is the seeding stage's, not `start`'s: a pair names the stage
#: that raises it, and the seed moved out of `start` when the document graph it
#: runs over became a stage of the build.
SPINE_SEED_RUNNER_CHOICE = "spine-seed.runner-choice"


@dataclass(frozen=True, kw_only=True)
class BarrierSpec:
    """One barrier: what may be answered, and what the record asks.

    Every admissible answer continues the run. A barrier ends it by going
    unanswered — no answer supplied, or one already spent in this process —
    which is the one path out and the one the record describes.
    """

    stage: str
    kind: str
    answers: tuple[str, ...]
    exit_code: int
    question: str

    @property
    def pair(self) -> str:
        return f"{self.stage}.{self.kind}"


_SPECS: tuple[BarrierSpec, ...] = (
    BarrierSpec(
        stage="spine-seed",
        kind="runner-choice",
        answers=(ANSWER_JUST, ANSWER_MAKE),
        exit_code=baton.EXIT_BARRIER,
        question=(
            "This repository has neither a justfile nor a Makefile, so the KB maintenance targets "
            "cannot be installed without being told which runner to write. Which runner?"
        ),
    ),
)

#: The registered pairs, keyed ``"<stage>.<kind>"``.
REGISTRY: Mapping[str, BarrierSpec] = MappingProxyType({item.pair: item for item in _SPECS})

#: The injection ``config.load`` and ``config.parse_decision`` take, so an answer
#: outside a barrier's admissible set is exit 13 at load — before anything runs.
ADMISSIBLE: Mapping[str, frozenset[str]] = MappingProxyType(
    {pair: frozenset(item.answers) for pair, item in REGISTRY.items()}
)


def spec(pair: str) -> BarrierSpec:
    """The registered spec for ``pair``. An unregistered pair is a driver defect (exit 15)."""
    runlog.require(pair in REGISTRY, "no such barrier is registered", pair=pair)
    return REGISTRY[pair]


# --- resolution --------------------------------------------------------------


class Resolver:
    """The run's answers: two doors, one vocabulary, each answer consumed once.

    Precedence is ``--decide`` over config for a pair. Consumption is
    per process and per pair: a second raise of the same pair returns no
    answer even when one is configured, which is what turns a static ``revise``
    on the design gate from an infinite loop into a stop.
    """

    def __init__(self, *, config_decisions: Mapping[str, Decision], cli_decisions: Sequence[Decision] = ()) -> None:
        self._config = dict(config_decisions)
        self._cli: dict[str, Decision] = {}
        for decision in cli_decisions:
            if decision.pair in self._cli:
                _log.warning(
                    "a later --decide replaces an earlier one for the same barrier",
                    extra={"context": {"pair": decision.pair, "answer": decision.answer}},
                )
            self._cli[decision.pair] = decision
        self._raised: set[str] = set()

    @property
    def raised(self) -> frozenset[str]:
        """Every pair this process has raised, answered or not."""
        return frozenset(self._raised)

    @property
    def unconsumed(self) -> tuple[str, ...]:
        """The ``--decide`` values whose pair was never raised in this run.

        Reported rather than silently dropped, so an operator resuming past an
        already-recorded stage learns that their answer did nothing:
        ``run._report_unconsumed`` states this list on stderr and in the run
        log, and it is additionally named in the baton and in ``exit.json``.
        """
        return tuple(sorted(decision.spec for pair, decision in self._cli.items() if pair not in self._raised))

    def take(self, pair: str) -> Decision | None:
        """Raise ``pair`` and consume its answer. ``None`` means stop.

        ``None`` covers both ways a barrier goes unresolved — no answer was
        supplied, or one was already consumed in this process — because
        they have the same consequence and the same record.
        """
        registered = spec(pair)
        first_raise = pair not in self._raised
        self._raised.add(pair)

        if not first_raise:
            _log.warning(
                "this barrier was already raised in this run, so its answer is spent",
                extra={"context": {"pair": pair}},
            )
            return None

        decision = self._cli.get(pair) or self._config.get(pair)
        if decision is None:
            _log.info("barrier raised with no answer supplied", extra={"context": {"pair": pair}})
            return None

        runlog.require(
            decision.answer in registered.answers,
            "a decision reached the run loop with an inadmissible answer",
            pair=pair,
            answer=decision.answer,
        )
        _log.info(
            "barrier answered",
            extra={"context": {"pair": pair, "answer": decision.answer, "source": decision.source}},
        )
        return decision


# --- the record ---------------------------------------------------------------


def record(
    registered: BarrierSpec,
    *,
    render: str,
    artifacts: Iterable[str] = (),
    run_dir: str,
    unconsumed: Sequence[str] = (),
) -> baton.BarrierRecord:
    """Build the barrier record. ``baton.render_record`` emits it; nothing here formats.

    ``render`` is the complete ``show-status`` stdout, passed through untouched.
    """
    runlog.require(bool(render.strip()), "a barrier record leads with the display, and none was captured")
    return baton.BarrierRecord(
        stage=registered.stage,
        kind=registered.kind,
        question=registered.question,
        answers=registered.answers,
        artifacts=tuple(artifacts),
        run_dir=run_dir,
        exit_code=registered.exit_code,
        render=render,
        unconsumed_decisions=tuple(unconsumed),
    )
