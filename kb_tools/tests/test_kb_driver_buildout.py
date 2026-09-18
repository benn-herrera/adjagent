"""The build-out stages: ``phase-3a``, ``overview-drafted`` and ``phase-5``.

The KB tree this driver walks over is no longer this driver's own output: the
distillation stages (``phase-0`` through ``phase-3``) that used to derive it
from a LaTeX survey are gone, replaced by a separately-authored pandoc front
end. What survives here is everything downstream of an already-built tree:

* **``phase-3a`` is a gate and a record, and nothing between them.** The three
  verifiers run behind ``kb-refresh``; green records the stage and red stops the
  run. No round is spent and no seat is dispatched, because each verifier
  compares one mechanically-produced artifact against another and a red one is
  a defect in a tool or in what was authored.
* **``overview-drafted`` writes the overview document and ``phase-5`` reviews
  it.** Two stages and two boundaries, because each spends a model call and
  neither may pay for the other's failure. The review side is a fixed sequence
  — one review, then one revision answering its findings — and no severity the
  reviewer returns fails the stage.

The fixture's ``repo`` starts at the state the pandoc pipeline hands off: a KB
spine, with every domain's leaves already distilled (:func:`distilled`) by the
case that needs them — this driver writes no document tree of its own, and the
tree is the only thing it is told about the corpus. The ledger and the runner
targets are the two seams
``test_kb_driver_run.py`` also uses. The templates are local stand-ins named
for the real ones, and their prose is not what this suite is about.
"""

import itertools
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_pipeline, kb_readme, kb_util
from kb_tools.kb_driver import barriers, baton, config, envelope, ledger, prompt_templates, run, runlog, steps
from kb_tools.tests import _fake_model as fake_model

#: A KB with nothing in it, used only to read the emitter's own artifact
#: vocabulary off ``build_all_records``. A list of filenames here would be a
#: second statement of what ``.index/`` holds.
EMPTY_KB = kb_index_lib.KbState(claim_entries=(), leaves=(), indexes=(), framework_nodes=(), experiments=())

#: The volumes this run is given, and the domain directories the document graph
#: put under ``kb-root/`` for them — a domain IS a volume, but the driver learns
#: that from the tree rather than from the source list. In sorted order, which
#: is the order the walk returns them in.
SOURCES = ("Dynamics.tex", "Foundations.tex", "Policy.tex")
DOMAINS = ("dynamics", "foundations", "policy")

#: The recorded-stage set a fixture starts each scenario from — one entry per
#: stage this table still has rows for, since ``phase-3a`` is the first row
#: any case here drives.
RECORDED_THROUGH_3A_PREDECESSOR = ("start",)
RECORDED_THROUGH_3A = (*RECORDED_THROUGH_3A_PREDECESSOR, "phase-3a")

#: The two meta-documentation stages, walked together by every case below that
#: wants the review: the draft is what the review is handed, and it lands in the
#: stage before — so a case walking the cycle alone would hand a reviewer a
#: README that was never written.
META_STAGES = ("overview-drafted", "phase-5")


# ---------------------------------------------------------------------------
# The templates a call composes against
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# What a call reads out of its brief
# ---------------------------------------------------------------------------


def field(brief: str, name: str) -> str:
    """One ``<Name>: <value>`` line of a stand-in template."""
    match = re.search(rf"^{re.escape(name)}: (.+)$", brief, re.MULTILINE)
    assert match is not None, f"the brief carries no {name!r} line"
    return match.group(1).strip()


#: The three verdicts these cases script, named for what each does to the gate.
#: ``CARRIED`` is the live one: a build of arXiv 2609.09855v1 returned exactly
#: this and stopped, which is the stop the severity gate exists to not make.
CLEAN = envelope.Verdict(critical=0, warning=0, note=0)
CARRIED = envelope.Verdict(critical=0, warning=1, note=2)
CRITICAL = envelope.Verdict(critical=1, warning=0, note=0)


#: How many leaves each domain directory holds — the shape the document graph
#: leaves behind, which is what ``phase-3a`` runs its verifiers over.
LEAVES_PER_DOMAIN = 2


