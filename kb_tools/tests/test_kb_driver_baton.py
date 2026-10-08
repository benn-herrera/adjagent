"""Baton completeness.

Every enumerated exit code renders a baton, and an unlisted code renders the
fallback: an unrecognized exit state is the one place a relaying session will
otherwise improvise.

One case here is not a unit case. A card's ASK and THEN RUN are the operator's
next action, so what must hold of a stage-record refusal's card is that the
action it names exists *for the row that produced it* — which means the code has
to arrive from the real refusal rather than from a constant transcribed beside
it. That case drives ``kb_pipeline`` through the ledger adapter against a temp
git repo, the way ``test_kb_driver_ledger.py`` does.
"""

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from kb_tools import kb_pipeline, kb_util
from kb_tools.kb_driver import baton, config, ledger

# A table transcribed from the design rather than from the code under test —
# the point of the guard is that the two agree.
DESIGN_CODES = (0, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)


def _asks(block: str) -> str:
    """The ASK section of a rendered baton."""
    lines = block.splitlines()
    start = lines.index(f"{baton.PREFIX} ASK THE USER:")
    end = next(i for i, line in enumerate(lines) if line.startswith(f"{baton.PREFIX} THEN RUN"))
    return "\n".join(lines[start + 1 : end])


def test_every_design_code_has_a_baton() -> None:
    assert baton.CODES == DESIGN_CODES


@pytest.mark.parametrize("code", DESIGN_CODES)
def test_every_code_renders_a_complete_card(code: int) -> None:
    # A pair is supplied so the two answer-substituting rows render their own
    # card rather than the no-barrier one — this guard is over the enumeration.
    block = baton.render(
        code,
        baton.BatonContext(
            invocation="--config cfg.toml", pair="spine-seed.runner-choice", question="q?", run_dir="/runs/1"
        ),
    )
    lines = block.splitlines()
    assert all(line.startswith(baton.PREFIX) for line in lines)
    assert f"{baton.PREFIX} PLACE IN YOUR MESSAGE BODY, VERBATIM:" in lines
    assert f"{baton.PREFIX} ASK THE USER:" in lines
    assert any(line.startswith(f"{baton.PREFIX} THEN RUN") for line in lines)
    assert _asks(block).strip()
    # Teeth: an enumerated code that lost its row would silently render the
    # fallback, which is a passing card for the wrong reason.
    assert "do not interpret it" not in block


@pytest.mark.parametrize("code", [1, 9, 20, 23, 99, -1])
def test_unlisted_code_renders_the_fallback(code: int) -> None:
    block = baton.render(code)
    assert "report this output verbatim and stop; do not interpret it" in _asks(block)
    assert f"{baton.PREFIX}   nothing" in block.splitlines()


def test_barrier_baton_carries_question_answers_and_resume_command() -> None:
    block = baton.render(
        baton.EXIT_BARRIER,
        baton.BatonContext(
            invocation="--config .claude-temp/kb-build/driver-run.toml",
            pair="spine-seed.runner-choice",
            question="This repository has neither a justfile nor a Makefile. Which runner?",
            admissible=("just", "make"),
        ),
    )
    assert "This repository has neither a justfile nor a Makefile. Which runner?" in block
    assert f"{baton.PREFIX} ADMISSIBLE ANSWERS:" in block
    assert "just | make" in block
    assert "THEN RUN, WITH THE ANSWER SUBSTITUTED:" in block
    assert f"{kb_util.driver_invocation()} run --config .claude-temp/kb-build/driver-run.toml" in block
    assert "--decide spine-seed.runner-choice=<answer>" in block


def test_unconsumed_decisions_are_named_in_the_baton() -> None:
    block = baton.render(
        baton.EXIT_OK,
        baton.BatonContext(unconsumed_decisions=("spine-seed.runner-choice=just",)),
    )
    assert "UNCONSUMED --decide (never raised in this run):" in block
    assert "spine-seed.runner-choice=just" in block


