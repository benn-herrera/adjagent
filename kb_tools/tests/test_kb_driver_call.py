"""Call policy: retry, the one re-ask, and the persistence route.

Every case drives the real ``call.Caller`` through the same
``inference.invoke`` a live call goes through, against ``_fake_model``'s synthetic
stream-json — save one, which substitutes the real ``SubprocessInvoker``
because the fault it is about is ``Popen``'s own and no synthetic invoker
raises it where it happens.
Two things are asserted about writes throughout, not only in the route tests:
that the route wrote exactly where its step row declares, and that nothing else
under the repository changed.

The step rows are the real ones from ``steps.py`` — what the run loop will pass
— while the templates are local stand-ins named for the real ones, because the
shipped templates are the prompt engineer's and their prose is not what this
suite is about. No row is local: every calling row in the table is a SINGLE
whose returned text the driver persists, so every case here runs through one.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from kb_tools import inference, kb_pipeline
from kb_tools.kb_driver import baton, call, config, envelope, prompt_templates, runlog, steps
from kb_tools.tests import _fake_model as fake_model

# --- the templates a call composes against ----------------------------------

TEMPLATES: Mapping[str, str] = {
    "phase-5-overview-passage.single.tmpl": ("KB: @!dyn.kb-root!@\nFindings: @!dyn.remediation-source-path!@\n"),
    "phase-5-review.single.tmpl": (
        "README: @!dyn.readme-path!@\nCONVENTIONS: @!dyn.conventions-path!@\n\n@!verdict-contract!@\n@!return-contract!@\n"
    ),
}

# Keyed by bare name and placed under the fragments directory by the fixture, so
# the layout is stated once, where the composer states it.
FRAGMENTS: Mapping[str, str] = {
    "return-contract.tmpl": "Return the artifact as the final message body.\n",
    "verdict-contract.tmpl": "End with VERDICT: critical=<n> warning=<n> note=<n>\n",
}

# --- the returns a scenario can make ----------------------------------------

VERDICT_TEXT = "Findings: the tree is navigable.\n\nVERDICT: critical=0 warning=2 note=1"

# A path slot's value is checked before the call is made — absolute, and there
# on disk — so these are functions of the repo under test rather than literals.
# The `repo` fixture stands both documents a review brief names up because a
# real `phase-5` meets them already written: `phase-3a`'s readiness stamp seeds
# CONVENTIONS.md and `ov.docs` assembles README.md in the stage before the
# review. Which of them the stage's own boundary then checks is a narrower set
# (`kb_pipeline.META_DOCS`) and not this fixture's question.


def docs_slots(repo: Path) -> dict[str, str]:
    return {"kb-root": str(repo / "kb-root"), "remediation-source-path": steps.NOTHING}


PASSAGE_TEXT = "This corpus argues one thing, and the place to start is its introduction.\n"


#: The pair a review brief states, each named for itself. A zip over a document
#: set would drop `conventions-path` the moment that set stopped holding two
#: names, and a dropped required slot is refused by `steps.REQUIRED_PATH_SLOTS`
#: rather than noticed here.
REVIEW_DOCS: dict[str, str] = {
    "readme-path": kb_pipeline.OVERVIEW_DOC,
    "conventions-path": kb_pipeline.CONVENTIONS_DOC,
}


def review_slots(repo: Path) -> dict[str, str]:
    return {slot: str(repo / "kb-root" / name) for slot, name in REVIEW_DOCS.items()}


# --- harness ----------------------------------------------------------------


@dataclass(frozen=True)
class Harness:
    """One caller, plus the evidence a test needs to look at afterwards."""

    caller: call.Caller
    invoker: fake_model.FakeInvoker
    sleeps: list[float]
    seen: list[fake_model.Context]
    paths: runlog.RunPaths
    root: Path

    def brief(self, seq: int, label: str) -> Path:
        return self.paths.briefs / f"{seq:03d}-{label}.md"

    def stream(self, seq: int, label: str, attempt: int) -> Path:
        return self.paths.calls / f"{seq:03d}-{label}-a{attempt}.stream.jsonl"


def _config(*, attempts: int = 3, silence: int = 30) -> config.DriverConfig:
    return config.DriverConfig(
        path=Path("driver-run.toml"),
        invocation="--config driver-run.toml",
        run=config.RunSection(
            sources=("AcmeWidgets.tex",),
            permission_mode="acceptEdits",
            charter_file=Path(kb_pipeline.CHARTER_RELPATH),
            runner=None,
        ),
        claude=config.ClaudeSection(command=("claude",), env={}),
        timeouts=config.TimeoutSection(single_seconds=60, silence_seconds=silence, by_step={}),
        retry=config.RetrySection(transport_attempts=attempts, backoff_seconds=(5, 30)),
        log=config.LogSection(level="INFO", run_dir=Path(".claude-temp/kb-driver")),
        decisions={},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo root with the scratch layout root and a kb-root the driver may never write.

    Both documents a review brief names stand because ``phase-5`` meets them
    written — the readiness stamp seeds CONVENTIONS.md at ``phase-3a`` and
    ``ov.docs`` assembles README.md in the stage before the review — and a path
    slot is checked against disk before its call is made.
    """
    root = tmp_path / "repo"
    (root / steps.SCRATCH_ROOT).mkdir(parents=True)
    (root / "kb-root").mkdir()
    for name in REVIEW_DOCS.values():
        (root / "kb-root" / name).write_text(f"# {name}\n", encoding="utf-8")
    return root