def leaves_for(domain: str, count: int = LEAVES_PER_DOMAIN) -> tuple[str, ...]:
    """The kb-root-relative leaves one domain directory holds."""
    return tuple(f"{domain}/leaf-{ordinal}.md" for ordinal in range(1, count + 1))


# ---------------------------------------------------------------------------
# The seams
# ---------------------------------------------------------------------------

PREFLIGHT = (
    "[preflight] FACT runner-file       justfile (runner: just)\n"
    "[preflight] PASS docent-commands   both present under .claude/commands\n"
    "[preflight] PASS: ready.\n"
)
PREFLIGHT_MISSING_DOCENT = (
    "[preflight] FACT runner-file       justfile (runner: just)\n"
    "[preflight] FAIL docent-commands   missing kb-next.md under .claude/commands — incomplete install; "
    "restore: run 'just install .' from the generator repo\n"
)


# A call's label is `<seq>-<step id>`; the sequence number is evidence, not identity.
_SEQ_PREFIX_RE = re.compile(r"^\d+-")

# One run directory per `drive()`, because a test that resumes a stage drives
# twice and `runlog.prepare` refuses to reuse one.
_RUN_SERIAL = itertools.count(1)


class Script:
    """Scripted returns per step id; the last one repeats. Records every call it served."""

    def __init__(self, returns: Mapping[str, object]) -> None:
        self._returns = dict(returns)
        self.calls: list[fake_model.Context] = []

    @property
    def order(self) -> list[str]:
        """Every step this run dispatched, in dispatch order, without its sequence prefix."""
        return [_SEQ_PREFIX_RE.sub("", context.step) for context in self.calls]

    def count(self, step_id: str) -> int:
        return sum(1 for context in self.calls if context.step.endswith(step_id))

    def contexts(self, step_id: str) -> list[fake_model.Context]:
        return [context for context in self.calls if context.step.endswith(step_id)]

    def brief(self, step_id: str) -> str:
        contexts = self.contexts(step_id)
        assert contexts, f"{step_id} was never called"
        return contexts[-1].brief_text()

    def scenario(self) -> fake_model.Scenario:
        def scenario(context: fake_model.Context) -> fake_model.Response:
            self.calls.append(context)
            for step_id, scripted in self._returns.items():
                if not context.step.endswith(step_id) and not context.step.endswith(f"{step_id}-reask"):
                    continue
                answers = scripted if isinstance(scripted, (list, tuple)) else [scripted]
                answer = answers[min(self.count(step_id) - 1, len(answers) - 1)]
                return fake_model.clean(answer(context) if callable(answer) else str(answer))(context)
            raise AssertionError(f"no scripted return for {context.step}")

        return scenario


def render_for(recorded: Sequence[str]) -> str:
    lines = [f"[kb-build] status: in progress ({len(recorded)} recorded)"]
    lines += [f"[{'x' if stage in recorded else ' '}] {stage}  {stage} display" for stage in kb_pipeline.STAGE_IDS]
    lines.append("[kb-build] next action — do the thing")
    return "\n".join(lines) + "\n"


