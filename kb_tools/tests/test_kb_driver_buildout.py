"""The build-out stages: ``phase-3a`` and ``overview-drafted``.

The KB tree this driver walks over is no longer this driver's own output: the
distillation stages (``phase-0`` through ``phase-3``) that used to derive it
from a LaTeX survey are gone, replaced by a separately-authored pandoc front
end. What survives here is everything downstream of an already-built tree:

* **``phase-3a`` is a gate and a record, and nothing between them.** The
  build-time check runs behind refresh; green records the stage and red stops the
  run. No round is spent and no model is called, because each verifier
  compares one mechanically-produced artifact against another and a red one is
  a defect in a tool or in what was authored.
* **``overview-drafted`` writes the overview document.** Its boundary stands
  immediately behind its one model call, so nothing failable can throw the
  answer away.

The fixture's ``repo`` starts at the state the pandoc pipeline hands off: a KB
spine, with every domain's leaves already distilled (:func:`distilled`) by the
case that needs them — this driver writes no document tree of its own, and the
tree is the only thing it is told about the corpus. The ledger, refresh and the
build-time check are the seams
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
from kb_tools.inference import liaison_tools
from kb_tools.kb_driver import barriers, baton, config, ledger, prompt_templates, run, runlog, steps
from kb_tools.tests import _chat_stub
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

#: The meta-documentation stage, which writes the overview document.
META_STAGES = ("overview-drafted",)


# ---------------------------------------------------------------------------
# The templates a call composes against
# ---------------------------------------------------------------------------

_DOCS = steps.STEPS_BY_ID["ov.docs"]

_CORRECTION_SLOT, _CORRECTION = _DOCS.correction or ("", "")

TEMPLATES: Mapping[str, str] = {
    _DOCS.template or "": f"Excerpts:\n@!dyn.excerpts!@\nWrite the passage.@!{_CORRECTION_SLOT}!@\n",
    prompt_templates.FRAGMENTS[_DOCS.system or ""]: "Write prose from the excerpts.\n",
    prompt_templates.ALTERNATIVES[_CORRECTION]: "\nNot allowed:\n@!dyn.rejected-lines!@",
}


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

    ``verify`` is a sequence consumed one per build-time check, the last
    repeating, so a case states the gate's verdict without reaching into the
    stage that reads it. ``refresh`` is every refresh's outcome.
    """

    def __init__(
        self,
        *,
        recorded: Sequence[str] = (),
        verify: Sequence[ledger.Outcome] = (),
        preflight_stdout: str = PREFLIGHT,
        refuses: Sequence[str] = (),
        refresh: ledger.Outcome = ledger.Outcome(baton.EXIT_OK),
    ) -> None:
        self.recorded = list(recorded)
        #: Each stage's boundary-commit body, as the record row supplied it.
        self.notes: dict[str, str] = {}
        #: The gate steps run, in order: ``"refresh"`` and ``"verify"``.
        self.gate_steps: list[str] = []
        self._refresh = refresh
        self._repo_root: Path | None = None
        self._verify = list(verify)
        self._verifies = 0
        self._preflight_stdout = preflight_stdout
        #: Stages whose record fails once, and the way a killed process leaves
        #: one: the stage's work ran and no boundary accounts for it. A second
        #: invocation records it, because the kill was the process's and not the
        #: stage's.
        self._refuses = set(refuses)

    def _advance(
        self, *, stage: str, inputs: kb_pipeline.BuildInputs, note: str = "", no_inference: bool = False
    ) -> ledger.Outcome:
        del inputs
        if stage in self._refuses:
            self._refuses.discard(stage)
            return ledger.Outcome(baton.EXIT_ENVIRONMENT, detail=(f"the boundary commit for {stage} did not land",))
        self.recorded.append(stage)
        self.notes[stage] = note
        return ledger.Outcome(baton.EXIT_OK)

    def _run_refresh(self) -> ledger.Outcome:
        self.gate_steps.append("refresh")
        return self._refresh

    def _build_verify(self) -> ledger.Outcome:
        self.gate_steps.append("verify")
        if not self._verify:
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
            start_build=lambda *, charter, inputs: ledger.Outcome(baton.EXIT_OK),
            advance_step=self._advance,
            show_status=lambda *, relay: ledger.Outcome(baton.EXIT_OK, stdout=render_for(self.recorded)),
            refresh=self._run_refresh,
            build_verify=self._build_verify,
        )