@pytest.fixture
def build(tmp_path: Path, repo: Path) -> Callable[..., Harness]:
    """A caller over the local template set and a laid-out run directory."""
    templates = tmp_path / "templates"
    templates.mkdir()
    fragments = templates / prompt_templates.FRAGMENTS_DIRNAME
    fragments.mkdir()
    for name, text in TEMPLATES.items():
        (templates / name).write_text(text, encoding="utf-8")
    for name, text in FRAGMENTS.items():
        (fragments / name).write_text(text, encoding="utf-8")
    paths = runlog.prepare(tmp_path / "kb-driver", "run-0001")

    def _build(scenario: fake_model.Scenario, **overrides: int) -> Harness:
        sleeps: list[float] = []
        seen: list[fake_model.Context] = []

        def watched(context: fake_model.Context) -> fake_model.Response:
            seen.append(context)
            return scenario(context)

        invoker = fake_model.FakeInvoker(watched)
        caller = call.Caller(
            invoker=invoker,
            config=_config(**overrides),
            repo_root=repo,
            paths=paths,
            prompt_templates_dir=templates,
            sleep=sleeps.append,
        )
        return Harness(caller=caller, invoker=invoker, sleeps=sleeps, seen=seen, paths=paths, root=tmp_path)

    return _build


def _snapshot(root: Path) -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in root.rglob("*") if path.is_file()}


def _changed(before: Mapping[Path, str], after: Mapping[Path, str]) -> set[Path]:
    return {path for path, text in after.items() if before.get(path) != text}


def _passage(repo: Path) -> Path:
    """``ov.docs``' one declared artifact: the prose answer, under the scratch layout."""
    return repo / steps.SCRATCH_ROOT / steps.overview_prose(stage=steps.STEPS_BY_ID["ov.docs"].stage)


# ---------------------------------------------------------------------------
# The persistence route, and the guarantee nothing else under the repo changes
# ---------------------------------------------------------------------------


