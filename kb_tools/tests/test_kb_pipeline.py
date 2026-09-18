"""Tests for the pipeline vocabulary itself (``kb_tools/kb_pipeline.py``).

``test_kb_util.py`` exercises the renders the CLI produces; this file tests the
stage table directly, for obligations whose *absence* is the contract and which
therefore have no rendered line to look for.
"""

import re
from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_pipeline, kb_util


def _stage(stage_id: str) -> kb_pipeline.Stage:
    stage = next((s for s in kb_pipeline.STAGES if s.id == stage_id), None)
    assert stage is not None, f"no stage {stage_id} in STAGES"
    return stage


def test_only_phase_3a_has_a_pre_commit_hook() -> None:
    """Pins the ``advance-step`` help text's claim that phase-3a alone writes readiness docs.

    ``kb_util.py``'s ``advance_step_help`` names phase-3a as the one stage that
    writes the KB's readiness docs. That claim is true only because
    :func:`kb_pipeline.stamp_readiness_docs` is wired as phase-3a's
    ``pre_commit`` and no other stage's; if the hook ever moves to a different
    stage (or a second one gains one), this goes red before the help text is
    left describing a stage that no longer writes it.

    The hook sits at the gate rather than at the finish so that every stage
    after it runs against a KB already carrying its orientation docs.
    """
    with_pre_commit = {stage.id for stage in kb_pipeline.STAGES if stage.pre_commit is not None}

    assert with_pre_commit == {"phase-3a"}


def test_a_document_the_readiness_stamp_writes_is_not_also_a_later_stages_contract() -> None:
    """One owner per document, and the earlier one wins whatever a later one declares.

    ``CONVENTIONS.md`` is stamped at ``phase-3a`` from a packaged template whose
    only slot is the project name, so it stands before the meta-documentation
    stages are reached and a boundary check for it there is satisfied by work
    neither stage did. What that costs is not a false green but a lost
    observable: a contract no run can fail cannot tell a stage that did its job
    from one that did nothing.

    The reviewer is still handed both paths — narrowing what a seat is asked to
    read is a different question from what a boundary checks, and this asserts
    only the second.
    """
    assert kb_pipeline.CONVENTIONS_DOC in kb_pipeline.READINESS_DOCS
    assert kb_pipeline.CONVENTIONS_DOC not in kb_pipeline.META_DOCS
    # Not vacuous by emptiness: the set still declares the one document whose
    # opening passage no read of the KB produces.
    assert kb_pipeline.META_DOCS == (kb_pipeline.OVERVIEW_DOC,)


def test_the_meta_documentation_boundary_refuses_on_the_overview_and_on_nothing_else(tmp_path: Path) -> None:
    """The stamped document standing does not buy the stage its boundary.

    The tree here is the one both meta-documentation stages really meet on a run
    whose draft never landed: ``phase-3a`` stamped ``CONVENTIONS.md`` and the
    overview was never written. The refusal names the overview, and the report
    holds no unit the readiness stamp already satisfied — otherwise a stage that
    wrote nothing covers half its contract for free.
    """
    kb = kb_util.kb_root(tmp_path)
    kb.mkdir(parents=True)
    (kb / kb_pipeline.CONVENTIONS_DOC).write_text("# Conventions\n", encoding="utf-8")
    ctx = kb_pipeline.CheckContext(repo_root=tmp_path)

    report = kb_pipeline._check_meta_docs(ctx)

    assert [unit.id for unit in report.units] == [kb_pipeline.OVERVIEW_DOC]
    refusal = kb_pipeline._coverage_refusal(report)
    assert refusal is not None and kb_pipeline.OVERVIEW_DOC in refusal

    # And it is the overview that lifts it: the stamped document was standing
    # the whole time and nothing about the refusal moved until this write.
    (kb / kb_pipeline.OVERVIEW_DOC).write_text("# Overview\n", encoding="utf-8")
    assert kb_pipeline._coverage_refusal(kb_pipeline._check_meta_docs(ctx)) is None


