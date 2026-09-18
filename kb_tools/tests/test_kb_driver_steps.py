"""The step table: stage coverage, row shape, and single-sourcing.

The table holds rows for every stage of the pipeline and a run walks all of
them, so the coverage assertions are against the whole stage vocabulary. The
table/walk split is retired with rung 1; what replaces it is the assertion
below, which is stronger — not "the walk lags the table" but "the two are the
same set, and it is the stage vocabulary's".

Nothing here tests what a row *does*; that is the run loop's suites. These
check that the table cannot silently disagree with the stage vocabulary or the
barrier registry's naming.
"""

import inspect

import pytest

from kb_tools import kb_pipeline, kb_util
from kb_tools.kb_driver import prompt_templates, run, steps

# ---------------------------------------------------------------------------
# Stage coverage
# ---------------------------------------------------------------------------


def test_the_table_covers_the_whole_stage_vocabulary_and_the_walk_covers_the_table() -> None:
    """Rung 1's structural claim: rows for every stage, and a walk over every row.

    A stage appended to ``kb_pipeline.STAGE_IDS`` fails this rather than being
    silently walked with no rows, and a walk narrowed back below the table
    fails it rather than quietly buying a green by not going there.
    """
    assert steps.TABLE_STAGE_IDS == kb_pipeline.STAGE_IDS
    assert len(steps.TABLE_STAGE_IDS) == 9


def test_every_row_of_the_table_is_executed_by_a_handler_or_driven_by_another_row() -> None:
    """The other half: a row nothing runs is a row the sequencer has silently dropped."""
    unexecuted = set(steps.STEP_IDS) - set(run._HANDLERS) - run.DRIVEN_STEPS

    assert not unexecuted


def test_no_handler_and_no_driven_row_names_a_row_the_table_does_not_hold() -> None:
    assert set(run._HANDLERS) <= set(steps.STEP_IDS)
    assert run.DRIVEN_STEPS <= set(steps.STEP_IDS)


def test_each_stage_of_the_table_appears_once_in_stage_id_order() -> None:
    """One contiguous run of rows per stage, in the order ``STAGE_IDS`` fixes."""
    appearances = tuple(dict.fromkeys(step.stage for step in steps.STEPS))

    assert appearances == steps.TABLE_STAGE_IDS


@pytest.mark.parametrize("stage", steps.TABLE_STAGE_IDS)
def test_every_stage_of_the_table_ends_in_exactly_one_ledger_row(stage: str) -> None:
    """A stage is recorded once, by its last row: the ledger is written only by the sanctioned ops."""
    rows = steps.steps_for(stage)
    recording = [row for row in rows if row.ledger_op is not None]

    assert rows
    assert len(recording) == 1
    assert recording[0] is rows[-1]


def _walked(stage: str) -> tuple[steps.Step, ...]:
    """The rows of one stage the linear walk executes, in order.

    A driven row is not one of them: it is executed by the handler of the row
    that drives it, so its position in the table is not a position in the walk.
    """
    return tuple(step for step in steps.steps_for(stage) if step.id not in run.DRIVEN_STEPS)


@pytest.mark.parametrize("stage", steps.TABLE_STAGE_IDS)
def test_no_failable_row_stands_between_an_inference_spending_row_and_its_boundary(stage: str) -> None:
    """R-C as a property of the table: expensive work that succeeded is never discarded.

    A row that spends inference must be the row immediately before its stage's
    ledger row — so the only thing that can happen between the spend and the
    commit that accounts for it is the commit itself. Two corollaries fall out,
    and both are the point rather than side effects: no stage may hold two such
    rows, and nothing failable may be appended after one.

    The walk's rows, because a row that drives another is one unit of expensive
    work: the call it drives takes no boundary of its own, the ledger's entries
    being the stage vocabulary. What the driving row's boundary accounts for is
    both calls, and a run killed between them re-spends both.

    Static, over the table alone: a timed run would price the guarantee in hours
    and could only ever observe the shape this asserts.
    """
    walked = _walked(stage)
    spending = [index for index, step in enumerate(walked) if step.spends_inference]

    assert len(spending) <= 1, f"{stage} holds {len(spending)} inference-spending rows, so one of them has no boundary"
    for index in spending:
        following = walked[index + 1 :]
        assert [step.id for step in following] == [walked[-1].id], (
            f"{walked[index].id} spends inference and {', '.join(step.id for step in following[:-1])} "
            f"stands between it and its boundary"
        )
        assert walked[-1].ledger_op is not None