def test_the_driver_persists_a_never_writers_return_and_writes_nowhere_else(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean(VERDICT_TEXT))
    findings = repo / steps.SCRATCH_ROOT / steps.findings(stage="phase-5", author="tech-writer-reviewer")
    before = _snapshot(harness.root)

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["p5.review"], seq=3, slots=review_slots(repo), outputs=(findings,))
    )

    assert outcome.ok
    assert outcome.written == (findings,)
    assert findings.read_text(encoding="utf-8") == VERDICT_TEXT + "\n"
    # Parsed, never judged: the reviewer judges and the driver counts.
    assert outcome.verdict == envelope.Verdict(critical=0, warning=2, note=1)
    # The artifact, the composed brief, the capture — and nothing else, anywhere.
    # **This is where "the driver process never writes under kb-root/" is
    # asserted**: the changed set is stated exhaustively rather than as a
    # negative about one directory, so a write anywhere it does not name fails
    # here. The boundary that refuses such a target is the test below it.
    assert _changed(before, _snapshot(harness.root)) == {
        findings,
        harness.brief(3, "p5.review"),
        harness.stream(3, "p5.review", 1),
    }


# ---------------------------------------------------------------------------
# The driver-persists route's write is atomic
# ---------------------------------------------------------------------------
#
# **The dying write is injected as data, not by patching.** A text carrying a
# lone surrogate cannot be encoded, so the write fails after the file has been
# opened and before all of its bytes are there — which is the shape a killed
# process leaves, reachable through whichever write call this module makes rather
# than through the one a patch happened to name. Every reader of these paths asks
# presence and non-emptiness and nothing else, so a zero-byte or truncated file
# under the final name reads as work that finished.

UNWRITABLE_TEXT = "A passage that does not survive encoding: " + "\ud800" + "\n"


def _persist_request(repo: Path, target: Path) -> call.CallRequest:
    return call.CallRequest(step=steps.STEPS_BY_ID["ov.docs"], seq=1, slots=docs_slots(repo), outputs=(target,))


def test_a_dying_persist_leaves_no_partial_artifact_under_the_final_name(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean(PASSAGE_TEXT))
    target = _passage(repo)

    with pytest.raises(UnicodeEncodeError):
        harness.caller._persist(_persist_request(repo, target), text=UNWRITABLE_TEXT)

    assert not target.exists(), "a write that died left a file under the name a resume reads as finished work"


def test_a_dying_persist_leaves_the_artifact_already_there_untouched(repo: Path, build: Callable[..., Harness]) -> None:
    """The target is the previous file or the whole new one, and there is no third state."""
    harness = build(fake_model.clean(PASSAGE_TEXT))
    target = _passage(repo)
    harness.caller._persist(_persist_request(repo, target), text=PASSAGE_TEXT)

    with pytest.raises(UnicodeEncodeError):
        harness.caller._persist(_persist_request(repo, target), text=UNWRITABLE_TEXT)

    assert target.read_text(encoding="utf-8") == PASSAGE_TEXT


def test_a_driver_persist_target_outside_the_scratch_root_is_a_boundary_error(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean(VERDICT_TEXT))
    stray = repo / "kb-root" / "phase-5-r1-review.md"

    with pytest.raises(runlog.BoundaryError, match="scratch layout root"):
        harness.caller.execute(
            call.CallRequest(step=steps.STEPS_BY_ID["p5.review"], seq=3, slots=review_slots(repo), outputs=(stray,))
        )
    assert not stray.exists()


def test_a_path_a_seat_could_not_act_on_is_refused_before_the_call(repo: Path, build: Callable[..., Harness]) -> None:
    """Relative, absent, or a named absence where the slot admits none.

    The first is measured: a review handed ``kb-root/README.md`` searched for a
    directory of that name, reviewed a different repository's knowledge base,
    and returned three critical findings about it. All three fail the same way
    at the seat — it goes looking — so all three are refused before it is asked.
    """
    harness = build(fake_model.clean(VERDICT_TEXT))
    findings = repo / steps.SCRATCH_ROOT / "review" / "phase-5-r1-tech-writer-reviewer.md"
    sound = review_slots(repo)
    broken = {
        "is relative": {**sound, "readme-path": "kb-root/README.md"},
        "is not there": {**sound, "readme-path": str(repo / "kb-root" / "absent.md")},
        "admits none": {**sound, "conventions-path": steps.NOTHING},
    }

    for complaint, slots in broken.items():
        with pytest.raises(runlog.BoundaryError, match=complaint):
            harness.caller.execute(
                call.CallRequest(step=steps.STEPS_BY_ID["p5.review"], seq=3, slots=slots, outputs=(findings,))
            )
    assert not harness.seen, "a brief no seat could act on was dispatched anyway"