class FakeLedger:
    """The recorded-stage set as a tool would report it, plus what each op was told.

    ``verify`` is a sequence consumed one per ``kb-verify`` run, the last
    repeating, so a case states the gate's verdict without reaching into the
    stage that reads it.
    """

    def __init__(
        self,
        *,
        recorded: Sequence[str] = (),
        verify: Sequence[ledger.Outcome] = (),
        preflight_stdout: str = PREFLIGHT,
        refuses: Sequence[str] = (),
    ) -> None:
        self.recorded = list(recorded)
        #: Each stage's boundary-commit body, as the record row supplied it. The
        #: rounds a findings loop ran are an attribute of that entry and are
        #: recorded nowhere else, so this is where a case reads them.
        self.notes: dict[str, str] = {}
        self.targets: list[str] = []
        self._repo_root: Path | None = None
        self._verify = list(verify)
        self._verifies = 0
        self._preflight_stdout = preflight_stdout
        #: Stages whose record fails once, and the way a killed process leaves
        #: one: the stage's work ran and no boundary accounts for it. A second
        #: invocation records it, because the kill was the process's and not the
        #: stage's.
        self._refuses = set(refuses)

    def _advance(self, *, stage: str, note: str = "", no_inference: bool = False) -> ledger.Outcome:
        if stage in self._refuses:
            self._refuses.discard(stage)
            return ledger.Outcome(baton.EXIT_ENVIRONMENT, detail=(f"the boundary commit for {stage} did not land",))
        self.recorded.append(stage)
        self.notes[stage] = note
        return ledger.Outcome(baton.EXIT_OK)

    def _run_target(self, *, target: str) -> ledger.Outcome:
        self.targets.append(target)
        if target != kb_util.TARGET_VERIFY or not self._verify:
            return ledger.Outcome(baton.EXIT_OK)
        outcome = self._verify[min(self._verifies, len(self._verify) - 1)]
        self._verifies += 1
        return outcome

    def ops(self, repo_root: Path) -> run.LedgerOps:
        """The seam, with the repo root bound — the real adapter's own shape."""
        self._repo_root = repo_root
        return run.LedgerOps(
            preflight=lambda: ledger.Outcome(baton.EXIT_OK, stdout=self._preflight_stdout),
            graph_init=lambda *, runner: ledger.Outcome(baton.EXIT_OK),
            document_graph=lambda *, sources, bibliographies, kb_root: ledger.Outcome(baton.EXIT_OK),
            claim_graph=lambda *, flags: ledger.Outcome(baton.EXIT_OK),
            start_build=lambda *, charter: ledger.Outcome(baton.EXIT_OK),
            advance_step=self._advance,
            show_status=lambda *, relay: ledger.Outcome(baton.EXIT_OK, stdout=render_for(self.recorded)),
            run_target=self._run_target,
        )


def red_gate(*paths: str) -> ledger.Outcome:
    """A verify outcome whose report names the files it faulted.

    The detail carries the report lines as well as the op and the rc, which is
    what ``ledger._failure_detail`` puts there: a card whose ASK names only the
    rc leaves the operator re-running the stage by hand to learn what it said.
    """
    faults = [f"[verify] {kb_util.FAIL} {path}: broken link" for path in paths]
    report = "\n".join(["[verify] metadata gate red", *faults])
    return ledger.Outcome(baton.EXIT_GATE_RED, stdout=report + "\n", detail=("kb-verify exited 1", *faults))