def red_gate(*paths: str) -> ledger.Outcome:
    """A verify outcome whose report names the files it faulted.

    The detail carries the report lines as well as the op and the rc, which is
    what ``ledger._failure_detail`` puts there: a card whose ASK names only the
    rc leaves the operator re-running the stage by hand to learn what it said.
    """
    faults = [f"[verify] {kb_util.FAIL} {path}: broken link" for path in paths]
    report = "\n".join(["[verify] metadata gate red", *faults])
    head = "verify (links rc=1, metadata rc=0, citations rc=0) exited 1"
    return ledger.Outcome(baton.EXIT_GATE_RED, stdout=report + "\n", detail=(head, *faults))


GREEN = ledger.Outcome(baton.EXIT_OK, stdout="[verify] green\n")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _named_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A server named in the environment, so a walk reaching a call row passes the launch check.

    Nothing contacts it: :class:`Script`'s fake answers every call in its place.
    """
    _chat_stub.name_server(monkeypatch, port=9, key_dir=tmp_path)


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
    (root / kb_pipeline.scratch_relroot()).mkdir(parents=True)
    (root / kb_pipeline.CHARTER_RELPATH).write_text("# Build charter\n\nBoth volumes.\n", encoding="utf-8")

    index_dir = kb_util.index_dir(root)
    index_dir.mkdir(parents=True)
    # The derived artifacts a real `phase-3a` refresh leaves behind. This
    # suite's ledger is a fake and no refresh runs, so the files are laid down
    # here: `overview-drafted` reads its counts out of them, and an absent one is the
    # different failure of an index that was never rebuilt.
    for name in kb_index_lib.build_all_records(EMPTY_KB):
        (index_dir / f"{name}.jsonl").write_text("", encoding="utf-8")

    commands = root / kb_util.harness_dirname() / kb_util.COMMANDS_DIRNAME
    commands.mkdir(parents=True)
    for name in kb_util.DOCENT_COMMAND_FILENAMES:
        (commands / name).write_text(f"# {name}\n", encoding="utf-8")
    # `phase-3a`'s readiness stamp writes this, and this suite's ledger is a
    # fake so no stamp runs; an absent one here would be a fixture that
    # under-models the state the overview stage really meets.
    (kb_util.kb_root(root) / kb_pipeline.CONVENTIONS_DOC).write_text("# Conventions\n", encoding="utf-8")
    return root


@pytest.fixture
def templates(tmp_path: Path) -> Path:
    directory = tmp_path / "templates"
    directory.mkdir()
    (directory / prompt_templates.FRAGMENTS_DIRNAME).mkdir()
    for name, text in TEMPLATES.items():
        (directory / name).write_text(text, encoding="utf-8")
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
    no_inference: bool = False,
) -> run.Result:
    """One run over ``stages``."""
    body = ["[run]", f"sources = {json.dumps(list(SOURCES))}", f"no_inference = {json.dumps(no_inference)}"]
    for pair, answer in dict(decisions).items():
        stage, _, kind = pair.rpartition(".")
        body += ["", f'[barriers."{stage}"."{kind}"]', f'decision = "{answer}"']
    path = repo_root / "driver-run.toml"
    path.write_text("\n".join(body) + "\n", encoding="utf-8")

    paths = runlog.prepare(tmp_path / "runs", f"20260901T120000-{next(_RUN_SERIAL)}")
    return run.execute(
        config=config.load(path, admissible=barriers.ADMISSIBLE),
        paths=paths,
        transport=fake_model.FakeChat(script.scenario()),
        ops=ops if ops is not None else fake.ops(repo_root),
        repo_root=repo_root,
        stages=stages,
        prompt_templates_dir=templates,
    )


# ---------------------------------------------------------------------------
# The scenarios each call runs
# ---------------------------------------------------------------------------


#: What the model returns at ``ov.docs``: the passage, and nothing else. It
#: writes no file, because the stage assembles the document.
PASSAGE = "This corpus is three volumes of synthetic material. Start at the first."


def overview_script() -> Script:
    return Script({"ov.docs": PASSAGE})


def stamp_leaf(repo_root: Path, path: str) -> Path:
    """One leaf as the pandoc pipeline leaves it: a rendered body under a metadata block."""
    leaf = kb_util.kb_root(repo_root) / path
    leaf.parent.mkdir(parents=True, exist_ok=True)
    body = f"[Up: {path}](../index.md)\n\nA distilled leaf.\n"
    leaf.write_text(fake_model.stamped_leaf(body, claims=()), encoding="utf-8")
    return leaf


def distilled(repo_root: Path) -> None:
    """The tree on disk — entry point, each domain's index, every derived leaf — the state this driver assumes on entry.

    Nothing in this table writes it: distillation is the pandoc front end's
    job, run before this driver ever sees the repo. ``phase-3a`` onward reads
    the tree, and this is the tree it reads.
    """
    kb_root = kb_util.kb_root(repo_root)
    entries = "".join(f"- [{domain.title()}]({domain}/index.md)\n" for domain in DOMAINS)
    (kb_root / kb_index_lib.ENTRY_POINT_FILENAME).write_text(f"# Knowledge Base\n\n{entries}", encoding="utf-8")
    for domain in DOMAINS:
        for path in leaves_for(domain):
            stamp_leaf(repo_root, path)
        leaves = "".join(f"- [{Path(path).stem}]({Path(path).name})\n" for path in leaves_for(domain))
        (kb_root / domain / "index.md").write_text(
            f"[↑ Knowledge Base](../entry-point.md)\n\n# {domain.title()}\n\n{leaves}", encoding="utf-8"
        )


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

    assert fake.gate_steps == ["refresh", "verify"]
    assert fake.recorded[-1] == "phase-3a"


def test_a_red_gate_stops_the_run_and_records_nothing(repo: Path, tmp_path: Path, templates: Path) -> None:
    """No round, no model call, no cap: a failed verifier ends the walk where it stands.

    Each verifier compares one mechanically-produced artifact against another,
    so a red one is a defect in a tool or in what was authored — not work a
    model call could close, and not a barrier anyone can answer. The verifier's
    own report is in the run log; what reaches the caller is the step that
    failed and exit 11.
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
    assert script.calls == [], "no model is called over a mechanical gate"
    assert "phase-3a" not in fake.recorded

    # The card the relay actually prints, from the very context the run ended
    # with: the failing gate's own lines are in it, and nothing in it asks a
    # question or offers a `--decide` for a barrier that was never raised.
    card = baton.render(result.exit_code, result.context)
    assert f"[verify] {kb_util.FAIL} {faulted}: broken link" in card
    assert "(missing —" not in card
    assert "--decide" not in card