def test_an_optional_path_slot_may_carry_the_named_absence(repo: Path, build: Callable[..., Harness]) -> None:
    """A first round has no findings to answer, which is an absence with a name."""
    passage = _passage(repo)
    harness = build(fake_model.clean(PASSAGE_TEXT))

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(passage,))
    )

    assert outcome.ok
    assert steps.NOTHING in harness.brief(3, "ov.docs").read_text(encoding="utf-8")


def test_an_empty_return_never_becomes_an_artifact(repo: Path, build: Callable[..., Harness]) -> None:
    harness = build(fake_model.clean("   \n"))
    target = repo / steps.SCRATCH_ROOT / "review" / "phase-5-r1-tech-writer-reviewer.md"

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["p5.review"], seq=20, slots=review_slots(repo), outputs=(target,))
    )

    assert outcome.exit_code == baton.EXIT_CONTRACT
    assert not target.exists()


# ---------------------------------------------------------------------------
# Composition: the seat, and the driver constants
# ---------------------------------------------------------------------------


def test_a_call_carries_its_rows_seat_on_agent(repo: Path, build: Callable[..., Harness]) -> None:
    """``--agent`` is how the seat's own definition — and its model pin — is selected."""
    step = steps.STEPS_BY_ID["p5.review"]
    harness = build(fake_model.clean(VERDICT_TEXT))
    findings = repo / steps.SCRATCH_ROOT / "review" / "phase-5-r1-tech-writer-reviewer.md"

    outcome = harness.caller.execute(call.CallRequest(step=step, seq=1, slots=review_slots(repo), outputs=(findings,)))

    assert outcome.ok
    assert harness.seen[0].agent == step.seat


def test_a_step_that_makes_no_call_is_a_boundary_error(build: Callable[..., Harness]) -> None:
    harness = build(fake_model.clean("ok"))

    with pytest.raises(runlog.BoundaryError, match="makes no call"):
        harness.caller.execute(call.CallRequest(step=steps.STEPS_BY_ID["p3a.record"], seq=4))


@pytest.mark.parametrize("smuggled", [["--model", "haiku"], ["--model=haiku"]])
def test_a_command_prefix_carrying_model_is_refused_in_either_spelling(
    repo: Path, build: Callable[..., Harness], smuggled: list[str]
) -> None:
    """Both spellings override every seat's frontmatter pin, so both are refused alike.

    Exact list membership reads the separated form and misses the joined one,
    which argparse accepts identically — so the pin was overridable with no log
    line, no exit-code change, and nothing on the card to read.
    """
    harness = build(fake_model.clean(PASSAGE_TEXT))
    caller = replace(
        harness.caller,
        config=replace(
            harness.caller.config,
            claude=replace(harness.caller.config.claude, command=("claude", *smuggled)),
        ),
    )

    with pytest.raises(runlog.BoundaryError, match="--model"):
        caller.execute(
            call.CallRequest(
                step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(_passage(repo),)
            )
        )

    assert harness.invoker.calls == 0