# ---------------------------------------------------------------------------
# What a stage is for
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage", kb_pipeline.STAGES, ids=[stage.id for stage in kb_pipeline.STAGES])
def test_a_stopped_build_names_the_stage_and_what_that_stage_is_for(stage: kb_pipeline.Stage, tmp_path: Path) -> None:
    """``display`` is the purpose label, and every render a stopped build leaves carries it.

    A build stops at a stage boundary, and what a reader has in front of them
    there is one of these three: the checklist, the stage-coverage read, or the
    boundary commit of the last stage that did record. Each names the stage and
    what it is for, from one string. The third is asserted end to end in
    ``test_kb_util.py``'s ledger walk, against the subjects git actually holds;
    here are the two rendered in process.
    """
    assert stage.display and stage.display != stage.id

    checklist = [line for line in kb_pipeline.checklist_lines({stage.id}) if line.split()[1] == stage.id][0]
    fact = kb_pipeline.stage_status(tmp_path, stage)[0]

    assert checklist.endswith(f"  {stage.display}")
    assert f"{kb_pipeline.FACT} {stage.id} ({stage.display}) — " in fact


# ---------------------------------------------------------------------------
# The stage-coverage read
#
# The op's own render, tested where the tree is constructed directly.
# `test_kb_util.py` is where it is driven through the running CLI; here it is
# the shape of one report.
# ---------------------------------------------------------------------------


def _status(stage_id: str, root: Path) -> list[str]:
    return kb_pipeline.stage_status(root, _stage(stage_id))


def test_an_argument_derived_unit_reports_the_question_and_not_the_tree(tmp_path: Path) -> None:
    """``start``'s charter, read where no record is being made.

    A read builds its context with no charter argument, so this unit cannot be
    satisfied here for a reason that is not a fact about the KB. Saying what
    the record would have been missing instead — the detail beside it — would
    be a claim about a tree this call never looked at.
    """
    lines = _status("start", tmp_path)

    assert len(lines) == 2
    assert lines[1].startswith(f"{kb_pipeline.STAGE_STATUS_TAG} {kb_pipeline.MISSING} charter ")
    assert kb_pipeline.ARGUMENT_ON_A_READ in lines[1]
    # The record path's own detail is what it must NOT have said.
    assert "the record names no charter" not in lines[1]


def test_no_read_line_parses_as_a_checklist_entry(tmp_path: Path) -> None:
    """The checklist block keeps its one producer, over every stage's report.

    ``^\\[[x* ]\\] `` is the parse agents lift the checklist with; a status
    line carrying a word in its brackets cannot be mistaken for one.
    """
    checklist = re.compile(r"^\[([x* ])\] (\S+)")

    for stage in kb_pipeline.STAGES:
        for line in kb_pipeline.stage_status(tmp_path, stage):
            assert line.startswith(kb_pipeline.STAGE_STATUS_TAG), (stage.id, line)
            assert not checklist.match(line), (stage.id, line)


# ---------------------------------------------------------------------------
# The two kinds of coverage check
#
# One kind asserts the stage did its work and has nothing to assert of a build
# that excluded the work. The other asserts the state handed across the
# boundary is valid for what comes next, and no path to the boundary excuses
# it. The classification is the unit's, so a check attached to two stages
# carries one answer to both.
# ---------------------------------------------------------------------------


def _unit(**fields: object) -> kb_pipeline.CoverageUnit:
    return kb_pipeline.CoverageUnit(
        **{"id": "u", "source": "s", "satisfied": True, "asserts_own_work": True, **fields}  # type: ignore[arg-type]
    )


def test_a_units_classification_has_no_default() -> None:
    """Total by construction: a new check cannot forget to say which kind it is.

    A default would pick one silently, and the wrong pick in either direction is
    a defect that reads green — a validity gate excused, or a stage that can
    never record a build it was never asked to do work for.
    """
    with pytest.raises(TypeError):
        kb_pipeline.CoverageUnit(id="u", source="s", satisfied=True)  # type: ignore[call-arg]


def test_the_check_two_stages_share_carries_one_classification(tmp_path: Path) -> None:
    """``_check_verify_gates`` is a validity check at ``depends-attributed`` too.

    The case a per-stage classification breaks: ``depends-attributed`` is a
    stage whose work a no-inference build excludes, so a stage-level rule would
    have excused its postcondition — and that postcondition is the head's exit
    gate over the whole KB, not an assertion about attribution having run.
    """
    sharing = [stage for stage in kb_pipeline.STAGES if stage.coverage is kb_pipeline._check_verify_gates]

    assert {stage.id for stage in sharing} == {"depends-attributed", "phase-3a"}
    for stage in sharing:
        report = stage.coverage(kb_pipeline.CheckContext(tmp_path))
        assert [unit.asserts_own_work for unit in report.units] == [False], stage.id