def test_missing_question_on_a_raised_barrier_is_visible_rather_than_blank() -> None:
    """The alarm, still armed: a raised barrier with no question looks like the defect it is."""
    block = baton.render(
        baton.EXIT_BARRIER,
        baton.BatonContext(invocation="--config cfg.toml", pair="spine-seed.runner-choice"),
    )
    assert "(missing — read the barrier record and report it verbatim)" in _asks(block)


@pytest.mark.parametrize("code", [baton.EXIT_BARRIER, baton.EXIT_GATE_RED])
def test_a_stage_that_failed_mechanically_is_not_rendered_as_an_ask(code: int) -> None:
    """No pair means no barrier: no blank question, and nothing to substitute an answer into.

    Both codes are reachable without a barrier — a red front end and a red gate
    are exits, not questions — and the barrier card asked those operators a
    blank question and told them to resume with `--decide <stage>.<kind>=`,
    which answers nothing that was raised.
    """
    block = baton.render(
        code,
        baton.BatonContext(
            invocation="--source main.tex",
            detail=("kb_claimgraph --pass 1 --scope block-hosted exited 1",),
        ),
    )

    assert "(missing —" not in block
    assert "<stage>.<kind>" not in block
    assert "--decide" not in block
    assert "THEN RUN, WITH THE ANSWER SUBSTITUTED:" not in block
    assert "kb_claimgraph --pass 1 --scope block-hosted exited 1" in _asks(block)


@pytest.fixture
def target_launched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str | None], str]:
    """The invocation of a run the ``kb-build`` target launched, in a repository carrying ``runner``'s file."""

    def launched(runner: str | None) -> str:
        repo = tmp_path / "consumer"
        (repo / ".git").mkdir(parents=True)
        if runner is not None:
            (repo / kb_util.runner_filename(runner)).write_text("", encoding="utf-8")
        monkeypatch.chdir(repo)
        runs = kb_util.build_live_dir() / kb_util.BUILD_RUNS_DIRNAME
        return config.load(None, run_overrides={"sources": ("a.tex", "b.tex")}, run_dir=runs).invocation

    return launched


@pytest.mark.parametrize(
    ("runner", "resume", "decide"),
    [
        (
            "just",
            "just kb-build a.tex b.tex",
            "just kb-build a.tex b.tex --decide spine-seed.runner-choice=<answer>",
        ),
        (
            "make",
            'make kb-build SOURCES="a.tex b.tex"',
            'make kb-build SOURCES="a.tex b.tex" DRIVER_FLAGS="--decide spine-seed.runner-choice=<answer>"',
        ),
    ],
)
def test_a_run_the_target_launched_is_resumed_through_the_target(
    target_launched: Callable[[str | None], str], runner: str, resume: str, decide: str
) -> None:
    """The target supplies its own ``--run-dir``, so the line hands it the sources and nothing else."""
    invocation = target_launched(runner)

    resumed = baton.render(baton.EXIT_TRANSPORT, baton.BatonContext(invocation=invocation))
    answered = baton.render(
        baton.EXIT_BARRIER, baton.BatonContext(invocation=invocation, pair="spine-seed.runner-choice", question="q?")
    )

    assert _then_run(resumed).splitlines()[0] == f"{baton.PREFIX}   {resume}"
    assert _then_run(answered).splitlines() == [f"{baton.PREFIX}   {decide}"]


def test_a_flag_beside_the_sources_rides_the_target_line(target_launched: Callable[[str | None], str]) -> None:
    invocation = target_launched("just")

    card = baton.render(baton.EXIT_TRANSPORT, baton.BatonContext(invocation=f"{invocation} --no-inference"))

    assert f"{baton.PREFIX}   just kb-build a.tex b.tex --no-inference" in card.splitlines()