def test_an_empty_composed_brief_is_a_boundary_error_rather_than_a_call(
    repo: Path, build: Callable[..., Harness], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The spawn boundary: nothing is worth spawning on a brief with nothing in it."""
    harness = build(fake_model.clean(PASSAGE_TEXT))

    def persist_nothing(briefs_dir: Path, *, seq: int, step_id: str, text: str) -> Path:
        del text
        path = briefs_dir / f"{seq:03d}-{step_id}.md"
        path.write_text("", encoding="utf-8")
        return path

    monkeypatch.setattr(prompt_templates, "persist", persist_nothing)

    with pytest.raises(runlog.BoundaryError, match="brief is empty"):
        harness.caller.execute(
            call.CallRequest(
                step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(_passage(repo),)
            )
        )

    assert harness.invoker.calls == 0


def test_a_call_spawned_while_another_is_live_is_a_boundary_error(repo: Path, build: Callable[..., Harness]) -> None:
    """Exactly one ``claude`` subprocess at a time — a policy of this driver's, held here.

    The re-entry is made from inside a scripted call, which is where a second
    spawn would happen for real: a scenario stands in for the process that is
    still live while the next one is started.
    """
    nested: list[runlog.BoundaryError] = []
    request = call.CallRequest(
        step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(_passage(repo),)
    )

    def reentrant(context: fake_model.Context) -> fake_model.Response:
        try:
            harness.caller.execute(replace(request, seq=4))
        except runlog.BoundaryError as exc:
            nested.append(exc)
        return fake_model.clean(PASSAGE_TEXT)(context)

    harness = build(reentrant)

    assert harness.caller.execute(request).ok
    assert [str(exc) for exc in nested] == ["a call would be spawned while another is still live"]
    # …and the guard released, so the next call is not poisoned by the last.
    assert harness.caller.execute(replace(request, seq=5)).ok


# ---------------------------------------------------------------------------
# Transport retry
# ---------------------------------------------------------------------------


def test_a_transport_death_is_retried_until_a_call_stands(repo: Path, build: Callable[..., Harness]) -> None:
    passage = _passage(repo)
    stands = fake_model.clean(PASSAGE_TEXT)
    harness = build(fake_model.sequence(fake_model.transport_die(), fake_model.transport_die(), stands))

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(passage,))
    )

    assert outcome.ok
    assert outcome.attempts == 3
    assert harness.invoker.calls == 3
    assert harness.sleeps == [5.0, 30.0]  # the coordinator's own backoff: driver and briefs state one policy
    # Every attempt's capture is its own evidence file.
    assert all(harness.stream(3, "ov.docs", attempt).is_file() for attempt in (1, 2, 3))


def test_exhausted_transport_retries_exit_12(repo: Path, build: Callable[..., Harness]) -> None:
    harness = build(fake_model.transport_die(stderr="connection reset\n"))
    passage = _passage(repo)

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(passage,))
    )

    assert outcome.exit_code == baton.EXIT_TRANSPORT
    assert harness.invoker.calls == 3
    assert outcome.detail[0] == "ov.docs: transport-failure after 3 attempt(s)"
    assert "connection reset" in outcome.detail
    assert not passage.exists()
    # A transport death is not a contract failure: the step is never re-asked.
    assert not harness.brief(3, f"ov.docs{call.REASK_SUFFIX}").exists()


def test_a_cli_rejection_is_never_retried_and_exits_13(repo: Path, build: Callable[..., Harness]) -> None:
    stderr = "error: unknown option '--frobnicate-widget'\n"
    harness = build(fake_model.cli_rejection(stderr))

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(_passage(repo),))
    )

    assert outcome.exit_code == baton.EXIT_CONFIG
    assert harness.invoker.calls == 1  # retrying it is three identical failures and a misleading exit 12
    assert harness.sleeps == []
    assert stderr.strip() in outcome.detail


def test_a_command_that_cannot_be_spawned_exits_14_and_carries_a_restore_line(
    tmp_path: Path, repo: Path, build: Callable[..., Harness]
) -> None:
    """A missing or mistyped ``[claude] command`` is an environment fault, not a driver defect.

    The real ``SubprocessInvoker``, because the fault is ``Popen``'s own
    ``FileNotFoundError`` and a substituted invoker cannot raise it in the place
    that matters. Exit 14 is where ``ledger._run`` already puts a tool it could
    not spawn, and its card is the one that fits: relay the ``restore:`` line
    and re-run after it. Unclassified, this leaves as exit 15 — the code whose
    card names the run directory as a bug report against the driver.
    """
    absent = tmp_path / "no-such-claude"
    harness = build(fake_model.clean(PASSAGE_TEXT))
    caller = replace(
        harness.caller,
        invoker=inference.SubprocessInvoker(),
        config=replace(
            harness.caller.config,
            claude=replace(harness.caller.config.claude, command=(str(absent),)),
        ),
    )
    passage = _passage(repo)

    outcome = caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(passage,))
    )

    assert outcome.exit_code == baton.EXIT_ENVIRONMENT
    assert outcome.attempts == 1, "a command that is not on the path is not on it three times either"
    assert harness.sleeps == []
    assert str(absent) in outcome.detail[0]
    assert "restore:" in outcome.detail[0]
    assert not passage.exists()


def test_a_silence_wedge_is_a_transport_failure_and_exhausts_to_12(repo: Path, build: Callable[..., Harness]) -> None:
    harness = build(fake_model.stall(), attempts=1, silence=1)

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["ov.docs"], seq=3, slots=docs_slots(repo), outputs=(_passage(repo),))
    )

    assert outcome.exit_code == baton.EXIT_TRANSPORT
    assert outcome.detail[0].startswith(f"ov.docs: {inference.Outcome.SILENCE.value}")


# ---------------------------------------------------------------------------
# Contract validation and the one re-ask (exit 17)
# ---------------------------------------------------------------------------


def test_a_contract_failure_re_asks_the_same_step_once_with_the_complaint(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(
        fake_model.sequence(fake_model.clean("no verdict anywhere in this text"), fake_model.clean(VERDICT_TEXT))
    )
    findings = repo / steps.SCRATCH_ROOT / steps.findings(stage="phase-5", author="tech-writer-reviewer")

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["p5.review"], seq=5, slots=review_slots(repo), outputs=(findings,))
    )

    assert outcome.ok
    assert outcome.verdict == envelope.Verdict(critical=0, warning=2, note=1)
    assert harness.invoker.calls == 2
    # Only the answer that stood became the artifact.
    assert findings.read_text(encoding="utf-8") == VERDICT_TEXT + "\n"

    first = harness.brief(5, "p5.review").read_text(encoding="utf-8")
    re_ask = harness.brief(5, f"p5.review{call.REASK_SUFFIX}").read_text(encoding="utf-8")
    assert re_ask.startswith(first.rstrip("\n"))  # the same brief …
    assert "VERDICT" in re_ask.removeprefix(first.rstrip("\n"))  # … with the validator's complaint attached


def test_a_second_contract_failure_exits_17_naming_the_step_and_the_complaint(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean("VERDICT: critical=none"))
    findings = repo / steps.SCRATCH_ROOT / steps.findings(stage="phase-5", author="tech-writer-reviewer")

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["p5.review"], seq=5, slots=review_slots(repo), outputs=(findings,))
    )

    assert outcome.exit_code == baton.EXIT_CONTRACT
    assert harness.invoker.calls == 2  # one ask, one re-ask, and no third
    assert outcome.detail[0].startswith("p5.review:")
    assert any("VERDICT" in line for line in outcome.detail[1:])
    assert not findings.exists()


def test_a_premature_dispatch_fails_the_contract_check_rather_than_passing_as_a_finished_call(
    repo: Path, build: Callable[..., Harness]
) -> None:
    # The async-dispatch shape: a first `result` announcing success before the
    # work the call started had run. Accepting it records a finished step whose
    # work never happened — the false green this architecture exists to
    # eliminate.
    harness = build(fake_model.sequence(fake_model.premature_dispatch(VERDICT_TEXT), fake_model.clean(VERDICT_TEXT)))
    findings = repo / steps.SCRATCH_ROOT / "review" / "phase-5-r1-tech-writer-reviewer.md"

    outcome = harness.caller.execute(
        call.CallRequest(step=steps.STEPS_BY_ID["p5.review"], seq=1, slots=review_slots(repo), outputs=(findings,))
    )

    assert outcome.ok  # the re-ask stood
    assert harness.invoker.calls == 2
    re_ask = harness.brief(1, f"p5.review{call.REASK_SUFFIX}").read_text(encoding="utf-8")
    assert "init events in one call" in re_ask
    assert "run_in_background" in re_ask
