"""The ordered step table — the only place that says what happens next.

The pipeline sequence as data. No brief template and no dispatched seat ever
names a stage id, a record command, or a successor step; the rows below are the
sequencer, and everything else in the driver reads them. The
guard is ``prompt_templates.lint`` run over :data:`TEMPLATE_PROHIBITIONS`, which also
carries the metadata markers — the other thing a brief may never spell.

What this module holds: rows, their call unit and system prompt, the template and the
per-call slots the run loop must compute, the artifacts the contract check
looks for, and the barriers a row can raise. What it must not hold: subprocess
calls, file writes, or template text. Stage order comes from ``kb_pipeline``
and is never restated here.

**Scope**: the rows below cover every stage of the pipeline, and a run walks all
of them. :data:`TABLE_STAGE_IDS` is sliced from ``kb_pipeline.STAGE_IDS`` so it
cannot disagree with the stage vocabulary about order or membership.

Executing a row is the run loop's job. This module is a table.

Stdlib only.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from .. import kb_pipeline, kb_util

# --- vocabularies -----------------------------------------------------------


class Unit(StrEnum):
    """A step's call unit. ``SINGLE`` is the one that makes a model call."""

    DRIVER_OP = "driver-op"
    GATE = "gate"
    SINGLE = "SINGLE"


class Writer(StrEnum):
    """Who writes a step's artifacts — the persistence routes."""

    NONE = "—"
    DRIVER = "driver"
    TOOL = "tool"


class LedgerOp(StrEnum):
    """The sanctioned ledger ops. Invoked as a subprocess by ``ledger.py``, never imported.

    The member values are ``kb_util``'s own op-name constants, so these are the
    subcommand tokens rather than a copy of them: one definition, two readers.
    """

    START_BUILD = kb_util.OP_START_BUILD
    ADVANCE_STEP = kb_util.OP_ADVANCE_STEP


# --- the scratch layout this cut touches ------------------------------------
#
# The `<scratch>/kb-build/` layout (`kb_pipeline.scratch_relroot`) is a
# contract governing build artifacts — things later stages consume and
# postconditions check. These constants are the driver's own statement of it: a
# row declares its outputs as patterns over them, and the run loop resolves the
# path it writes from the same format string, so a row's declaration and the
# file it produces cannot drift.

# The charter is not a member of this layout and may not become one: it is an
# input that must already stand when the build opens, and the `start` boundary
# names its path permanently, so it lives at `kb_pipeline.CHARTER_RELPATH` in
# the tracked tree. Staging deletes this one wholesale.

# The model's whole half of the meta-documentation stage: one prose answer,
# which the driver persists here and then substitutes into the packaged overview
# template. One path per stage: the latest answer is the one the document stands
# on.
_PROSE_FMT = "{stage}/overview-prose.md"
OVERVIEW_PROSE = _PROSE_FMT.format(stage="<stage>")


def overview_prose(*, stage: str) -> str:
    """Where ``stage``'s prose answer lands, scratch-relative."""
    return _PROSE_FMT.format(stage=stage)


# --- what a template may never say --------------------------------------------

# `start` is a stage id and an ordinary English word. Matched as prose it
# would fail every template that says "start with the charter", so it is
# flagged only in its sequencing spelling. Every other id is unambiguous.
AMBIGUOUS_STAGE_IDS = frozenset({"start"})

# The two ledger-write verbs, which the driver owns outright. Both are banned
# by name: banning only one leaves a brief free to spell the other.
SEQUENCING_TOKENS: tuple[str, ...] = (LedgerOp.ADVANCE_STEP.value, LedgerOp.START_BUILD.value)

# The three metadata marker openers `kb_write.render` alone composes.
# A brief that spells one is a freehand
# instruction — the agent is being told to hand-write metadata the write API
# exists to compose — and freehand sites are not a list a reviewer re-checks by
# hand. They join the sequencing tokens in one map because the lint asks one
# question of a template line: does it say something it may not say.
METADATA_MARKER_TOKENS: tuple[str, ...] = ("<!-- id:", "<!-- kb-frontmatter", "<!-- claim-quality:")