@pytest.mark.parametrize("stage", [stage for stage in kb_pipeline.STAGES if stage.work_is_inference])
def test_an_inference_stages_own_work_units_are_excused_and_its_validity_units_are_not(
    stage: kb_pipeline.Stage,
) -> None:
    """The rule, applied to each stage whose work is a model call."""
    report = kb_pipeline.CoverageReport.declared(
        (
            _unit(id="did-my-work", satisfied=False, asserts_own_work=True),
            _unit(id="state-validity", satisfied=False, asserts_own_work=False),
        ),
        unit_class="two kinds of unit",
    )
    excused = kb_pipeline._excused(report, stage, kb_pipeline.CheckContext(Path("/nowhere"), no_inference=True))
    by_id = {unit.id: unit for unit in excused.units}

    assert by_id["did-my-work"].satisfied and by_id["did-my-work"].vacuous
    assert by_id["did-my-work"].detail == kb_pipeline.WORK_EXCLUDED_DETAIL
    assert not by_id["state-validity"].satisfied and not by_id["state-validity"].vacuous


@pytest.mark.parametrize("stage", [stage for stage in kb_pipeline.STAGES if not stage.work_is_inference])
def test_a_stage_whose_work_is_not_inference_is_excused_nothing(stage: kb_pipeline.Stage) -> None:
    """Both halves are needed, and this is the half a one-condition rule would lose.

    A build that spent no model call still derived its tree and seeded its
    spine for real. Excusing every own-work unit on the strength of the flag
    alone would record a broken tree green.
    """
    report = kb_pipeline.CoverageReport.declared(
        (_unit(id="did-my-work", satisfied=False, asserts_own_work=True),), degenerate=True
    )
    excused = kb_pipeline._excused(report, stage, kb_pipeline.CheckContext(Path("/nowhere"), no_inference=True))

    assert excused == report


@pytest.mark.parametrize("stage", list(kb_pipeline.STAGES))
def test_a_build_that_spent_inference_is_excused_nothing_either(stage: kb_pipeline.Stage) -> None:
    """The flag is the only door, and it is the build's statement rather than a check's."""
    report = kb_pipeline.CoverageReport.declared(
        (_unit(id="did-my-work", satisfied=False, asserts_own_work=True),), degenerate=True
    )

    assert kb_pipeline._excused(report, stage, kb_pipeline.CheckContext(Path("/nowhere"))) == report


# ---------------------------------------------------------------------------
# The import direction the stage table now depends on
# ---------------------------------------------------------------------------


def test_kb_pipeline_imports_nothing_from_the_claim_graph_builder() -> None:
    """The cycle is impossible rather than held apart by where a line sits.

    ``kb_claimgraph`` reads this stage table, so an import back the other way
    would close a cycle. Two of them used to sit inside function bodies, which
    is exactly the tidy-up a later reader performs — nothing failed first and
    nothing said why they were there. What they reached for now lives in
    ``kb_index_lib``: the document walk, and the awaiting reason.
    """
    source = Path(kb_pipeline.__file__).read_text(encoding="utf-8")
    code = [line for line in source.splitlines() if line.strip().startswith(("import ", "from "))]

    assert [line for line in code if "kb_claimgraph" in line] == []
    assert kb_index_lib.UNSCANNED_REASON
    assert "kb_claimgraph" not in str(kb_index_lib.document_texts.__module__)


def test_the_awaiting_reason_is_one_literal_wherever_it_is_read() -> None:
    """The writer names it and the coverage check reads it — one definition, two sides."""
    from kb_tools.kb_claimgraph import assemble, conform

    assert assemble.UNSCANNED_REASON is kb_index_lib.UNSCANNED_REASON
    assert conform.determination({"no-claim": kb_index_lib.UNSCANNED_REASON}) is conform.Determination.AWAITING


def test_the_document_walk_is_one_walk(tmp_path: Path) -> None:
    """The coverage checks and the claim-graph builder see the same document set.

    Two implementations of the exclusion rules is how one of them starts
    checking a set the other does not — and the coverage check that reads the
    awaiting reason is exactly a question about "every document of this KB".
    """
    from kb_tools.kb_claimgraph import tree

    kb_root = kb_util.kb_root(tmp_path)
    for relative in ("entry-point.md", "vol/index.md", "vol/leaf.md", ".index/skipped.md"):
        target = kb_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {relative}\n", encoding="utf-8")

    assert set(kb_index_lib.document_texts(kb_root)) == set(tree.read(kb_root).documents)
    assert ".index/skipped.md" not in kb_index_lib.document_texts(kb_root)