def test_a_red_refresh_stops_the_run_before_the_check_runs(repo: Path, tmp_path: Path, templates: Path) -> None:
    """Nothing downstream can read an index that was never rebuilt, so no check runs over it."""
    distilled(repo)
    red = ledger.Outcome(baton.EXIT_GATE_RED, detail=("refresh exited 1",))
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A_PREDECESSOR, refresh=red)

    result = drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=Script({}),
        fake=fake,
        stages=("phase-3a",),
    )

    assert result.exit_code == baton.EXIT_GATE_RED
    assert "refresh exited 1" in result.detail
    assert fake.gate_steps == ["refresh"]
    assert "phase-3a" not in fake.recorded


# ---------------------------------------------------------------------------
# overview-drafted: the meta-doc and the docent check
# ---------------------------------------------------------------------------


def test_the_stage_assembles_the_overview_document_and_records(repo: Path, tmp_path: Path, templates: Path) -> None:
    """The stage assembles; the model answers. One call, and no document composed by a model."""
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A)
    script = overview_script()

    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=script, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert script.order == ["ov.docs"]
    assert fake.recorded[-1] == "overview-drafted"
    # The one call is asked over the tree's excerpts, under the row's system prompt.
    (asked,) = script.calls
    assert kb_readme.compose_excerpts(kb_util.kb_root(repo)).text in asked.prompt
    assert asked.system_prompt == TEMPLATES[prompt_templates.FRAGMENTS[_DOCS.system or ""]]

    document = (kb_util.kb_root(repo) / kb_pipeline.OVERVIEW_DOC).read_text(encoding="utf-8")
    # The model's answer reaches the document verbatim, and nothing else it
    # returned does — every other word is the template's.
    assert PASSAGE in document
    assert not kb_readme.slots(document), "a slot reached the knowledge base unfilled"


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
        script=overview_script(),
        fake=fake,
        stages=("phase-3a", *META_STAGES),
    )

    assert [fake.notes[stage] for stage in ("phase-3a", *META_STAGES)] == ["", ""]


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
    (repo / kb_util.harness_dirname() / kb_util.COMMANDS_DIRNAME / kb_util.DOCENT_COMMAND_FILENAMES[1]).unlink()
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A, preflight_stdout=PREFLIGHT_MISSING_DOCENT)
    script = overview_script()

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
# The environment a model call needs, checked before the walk
# ---------------------------------------------------------------------------