GREEN = ledger.Outcome(baton.EXIT_OK, stdout="[verify] green\n")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _quiet_logs() -> Iterator[None]:
    yield
    import logging

    driver_log = logging.getLogger("kb_driver")
    for handler in list(driver_log.handlers):
        driver_log.removeHandler(handler)
        handler.close()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A consuming repo at the state the pandoc pipeline hands off.

    The spine and nothing else under ``kb-root/`` — a case that wants a domain
    already distilled calls :func:`distilled` itself, which is what every case
    past ``phase-3a`` does. That call is what puts the volume directories the
    domain partition is walked off on disk, so a case reaching a fix wave
    without it has no tree to partition, which is the honest state rather than
    a fixture detail.
    """
    root = tmp_path / "repo"
    (root / steps.SCRATCH_ROOT).mkdir(parents=True)
    (root / kb_pipeline.CHARTER_RELPATH).write_text("# Build charter\n\nBoth volumes.\n", encoding="utf-8")

    index_dir = kb_util.index_dir(root)
    index_dir.mkdir(parents=True)
    # The derived artifacts a real `phase-3a` refresh leaves behind. This
    # suite's ledger is a fake and no refresh runs, so the files are laid down
    # here: `phase-5` reads its counts out of them, and an absent one is the
    # different failure of an index that was never rebuilt.
    for name in kb_index_lib.build_all_records(EMPTY_KB):
        (index_dir / f"{name}.jsonl").write_text("", encoding="utf-8")

    commands = root / kb_util.CLAUDE_DIRNAME / kb_util.COMMANDS_DIRNAME
    commands.mkdir(parents=True)
    for name in kb_util.DOCENT_COMMAND_FILENAMES:
        (commands / name).write_text(f"# {name}\n", encoding="utf-8")
    # `phase-3a`'s readiness stamp writes this, and this suite's ledger is a
    # fake so no stamp runs. `phase-5`'s review is handed its path and the call
    # is refused where the file is not there, so an absent one here would be a
    # fixture that under-models the state the stage really meets.
    (kb_util.kb_root(root) / kb_pipeline.CONVENTIONS_DOC).write_text("# Conventions\n", encoding="utf-8")
    return root


@pytest.fixture
def templates(tmp_path: Path) -> Path:
    directory = tmp_path / "templates"
    directory.mkdir()
    fragments = directory / prompt_templates.FRAGMENTS_DIRNAME
    fragments.mkdir()
    for name, text in TEMPLATES.items():
        (directory / name).write_text(text, encoding="utf-8")
    for name, text in FRAGMENTS.items():
        (fragments / name).write_text(text, encoding="utf-8")
    return directory


def drive(
    *,
    repo_root: Path,
    tmp_path: Path,
    templates: Path,
    script: Script,
    fake: FakeLedger,
    stages: Sequence[str],
    decisions: Mapping[str, str] = (),
    ops: run.LedgerOps | None = None,
) -> run.Result:
    body = ["[run]", f"sources = {json.dumps(list(SOURCES))}", 'permission_mode = "acceptEdits"']
    for pair, answer in dict(decisions).items():
        stage, _, kind = pair.rpartition(".")
        body += ["", f'[barriers."{stage}"."{kind}"]', f'decision = "{answer}"']
    path = repo_root / "driver-run.toml"
    path.write_text("\n".join(body) + "\n", encoding="utf-8")

    paths = runlog.prepare(tmp_path / "runs", f"20260901T120000-{next(_RUN_SERIAL)}")
    lock = runlog.repo_lock_path(repo_root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pid": 1, "run_id": paths.run_id}), encoding="utf-8")
    return run.execute(
        config=config.load(path, admissible=barriers.ADMISSIBLE),
        paths=paths,
        invoker=fake_model.FakeInvoker(script.scenario()),
        ops=ops if ops is not None else fake.ops(repo_root),
        repo_root=repo_root,
        stages=stages,
        prompt_templates_dir=templates,
    )


# ---------------------------------------------------------------------------
# The scenarios each call runs
# ---------------------------------------------------------------------------


#: What the seat returns at ``ov.docs`` / ``p5.fix``: the passage, and nothing
#: else. It writes no file, because the stage assembles the document.
PASSAGE = "This corpus is three volumes of synthetic material. Start at the first."

#: What the seat returns at ``p5.fix``. It differs from :data:`PASSAGE` so that
#: a case can tell which of the two calls the standing document was assembled
#: over; the revision runs either way.
FIXED_PASSAGE = "This corpus is three volumes of synthetic material, and index.md is where a reader starts."


def phase_5_script(*, verdict: envelope.Verdict = CLEAN) -> Script:
    return Script(
        {
            "ov.docs": PASSAGE,
            "p5.fix": FIXED_PASSAGE,
            # `fake_model.verdict` composes the line `envelope.parse_verdict` reads,
            # so a scripted review cannot spell a format the driver would refuse.
            "p5.review": fake_model.verdict(critical=verdict.critical, warning=verdict.warning, note=verdict.note),
        }
    )


def stamp_leaf(repo_root: Path, path: str) -> Path:
    """One leaf as the pandoc pipeline leaves it: a rendered body under a metadata block."""
    leaf = kb_util.kb_root(repo_root) / path
    leaf.parent.mkdir(parents=True, exist_ok=True)
    body = f"[Up: {path}](../index.md)\n\nA distilled leaf.\n"
    leaf.write_text(fake_model.stamped_leaf(body, claims=()), encoding="utf-8")
    return leaf


def distilled(repo_root: Path) -> None:
    """Every derived leaf stamped on disk — the state this driver assumes on entry.

    Nothing in this table writes it: distillation is the pandoc front end's
    job, run before this driver ever sees the repo. ``phase-3a`` onward reads
    the tree, and this is the tree it reads.
    """
    for domain in DOMAINS:
        for path in leaves_for(domain):
            stamp_leaf(repo_root, path)


# ---------------------------------------------------------------------------
# phase-3a: the gate, and the two ways it ends
# ---------------------------------------------------------------------------


def test_the_gate_refreshes_before_it_verifies(repo: Path, tmp_path: Path, templates: Path) -> None:
    """A derived-state read needs a refresh in front of it."""
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A_PREDECESSOR)

    drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=Script({}),
        fake=fake,
        stages=("phase-3a",),
    )

    assert fake.targets == [kb_util.TARGET_REFRESH, kb_util.TARGET_VERIFY]
    assert fake.recorded[-1] == "phase-3a"


def test_a_red_gate_stops_the_run_and_records_nothing(repo: Path, tmp_path: Path, templates: Path) -> None:
    """No round, no seat, no cap: a failed verifier ends the walk where it stands.

    Each of the three verifiers compares one mechanically-produced artifact
    against another, so a red one is a defect in a tool or in what was authored
    — not work a dispatched seat could close, and not a barrier anyone can
    answer. The verifier's own report is in the run log; what reaches the caller
    is the target that failed and exit 11.
    """
    distilled(repo)
    faulted = f"{kb_util.KB_DIRNAME}/{DOMAINS[1]}/{DOMAINS[1]}.md"
    script = Script({})
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A_PREDECESSOR, verify=[red_gate(faulted), GREEN])

    result = drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=script,
        fake=fake,
        stages=("phase-3a",),
    )

    assert result.exit_code == baton.EXIT_GATE_RED
    assert result.pair == "", "a red gate is an exit, not a barrier — no answer would repair the KB"
    assert script.calls == [], "no seat is dispatched over a mechanical gate"
    assert "phase-3a" not in fake.recorded
    assert not (repo / steps.SCRATCH_ROOT / "review").exists(), "nothing writes a findings round here"

    # The card the relay actually prints, from the very context the run ended
    # with: the failing gate's own lines are in it, and nothing in it asks a
    # question or offers a `--decide` for a barrier that was never raised.
    card = baton.render(result.exit_code, result.context)
    assert f"[verify] {kb_util.FAIL} {faulted}: broken link" in card
    assert "(missing —" not in card
    assert "--decide" not in card


def test_an_environment_fault_stops_the_run_the_same_way_a_red_gate_does(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """Exit 14, and the restore line the ledger composed — never a fix cycle."""
    distilled(repo)
    missing = ledger.Outcome(baton.EXIT_ENVIRONMENT, detail=("no justfile or Makefile — restore: install targets",))

    result = drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=Script({}),
        fake=FakeLedger(recorded=RECORDED_THROUGH_3A_PREDECESSOR, verify=[missing]),
        stages=("phase-3a",),
    )

    assert result.exit_code == baton.EXIT_ENVIRONMENT
    assert any("restore:" in line for line in result.detail)


# ---------------------------------------------------------------------------
# phase-5: meta-docs, the fixed review sequence, and the docent check
# ---------------------------------------------------------------------------


def test_the_stage_assembles_the_overview_document_reviews_it_and_records(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The stage assembles; the seat answers. One call each, and no document composed by a model."""
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A)
    script = phase_5_script()

    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=script, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert script.order == ["ov.docs", "p5.review", "p5.fix"]
    assert fake.recorded[-1] == "phase-5"

    document = (kb_util.kb_root(repo) / kb_pipeline.OVERVIEW_DOC).read_text(encoding="utf-8")
    # The seat's answer reaches the document verbatim, and nothing else it
    # returned does — every other word is the template's or the index's. The
    # revision ran last, so its answer is the one standing.
    assert FIXED_PASSAGE in document
    assert not kb_readme.slots(document), "a slot reached the knowledge base unfilled"
    # The counts the seat was never asked for: this corpus has no claims, and
    # the document says so because the index does.
    assert f"{len(DOMAINS) * LEAVES_PER_DOMAIN} documents" in document