@pytest.mark.parametrize("stage", steps.TABLE_STAGE_IDS)
def test_a_driven_row_spends_inside_a_walked_row_of_its_own_stage(stage: str) -> None:
    """The other half: a driven row's boundary is its driver's, so it must share the stage.

    A driven row costs a model call and takes no boundary of its own. That is
    only sound while the row that drives it stands in the same stage — the two
    calls and the commit that accounts for them are then one stage's business. A
    driven row whose driver sat in an earlier stage would spend a call behind a
    boundary already written.
    """
    driven = [step for step in steps.steps_for(stage) if step.id in run.DRIVEN_STEPS]
    if not driven:
        pytest.skip(f"{stage} drives no row")
    drivers = [step for step in _walked(stage) if step.spends_inference]

    assert drivers, f"{stage} holds a driven row and no walked row that could drive one"
    for step in driven:
        assert step.spends_inference, "a driven row that costs nothing needs no driver to sit in"


def test_only_the_first_stage_starts_the_build() -> None:
    starting = [step.id for step in steps.STEPS if step.ledger_op is steps.LedgerOp.START_BUILD]

    assert starting == ["start.record"]
    assert steps.STEPS_BY_ID["start.record"].stage == kb_pipeline.FIRST_STAGE_ID


# ---------------------------------------------------------------------------
# Row shape
# ---------------------------------------------------------------------------


def test_step_ids_are_unique_and_indexed() -> None:
    assert len(steps.STEP_IDS) == len(set(steps.STEP_IDS))
    assert set(steps.STEPS_BY_ID) == set(steps.STEP_IDS)


CALL_UNITS = (steps.Unit.SINGLE,)
CALL_ROWS = [step for step in steps.STEPS if step.unit in CALL_UNITS]
CALL_IDS = [step.id for step in CALL_ROWS]


@pytest.mark.parametrize("step", steps.STEPS, ids=steps.STEP_IDS)
def test_only_a_row_that_calls_inference_carries_a_brief(step: steps.Step) -> None:
    if step.unit in CALL_UNITS:
        assert step.template and step.template.endswith(".tmpl")
    else:
        assert step.template is None
        assert step.slots == ()


@pytest.mark.parametrize("step", CALL_ROWS, ids=CALL_IDS)
def test_a_templates_name_matches_its_call_unit(step: steps.Step) -> None:
    """A naming convention only: the step table names every template it uses."""
    assert step.template is not None and ".single." in step.template


@pytest.mark.parametrize("step", CALL_ROWS, ids=CALL_IDS)
def test_every_call_row_names_the_seat_it_dispatches(step: steps.Step) -> None:
    """``--agent`` carries that name, and ``call.py`` refuses a call row without one."""
    assert step.seat, "a call row names the seat --agent will carry"


@pytest.mark.parametrize("step", steps.STEPS, ids=steps.STEP_IDS)
def test_only_a_call_row_declares_parses(step: steps.Step) -> None:
    if step.parses:
        assert step.unit in CALL_UNITS
        assert step.template


def test_the_verdict_is_asked_of_the_one_review_row() -> None:
    """The whole parse vocabulary is one format, and one row declares it.

    The verdict rides the *returned text*: a never-writer SINGLE whose return
    ``call.py`` persists and parses.
    """
    assert {step.id for step in steps.STEPS if steps.Parse.VERDICT in step.parses} == {"p5.review"}
    assert set(steps.Parse) == {steps.Parse.VERDICT}


def test_declared_outputs_are_scratch_relative_layout_patterns() -> None:
    for step in steps.STEPS:
        for output in step.outputs:
            assert not output.startswith("/")
            assert not output.startswith(steps.SCRATCH_ROOT), "outputs are relative to the scratch root"


# ---------------------------------------------------------------------------
# Barriers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("step", steps.STEPS, ids=steps.STEP_IDS)
def test_every_barrier_a_row_raises_names_a_stage_and_a_kind(step: steps.Step) -> None:
    for pair in step.raises:
        stage, dot, kind = pair.rpartition(".")
        assert dot and kind
        assert stage in kb_pipeline.STAGE_IDS, f"{pair} names no stage in the vocabulary"


def test_the_tables_barrier_pairs_are_each_raised_once() -> None:
    raised = [pair for step in steps.STEPS for pair in step.raises]

    assert len(raised) == len(set(raised))
    assert set(raised) == {"spine-seed.runner-choice"}