# The write ops' one flag. A template that needs it names it through a slot the
# caller's constant pool fills; spelling it by hand is the same freehand act
# removed from the op token, and it is the token a rename would leave stale in
# every brief at once. Banning the literal is what makes "no site hand-types the flag" a
# property of the template set rather than of the sites that happen to exist.
WRITE_FLAG_TOKENS: tuple[str, ...] = (kb_util.VALUES_FLAG,)


def _template_prohibitions() -> dict[str, re.Pattern[str]]:
    # Boundaries exclude `.` and `-` so that one id does not match inside
    # another that extends it — each is flagged under its own name — and so a
    # layout path the driver itself supplies is not read as prose naming a
    # stage.
    patterns: dict[str, re.Pattern[str]] = {}
    for stage_id in kb_pipeline.STAGE_IDS:
        body = re.escape(stage_id)
        if stage_id in AMBIGUOUS_STAGE_IDS:
            patterns[f"--stage {stage_id}"] = re.compile(rf"--stage\s+{body}(?![\w.-])", re.IGNORECASE)
        else:
            patterns[stage_id] = re.compile(rf"(?<![\w.-]){body}(?![\w.-])", re.IGNORECASE)
    for token in SEQUENCING_TOKENS + METADATA_MARKER_TOKENS + WRITE_FLAG_TOKENS:
        patterns[token] = re.compile(re.escape(token), re.IGNORECASE)
    return patterns


TEMPLATE_PROHIBITIONS: Mapping[str, re.Pattern[str]] = MappingProxyType(_template_prohibitions())


# --- the row -----------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Step:
    """One row of the step table.

    ``outputs`` are layout patterns, scratch-relative, with ``<...>`` marking a
    segment the run loop expands (a stage id). ``slots`` are the per-call
    values the run loop computes; the slots the composer resolves for itself —
    fragments, alternatives — are deliberately absent. ``system`` is the
    fragment the composer renders whole as a calling row's system prompt.
    ``correction`` is the alternative slot a re-ask after a rejected reply
    fills, and the choice it fills it with; the first ask fills it with nothing.
    """

    id: str
    stage: str
    unit: Unit
    writer: Writer = Writer.NONE
    system: str | None = None
    template: str | None = None
    correction: tuple[str, str] | None = None
    slots: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    raises: tuple[str, ...] = ()
    ledger_op: LedgerOp | None = None
    #: This row's **whole** work is a model call made inside a tool the driver
    #: invokes — ``kb_claimgraph``'s ``ask.ask_without_tools`` — so a build
    #: spending none drops the row outright. :attr:`spends_inference` is what
    #: reads it.
    spends_own_inference: bool = False
    #: **Part** of this row's work is a model call made inside the tool it
    #: invokes, and the rest settles what must not be discarded with the
    #: questions — so a build spending none keeps the row and passes the tool its
    #: own ``--no-inference`` (``run._claim_graph``). The split is the row's to
    #: state, so it is a declaration rather than a derived fact.
    #: :attr:`calls_a_model` is what reads it.
    spends_inference_in_part: bool = False

    @property
    def spends_inference(self) -> bool:
        """Whether running this row costs a model call, by whichever route — what a run spending none drops.

        The two routes are not otherwise comparable and that is why this exists:
        :attr:`spends_own_inference` is a model called *inside* a tool the
        driver invokes, and a row naming a ``system`` prompt is a call the driver
        makes itself. A run spending no inference does without both, so it is
        this union — never either half — that decides which rows it walks.
        """
        return self.spends_own_inference or self.system is not None

    @property
    def calls_a_model(self) -> bool:
        """Whether this row, in a run spending inference, calls the server the environment names.

        Wider than :attr:`spends_inference` by the rows that spend part of their
        work on one: what the launch check of the environment reads.
        """
        return self.spends_inference or self.spends_inference_in_part


