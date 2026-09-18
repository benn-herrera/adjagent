"""The outer loop: stage iteration, step execution, resume, exit selection.

The sequencer. It walks ``steps.py``'s table in order, computes each row's
per-call slots, hands calls to ``call.py``, records stages through
``ledger.py``, raises registry barriers through ``barriers.py``, and chooses the
exit code the run ends on. It holds no template text, constructs no subprocess,
and reads no TOML.

**Nothing a later stage reads is carried in an attribute.**
:data:`RUNNER_ATTRIBUTES` is the closed set a :class:`Runner` may hold and is
where the criterion that admits one is stated; everything else is re-derived at
the point of use, the way ``_recorded`` is re-read from the ledger and the way
``seed.graph-init`` asks the working tree which runner file it carries.

**Position comes from the ledger, and from nothing else.** A recorded stage is
not re-walked and an unrecorded one is walked from its first row, so what a
resume re-runs is everything the last boundary does not account for — including
work whose artifact is sitting on disk. That is the discard rule rather than a
lost optimization: an artifact no boundary accounts for cannot be told from one
a dying process half-earned, and the stage table is what makes discarding it
cheap, every row that spends a model call standing immediately in front of its
own boundary (``steps.STEPS``; SPEC.md, The Driver's Contract).

**A launch is an invocation that finds ``start`` unrecorded, and nothing
configures that.** There is no build-mode setting and no row states a mode it
belongs to: the ledger's recorded-stage set is read at the top of every walk and
is the whole of what says where this invocation stands. The one place the
distinction is acted on is :meth:`Runner._pre_kb_root`, a row of the ``start``
stage — so it runs on a launch and never on a resume, by the same skip that
makes a recorded stage unwalked — where a ``kb-root/`` holding documents this
build did not write refuses rather than being overwritten.

**Nothing here counts a call, and no call's number is read back off disk.** A
stage's rows are a fixed sequence, so what a stage spent is what its rows are:
``phase-5`` dispatches one review and one revision, and its ledger entry says
both are behind it. A file an earlier process left under the scratch layout is
therefore not a spent anything — it is work no boundary accounts for, and the
row that really runs overwrites it.

**Barriers are exits.** Nothing here blocks on a human. A raise persists the
barrier record, relays it, and ends the walk with the registry's exit code; the
answer arrives on the next invocation. A barrier answered from config or
``--decide`` resumes the walk in place, and a second raise of the same pair in
one process is an automatic stop.

**No row grades what it writes.** Every rigor value and every on-point fraction
a minting row authors is the unscored literal, and stays it: the build authors
the graph and the maintenance tooling scores it, through its own front door.
``*pending*`` is the expected terminal state, and nothing here refuses it. No
row of this table mints anything, either: the three ``kb_claimgraph``
invocations mint mechanically, inside the tool, checked by that tool's own gate
and by ``phase-3a``'s verify coverage.

**No stage repairs a gate.** ``phase-3a`` runs the three verifiers and either
records or stops: what each of them compares is one mechanically-produced
artifact against another, so a red one is a defect in a tool or in what was
authored and there is nothing for a seat to remediate in the KB. ``phase-5``
is a fixed sequence over the documents ``overview-drafted`` wrote and its
boundary committed — one review, then one revision answering it
(:meth:`Runner._p5_review_and_fix`). **No severity fails the stage**: every
finding the reviewer sorted is reported by :meth:`Runner._report_review`, the
revision answers what it can, and the stage records.

**Scope**: the walk covers :data:`steps.TABLE_STAGE_IDS` — every stage of the
pipeline. ``execute`` still takes the stage list, because a test that means to
exercise one stage's rows should not have to walk every other stage to reach
them; exit 0 means every stage walked is recorded.

**One flag bounds the walk, and a bounded run is not a failed one.**
``--through`` names the last stage to walk, cut in :meth:`Runner._walk`.
Reaching it is exit :data:`baton.EXIT_BOUNDED`: the ledger stands where the
walk stopped and the next invocation resumes there.

**``--no-inference`` excludes rows and bounds nothing.** Every row that would
cost a model call is dropped by :meth:`Runner._applies` — a property the rows
derive (``steps.Step.spends_inference``) rather than a stage id anything here
names — and the walk carries on past it, so the build closes out. The boundary
commit of a stage that lost rows says so (:meth:`Runner._stage_note`), and the
record carries the same flag onward so the ledger's own coverage check knows
what kind of build it is recording. A bounded run stops and resumes; a build
spending no inference is finished without those rows.

Stdlib only.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType

from .. import inference, kb_pipeline, kb_readme, kb_util
from . import barriers, baton, call, checklist, envelope, ledger, runlog, steps
from .config import NO_INFERENCE_FLAG, THROUGH_FLAG, Decision, DriverConfig

_log = runlog.logger("run")

#: The review ``p5.fix``'s handler dispatches ahead of its own call.
REVIEW_STEP = "p5.review"

# Rows whose execution belongs to another row's handler rather than to the
# linear walk, so the walk must not also run them in table order. `p5.review`
# is the one: its stage is a fixed sequence of two calls, and running them from
# one handler is what puts both in front of one boundary rather than leaving the
# review's call accounted for by nothing (SPEC.md, The Driver's Contract).
DRIVEN_STEPS: frozenset[str] = frozenset({REVIEW_STEP})

# Preflight's own remediation marker. `ov.docent-check` relays the `restore:`
# line preflight already prints for a missing docent command rather than
# composing a second wording of the same action.
_RESTORE_MARKER = "restore:"


# --- the terminal state ------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Result:
    """How the run ended, and everything its baton and ``exit.json`` need.

    ``context`` is built once, by :func:`execute`, and is the same object the
    barrier record's own baton was rendered from — so the card in the file and
    the card on the terminal cannot differ.
    """

    exit_code: int
    detail: tuple[str, ...] = ()
    pair: str = ""
    question: str = ""
    admissible: tuple[str, ...] = ()
    unconsumed_decisions: tuple[str, ...] = ()
    barrier_record: Path | None = None
    context: baton.BatonContext = baton.BatonContext()


class _Halt(Exception):
    """A terminal state reached inside the walk. Carries the :class:`Result` that holds."""

    def __init__(self, result: Result) -> None:
        super().__init__(f"halt: exit {result.exit_code}")
        self.result = result


def _context(config: DriverConfig, paths: runlog.RunPaths, result: Result) -> baton.BatonContext:
    """The baton context for a result. One function, so file and terminal agree."""
    return baton.BatonContext(
        invocation=config.invocation,
        pair=result.pair,
        question=result.question,
        admissible=result.admissible,
        run_dir=str(paths.run_dir),
        detail=result.detail,
        unconsumed_decisions=result.unconsumed_decisions,
    )


def write_report(
    paths: runlog.RunPaths,
    *,
    exit_code: int,
    barrier_record: Path | None = None,
    unconsumed_decisions: Sequence[str] = (),
) -> None:
    """The run directory's terminal report: ``cadence.jsonl``, then ``exit.json``.

    Called on **every** way out of a run, the ones nobody planned included — a
    boundary check that failed, a signal, an exception no handler names. Those
    are the endings whose own card calls the run directory the bug report, and
    ``exit.json`` is the one channel a backgrounded session has for learning how
    a run ended, so they are exactly the endings that may not leave it empty.

    The cadence extraction lives here rather than beside ``write_exit_json`` for
    one reason: a record carries the *stage* a call served, and ``cli`` states in
    its own docstring that it holds no stage knowledge. This is the outermost
    layer that has any, and by the time a run is over every capture in ``calls/``
    is complete — so the pass is one read of each and no call is missed. Both
    files are always written, so "missing" never has to be told apart from
    "never extracted": a run that made no calls leaves an empty
    ``cadence.jsonl``.
    """
    runlog.write_cadence(paths, stages={step.id: step.stage for step in steps.STEPS_BY_ID.values()})
    runlog.write_exit_json(
        paths,
        exit_code=exit_code,
        barrier_record=barrier_record,
        unconsumed_decisions=unconsumed_decisions,
    )


# --- the ledger seam ---------------------------------------------------------


@dataclass(frozen=True)
class LedgerOps:
    """The ledger surface the walk uses, bound to one repo root — the tests' seam.

    A seam rather than a direct call because the loop's decisions are worth
    testing without a git repository and a real toolchain behind every one of
    them, and the adapter itself is tested against the real ``kb_util`` in its
    own suite. Each callable is keyword-only, so no pair of same-typed
    arguments can be swapped at a call site.
    """

    preflight: Callable[..., ledger.Outcome]
    graph_init: Callable[..., ledger.Outcome]
    # The two build front ends the head runs. `document_graph` takes the run's
    # own sources; `claim_graph` takes the flags of whichever of its three
    # invocations the calling row means, so the row states which pass it is and
    # the adapter states nothing.
    document_graph: Callable[..., ledger.Outcome]
    claim_graph: Callable[..., ledger.Outcome]
    start_build: Callable[..., ledger.Outcome]
    # `note` is the boundary commit's body — empty for most rows, and words
    # for a stage whose rows this build dropped. `no_inference` is not the same
    # thing said twice: the note is prose for a reader, and the flag is the
    # build property `kb_pipeline` maps to which coverage units it excuses. A
    # gate keyed on the note's wording would be a check reading prose.
    advance_step: Callable[..., ledger.Outcome]
    show_status: Callable[..., ledger.Outcome]
    # The consuming repo's `kb-refresh` / `kb-verify`, which the `refresh` and
    # `gate` row subtypes run. A nonzero target is a red gate (exit 11) and the
    # mapping lives in the adapter, not here.
    run_target: Callable[..., ledger.Outcome]


def ledger_ops_for(repo_root: Path) -> LedgerOps:
    """The real ops, with the repo root bound once."""
    return LedgerOps(
        preflight=lambda: ledger.preflight(repo_root),
        graph_init=lambda *, runner: ledger.graph_init(repo_root, runner=runner),
        document_graph=lambda *, sources, bibliographies, kb_root: ledger.document_graph(
            repo_root, sources=sources, bibliographies=bibliographies, kb_root=kb_root
        ),
        claim_graph=lambda *, flags: ledger.claim_graph(repo_root, flags=flags),
        start_build=lambda *, charter: ledger.record_start(repo_root, charter=charter),
        advance_step=lambda *, stage, note="", no_inference=False: ledger.record_stage(
            repo_root, stage=stage, note=note, no_inference=no_inference
        ),
        show_status=lambda *, relay: ledger.show_status(repo_root, relay=relay),
        run_target=lambda *, target: ledger.run_target(repo_root, target=target),
    )


# --- the predicates and readings, as their own units -------------------------


def present(path: Path) -> bool:
    """Existence and non-emptiness — the only artifact question the driver asks."""
    return path.is_file() and path.stat().st_size > 0


#: What a bibliography file is called. The document graph takes the flag once
#: per file and resolves citations against their union.
BIBLIOGRAPHY_SUFFIX = ".bib"


def bibliographies_beside(repo_root: Path, sources: Sequence[str]) -> tuple[Path, ...]:
    """Every bibliography sitting in a directory one of this run's sources sits in.

    A launch names its sources and nothing else, so where ``[run] bibliography``
    names none this is where the document graph's bibliographies come from: a
    corpus keeps its ``.bib`` beside the volume roots that cite it.

    **Sorted, and that is the determinism requirement rather than tidiness.** A
    key two files define resolves to the first one passed, so a set discovered
    by a directory read has to be ordered by something the filesystem does not
    decide, or two builds of one corpus could differ.

    Resolving the **volume roots** this way is refused by that front end, and
    for a reason that does not carry over: name the wrong root and its content
    is converted twice with every per-volume check passing on both copies,
    invisibly. A ``.bib`` the corpus does not cite is inert — citeproc renders
    only cited entries — so passing one costs nothing.
    """
    directories = dict.fromkeys((repo_root / source).resolve().parent for source in sources)
    return tuple(sorted({path for directory in directories for path in directory.glob(f"*{BIBLIOGRAPHY_SUFFIX}")}))


# --- what a Runner may hold --------------------------------------------------

#: Every attribute a :class:`Runner` may hold, and the whole of it.
#:
#: **The criterion is the stage boundary.** A resume re-enters the walk at one —
#: a recorded stage is never re-walked, and an unrecorded stage is walked from
#: its first row — so an attribute one row writes is read *stale* by a later
#: invocation exactly when its reader runs in a different stage from its writer.
#: Inside one stage there is no process boundary to lose a value across; across
#: two there always is. An attribute is therefore admissible on exactly three
#: grounds, and a name is added here only by naming which of them it stands on:
#:
#: * **the invocation fixes it**, so the invocation that resumes fixes it the
#:   same way — the constructor's arguments, and ``scratch``, computed from one;
#: * **every reader runs in the writer's own stage**, so no resume observes it —
#:   ``_seq``, whose readers are the call it numbers;
#: * **the walk re-derives it before any row reads it** — ``_recorded``, re-read
#:   from the ledger at the top of :meth:`Runner.run`.
#:
#: Anything else is resumption state and has no home here: re-derive it at the
#: point of use. ``seed.graph-init`` asking ``kb_util.detected_runner`` is that
#: shape; the same answer carried from ``pre.preflight``, two stages earlier, was
#: the defect it replaced — a resume skips ``start``, so the attribute held its
#: constructor default and the ``spine-seed.runner-choice`` barrier could not
#: fire on any invocation that resumed.
#:
#: Closure is all a machine can check here; which ground an attribute stands on
#: is the author's reading, and this registry is where it is stated.
#: :meth:`Runner._check_attributes` enforces the closure, at construction and at
#: every stage transition.
RUNNER_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "config",
        "paths",
        "repo_root",
        "caller",
        "answers",
        "ops",
        "stages",
        "scratch",
        "_seq",
        "_recorded",
    }
)


# --- the walk ----------------------------------------------------------------


class Runner:
    """One process's walk through the step table.

    Every method that can end the run raises :class:`_Halt`; the walk itself
    reads as a sequence of steps rather than as a chain of error checks, which
    is the only way a sequencer of this many stages stays legible.

    **It carries no resumption state.** :data:`RUNNER_ATTRIBUTES` is the closed
    set of attributes it may hold and states what admits one; every other
    reading a row needs is taken at the point of use, from the ledger or from
    the working tree.
    """

    def __init__(
        self,
        *,
        config: DriverConfig,
        paths: runlog.RunPaths,
        repo_root: Path,
        caller: call.Caller,
        answers: barriers.Resolver,
        ops: LedgerOps,
        stages: Sequence[str] = steps.TABLE_STAGE_IDS,
    ) -> None:
        self.config = config
        self.paths = paths
        self.repo_root = repo_root
        self.caller = caller
        self.answers = answers
        self.ops = ops
        self.stages = tuple(stages)
        self.scratch = repo_root / steps.SCRATCH_ROOT
        self._seq = 0
        self._recorded: frozenset[str] = frozenset()
        self._check_attributes()

    def _check_attributes(self) -> None:
        """The closure half of :data:`RUNNER_ATTRIBUTES`, which states the criterion.

        Run at construction and again at every stage transition, so an
        attribute bound in ``__init__`` and one a row assigns mid-walk are both
        caught — the second at the next boundary, which is the granularity the
        criterion is about.

        The offending names go in the *message*, not the record's context:
        :class:`runlog.BoundaryError`'s text is what exit 15's card carries, and
        a card saying only that the attribute set is wrong names nothing to fix.
        """
        held = set(vars(self))
        faults = [
            f"{label}: {', '.join(sorted(names))}"
            for label, names in (
                ("undeclared", held - RUNNER_ATTRIBUTES),
                ("declared but unbound", RUNNER_ATTRIBUTES - held),
            )
            if names
        ]
        runlog.require(
            not faults,
            f"a Runner's attributes are not the set RUNNER_ATTRIBUTES declares [{'; '.join(faults)}] — that "
            f"registry states what admits one, and a value a row of a later stage reads is resumption state "
            f"with no home on this object: re-derive it at the point of use",
        )

    # --- entry ---------------------------------------------------------------

    def run(self) -> Result:
        """Walk this run's stages in ledger order. Exit 0 when every one is recorded."""
        missing = sorted(set(steps.STEP_IDS) - set(_HANDLERS) - DRIVEN_STEPS)
        runlog.require(not missing, f"step table rows with no handler: {', '.join(missing)}")

        self._recorded = self._recorded_stages()
        for stage in self.stages:
            if stage in self._recorded:
                _log.info("stage is already recorded; skipping it", extra={"context": {"stage": stage}})
                continue
            walk = self._walk()
            if stage not in walk:
                return self._stopped_at_bound(stage, walk)
            self._run_stage(stage)

        _log.info(
            "the implemented cut is complete",
            extra={"context": {"stages": ", ".join(self.stages), "run_dir": str(self.paths.run_dir)}},
        )
        return self._result(baton.EXIT_OK)

    # --- the two bounds ------------------------------------------------------

    def _walk(self) -> tuple[str, ...]:
        """The stages this run may walk, cut by its one bound.

        ``--no-inference`` is not among the cuts and never was a stage-level
        question: it drops rows, in :meth:`_applies`, and every stage is still
        walked and still recorded.
        """
        walk = self.stages
        through = self.config.run.through
        if through in walk:
            walk = walk[: walk.index(through) + 1]
        return walk

    def _bound_reason(self, stage: str) -> str:
        """Why the walk stopped before ``stage``, in the operator's words.

        One bound, so one answer. It is still a method rather than an inlined
        string because the card that prints it is rendered from a result and
        the reason belongs beside the cut that produced it.
        """
        del stage
        return f"{THROUGH_FLAG} {self.config.run.through}"

    def _stopped_at_bound(self, stage: str, walk: Sequence[str]) -> Result:
        """End the run at its bound: told to stop, ledger resumable, nothing failed.

        The stage reached is named here rather than at launch because only this
        layer knows one. Exit :data:`baton.EXIT_BOUNDED`, whose card resumes
        without the bound.
        """
        reason = self._bound_reason(stage)
        _log.info(
            "the run stopped at its bound; the stages past it are unwalked and the ledger resumes there",
            extra={"context": {"stopped_before": stage, "walked": ", ".join(walk), "bound": reason}},
        )
        return self._result(
            baton.EXIT_BOUNDED,
            detail=(
                f"walked through {walk[-1] if walk else '(no stage)'} and stopped before {stage} — {reason}",
                "the ledger is resumable: re-run without the bound to continue from here",
            ),
        )

    def _run_stage(self, stage: str) -> None:
        self._check_attributes()
        for step in steps.steps_for(stage):
            if step.id in DRIVEN_STEPS:
                continue
            if not self._applies(step):
                _log.info(
                    "row does not apply to this run",
                    extra={"context": {"step": step.id, "spends_inference": step.spends_inference}},
                )
                continue
            _log.info("step", extra={"context": {"step": step.id, "stage": stage, "unit": step.unit.value}})
            _HANDLERS[step.id](self, step)

    def _applies(self, step: steps.Step) -> bool:
        """The one condition left: what this run will spend.

        The predicate itself is ``steps``', because the note below asks the same
        question of the same rows, and two readings of "does this row apply" is
        one more than the table can have.
        """
        return steps.applies(step, spend_inference=not self.config.run.no_inference)

    # --- terminal states -----------------------------------------------------

    def _result(self, exit_code: int, **fields: object) -> Result:
        """A result carrying the run's final unconsumed-decision list."""
        return Result(exit_code=exit_code, unconsumed_decisions=self.answers.unconsumed, **fields)  # type: ignore[arg-type]

    def _halt(self, exit_code: int, *detail: str) -> None:
        raise _Halt(self._result(exit_code, detail=tuple(detail)))

    def _halt_unless(self, outcome: ledger.Outcome) -> ledger.Outcome:
        """A ledger op's rc is already a driver exit code; a failed one ends the run."""
        if not outcome.ok:
            raise _Halt(self._result(outcome.exit_code, detail=outcome.detail))
        return outcome

    # --- barriers ------------------------------------------------------------

    def _decide(self, pair: str, *, artifacts: Sequence[Path] = (), detail: Sequence[str] = ()) -> Decision:
        """Resolve a barrier, or end the run at it.

        Every admissible answer continues, so what ends the run here is an
        unanswered barrier: no answer was supplied, or one was already spent in
        this process. Both reach the same record and the same code.
        """
        spec = barriers.spec(pair)
        decision = self.answers.take(pair)
        if decision is not None:
            return decision
        raise _Halt(self._raise_barrier(spec, artifacts=artifacts, detail=detail))

    def _raise_barrier(
        self,
        spec: barriers.BarrierSpec,
        *,
        artifacts: Sequence[Path],
        detail: Sequence[str],
    ) -> Result:
        """Persist the barrier record, relay it, and return the result that ends the run.

        The record file is this body followed by the very baton ``cli.main`` is
        about to print, rendered from the same context — so the file and the
        terminal carry the same bytes, with the baton appearing exactly once in
        each.
        """
        # The display is read without relaying: it is about to be printed as
        # the head of the record, and printing it twice is the one way a
        # relayed render stops being liftable.
        status = self.ops.show_status(relay=False)
        record = barriers.record(
            spec,
            render=status.stdout,
            artifacts=[self._repo_relative(path) for path in artifacts],
            run_dir=str(self.paths.run_dir),
            unconsumed=self.answers.unconsumed,
        )

        result = self._result(
            spec.exit_code,
            detail=tuple(detail),
            pair=spec.pair,
            question=spec.question,
            admissible=spec.answers,
            barrier_record=self.paths.barriers / f"{spec.stage}-{spec.kind}.md",
        )
        body = baton.render_record(record)
        card = baton.render(spec.exit_code, _context(self.config, self.paths, result))
        assert result.barrier_record is not None  # set immediately above
        result.barrier_record.write_text(f"{body}\n{card}\n", encoding="utf-8")

        _log.warning(
            "barrier raised; the run stops here",
            extra={
                "context": {
                    "pair": spec.pair,
                    "exit_code": spec.exit_code,
                    "record": str(result.barrier_record),
                }
            },
        )
        # The complete render, verbatim, at the head of the message body
        # the session pastes. cli.main prints the baton under it.
        runlog.relay(body)
        return result

    # --- ledger reads and the display ----------------------------------------

    def _recorded_stages(self) -> frozenset[str]:
        """The recorded-stage set, from the ledger's own render."""
        status = self._halt_unless(self.ops.show_status(relay=False))
        # `checklist.recorded_stages` is the one parse of the checklist block. A
        # second regex over the same render here is how two readings of one
        # format start to disagree.
        return checklist.recorded_stages(status.stdout)

    def _display(self) -> None:
        """The complete verbatim stdout of show-status, at every stage transition."""
        self._halt_unless(self.ops.show_status(relay=True))

    def _repo_relative(self, path: Path) -> str:
        """A path as a log line, a barrier record or a relay card states it.

        For a reader who is standing in this repository, never for a brief:
        a seat resolves a path against a cwd no brief states, so a path a brief
        carries is :meth:`_brief_path`'s.
        """
        try:
            return str(path.relative_to(self.repo_root))
        except ValueError:
            return str(path)

    @staticmethod
    def _brief_path(path: Path | None) -> str:
        """A path as a brief states it: absolute, or the named absence.

        ``steps.PATH_SLOTS`` says which slots this is the composer of, and
        ``call.py`` refuses the call where a value reaches one any other way.
        """
        return steps.NOTHING if path is None else str(path)

    # --- calls ---------------------------------------------------------------

    def _call(
        self,
        step: steps.Step,
        *,
        slots: Mapping[str, str],
        outputs: Sequence[Path] = (),
    ) -> call.CallOutcome:
        """One row's call. A failed contract ends the run at the code ``call.py`` chose."""
        self._seq += 1
        outcome = self.caller.execute(
            call.CallRequest(step=step, seq=self._seq, slots=dict(slots), outputs=tuple(outputs))
        )
        if not outcome.ok:
            raise _Halt(self._result(outcome.exit_code, detail=outcome.detail))
        return outcome

    # --- pre-stage rows ------------------------------------------------------

    def _pre_lock(self, step: steps.Step) -> None:
        """``pre.lock``: the lock is taken by ``cli`` around the whole run; assert it is held.

        The lock is the repository's, not the run directory's, so this
        asks the repo root about it rather than ``paths``.
        """
        del step
        lock = runlog.repo_lock_path(self.repo_root)
        runlog.require(lock.is_file(), "the run lock is not held", lock=str(lock))

    def _pre_preflight(self, step: steps.Step) -> None:
        """``pre.preflight``: the mechanical environment report; any failure is exit 14.

        Nothing is read back off the report. Its ``runner-file`` FACT is a
        statement to the operator, and the row that needs the same answer asks
        the working tree for it (:meth:`_seed_graph_init`) rather than taking it
        from here — this row belongs to ``start``, which a resume skips whole.
        """
        del step
        self._halt_unless(self.ops.preflight())

    def _pre_charter(self, step: steps.Step) -> None:
        """``pre.charter``: say where the charter was looked for when none was found.

        A charter is optional (SPEC.md, The Driver's Contract), and its one
        consumer is ``start.record``, which names the path in the ``start``
        boundary where one stands and records the absence in words where none
        does. No brief carries it and no row's ``slots`` declares a charter
        slot, so this row resolves nothing for one. What it does is name the
        configured path at the moment it was looked at and found empty — a
        charter written somewhere this build never looked is visible in the run
        log rather than inferred from a boundary that named none.
        """
        del step
        if self._charter() is None:
            _log.info(
                "no charter stands at the configured path; this build carries none",
                extra={"context": {"charter_file": str(self.config.run.charter_file)}},
            )

    def _charter(self) -> str | None:
        """The charter's repo-relative path, or ``None`` where the build carries none."""
        if not present(self.repo_root / self.config.run.charter_file):
            return None
        return str(self.config.run.charter_file)

    def _pre_kb_root(self, step: steps.Step) -> None:
        """``pre.kb-root``: refuse to open a build over a KB this build did not write.

        The tri-state (``kb_util.kb_root_state``) decides, and each value has a
        behaviour of its own:

        * ``absent`` — nothing is there and ``document-graph`` creates it.
          Proceed.
        * ``spine-only`` — the directory holds nothing outside ``.index/``,
          which is derived space rebuilt unconditionally from the authored
          Markdown. There is no authored byte to lose, so this is the seeded-
          but-empty case and it proceeds too, stating what it found rather than
          passing silently: it is not the same state as ``absent`` and a reader
          of the log should not have to infer which one held.
        * ``populated`` — the tree holds documents, and ``dg.build`` writes a
          tree whole. Refuse.

        **This runs on a launch and never on a resume**, because every row of
        the ``start`` stage is skipped once ``start`` is recorded. That is the
        whole mechanism: an invocation that finds ``start`` unrecorded is
        opening a build, so a populated ``kb-root/`` in front of it is somebody
        else's work; an invocation that finds it recorded is continuing one, and
        the populated tree in front of *it* is the build's own product.
        """
        del step
        state = kb_util.kb_root_state(self.repo_root)
        kb_root = self._repo_relative(kb_util.kb_root(self.repo_root))
        if state != kb_util.KB_ROOT_POPULATED:
            _log.info("kb-root state at launch", extra={"context": {"state": state, "kb_root": kb_root}})
            return
        self._halt(
            baton.EXIT_ENVIRONMENT,
            f"pre.kb-root: {kb_root} is {state} and this invocation is opening a build, not resuming "
            f"one — the document graph writes the tree whole, so the documents there would be "
            f"overwritten",
            "restore: resume the build that wrote them (the ledger's recorded stages are its "
            "position; no mode flag selects it), or move that tree aside and re-run to build afresh",
        )

    def _start_record(self, step: steps.Step) -> None:
        """``start.record``: the build boundary. rc 5 (already started) reads as done.

        A build with no charter records without one: the commit's body names the
        charter where there is one to name, and states the absence where there is
        not (``kb_pipeline.NO_CHARTER_BODY``).
        """
        self._halt_unless(self.ops.start_build(charter=self._charter() or ""))
        self._stage_recorded(step.stage)

    # --- the head: the build's own production --------------------------------

    def _bibliographies(self) -> tuple[Path, ...]:
        """The bibliographies the document graph resolves citations against.

        Resolved from where the sources sit, and narrowed to one file by
        ``[run] bibliography`` where a run needs that said — which is what keeps
        the launch line to the sources it already carries.

        **Several ``.bib`` files is not an ambiguity, and there was never a
        choice to make.** ``--bibliography`` is repeatable: the reader merges
        every file it is given, and citeproc renders only the entries a source
        actually cites, so a template's stray ``sample-base.bib`` full of
        unrelated works is inert. The union therefore contains whatever file the
        author declared, and a ``\\bibliography{strings,refs}`` naming two files
        as one bibliography is an ordinary corpus rather than a conflict.

        **Absence is legal too.** A corpus with no ``.bib`` is an ordinary
        corpus: many ship a pre-generated ``.bbl`` or inline ``\\bibitem``, and
        their citations still reach the tree carrying their own keys — what is
        lost is resolution and the references leaf, not the citations.
        """
        named = self.config.run.bibliography
        if named:
            path = self.repo_root / named
            if not path.is_file():
                self._halt(
                    baton.EXIT_ENVIRONMENT,
                    f"[run] bibliography names {named}, and no file stands there — restore: correct the "
                    f"path, or remove the key and keep the corpus's {BIBLIOGRAPHY_SUFFIX} beside its sources",
                )
            return (path,)
        found = bibliographies_beside(self.repo_root, self.config.run.sources)
        if not found:
            _log.info(
                "no bibliography sits beside this build's sources; citations will carry their own keys "
                "and no volume gains a references leaf",
                extra={"context": {"sources": ", ".join(self.config.run.sources)}},
            )
        return found

    def _dg_build(self, step: steps.Step) -> None:
        """``dg.build``: the document tree, derived from this run's sources.

        The tree is the build's own product rather than something handed to it.
        Every source is a volume root, and ``kb-root/`` is where the tree lands
        — a name the toolchain hard-codes and takes no override for.

        The front end writes the tree whole, so this row over a tree a finished
        build already stamped would overwrite the documents the spine sits in.
        Two things keep it off that tree: a recorded stage is never re-walked,
        and ``pre.kb-root`` refuses to open a build over a populated one.
        """
        del step
        self._halt_unless(
            self.ops.document_graph(
                sources=self.config.run.sources,
                bibliographies=[str(path) for path in self._bibliographies()],
                kb_root=str(self._kb_root),
            )
        )

    def _seed_graph_init(self, step: steps.Step) -> None:
        """``seed.graph-init``: initialise the claim-graph spine over the tree.

        A ``kb-root/`` with no document tree in it halts the run: the stage
        above is what writes one, and its boundary commit is also what leaves
        the worktree clean for this seed's own preflight.

        **Whether this repository carries a runner file is read here, from the
        working tree.** It is the same reading ``preflight`` reports as a FACT —
        ``kb_util.detected_runner``, one definition — and taking it at the point
        of use is what lets the barrier fire on a resume: ``pre.preflight`` is a
        ``start`` row, so an invocation that finds ``start`` recorded never runs
        it, and an attribute holding its answer would hold its constructor
        default instead (:data:`RUNNER_ATTRIBUTES`).
        """
        del step
        runner = self.config.run.runner
        if runner is None and kb_util.detected_runner(self.repo_root) is None:
            runner = self._decide(barriers.SPINE_SEED_RUNNER_CHOICE).answer

        self._halt_unless(self.ops.graph_init(runner=runner))

    def _claim_graph(self, step: steps.Step) -> None:
        """One ``kb_claimgraph`` invocation, composed from the stage the row belongs to.

        The row states nothing about passes or scopes. Which invocation its
        stage is, is ``kb_pipeline``'s declaration, and the tool resolves the
        same flags back to the same stage on the other side of the subprocess —
        so a row cannot ask for a pass that runs as a different stage.
        """
        stage = kb_pipeline.stage_by_id(step.stage)
        runlog.require(
            stage.claimgraph_invocation is not None,
            "a claim-graph row's stage declares no invocation",
            step=step.id,
            stage=step.stage,
        )
        assert stage.claimgraph_invocation is not None  # required above
        # The tool's own flag, not a dropped row: stage D's narrowing settles
        # every edge containment decides whether or not a model is reachable,
        # and only the pairs left open need one.
        flags = stage.claimgraph_invocation.flags + (
            (kb_util.NO_INFERENCE_FLAG,) if self.config.run.no_inference else ()
        )
        self._halt_unless(self.ops.claim_graph(flags=flags))

    def _declared_build(self, step: steps.Step) -> None:
        """``declared.build``: the claims the corpus's author marked, mechanically."""
        self._claim_graph(step)

    def _discover_build(self, step: steps.Step) -> None:
        """``discover.build``: stage C-inf, one ask per awaiting document.

        The model this row spends is spawned inside ``kb_claimgraph``, through
        that package's own seat seam, and the whole of the row is that call —
        which is the row's ``spends_own_inference`` declaration, and why a run
        told to spend none never reaches this handler at all.
        """
        self._claim_graph(step)

    def _depends_attribute(self, step: steps.Step) -> None:
        """``depends.attribute``: stage D, over the graph discovery left."""
        self._claim_graph(step)

    # --- recording -----------------------------------------------------------

    def _record_stage(self, step: steps.Step) -> None:
        """Every stage's last row: ``advance-step``, then the render.

        The record carries two things beyond the stage. The note is prose, for a
        reader of the commit trail. ``no_inference`` is the build property the
        ledger's own coverage check reads — passed on every record rather than
        only on the stages that lost rows, because which units it excuses is
        ``kb_pipeline``'s classification and not this layer's to anticipate.
        """
        self._halt_unless(
            self.ops.advance_step(
                stage=step.stage,
                note=self._stage_note(step.stage),
                no_inference=self.config.run.no_inference,
            )
        )
        self._stage_recorded(step.stage)

    def _stage_note(self, stage: str) -> str:
        """What the boundary commit says about this stage beyond that it happened.

        One clause, and only a build that dropped a row earns it.

        **A dropped row is the one thing about a finished build its own product
        cannot state.** A document a stage never read looks exactly like one it
        read and found nothing in — both carry the awaiting reason the declared
        pass wrote — so a later reader counting documents learns nothing, and the
        ledger is the build record. Writing it here is what keeps that reader
        from having to infer it.

        The rows are named rather than counted: which of a stage's rows cost a
        model call is the step table's answer (``steps.inference_rows``), and a
        note stating a number would be a second view of it.

        What a stage that ran everything *did* needs no clause: its rows are a
        fixed sequence, so its entry saying the stage is behind the build says
        every one of them ran.
        """
        if not self.config.run.no_inference:
            return ""
        dropped = steps.inference_rows(stage)
        if not dropped:
            return ""
        return (
            f"{NO_INFERENCE_FLAG}: this build spent no model call, so {', '.join(dropped)} did not run. "
            f"Every row of this stage that costs none ran; what the dropped rows would have authored is "
            f"absent from the KB, and whatever the stage before them wrote about it stands."
        )

    def _stage_recorded(self, stage: str) -> None:
        self._recorded = self._recorded | {stage}
        self._display()

    # --- the runner targets: the `gate` row subtype --------------------------

    def _run_target(self, target: str) -> ledger.Outcome:
        return self.ops.run_target(target=target)

    def _gate(self) -> ledger.Outcome:
        """A ``gate`` row: ``kb-refresh`` then ``kb-verify``. Returns verify's outcome.

        A refresh that cannot run at all ends the run here — nothing downstream
        can read an index that was never rebuilt. Only verify's outcome is a
        gate verdict; an exit 14 (no runner target installed) is an environment
        fault rather than a finding about the KB.
        """
        self._halt_unless(self._run_target(kb_util.TARGET_REFRESH))
        return self._run_target(kb_util.TARGET_VERIFY)

    @property
    def _kb_root(self) -> Path:
        return kb_util.kb_root(self.repo_root)

    # --- phase-3a ------------------------------------------------------------

    def _p3a_gate(self, step: steps.Step) -> None:
        """``p3a.gate``: ``kb-refresh`` then ``kb-verify``, green or the run stops.

        There is no repair round here and no seat to run one. Each of the three
        verifiers compares one mechanically-produced artifact against another —
        every edge resolving among the claims that exist, the graph acyclic, the
        derived index against the authored bytes — so a red one is a defect in a
        tool or in what was authored, and neither is answered by rewriting the
        KB. The verifier's whole report reaches the run log at INFO
        (``ledger.run_target``); what reaches the card is which target failed
        and the lines of its report that name the failure, bounded
        (``ledger._failure_detail``). No barrier is raised, so the card is the
        no-answer one rather than the answer-substituting one.
        """
        del step
        self._halt_unless(self._gate())

    # --- phase-5: the review, and the one revision that answers it ------------

    def _findings_path(self, step: steps.Step) -> Path:
        """Where the review row's findings land: one review, one author, one file."""
        return self.scratch / steps.findings(stage=step.stage, author=steps.META_REVIEW_SEAT)

    def _report_review(self, verdict: envelope.Verdict, *, stage: str, findings: Path) -> None:
        """State the review's counts by severity, where the findings are, and what follows.

        **The whole statement is in the message text**, because the console tee
        prints messages alone and a count in the record's context would reach the
        run log and not the operator — the same reason the permission-mode
        announcement carries its value in its words.

        **Both forms are stated**, the way ``kb_docgraph.build._declarations``
        states its zero: no severity fails this stage, so a build that said
        nothing about what the reviewer raised would read exactly like a build
        whose reviewer raised nothing (SPEC.md, The Driver's Contract). This line
        is also where the stage says it ran both of its calls: the review it is
        reporting, and the revision it names as following.
        """
        raised = verdict.critical + verdict.warning + verdict.note
        consequence = (
            f"no severity fails this stage, so the {raised} finding(s) are answered by the one revision "
            "that follows and by nothing after it"
            if raised
            else "the reviewer raised no finding at any severity over these documents, and the one "
            "revision that follows runs regardless"
        )
        where = self._repo_relative(findings)
        _log.info(
            f"{stage} review: critical={verdict.critical} warning={verdict.warning} "
            f"note={verdict.note} — {consequence}; findings: {where}",
            extra={
                "context": {
                    "stage": stage,
                    "critical": verdict.critical,
                    "warning": verdict.warning,
                    "note": verdict.note,
                    "findings": where,
                }
            },
        )

    def _meta_docs(self, step: steps.Step, *, source: Path | None) -> None:
        """``ov.docs`` and ``p5.fix``: ask the seat for prose, then assemble the document.

        One template, two call sites. What changes between them is whether the
        call is answering a reviewer's findings or answering for the first time,
        and that is a slot with a named absence on the first pass.

        **The seat composes no document.** It answers the one question no read of
        the KB answers — what this corpus is and where a reader starts — and its
        return is prose, which ``call.py`` persists under the scratch layout.
        Every count the document states is read here, at the moment it is
        written, so the numbers are exact by construction rather than checked
        after the fact by a second call.
        """
        prose = self.scratch / steps.overview_prose(stage=step.stage)
        self._call(
            step,
            slots={
                "kb-root": self._brief_path(self._kb_root),
                "remediation-source-path": self._brief_path(source),
            },
            outputs=(prose,),
        )
        self._assemble_overview(step, prose=prose, target=self._kb_root / kb_pipeline.OVERVIEW_DOC)

    def _assemble_overview(self, step: steps.Step, *, prose: Path, target: Path) -> None:
        """The stage's own half: the packaged template, the derived facts, the seat's answer.

        The one place this driver writes under ``kb-root/``, and it writes bytes
        it composed rather than bytes a model returned — the seat's answer
        reaches the file as the value of one slot, in a document whose every
        other word is the template's or the index's.

        Both call sites compose over whatever stands: the draft because
        re-composing what stands is exactly what it is for on a resume past a
        lost boundary, and the revision because it is asked the same question the
        draft was, from the tree, with the review beside it.
        """
        try:
            text = kb_readme.assemble(
                kb_root=self._kb_root,
                project_name=self.repo_root.name,
                prose={kb_readme.PROSE_SLOT: prose.read_text(encoding="utf-8").strip()},
            )
        except (kb_pipeline.PipelineError, FileNotFoundError) as exc:
            self._halt(baton.EXIT_ENVIRONMENT, f"{step.id}: {exc}")
            return
        except kb_readme.TemplateError as exc:
            # The shipped template and the shipped fact set disagree: neither is
            # anything an operator supplied, so this is a defect in the install
            # rather than a state a build can absorb.
            raise runlog.BoundaryError(str(exc)) from exc
        target.write_text(text, encoding="utf-8")
        _log.info(
            "the overview document was assembled from the index and the seat's answer",
            extra={"context": {"step": step.id, "document": self._repo_relative(target)}},
        )

    def _p5_review_and_fix(self, step: steps.Step) -> None:
        """``p5.fix``: the stage's whole work — one review, then one revision answering it.

        **A sequence, not a loop.** The review runs, its findings are reported at
        every severity, and the revision is handed the file it wrote. Nothing
        re-reviews, nothing is counted, and no severity the reviewer returns
        fails the stage: what a reviewer called critical and what it called a
        note reach the same one revision and the same boundary behind it.

        The review is a SINGLE never-writer: the seat returns its findings,
        ``call.py`` writes them at the path the row declares and parses the
        ``VERDICT`` off what it wrote. One reviewing seat, so its findings file
        already *is* the revision's one remediation source and nothing merges
        anything.
        """
        review = steps.STEPS_BY_ID[REVIEW_STEP]
        findings = self._findings_path(review)
        # Each document named for itself, because the pair this brief reads and
        # the set this stage's boundary checks are no longer the same set: the
        # reviewer still judges CONVENTIONS.md, which `phase-3a` stamped and no
        # boundary here asks after.
        outcome = self._call(
            review,
            slots={
                "readme-path": self._brief_path(self._kb_root / kb_pipeline.OVERVIEW_DOC),
                "conventions-path": self._brief_path(self._kb_root / kb_pipeline.CONVENTIONS_DOC),
            },
            outputs=(findings,),
        )
        runlog.require(outcome.verdict is not None, "a review returned without the verdict its row declares")
        assert outcome.verdict is not None  # required above
        self._report_review(outcome.verdict, stage=review.stage, findings=findings)

        self._meta_docs(step, source=findings)

    # --- overview-drafted ----------------------------------------------------

    def _ov_docs(self, step: steps.Step) -> None:
        """``ov.docs``: the overview document, assembled over the seat's first answer.

        **No skip on what is already on disk.** The row's own boundary is the row
        behind it, so the only invocation that reaches this one is an invocation
        the ledger says never recorded the stage — and an answer left by an
        earlier attempt is then work no boundary accounts for, which is discarded
        rather than adopted (SPEC.md, The Driver's Contract). It costs one call to
        re-ask, against trusting a file a dying process may have half-written.
        """
        self._meta_docs(step, source=None)

    def _ov_docent_check(self, step: steps.Step) -> None:
        """``ov.docent-check``: the commands that make a finished KB navigable are installed.

        The filenames are ``kb_util``'s constant, imported and never restated —
        a KB whose docent commands are absent is an incomplete install (exit
        14), not a barrier, because no answer an operator could give would
        install them. The remediation relayed is preflight's own ``restore:``
        line rather than a second wording of the same action.
        """
        commands = self.repo_root / kb_util.CLAUDE_DIRNAME / kb_util.COMMANDS_DIRNAME
        missing = [name for name in kb_util.DOCENT_COMMAND_FILENAMES if not (commands / name).is_file()]
        if not missing:
            return
        report = self.ops.preflight().stdout
        restore = tuple(line.strip() for line in report.splitlines() if _RESTORE_MARKER in line)
        self._halt(
            baton.EXIT_ENVIRONMENT,
            f"{step.id}: missing {', '.join(missing)} under {self._repo_relative(commands)} — incomplete install",
            *(restore or ("restore: re-install the agent set into this repository, then re-run",)),
        )


