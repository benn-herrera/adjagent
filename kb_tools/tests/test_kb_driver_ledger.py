"""Tests for the ledger adapter, against a temp git repo and the real ``kb_util``.

Nothing here is mocked: every case builds a consuming repo with ``git init`` in
``tmp_path`` and drives the shipped ``python3 -m kb_tools.kb_util`` surface as a
subprocess, which is what the adapter does in a real run. The two properties
under test are the rc→exit mapping and the display relay: the tool's complete
stdout reaches the driver's stdout byte-for-byte, never trimmed and never
re-rendered.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from kb_tools import install_location, kb_pipeline, kb_util
from kb_tools.kb_driver import baton, ledger, runlog

_THIS_DIR = Path(__file__).resolve().parent
_PKG_PARENT = install_location.current().agents_dir

_CHARTER = "docs/charter.md"

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _repo(root: Path, *, docent: bool = True, files: dict[str, str] | None = None) -> Path:
    """A committed, preflight-clean consuming repo.

    Identity and signing are pinned in the repo's local config: the pipeline
    makes its own commits and must do so exactly as it would in a consumer's
    repo.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    for key, value in (
        ("user.email", "fixture@example.invalid"),
        ("user.name", "fixture"),
        ("commit.gpgsign", "false"),
    ):
        _git(root, "config", key, value)
    if docent:
        commands = root / ".claude" / "commands"
        commands.mkdir(parents=True)
        for name in kb_util.DOCENT_COMMAND_FILENAMES:
            (commands / name).write_text(f"# {name}\n", encoding="utf-8")
    (root / ".gitignore").write_text(".claude-temp/\n", encoding="utf-8")
    for relpath, content in (files or {}).items():
        target = root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    return root


#: A minimal conforming document tree, frontmatter and all — ``graph-init``'s
#: precondition. The verb initialises claim-graph metadata over documents, so a
#: fixture with none exercises only its refusal.
_DOCUMENT_TREE: dict[str, str] = {
    "kb-root/entry-point.md": (
        "<!-- kb-frontmatter\nkind: entry-point\n-->\n\n# Entry Point\n\n- [Volume](vol/index.md)\n"
    ),
    "kb-root/vol/index.md": (
        "[\u2191 Entry Point](../entry-point.md)\n\n<!-- kb-frontmatter\nkind: index\n-->\n\n"
        "# Volume\n\n- [Leaf](leaf.md)\n"
    ),
    "kb-root/vol/leaf.md": (
        '[\u2191 Volume](index.md)\n\n<!-- kb-frontmatter\nkind: leaf\nno-claim: "fixture leaf; it '
        'states no result"\n-->\n\n# Leaf\n\nBody text.\n'
    ),
}


def _tree_repo(root: Path, *, docent: bool = True, files: dict[str, str] | None = None) -> Path:
    """``_repo`` carrying the document tree ``graph-init`` requires."""
    return _repo(root, docent=docent, files={**_DOCUMENT_TREE, **(files or {})})


def _seeded_repo(root: Path, **files: str) -> Path:
    """A repo with the head's product on disk: the tree, a spine, and a charter.

    The ledger records against what a stage produced, so a repo standing in for
    a build in flight carries the document tree as well as the spine.
    """
    return _repo(root, files={**_DOCUMENT_TREE, "kb-root/.index/.keep": "", _CHARTER: "# Charter\n", **files})


