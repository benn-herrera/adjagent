"""Run-directory layout, the run lock, exit.json, and the log tee.

``exit.json`` is the run directory's own record of how the run ended, so its
field set is a contract: the terminal code, the barrier record path, and the
``--decide`` values that were never raised.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from kb_tools import inference, kb_lock
from kb_tools.kb_driver import runlog
from kb_tools.tests import _lock_holder

EXIT_JSON_FIELDS = {"exit_code", "barrier_record", "unconsumed_decisions"}


@pytest.fixture
def configured(tmp_path: Path) -> Iterator[runlog.RunPaths]:
    """A prepared run directory with logging attached, torn down after the test."""
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")
    runlog.configure(run_log=paths.run_log, level="INFO")
    yield paths
    driver_log = logging.getLogger("kb_driver")
    for handler in list(driver_log.handlers):
        driver_log.removeHandler(handler)
        handler.close()


def _records(run_log: Path) -> list[dict]:
    return [json.loads(line) for line in run_log.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_prepare_lays_out_the_run_directory(tmp_path: Path) -> None:
    paths = runlog.prepare(tmp_path / "kb-driver", "20260901T120000-42")

    assert paths.run_dir.is_dir()
    assert paths.briefs.is_dir() and paths.calls.is_dir() and paths.barriers.is_dir()
    # LATEST lives at the parent; everything else inside the run. The lock is
    # not a run-directory path at all — it belongs to the repo.
    assert paths.latest.parent == paths.parent
    assert not hasattr(paths, "lock")
    assert paths.run_log.parent == paths.run_dir
    assert paths.latest.read_text(encoding="utf-8").strip() == str(paths.run_dir)
    assert paths.run_pid.read_text(encoding="utf-8").strip().isdigit()


def test_prepare_refuses_to_reuse_a_run_directory(tmp_path: Path) -> None:
    parent = tmp_path / "kb-driver"
    runlog.prepare(parent, "run-1")
    with pytest.raises(runlog.BoundaryError, match="already exists"):
        runlog.prepare(parent, "run-1")


def test_run_id_is_sortable_and_unique_per_process() -> None:
    run_id = runlog.new_run_id()
    date, _, pid = run_id.partition("-")
    assert len(date) == len("20260901T120000")
    assert pid.isdigit()


# ---------------------------------------------------------------------------
# exit.json
# ---------------------------------------------------------------------------


def test_exit_json_carries_exactly_the_named_fields(tmp_path: Path) -> None:
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")
    record = paths.barriers / "spine-seed-runner-choice.md"

    written = runlog.write_exit_json(
        paths,
        exit_code=10,
        barrier_record=record,
        unconsumed_decisions=["spine-seed.runner-choice=just"],
    )
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert set(payload) == EXIT_JSON_FIELDS
    assert payload["exit_code"] == 10
    assert payload["barrier_record"] == str(record)
    assert payload["unconsumed_decisions"] == ["spine-seed.runner-choice=just"]


def test_exit_json_records_no_barrier_for_a_plain_exit(tmp_path: Path) -> None:
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")
    payload = json.loads(runlog.write_exit_json(paths, exit_code=0).read_text(encoding="utf-8"))

    assert set(payload) == EXIT_JSON_FIELDS
    assert payload["barrier_record"] is None
    assert payload["unconsumed_decisions"] == []


# ---------------------------------------------------------------------------
# cadence.jsonl
# ---------------------------------------------------------------------------

#: Synthetic ids: ``read_cadence`` takes this map as a parameter precisely
#: because ``runlog`` holds no stage knowledge, so these need to be registered
#: nowhere — only to carry the shapes the capture-name grammar must survive.
_STAGES = {"ex.first-step": "example-stage-one", "ex.second-step": "example-stage-two"}


def _capture(paths: runlog.RunPaths, *, seq: int, label: str, attempt: int, lines: list[str]) -> Path:
    """A capture written through the same grammar the caller composes with."""
    path = runlog.call_stream_path(paths, seq=seq, label=label, attempt=attempt)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def _result(*, duration_ms: int) -> str:
    """The line ``inference.call_chat`` closes each attempt of a capture with."""
    return json.dumps({"type": inference.REQUEST_RECORD, "duration_ms": duration_ms, "outcome": "ok"})


_USAGE = json.dumps({"choices": [], "usage": {"prompt_tokens": 40, "completion_tokens": 3}})


def test_cadence_carries_one_record_per_capture_with_its_stage(tmp_path: Path) -> None:
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")
    _capture(paths, seq=11, label="ex.first-step", attempt=1, lines=[_USAGE, _result(duration_ms=1200)])
    _capture(paths, seq=12, label="ex.second-step", attempt=1, lines=[_result(duration_ms=900)])

    records = runlog.read_cadence(paths, stages=_STAGES)

    assert records == [
        {
            "seq": 11,
            "step": "ex.first-step",
            "stage": "example-stage-one",
            "attempt": 1,
            "re_ask": False,
            "duration_ms": 1200,
            "prompt_tokens": 40,
            "completion_tokens": 3,
            "cached_tokens": None,
        },
        {
            "seq": 12,
            "step": "ex.second-step",
            "stage": "example-stage-two",
            "attempt": 1,
            "re_ask": False,
            "duration_ms": 900,
            "prompt_tokens": None,
            "completion_tokens": None,
            "cached_tokens": None,
        },
    ]


def test_a_re_ask_and_a_hyphenated_step_id_are_told_apart(tmp_path: Path) -> None:
    """``ex.first-step`` and ``-reask`` both contain the separator.

    A reader splitting on the first or last hyphen gets one of them wrong, so
    the capture-name pattern is anchored at both ends instead.
    """
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")
    _capture(paths, seq=11, label="ex.first-step-reask", attempt=2, lines=[_result(duration_ms=5)])

    (record,) = runlog.read_cadence(paths, stages=_STAGES)

    assert record["step"] == "ex.first-step"
    assert record["stage"] == "example-stage-one"
    assert record["re_ask"] is True
    assert record["attempt"] == 2


def test_a_capture_no_request_closed_contributes_nothing(tmp_path: Path) -> None:
    """Chunks with no closing record are a request that never finished: it has no duration to report."""
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")
    _capture(paths, seq=1, label="p3.distill", attempt=1, lines=[_USAGE])
    _capture(paths, seq=2, label="p3.distill", attempt=1, lines=["{ not json", _result(duration_ms=7)])

    records = runlog.read_cadence(paths, stages=_STAGES)

    assert [record["seq"] for record in records] == [2]


def test_an_unparsable_capture_name_is_logged_and_skipped_not_raised(configured: runlog.RunPaths) -> None:
    """An evidence pass on the way out of a finished run must not turn it into exit 15."""
    paths = configured
    (paths.calls / f"not-a-capture{runlog.CALL_STREAM_SUFFIX}").write_text(
        _result(duration_ms=1) + "\n", encoding="utf-8"
    )

    assert runlog.read_cadence(paths, stages=_STAGES) == []
    assert any("does not parse" in record["message"] for record in _records(paths.run_log))


def test_cadence_is_written_even_when_the_run_made_no_calls(tmp_path: Path) -> None:
    """ "Absent" must never have to be told apart from "the extraction did not run"."""
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")

    written = runlog.write_cadence(paths, stages=_STAGES)

    assert written == paths.cadence
    assert written.read_text(encoding="utf-8") == ""


def test_write_cadence_emits_one_json_object_per_line(tmp_path: Path) -> None:
    paths = runlog.prepare(tmp_path / "kb-driver", "run-1")
    _capture(paths, seq=1, label="p3.distill", attempt=1, lines=[_result(duration_ms=3)])

    lines = runlog.write_cadence(paths, stages=_STAGES).read_text(encoding="utf-8").splitlines()

    assert [json.loads(line)["step"] for line in lines] == ["p3.distill"]


# ---------------------------------------------------------------------------
# The lock (pre.lock)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(kb_lock.fcntl is None, reason="no advisory lock without fcntl (Windows)")
def test_a_writer_holding_the_write_lock_past_the_wait_refuses_the_run_and_frees_the_run_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(kb_lock, "WRITE_LOCK_WAIT", 0.05)

    with _lock_holder.held(repo):
        with pytest.raises(runlog.LockedError):
            with runlog.run_lock(repo, state_dir=tmp_path / "runs" / "run-1"):
                pytest.fail("a run must not start while a writer holds the KB")
        assert kb_lock.running_build(repo) is None
    assert not kb_lock.run_lock_path(repo).exists()


# ---------------------------------------------------------------------------
# Logging and the relay
# ---------------------------------------------------------------------------


def test_run_log_is_jsonl_and_carries_context(configured: runlog.RunPaths) -> None:
    runlog.logger("test").info("run started", extra={"context": {"run_id": "run-1"}})

    record = _records(configured.run_log)[0]
    assert record["message"] == "run started"
    assert record["level"] == "INFO"
    assert record["logger"] == "kb_driver.test"
    assert record["context"] == {"run_id": "run-1"}
    assert record["ts"]


def test_relay_writes_verbatim_bytes_once(configured: runlog.RunPaths, capsys: pytest.CaptureFixture[str]) -> None:
    block = "[relay] ---\n[relay] ASK THE USER:\n[relay]   none"
    runlog.relay(block)

    out = capsys.readouterr().out
    assert out == block + "\n"  # no level prefix, and no second copy from the console tee
    assert _records(configured.run_log)[0]["message"] == block


def test_require_raises_and_logs_on_violation(configured: runlog.RunPaths) -> None:
    runlog.require(True, "never raised")
    with pytest.raises(runlog.BoundaryError, match="spawn while one is live"):
        runlog.require(False, "second spawn while one is live", step="p0.survey")

    record = _records(configured.run_log)[0]
    assert record["level"] == "ERROR"
    assert record["context"] == {"step": "p0.survey"}