#: Row id → the handler that executes it. A row with no entry here and no place
#: in :data:`DRIVEN_STEPS` fails the boundary check at the top of the walk,
#: so a new row cannot be silently unexecuted.
_HANDLERS: Mapping[str, Callable[[Runner, steps.Step], None]] = MappingProxyType(
    {
        "pre.lock": Runner._pre_lock,
        "pre.preflight": Runner._pre_preflight,
        "pre.charter": Runner._pre_charter,
        "pre.kb-root": Runner._pre_kb_root,
        "start.record": Runner._start_record,
        "dg.build": Runner._dg_build,
        "dg.record": Runner._record_stage,
        "seed.graph-init": Runner._seed_graph_init,
        "seed.record": Runner._record_stage,
        "declared.build": Runner._declared_build,
        "declared.record": Runner._record_stage,
        "discover.build": Runner._discover_build,
        "discover.record": Runner._record_stage,
        "depends.attribute": Runner._depends_attribute,
        "depends.record": Runner._record_stage,
        "p3a.gate": Runner._p3a_gate,
        "p3a.record": Runner._record_stage,
        "ov.docent-check": Runner._ov_docent_check,
        "ov.docs": Runner._ov_docs,
        "ov.record": Runner._record_stage,
        "p5.fix": Runner._p5_review_and_fix,
        "p5.record": Runner._record_stage,
    }
)