def test_a_resume_with_a_model_call_left_refuses_an_environment_naming_no_server_before_any_stage(
    repo: Path, tmp_path: Path, templates: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit 14 naming the variable, and nothing walked — not even the mechanical stage in front of the call.

    A resume skips ``start``, which is why the check is not a ``start`` row.
    """
    distilled(repo)
    monkeypatch.delenv(liaison_tools.BASE_URL_ENV)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A_PREDECESSOR)
    script = overview_script()

    result = drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=script,
        fake=fake,
        stages=("phase-3a", *META_STAGES),
    )

    assert result.exit_code == baton.EXIT_ENVIRONMENT
    assert liaison_tools.BASE_URL_ENV in result.detail[0]
    assert any(line.startswith("restore:") for line in result.detail)
    assert fake.gate_steps == [] and script.calls == []
    assert fake.recorded == list(RECORDED_THROUGH_3A_PREDECESSOR)


@pytest.mark.parametrize(
    ("stages", "no_inference"),
    [
        pytest.param(("phase-3a", *META_STAGES), True, id="a-run-spending-none"),
        pytest.param(("phase-3a",), False, id="a-walk-with-no-model-call-left"),
    ],
)
def test_a_run_that_will_call_no_model_needs_no_server(
    repo: Path,
    tmp_path: Path,
    templates: Path,
    monkeypatch: pytest.MonkeyPatch,
    stages: tuple[str, ...],
    no_inference: bool,
) -> None:
    distilled(repo)
    monkeypatch.delenv(liaison_tools.BASE_URL_ENV)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A_PREDECESSOR)

    result = drive(
        repo_root=repo,
        tmp_path=tmp_path,
        templates=templates,
        script=Script({}),
        fake=fake,
        stages=stages,
        no_inference=no_inference,
    )

    assert result.exit_code == baton.EXIT_OK, result.detail
    assert fake.recorded[-1] == stages[-1]


# ---------------------------------------------------------------------------
# What a resume re-spends: the boundary is the whole of the answer
#
# The model is a test double, so the "expensive" row costs a scripted return here. The
# property under test is what the walk *asks for* a second time, which is a
# decision it takes from the ledger and from nothing else — and asking it of a
# real model would price the same assertion in hours.
# ---------------------------------------------------------------------------


def _overview_prose(repo: Path) -> Path:
    """The draft row's own declared artifact, under the scratch layout."""
    return repo / kb_pipeline.scratch_relroot() / steps.overview_prose(stage=META_STAGES[0])


def test_a_resume_past_a_recorded_boundary_does_not_buy_the_draft_again(
    repo: Path, tmp_path: Path, templates: Path
) -> None:
    """The boundary landed, so the stage is behind the build and its call is not re-issued.

    The draft's answer is accounted for by a commit of its own the moment it is
    earned, so no later invocation can send a resume back through it.
    """
    distilled(repo)
    fake = FakeLedger(recorded=RECORDED_THROUGH_3A)
    first = overview_script()

    drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=first, fake=fake, stages=META_STAGES)
    assert first.count("ov.docs") == 1
    assert META_STAGES[0] in fake.recorded

    second = overview_script()
    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=second, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert second.order == [], "a recorded stage is not re-walked, so its call is not re-issued"


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
    first = overview_script()

    stopped = drive(
        repo_root=repo, tmp_path=tmp_path, templates=templates, script=first, fake=fake, stages=(META_STAGES[0],)
    )

    assert stopped.exit_code == baton.EXIT_ENVIRONMENT
    assert META_STAGES[0] not in fake.recorded
    assert first.count("ov.docs") == 1
    prose = _overview_prose(repo)
    assert prose.is_file() and (kb_util.kb_root(repo) / kb_pipeline.OVERVIEW_DOC).is_file()

    second = overview_script()
    result = drive(repo_root=repo, tmp_path=tmp_path, templates=templates, script=second, fake=fake, stages=META_STAGES)

    assert result.exit_code == baton.EXIT_OK
    assert second.count("ov.docs") == 1, "the stage is unrecorded, so its work is re-run rather than read off disk"
    assert fake.recorded[-1] == META_STAGES[-1]


# ---------------------------------------------------------------------------
# The two-party contract between the loop's slots and the rows' templates
# ---------------------------------------------------------------------------


def test_the_slots_the_loop_supplies_compose_every_build_out_template(templates: Path) -> None:
    """Every row of these stages composes: the table's slots fill the template's, both ways."""
    build_out = ("phase-3a", "overview-drafted")
    composed = 0
    for step in steps.STEPS:
        if step.template is None or step.stage not in build_out:
            continue
        text = prompt_templates.render(
            step.template,
            slots={slot: f"<{slot}>" for slot in step.slots},
            alternatives={step.correction[0]: None} if step.correction else {},
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