@pytest.mark.parametrize("verdict", [CLEAN, CARRIED, CRITICAL], ids=["clean", "carried", "critical"])
def test_no_severity_the_reviewer_returns_fails_the_stage(
    repo: Path, tmp_path: Path, templates: Path, verdict: envelope.Verdict
) -> None:
    """The same two calls and the same boundary, whatever the reviewer ruled.

    A gate over a review's severities is a stage exiting on a model's opinion,
    and a loop over one is a build that ends when a reviewer runs out of things
    to say. The stage is a structure instead: the review runs, the revision
    answers what it wrote, the stage records, and the findings stand in the run
    log for a reader to act on later.
    """
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A)
    script = phase_5_script(verdict=verdict)

    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=script, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert result.pair == "", "a finding is reported, and a report is not a barrier"
    assert script.order == ["ov.docs", "p5.review", "p5.fix"]
    assert fake.recorded[-1] == "phase-5"


def test_a_revision_composing_the_document_already_standing_is_not_a_failure(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The seat answers with the draft's own passage, so the document does not move.

    Nothing here compares what the revision composed against what stood: the
    stage runs two calls and records, and a revision that reaches the same
    passage from the same tree has answered the question it was asked. The
    document that stands is the one the revision composed, byte for byte the
    draft's.
    """
    distilled(repo)
    script = Script({"ov.docs": PASSAGE, "p5.fix": PASSAGE, "p5.review": fake_model.verdict(critical=1)})
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A)

    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=script, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert script.count("p5.fix") == 1
    assert fake.recorded[-1] == "phase-5"
    document = (kb_util.kb_root(repo) / kb_pipeline.OVERVIEW_DOC).read_text(encoding="utf-8")
    assert PASSAGE in document


def _findings_path(repo: Path) -> Path:
    """Where the review's findings land — the path the review row declares."""
    return repo / steps.SCRATCH_ROOT / steps.findings(stage="phase-5", author=steps.META_REVIEW_SEAT)


def test_a_findings_file_a_dead_process_left_is_overwritten_by_the_review_that_runs(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """Nothing on disk is read as evidence that a call already happened.

    The zero-byte file is what a process killed mid-write leaves. A stage the
    walk reaches is a stage no boundary accounts for, so its review runs and
    lands on that path rather than being skipped or counted.
    """
    distilled(repo)
    orphan = _findings_path(repo)
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.touch()
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A)
    script = phase_5_script(verdict=CRITICAL)

    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=script, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert script.count("p5.review") == 1
    assert fake.recorded[-1] == "phase-5"
    assert orphan.read_text(encoding="utf-8").strip(), "the review that ran did not land on the orphan's path"


def test_a_stage_that_ran_everything_records_a_boundary_with_no_note(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The rows are a fixed sequence, so the entry saying the stage is behind the build says it ran them.

    A note stating what a stage spent would be a second view of the step table,
    and it would go stale against it silently. The one thing a finished build
    cannot state about itself is a row it *dropped*, which is the note that
    survives (``test_kb_driver_head.py`` drives it).
    """
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A_PREDECESSOR)

    drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=phase_5_script(verdict=CRITICAL),
        fake=fake,
        stages=("phase-3a", *META_STAGES),
    )

    assert [fake.notes[stage] for stage in ("phase-3a", *META_STAGES)] == ["", "", ""]


@pytest.mark.parametrize(
    ("returned", "expected"),
    [
        (CARRIED, "the 3 finding(s) are answered by the one revision that follows"),
        (CLEAN, "the reviewer raised no finding at any severity"),
    ],
    ids=["non-zero", "zero"],
)
def test_the_review_reports_its_counts_by_severity_and_where_the_findings_are(
    repo: Path,
    tmp_path: Path,
    templates: Path,
    caplog: pytest.LogCaptureFixture,
    returned: envelope.Verdict,
    expected: str,
) -> None:
    """Both forms reach the operator, and the whole statement is in the message.

    The zero form is the load-bearing half: a build that said nothing when the
    reviewer raised no warning would read exactly like one whose warnings went
    unreported, and promoting a severity to a stop on our own schedule depends
    on having seen it. The console tee prints messages alone, so the counts and
    the path are asserted against the message text and not the record's context.
    """
    distilled(repo)
    script = phase_5_script(verdict=returned)
    findings = steps.findings(stage="phase-5", author=steps.META_REVIEW_SEAT)

    with caplog.at_level("INFO", logger="kb_driver.run"):
        drive(
            repo_root=repo,
            tmp_path=tmp_path,
            templates=templates,
            script=script,
            fake=FakeLedger(recorded=RECORDED_THROUGH_3A),
            stages=META_STAGES,
        )

    line = next(
        (message for message in caplog.messages if message.startswith("phase-5 review:")),
        None,
    )
    assert line is not None, "the review reported no counts at all"
    assert f"critical={returned.critical} warning={returned.warning} note={returned.note}" in line
    assert expected in line
    assert f"findings: {steps.SCRATCH_ROOT}/{findings}" in line


def test_the_fix_call_reads_the_reviewers_findings_and_the_first_pass_does_not(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """One template, two call sites: the difference is one slot with a named absence."""
    distilled(repo)
    script = phase_5_script(verdict=CRITICAL)

    drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=script,
        fake=FakeLedger(recorded=RECORDED_THROUGH_3A),
        stages=META_STAGES,
    )

    assert field(script.brief("ov.docs"), "Findings") == steps.NOTHING
    findings = steps.findings(stage="phase-5", author=steps.META_REVIEW_SEAT)
    assert field(script.brief("p5.fix"), "Findings").endswith(Path(findings).name)


def test_every_path_a_brief_hands_a_seat_resolves_without_a_base(repo: Path, tmp_path: Path, templates: Path) -> None:
    """A relative path here is one a seat resolves against a cwd no brief states.

    Measured: a review handed ``kb-root/README.md`` searched for a directory of
    that name, reviewed a different repository's knowledge base, and returned
    three critical findings about it.
    """
    distilled(repo)
    script = phase_5_script(verdict=CRITICAL)

    drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=script,
        fake=FakeLedger(recorded=RECORDED_THROUGH_3A),
        stages=META_STAGES,
    )

    stated = {
        ("ov.docs", "KB"): repo / "kb-root",
        ("p5.review", "README"): repo / "kb-root" / kb_pipeline.OVERVIEW_DOC,
        ("p5.review", "CONVENTIONS"): repo / "kb-root" / kb_pipeline.CONVENTIONS_DOC,
        ("p5.fix", "Findings"): repo
        / steps.SCRATCH_ROOT
        / steps.findings(stage="phase-5", author=steps.META_REVIEW_SEAT),
    }
    for (step_id, name), expected in stated.items():
        stated_path = field(script.brief(step_id), name)
        assert Path(stated_path).is_absolute(), f"{step_id}'s {name} has no base"
        assert stated_path == str(expected), f"{step_id}'s {name} names the wrong path"


def test_missing_docent_commands_stop_the_build_with_preflights_own_restore_line(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """Exit 14 and a relayed ``restore:``, never a barrier — no answer would install them.

    **It stops before the draft is asked for, and that is where the row sits for
    this reason.** The check can fail, so it may not stand behind a call: after
    one, its failure would throw away an answer the ledger never accounted for.
    In front of one, an incomplete install costs the run nothing but the stage.
    """
    distilled(repo)
    (repo / kb_util.CLAUDE_DIRNAME / kb_util.COMMANDS_DIRNAME / kb_util.DOCENT_COMMAND_FILENAMES[1]).unlink()
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A, preflight_stdout=PREFLIGHT_MISSING_DOCENT)
    script = phase_5_script()

    result = drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=script,
        fake=fake,
        stages=META_STAGES,
    )

    assert result.exit_code == baton.EXIT_ENVIRONMENT
    assert result.pair == "", "a missing install is an exit, not a barrier"
    assert any(kb_util.DOCENT_COMMAND_FILENAMES[1] in line for line in result.detail)
    assert any("restore:" in line for line in result.detail)
    assert script.calls == [], "the check stands in front of the call, so nothing was spent on this stop"
    assert [stage for stage in META_STAGES if stage in fake.recorded] == []


# ---------------------------------------------------------------------------
# What a resume re-spends: the boundary is the whole of the answer
#
# The seat is a test double, so the "expensive" row costs a scripted return here. The
# property under test is what the walk *asks for* a second time, which is a
# decision it takes from the ledger and from nothing else — and asking it of a
# real model would price the same assertion in hours.
# ---------------------------------------------------------------------------


def _overview_prose(repo: Path) -> Path:
    """The draft row's own declared artifact, under the scratch layout."""
    return repo / steps.SCRATCH_ROOT / steps.overview_prose(stage=META_STAGES[0])


def test_a_resume_past_a_recorded_boundary_does_not_buy_the_draft_again(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The boundary landed, so the stage is behind the build and its call is not re-issued.

    This is the guarantee the split exists for: the draft's answer is accounted
    for by a commit of its own the moment it is earned, so no later failure in
    the review cycle can send a resume back through it.
    """
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A)
    first = phase_5_script()

    drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=first, fake=fake, stages=(META_STAGES[0],))
    assert first.count("ov.docs") == 1
    assert META_STAGES[0] in fake.recorded

    second = phase_5_script()
    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=second, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert second.count("ov.docs") == 0, "a recorded stage is not re-walked, so its call is not re-issued"
    assert second.order == ["p5.review", "p5.fix"]


def test_a_resume_after_a_lost_boundary_re_runs_the_draft_over_the_answer_on_disk(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """No boundary accounts for it, so it is discarded — the artifact on disk included.

    The first invocation's record fails, which is the state a killed process
    leaves: the answer and the document assembled from it are on disk and the
    ledger says the stage never happened. The resume re-asks rather than adopting
    them, because an artifact no boundary accounts for cannot be told from one a
    dying process half-wrote.
    """
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A, refuses=(META_STAGES[0],))
    first = phase_5_script()

    stopped = drive(
        repo_root=repo, tmp_path=tmp_path, templates=templates, script=first, fake=fake, stages=(META_STAGES[0],)
    )

    assert stopped.exit_code == baton.EXIT_ENVIRONMENT
    assert META_STAGES[0] not in fake.recorded
    assert first.count("ov.docs") == 1
    prose = _overview_prose(repo)
    assert prose.is_file() and (kb_util.kb_root(repo) / kb_pipeline.OVERVIEW_DOC).is_file()

    second = phase_5_script()
    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=second, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert second.count("ov.docs") == 1, "the stage is unrecorded, so its work is re-run rather than read off disk"
    assert fake.recorded[-1] == META_STAGES[-1]


# ---------------------------------------------------------------------------
# The two-party contract between the loop's slots and the rows' templates
# ---------------------------------------------------------------------------


def test_the_slots_the_loop_supplies_compose_every_build_out_template(templates: Path) -> None:
    """Every row of these stages composes: the table's slots fill the template's, both ways."""
    build_out = ("phase-3a", "phase-5")
    composed = 0
    for step in steps.STEPS:
        if step.template is None or step.stage not in build_out:
            continue
        text = prompt_templates.render(
            step.template,
            slots={slot: f"<{slot}>" for slot in step.slots},
            directory=templates,
        )
        assert text.strip()
        composed += 1

    assert composed == len([step for step in steps.STEPS if step.template and step.stage in build_out])


def test_no_build_out_template_names_a_stage_id_or_the_record_verb(templates: Path) -> None:
    """The lint over the stand-ins, so a real template that broke it would be caught the same way."""
    assert (
        prompt_templates.lint(prompt_templates.template_paths(templates), prohibited=steps.TEMPLATE_PROHIBITIONS) == []
    )