# --- the entry point ---------------------------------------------------------


def _report_unconsumed(decisions: Sequence[str]) -> None:
    """State the ``--decide`` answers no barrier asked for. Silence is the one wrong outcome.

    **The whole statement is in the message text, and it goes to stderr.** The
    console tee prints a record's message alone, so a list carried in the
    context would reach ``run.log`` and not the operator; and stdout is what a
    session pastes — the ledger render, the baton, a failing tool's report — so
    a notice about the invocation itself belongs on the other stream, where it
    cannot land inside a block somebody is about to copy.

    An over-specified resume is the ordinary way this happens and it is not a
    failure: the answer decided nothing because the barrier it names was never
    raised, and the run's exit is whatever the walk decided. What it may not be
    is quiet, because the operator supplied the answer believing it would act.
    """
    if not decisions:
        return
    runlog.notify(
        f"{len(decisions)} --decide answer(s) decided nothing in this run: {', '.join(decisions)} — "
        f"the barrier each one names was never raised, so each was discarded"
    )


def execute(
    *,
    config: DriverConfig,
    paths: runlog.RunPaths,
    decisions: Sequence[Decision] = (),
    invoker: inference.Invoker | None = None,
    ops: LedgerOps | None = None,
    repo_root: Path | None = None,
    stages: Sequence[str] = steps.TABLE_STAGE_IDS,
    prompt_templates_dir: Path | None = None,
) -> Result:
    """Run the build from its ledger position and return the terminal state.

    ``stages`` is the walk, defaulting to every stage of the pipeline. It stays
    a parameter for the same reason ``ops`` and ``invoker`` are — a test that
    means to exercise one stage's rows should not have to walk every other
    stage to reach them — but no caller narrows it to buy a green any more: the
    default is the whole walk.
    ``prompt_templates_dir`` is the same
    parameterization ``call.Caller`` already documents — composition
    parameterized at its source, so a scenario can be composed against templates
    other than the installed set.

    Every *pipeline* ending returns rather than raises, including a barrier.
    :class:`runlog.BoundaryError` still propagates: a driver defect is exit 15
    and never a pipeline outcome, and ``cli`` is where that translation lives.
    """
    # The resolver is built before the root is resolved, so that even a run
    # that never reaches a barrier reports the decisions that answered nothing
    # Every terminal path carries that list, not only the ones that got
    # far enough to raise something.
    answers = barriers.Resolver(config_decisions=config.decisions, cli_decisions=decisions)

    if repo_root is None:
        try:
            repo_root = kb_util.find_git_root()
        except kb_util.RepoRootError as exc:
            result = Result(
                exit_code=baton.EXIT_ENVIRONMENT,
                detail=(str(exc),),
                unconsumed_decisions=answers.unconsumed,
            )
            return replace(result, context=_context(config, paths, result))

    runner = Runner(
        config=config,
        paths=paths,
        repo_root=repo_root,
        caller=call.Caller(
            invoker=invoker if invoker is not None else inference.SubprocessInvoker(),
            config=config,
            repo_root=repo_root,
            paths=paths,
            **({} if prompt_templates_dir is None else {"prompt_templates_dir": prompt_templates_dir}),
        ),
        answers=answers,
        ops=ops if ops is not None else ledger_ops_for(repo_root),
        stages=stages,
    )

    try:
        result = runner.run()
    except _Halt as halt:
        result = halt.result

    # The unconsumed list is final only once the walk has stopped raising.
    result = replace(result, unconsumed_decisions=answers.unconsumed)
    _report_unconsumed(result.unconsumed_decisions)
    return replace(result, context=_context(config, paths, result))