def test_a_repository_with_no_runner_file_is_handed_the_driver_line(
    target_launched: Callable[[str | None], str],
) -> None:
    """No target to name, so the line keeps every flag, the run directory included."""
    invocation = target_launched(None)

    card = baton.render(baton.EXIT_TRANSPORT, baton.BatonContext(invocation=invocation))

    assert f"{kb_util.driver_invocation()} run {invocation}" in _then_run(card)


def test_a_run_launched_elsewhere_is_handed_the_driver_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The target would file the resumed run's evidence under its own directory, not this run's."""
    repo = tmp_path / "consumer"
    (repo / ".git").mkdir(parents=True)
    (repo / "justfile").write_text("", encoding="utf-8")
    monkeypatch.chdir(repo)
    invocation = config.load(None, run_overrides={"sources": ("a.tex",)}, run_dir=tmp_path / "runs").invocation

    card = baton.render(baton.EXIT_TRANSPORT, baton.BatonContext(invocation=invocation))

    assert f"{kb_util.driver_invocation()} run {invocation}" in _then_run(card)
    assert kb_util.TARGET_BUILD not in card


def test_detail_lines_ride_the_ask() -> None:
    block = baton.render(
        baton.EXIT_CONFIG,
        baton.BatonContext(detail=("[run] sources is required and has no default",)),
    )
    assert "[run] sources is required and has no default" in _asks(block)


# ---------------------------------------------------------------------------
# A stage-record refusal: the card names an action that row has
# ---------------------------------------------------------------------------


def _then_run(block: str) -> str:
    """The THEN RUN section of a rendered baton."""
    lines = block.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{baton.PREFIX} THEN RUN"))
    return "\n".join(lines[start + 1 : -1])


def _consumer(root: Path) -> Path:
    """A committed git repo the ledger ops can record into."""
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    for key, value in (
        ("user.email", "fixture@example.invalid"),
        ("user.name", "fixture"),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(["git", "config", key, value], cwd=root, check=True, capture_output=True)
    (root / ".gitignore").write_text(".claude-temp/\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=root, check=True, capture_output=True)
    return root


def test_a_head_record_refusal_names_an_action_that_row_has(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The head's first record row, refused for a missing tree: what the card tells the operator to do.

    The row invokes a tool and reads an exit code — it composes no brief and
    dispatches no seat — so a card diagnosing a brief/worker mismatch names a
    remedy the row has no parts for, and one directing "nothing" leaves an
    operator with a restorable state and no route out of it. What it does have
    is an unrecorded stage: a resume re-walks it once the missing output stands.
    """
    repo = _consumer(tmp_path / "consumer")
    assert ledger.record_start(repo, charter="").ok
    # Read off the vocabulary: what is under test is the refusal's card, not
    # which stage the head opens with.
    head_stage = kb_pipeline.STAGE_IDS[1]

    outcome = ledger.record_stage(repo, stage=head_stage)
    capsys.readouterr()

    # Rendered from the code the row actually came back with, so what is under
    # test is the card an operator gets and not a constant chosen here. The card
    # alone, no detail, so the words asserted absent are the card's own and not
    # some line the refusal happened to print.
    card = baton.render(outcome.exit_code, baton.BatonContext(invocation="--source main.tex"))
    assert "do not interpret it" not in card, "an enumerated code must not fall through to the fallback"
    assert "brief" not in card and "worker" not in card
    # The action: resume, once what the refusal named is there.
    assert f"{kb_util.driver_invocation()} run --source main.tex" in _then_run(card)
    assert f"{baton.PREFIX}   nothing" not in card.splitlines()
    # And the refusal's own account of what is missing rides the ASK, so the
    # operator is told which output the resume is waiting on.
    asks = _asks(baton.render(outcome.exit_code, baton.BatonContext(detail=outcome.detail)))
    assert head_stage in asks
    assert kb_pipeline.MISSING in asks
    assert outcome.exit_code == baton.EXIT_COVERAGE