def test_a_findings_path_names_the_stage_and_the_author_and_nothing_else() -> None:
    """One review per stage, one file per reviewing seat, and no counter in the name."""
    assert steps.findings(stage="phase-5", author="gate") == "review/phase-5-gate.md"


# ---------------------------------------------------------------------------
# The path slots and the lint vocabulary
# ---------------------------------------------------------------------------


def test_every_path_slot_is_a_slot_some_shipped_template_declares() -> None:
    """A misspelled entry checks nothing, and reads exactly like one that does.

    Against the shipped templates rather than against the rows, because the
    vocabulary deliberately reaches the slots of a template no row dispatches
    yet — which is what stops a first caller of one from having to know.
    """
    declared = {
        slot.removeprefix(prompt_templates.DYNAMIC_PREFIX)
        for path in prompt_templates.template_paths()
        for slot in prompt_templates.slots_of(path.read_text(encoding="utf-8"), source=path.name)
        if slot.startswith(prompt_templates.DYNAMIC_PREFIX)
    }

    assert steps.PATH_SLOTS <= declared


def test_the_lint_vocabulary_covers_every_stage_id_and_both_ledger_write_verbs() -> None:
    """Both write verbs are banned by name, which is the widening the ops brought.

    While the retired op flag was the second token a brief could say
    ``start-build`` freely and only that flag spelling was caught. Both verbs
    are subcommands now, and a brief may name neither.
    """
    labels = set(steps.TEMPLATE_PROHIBITIONS)

    for stage_id in kb_pipeline.STAGE_IDS:
        assert stage_id in labels or f"--stage {stage_id}" in labels
    assert {kb_util.OP_ADVANCE_STEP, kb_util.OP_START_BUILD} <= labels


@pytest.mark.parametrize("stage_id", [s for s in kb_pipeline.STAGE_IDS if s not in steps.AMBIGUOUS_STAGE_IDS])
def test_each_unambiguous_stage_id_is_flagged_under_its_own_name(stage_id: str) -> None:
    """``phase-1`` must not answer for ``phase-1a``: each id is reported as itself."""
    matched = {label for label, pattern in steps.TEMPLATE_PROHIBITIONS.items() if pattern.search(f"record {stage_id}")}

    assert matched == {stage_id}


# ---------------------------------------------------------------------------
# Spending no inference
# ---------------------------------------------------------------------------


def test_a_row_spends_inference_by_either_route_and_the_two_stay_distinguishable() -> None:
    """The union is what a no-inference run drops; the halves are not interchangeable.

    The two halves reach a model by different code — the driver's own transport
    for a ``seat``, a tool the driver invokes for ``spends_own_inference`` — so
    they have to stay tellable apart, which is why the derived property sits
    beside both rather than replacing either.
    """
    dispatched = {step.id for step in steps.STEPS if step.seat is not None}
    inside_a_tool = {step.id for step in steps.STEPS if step.spends_own_inference}
    spending = {step.id for step in steps.STEPS if step.spends_inference}

    assert dispatched and inside_a_tool
    assert dispatched.isdisjoint(inside_a_tool)
    assert spending == dispatched | inside_a_tool


def test_no_ledger_row_spends_inference() -> None:
    """What lets the walk continue past a stage whose work was dropped.

    A stage nothing recorded is a stage no later stage can be recorded after,
    so a build spending no inference finishes only if recording never costs
    one. Asserted rather than assumed: a record row that grew a seat would make
    the whole mode unreachable, and quietly.
    """
    assert [step.id for step in steps.STEPS if step.ledger_op is not None and step.spends_inference] == []


def test_a_run_spending_no_inference_drops_exactly_the_rows_that_cost_one() -> None:
    """``applies`` is row-level, and the row's cost is the whole of what it reads."""
    dropped = {step.id for step in steps.STEPS if not steps.applies(step, spend_inference=False)}

    assert dropped == {step.id for step in steps.STEPS if step.spends_inference}


def test_a_row_applies_to_every_run_that_will_spend_what_it_costs() -> None:
    """No row is conditional on anything else, and that is the property to hold.

    The table used to let a row name the build mode it belonged to, which is how
    a build entering against a KB it had not built skipped the rows that would
    overwrite one. The modes are gone and no second condition replaced them: the
    ledger decides what is re-walked, and ``pre.kb-root`` decides what may be
    opened. A row that grew a condition of its own would put a third answer
    beside those two without either of them knowing.
    """
    assert all(steps.applies(step) for step in steps.STEPS)