# --- the table ---------------------------------------------------------------

_START = "start"
_DOCUMENT_GRAPH = "document-graph"
_SPINE_SEED = "spine-seed"
_CLAIMS_DECLARED = "claims-declared"
_CLAIMS_DISCOVERED = "claims-discovered"
_EQUATIONS_MINTED = "equations-minted"
_DEPENDS_ATTRIBUTED = "depends-attributed"
_PHASE_3A = "phase-3a"
_OVERVIEW_DRAFTED = "overview-drafted"


def _through(stage: str) -> tuple[str, ...]:
    """The stage vocabulary up to and including ``stage``. Order is never restated here."""
    return kb_pipeline.STAGE_IDS[: kb_pipeline.STAGE_IDS.index(stage) + 1]


#: Every stage this table holds rows for, and every stage a run may walk — the
#: whole pipeline. ``_through(_OVERVIEW_DRAFTED)`` rather than ``kb_pipeline.STAGE_IDS``
#: directly, so that a stage appended to the vocabulary after ``overview-drafted``
#: arrives here as a row this table is missing rather than as a stage the walk
#: silently claims to cover.
TABLE_STAGE_IDS: tuple[str, ...] = _through(_OVERVIEW_DRAFTED)

STEPS: tuple[Step, ...] = (
    # --- pre-stage: before `start` is recorded -------------------------------
    # `pre.lock` holds <repo>/<scratch>/kb-driver.lock — the REPOSITORY's
    # lock, not the run directory's, so a second `--run-dir` cannot slip past
    # it. A live pid there is exit 16.
    Step(id="pre.lock", stage=_START, unit=Unit.DRIVER_OP, writer=Writer.DRIVER),
    # Preflight's stdout is relayed verbatim; rc != 0 is exit 14. Nothing is
    # read back off it: its `runner-file` FACT is a statement to the operator,
    # and `seed.graph-init` — which needs the same answer to decide whether to
    # raise `spine-seed.runner-choice` — asks the working tree itself. This row
    # is a `start` row, and a resume skips the stage whole, so an answer carried
    # from here would be absent on exactly the invocations that resume.
    Step(id="pre.preflight", stage=_START, unit=Unit.DRIVER_OP),
    # A charter is optional and is never composed here: the row resolves
    # whether one stands at the configured path, so the record and the two
    # briefs that quote it read one answer instead of each asking the
    # filesystem their own question.
    Step(id="pre.charter", stage=_START, unit=Unit.DRIVER_OP),
    # The launch guard, and it is a launch guard because of where it sits: every
    # row of this stage is skipped once `start` is recorded, so this row runs on
    # the invocation that opens a build and on no other. A resume therefore
    # never meets it, which is what lets it refuse the one state that destroys
    # work — a build opened over a `kb-root/` somebody else's build filled — and
    # still let the same populated tree through on every invocation after.
    # Last before `start.record` on purpose: nothing between the reading and the
    # first write can change the answer.
    Step(id="pre.kb-root", stage=_START, unit=Unit.DRIVER_OP),
    # `start-build`, carrying `--charter <path>` only where a charter stands;
    # rc 5 (already started) reads as done.
    Step(
        id="start.record",
        stage=_START,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.START_BUILD,
    ),
    # --- the head: the build's own production ---------------------------------
    #
    # Six tool rows and their records. Every one of them invokes a module and
    # reads an exit code, so none briefs a seat and none raises a barrier of its
    # own — the two exceptions being stated where they sit. The order is forced
    # end to end: the seed refuses a `kb-root/` with no tree in it, the declared
    # pass refuses a `kb-root/` with no spine, the node pass reads the leaves the
    # declared pass recorded unread, equations are minted from the references
    # its verdicts leave counting, and stage D authors edges over the node set
    # those three fixed. Each stage's boundary commit is also what leaves the worktree
    # clean for the next stage's tool, which is why the seed is a stage of its
    # own rather than a row of `start`: its preflight refuses the dirty worktree
    # the document graph has just created.
    #
    # No row here is conditional. Each runs on the invocation that walks its
    # stage and never again, because a recorded stage is not re-walked — so
    # what keeps `dg.build` off a tree a finished build stamped is the ledger,
    # and what keeps it off a tree nobody here built is `pre.kb-root`.
    # --- document-graph — LaTeX volumes in, the Markdown tree out -------------
    # `kb_docgraph`: rc 1 (a check failed) → exit 11; rc 2 (a source or the
    # bibliography is not there) → exit 14.
    Step(id="dg.build", stage=_DOCUMENT_GRAPH, unit=Unit.DRIVER_OP, writer=Writer.TOOL),
    Step(
        id="dg.record",
        stage=_DOCUMENT_GRAPH,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
    # --- spine-seed — the claim-graph metadata seed ----------------------------
    # `kb_util graph-init`: rc 3 (kb-root holds no document tree) → exit 14, the
    # stage above not having produced one; rc 2 → exit 14; rc 1 → 11. The one
    # barrier the head raises, and it is the same question it has always asked:
    # a repository carrying neither runner file cannot be told where the include
    # line goes, and no other row of the build can answer it either. The row
    # reads that condition off the working tree when it runs, so the barrier is
    # reachable on a resume as well as on a launch.
    Step(
        id="seed.graph-init",
        stage=_SPINE_SEED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        raises=("spine-seed.runner-choice",),
    ),
    Step(
        id="seed.record",
        stage=_SPINE_SEED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
    # --- claims-declared — the graph the author marked, mechanically ----------
    Step(
        id="declared.build",
        stage=_CLAIMS_DECLARED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
    ),
    Step(
        id="declared.record",
        stage=_CLAIMS_DECLARED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
    # --- claims-discovered — the node pass --------------------------------------
    # The whole of this row is a model call, and it is made inside
    # `kb_claimgraph` rather than by this driver: the reader is that package's
    # `ask.ask_without_tools`. That is what `spends_own_inference` declares, and
    # it is why the field sits beside `system` rather than being collapsed into
    # it — the two routes are dropped by the same flag and reached by different
    # code.
    #
    # `--no-inference` excludes this row outright, which is not a bound: the
    # walk continues, `discover.record` still writes the boundary, and the node
    # pass's record still lists every leaf this row would have read as unread
    # (ARCHITECTURE.md, The Driver).
    Step(
        id="discover.build",
        stage=_CLAIMS_DISCOVERED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        spends_own_inference=True,
    ),
    Step(
        id="discover.record",
        stage=_CLAIMS_DISCOVERED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
    # --- equations-minted — the node set's close ------------------------------
    # Mechanical, and a stage of its own rather than a tail on `discover.build`:
    # as a tail it would stop that row declaring its inference, and the ledger
    # would no longer name the row a build spending none drops.
    Step(
        id="equations.build",
        stage=_EQUATIONS_MINTED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
    ),
    Step(
        id="equations.record",
        stage=_EQUATIONS_MINTED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
    # --- depends-attributed — stage D -----------------------------------------
    # **The row runs in every build, and only part of it costs a call.** Stage
    # D's narrowing drafts every edge candidate mechanically — *supported by*
    # where containment directs it, a `\ref` inside a proof body being
    # direction-bearing by construction, and *mention* everywhere else — and
    # the classification puts each candidate to `ask.ask_without_tools` as one
    # letter ask. The row therefore declares no inference of its own: dropping
    # it would discard the drafts along with the asks, and a graph that records
    # no relationship it holds in hand asserts its claims rest on nothing
    # (`kb_tools/AGENTS.md`, the second bullet). `run.py` passes the tool its
    # own `--no-inference` instead, and every candidate takes its draft.
    Step(
        id="depends.attribute",
        stage=_DEPENDS_ATTRIBUTED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        spends_inference_in_part=True,
    ),
    Step(
        id="depends.record",
        stage=_DEPENDS_ATTRIBUTED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
    # --- phase-3a — validation gate -------------------------------------------
    # Gate and record, and nothing between them: `kb-refresh` then `kb-verify`,
    # green or the run stops. The repair dispatch this stage used to drive is gone
    # with its subject — every gate the three verifiers run compares one
    # mechanically-produced artifact against another, so a red one is a defect
    # in a tool or in what was authored, and neither is a seat's to rewrite in
    # the KB.
    Step(id="p3a.gate", stage=_PHASE_3A, unit=Unit.GATE),
    Step(
        id="p3a.record",
        stage=_PHASE_3A,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
    # --- overview-drafted — the overview document, written --------------------
    # **The stage assembles the document; the model is never asked to compose
    # one.** What is left for a model is the part no read produces — what this
    # corpus is and where a reader starts — and the answer to that is prose and
    # nothing else. Hence `Writer.DRIVER`: the returned text *is* the artifact,
    # persisted under the scratch layout, and `run._meta_docs` substitutes it.
    #
    # **The draft's boundary stands immediately behind it because it spends a
    # model call.** Anything failable between the two would leave the draft's
    # answer behind it, and a resume would buy it a second time; the boundary
    # below is what earns it once (`kb_pipeline.STAGES`, the granularity comment).
    #
    # The docent check runs *first* for the same reason read the other way: it
    # can fail, so it may not stand behind the call. An incomplete install is
    # also cheaper to meet before a call is made than after. A driver-op
    # over an imported constant: the docent commands are what make a finished KB
    # navigable, and their absence is an incomplete install (exit 14), never a
    # barrier — there is no answer that would install them.
    Step(id="ov.docent-check", stage=_OVERVIEW_DRAFTED, unit=Unit.DRIVER_OP),
    Step(
        id="ov.docs",
        stage=_OVERVIEW_DRAFTED,
        unit=Unit.SINGLE,
        writer=Writer.DRIVER,
        system="overview-system",
        template="overview-passage.tmpl.md",
        correction=("passage-correction", "overview-correction"),
        slots=("excerpts",),
        outputs=(OVERVIEW_PROSE,),
    ),
    Step(
        id="ov.record",
        stage=_OVERVIEW_DRAFTED,
        unit=Unit.DRIVER_OP,
        writer=Writer.TOOL,
        ledger_op=LedgerOp.ADVANCE_STEP,
    ),
)

STEP_IDS: tuple[str, ...] = tuple(step.id for step in STEPS)
STEPS_BY_ID: Mapping[str, Step] = MappingProxyType({step.id: step for step in STEPS})


def steps_for(stage: str) -> tuple[Step, ...]:
    """Every row of one stage, in table order."""
    return tuple(step for step in STEPS if step.stage == stage)


def applies(step: Step, *, spend_inference: bool = True) -> bool:
    """Whether a row runs in this run — the one condition a run still carries.

    ``spend_inference`` is **row-level rather than a bound**: a run spending none
    drops every row that would cost a model call and walks every stage
    regardless, so the stages around an excluded row still run and the build
    still closes out.

    There is no second condition. A row used to be able to name the build mode
    it belonged to, which is how a build entering against a KB it had not built
    skipped the rows that would overwrite it; the modes are gone, and what keeps
    those rows off such a tree is the ledger (a recorded stage is not re-walked)
    and the launch guard that refuses to open a build over one.

    A stage's ledger row never costs a model call — a record makes none and
    invokes no tool that makes one — which is what lets the walk continue
    past a stage whose work it dropped.
    """
    return spend_inference or not step.spends_inference


def inference_rows(stage: str) -> tuple[str, ...]:
    """The ids of ``stage``'s rows a run spending no inference does without.

    Derived from :attr:`Step.spends_inference`, never from a stage id: a stage
    that gains or loses an inference-spending row moves this answer without an
    edit here.
    """
    return tuple(step.id for step in steps_for(stage) if step.spends_inference)