def _kb_util_directly(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """The same invocation the adapter makes, run here — the byte-identity reference."""
    return subprocess.run(
        [sys.executable, "-m", "kb_tools.kb_util", *args],
        cwd=repo,
        env={**os.environ, "PYTHONPATH": str(_PKG_PARENT), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


# ---------------------------------------------------------------------------
# pre.preflight
# ---------------------------------------------------------------------------


def test_preflight_passes_on_a_clean_repo(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _repo(tmp_path / "consumer")

    outcome = ledger.preflight(repo)

    assert outcome.ok
    assert outcome.exit_code == baton.EXIT_OK
    assert "[preflight] PASS: environment ready." in capsys.readouterr().out


def test_preflight_failure_is_exit_14_carrying_its_restore_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # No docent commands: a FAIL item that names its own restoring action.
    repo = _repo(tmp_path / "consumer", docent=False)

    outcome = ledger.preflight(repo)

    assert outcome.exit_code == baton.EXIT_ENVIRONMENT
    out = capsys.readouterr().out
    assert "[preflight] FAIL docent-commands" in out
    assert "restore: run 'just install" in out
    assert outcome.detail[0] == f"kb_util {kb_util.OP_PREFLIGHT} exited 1"


# ---------------------------------------------------------------------------
# seed.graph-init
# ---------------------------------------------------------------------------


def test_graph_init_initialises_over_a_document_tree(tmp_path: Path) -> None:
    repo = _tree_repo(tmp_path / "consumer", files={"justfile": "default:\n    @true\n"})

    outcome = ledger.graph_init(repo)

    assert outcome.ok, outcome.detail
    assert (repo / "kb-root" / ".index" / "claims.jsonl").is_file()
    assert not (repo / "kb-root" / ".index" / "SCHEMA.md").exists()


def test_graph_init_with_no_document_tree_is_exit_14(tmp_path: Path) -> None:
    """rc 3: kb-root holds nothing to initialise over, and no barrier asks about it.

    The one corrective act is to run the document-graph front end over the
    sources — upstream work, not a question this run could put to anybody — so
    it halts on the environment rung rather than stopping for an answer.
    """
    repo = _repo(tmp_path / "consumer", files={"justfile": "default:\n    @true\n"})

    outcome = ledger.graph_init(repo)

    assert outcome.exit_code == baton.EXIT_ENVIRONMENT
    assert not outcome.ok


def test_graph_init_blocked_by_preflight_is_exit_14(tmp_path: Path) -> None:
    """rc 2: nothing seeded, and the fault is in the environment."""
    repo = _tree_repo(tmp_path / "consumer", docent=False, files={"justfile": "default:\n    @true\n"})

    outcome = ledger.graph_init(repo)

    assert outcome.exit_code == baton.EXIT_ENVIRONMENT
    assert not (repo / "kb-root" / ".index").exists()


def test_graph_init_with_a_red_verify_is_exit_11(tmp_path: Path) -> None:
    """rc 1: seeding ran and the gates came back red — a gate failure, not an environment one."""
    # A dead link under kb-root fails verify_md_links, which graph-init runs
    # before it reports success.
    repo = _tree_repo(
        tmp_path / "consumer",
        files={"justfile": "default:\n    @true\n", "kb-root/broken.md": "[missing](nowhere.md)\n"},
    )

    outcome = ledger.graph_init(repo)

    assert outcome.exit_code == baton.EXIT_GATE_RED
    assert outcome.detail[0] == f"kb_util {kb_util.OP_GRAPH_INIT} exited 1"


def test_graph_init_without_a_runner_file_passes_the_configured_runner_through(tmp_path: Path) -> None:
    repo = _tree_repo(tmp_path / "consumer")

    outcome = ledger.graph_init(repo, runner="just")

    assert outcome.ok, outcome.detail
    assert kb_util.install_line("just") in (repo / "justfile").read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# start.record and the stage records
# ---------------------------------------------------------------------------


def test_start_build_records_the_boundary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _seeded_repo(tmp_path / "consumer")

    outcome = ledger.record_start(repo, charter=_CHARTER)

    assert outcome.ok, outcome.detail
    assert "[x] start" in capsys.readouterr().out


def test_start_build_on_a_started_build_reads_as_done(tmp_path: Path) -> None:
    """rc 5: the boundary exists, which is what the row wanted (redo-safe)."""
    repo = _seeded_repo(tmp_path / "consumer")
    assert ledger.record_start(repo, charter=_CHARTER).ok

    again = ledger.record_start(repo, charter=_CHARTER)

    assert again.ok
    assert again.exit_code == baton.EXIT_OK


def test_out_of_order_record_is_exit_14(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """rc 4: the ledger refuses; the render that comes back carries the real position."""
    repo = _seeded_repo(tmp_path / "consumer")

    outcome = ledger.record_stage(repo, stage="overview-drafted")

    assert outcome.exit_code == baton.EXIT_ENVIRONMENT
    assert "[ ] overview-drafted" in capsys.readouterr().out
    assert any("predecessors are unrecorded" in line for line in outcome.detail)


def test_recording_a_stage_is_inert_the_second_time(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path / "consumer")
    subprocess.run(
        [sys.executable, "-m", "kb_tools.refresh_kb_metadata"],
        cwd=repo,
        env={**os.environ, "PYTHONPATH": str(_PKG_PARENT), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        check=True,
    )
    # The stage after `start`, read off the vocabulary: what is under test is
    # that a second record of one stage is inert, not which stage it was.
    after_start = kb_pipeline.STAGE_IDS[1]
    assert ledger.record_start(repo, charter=_CHARTER).ok
    assert ledger.record_stage(repo, stage=after_start).ok

    again = ledger.record_stage(repo, stage=after_start)

    assert again.ok
    assert "already recorded" in again.stdout


def test_an_unknown_stage_id_is_refused_as_an_environment_fault(tmp_path: Path) -> None:
    """A usage error from the tool (rc 2) is mapped, not left to the fallback baton."""
    repo = _seeded_repo(tmp_path / "consumer")

    outcome = ledger.record_stage(repo, stage="phase-99")

    assert outcome.exit_code == baton.EXIT_ENVIRONMENT


def test_record_start_without_a_charter_records_the_boundary_and_names_the_absence(tmp_path: Path) -> None:
    """A charter is optional, so the boundary lands — and its body says it was given none.

    Not an empty body. That is equally what a caller which dropped the argument
    leaves behind, and the boundary commit is the only durable place the two can
    be told apart, so the absence is stated rather than left to be inferred.
    """
    repo = _seeded_repo(tmp_path / "consumer")

    outcome = ledger.record_start(repo, charter="")

    assert outcome.ok, outcome.detail
    subject_and_body = subprocess.run(
        ["git", "log", "-1", "--format=%B"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert "start" in subject_and_body
    assert kb_pipeline.NO_CHARTER_BODY in subject_and_body


# ---------------------------------------------------------------------------
# The display relay
# ---------------------------------------------------------------------------


def test_relayed_stdout_is_byte_identical_to_the_tools_own(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The complete verbatim stdout of show-status, across the process boundary."""
    repo = _seeded_repo(tmp_path / "consumer")
    assert ledger.record_start(repo, charter=_CHARTER).ok
    capsys.readouterr()
    reference = _kb_util_directly(repo, kb_util.OP_SHOW_STATUS)
    assert reference.returncode == 0, reference.stderr

    outcome = ledger.show_status(repo)

    relayed = capsys.readouterr().out
    assert outcome.ok
    assert relayed == reference.stdout
    assert outcome.stdout == reference.stdout


def test_a_failing_op_still_relays_its_whole_render(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The refusal render is display too: it carries the checklist and the units."""
    repo = _seeded_repo(tmp_path / "consumer")

    outcome = ledger.record_stage(repo, stage="overview-drafted")

    assert capsys.readouterr().out == outcome.stdout
    assert outcome.stdout.endswith("\n")
    assert "[kb-build] status:" in outcome.stdout


def test_relay_can_be_suppressed_for_a_read_that_is_not_a_transition(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _seeded_repo(tmp_path / "consumer")

    outcome = ledger.show_status(repo, relay=False)

    assert capsys.readouterr().out == ""
    assert "[kb-build] status:" in outcome.stdout


# ---------------------------------------------------------------------------
# The gate steps: refresh and the build-time check, in-process
# ---------------------------------------------------------------------------

#: The fixture tree's leaf with one dead link in its body: red for links alone.
_BROKEN_LINK = {"kb-root/vol/leaf.md": _DOCUMENT_TREE["kb-root/vol/leaf.md"] + "\n[gone](nowhere.md)\n"}


@pytest.mark.parametrize(
    ("files", "expected"),
    [({}, baton.EXIT_OK), (_BROKEN_LINK, baton.EXIT_GATE_RED)],
    ids=["green", "red"],
)
def test_a_gate_report_is_kept_out_of_the_relay_without_changing_the_rc_mapping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], files: dict[str, str], expected: int
) -> None:
    """The paste instruction is 'everything above this block'; a gate dump must not be in it."""
    repo = _seeded_repo(tmp_path / "consumer", **files)

    assert ledger.refresh(repo).ok
    outcome = ledger.build_verify(repo)

    assert outcome.exit_code == expected
    assert outcome.stdout.strip() != ""
    assert capsys.readouterr().out == ""


def test_a_red_build_verify_names_every_verifiers_code_and_the_failing_line(tmp_path: Path) -> None:
    repo = _seeded_repo(tmp_path / "consumer", **_BROKEN_LINK)
    assert ledger.refresh(repo).ok

    outcome = ledger.build_verify(repo)

    assert outcome.exit_code == baton.EXIT_GATE_RED
    assert outcome.detail[0].startswith("verify (links rc=1, metadata rc=0, citations rc=0) exited 1"), outcome.detail
    assert any("nowhere.md" in line for line in outcome.detail), outcome.detail


def test_a_refresh_that_cannot_run_is_a_red_gate_naming_the_refresh(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "consumer")

    outcome = ledger.refresh(repo)

    assert outcome.exit_code == baton.EXIT_GATE_RED
    assert outcome.detail[0] == "refresh exited 2"


def test_the_gate_steps_spawn_no_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Refresh and the build-time check are imported and called, never reached through a runner."""
    repo = _seeded_repo(tmp_path / "consumer")

    def no_spawn(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a gate step spawned a process: {args}")

    monkeypatch.setattr(subprocess, "run", no_spawn)
    monkeypatch.setattr(subprocess, "Popen", no_spawn)

    assert ledger.refresh(repo).ok
    assert ledger.build_verify(repo).ok


# ---------------------------------------------------------------------------
# The failing op's own diagnostic
# ---------------------------------------------------------------------------
#
# A stage says what is wrong on whichever stream it chose: `kb_claimgraph`
# prints its FAIL findings on stdout and exits 1, an unhandled exception in
# `kb_docgraph` arrives as a traceback on stderr. A detail built from stderr
# alone relayed `exited 1` and nothing else for every stage of the first kind,
# and each of those failures had to be diagnosed by re-running the stage by
# hand outside the driver.

_STDOUT_FAULT = f"[verify] {kb_util.FAIL} point-2 index.md sits at an index path but lists no children"
_STDERR_FAULT = "ValueError: the document tree does not conform"


@pytest.mark.parametrize(
    ("out", "err", "expected"),
    [
        (_STDOUT_FAULT, "", (_STDOUT_FAULT,)),
        ("", _STDERR_FAULT, (_STDERR_FAULT,)),
        (_STDOUT_FAULT, _STDERR_FAULT, (_STDOUT_FAULT, _STDERR_FAULT)),
    ],
    ids=["stdout", "stderr", "both"],
)
def test_a_failing_ops_report_reaches_the_detail_whichever_stream_carried_it(
    out: str, err: str, expected: tuple[str, ...]
) -> None:
    outcome = ledger._gate_step("verify", returncode=1, stdout=out, stderr=err)

    assert outcome.exit_code == baton.EXIT_GATE_RED
    assert outcome.detail[0] == "verify exited 1"
    for line in expected:
        assert line in outcome.detail, outcome.detail


def _completed(*, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["kb-verify"], returncode=1, stdout=stdout, stderr=stderr)


def test_a_long_traceback_is_bounded_and_keeps_the_line_that_names_the_failure() -> None:
    """The tail is what survives a traceback: the exception's own message is its last line."""
    frames = [f'  File "kb_docgraph/build.py", line {n}, in build' for n in range(500)]
    detail = ledger._failure_detail("kb_docgraph", _completed(stderr="\n".join(["Traceback:", *frames, _STDERR_FAULT])))

    assert detail[0] == "kb_docgraph exited 1"
    assert detail[-1] == _STDERR_FAULT
    assert len(detail) <= ledger.FAILURE_DETAIL_LINES + 3, detail
    assert any("line(s) of the report omitted" in line for line in detail), "a truncation nobody announced"


def test_a_long_report_keeps_its_fail_lines_wherever_they_sit_in_it() -> None:
    """The bound may cost context; it may not cost the finding.

    A `FAIL` near the head of a long report is exactly what a tail-only bound
    would drop, and it is the one line the operator has to see.
    """
    report = [f"[verify] {kb_util.FACT} scanned {n}" for n in range(300)]
    report[2] = _STDOUT_FAULT

    detail = ledger._failure_detail("kb-verify", _completed(stdout="\n".join(report)))

    assert _STDOUT_FAULT in detail
    assert detail[-1] == report[-1]
    assert len(detail) <= ledger.FAILURE_DETAIL_LINES + 3, detail


def test_a_short_report_is_carried_whole_and_says_nothing_about_truncation() -> None:
    detail = ledger._failure_detail("kb_claimgraph --pass 1", _completed(stdout=f"first\n{_STDOUT_FAULT}"))

    assert detail == ("kb_claimgraph --pass 1 exited 1", "first", _STDOUT_FAULT)