def test_the_rows_a_stage_loses_are_named_by_the_table_and_not_by_a_stage_id() -> None:
    """``inference_rows`` is the note's source, derived from the rows themselves."""
    by_stage = {stage: steps.inference_rows(stage) for stage in steps.TABLE_STAGE_IDS}

    # `depends-attributed` is deliberately absent: its row spends no inference
    # of its own, because the narrowing settles every edge containment decides
    # whether or not a model is reachable and only the pairs left open need
    # one. The tool is told with its own `--no-inference` and reports what went
    # unasked; no row is dropped, so the stage loses nothing to name.
    assert {stage for stage, rows in by_stage.items() if rows} == {
        "claims-discovered",
        "overview-drafted",
        "phase-5",
    }
    for stage, rows in by_stage.items():
        assert set(rows) <= {step.id for step in steps.steps_for(stage)}, stage


# ---------------------------------------------------------------------------
# The stage table and the step table, held equal
#
# `stages_without_own_inference` used to guarantee, at runtime, that an
# inference-spending row inserted anywhere could not escape the bound. The
# bound is gone; the failure it guarded against is not. What replaces it is a
# single declaration both consumers read (`kb_pipeline.Stage.work_is_inference`)
# and the derivation performed HERE, over `steps.STEPS`, compared in both
# directions. A test that only asked whether the declaration is self-consistent
# would pass on a table that had quietly stopped describing the rows.
# ---------------------------------------------------------------------------


def test_the_stage_declaration_and_the_rows_agree_about_which_stages_spend_inference() -> None:
    """Derived here, declared there, compared both ways.

    A row gaining a seat or ``spends_own_inference`` in a stage the table calls
    mechanical fails this; so does a stage declaring itself inferential with no
    row that costs a call. Neither can reach a shipped run, which is the
    guarantee the deleted runtime derivation used to carry.
    """
    derived = {
        stage for stage in steps.TABLE_STAGE_IDS if any(step.spends_inference for step in steps.steps_for(stage))
    }
    declared = {stage.id for stage in kb_pipeline.STAGES if stage.work_is_inference}

    assert derived == declared, f"only in the rows: {derived - declared}; only in the table: {declared - derived}"


def test_the_declaration_is_the_one_runtime_source_and_nothing_re_derives_it() -> None:
    """Both consumers read the declaration; neither computes a second answer.

    The trap this closes is the driver deriving at runtime while the tool reads
    a declaration — they would then disagree only in a shipped run, where no
    test is watching. ``_excused`` is the sole reader of the stage-level fact,
    and it reads the field.
    """
    source = inspect.getsource(kb_pipeline._excused)

    assert "stage.work_is_inference" in source
    assert "spends_inference" not in source and "steps" not in source


@pytest.mark.parametrize("stage", [stage for stage in kb_pipeline.STAGES if stage.claimgraph_invocation])
def test_each_claim_graph_stage_composes_and_resolves_to_itself(stage: kb_pipeline.Stage) -> None:
    """The invocation table, read in both directions.

    The driver composes flags from the stage; the tool parses those flags and
    asks what stage they are. A round trip that did not land back on the same
    stage would mean a build running a pass as one stage and recording it as
    another.
    """
    assert stage.claimgraph_invocation is not None  # the parametrization's own filter
    invocation = stage.claimgraph_invocation

    assert kb_pipeline.claimgraph_stage(which_pass=invocation.which_pass, scope=invocation.scope) is stage
    assert invocation.flags[:2] == ("--pass", str(invocation.which_pass))


def test_every_claim_graph_row_belongs_to_a_stage_that_declares_an_invocation() -> None:
    """The driver has no pass number of its own left to get wrong."""
    invoking = {stage.id for stage in kb_pipeline.STAGES if stage.claimgraph_invocation}
    rows = {steps.STEPS_BY_ID[step_id].stage for step_id in ("declared.build", "discover.build", "depends.attribute")}

    assert rows == invoking


def test_each_stages_precondition_is_the_stage_before_it() -> None:
    """One statement of the order, read by the driver's table and by the tool alike."""
    assert kb_pipeline.precondition_of(kb_pipeline.STAGES[0]) is None
    for earlier, later in zip(kb_pipeline.STAGES, kb_pipeline.STAGES[1:]):
        assert kb_pipeline.precondition_of(later) is earlier
