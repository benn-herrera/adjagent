"""Call policy: retry, the one re-ask, the environment refusal, and the persistence route.

Every case drives the real ``call.Caller``. Most stand ``_fake_model.FakeChat``
in for its transport, because what they are about is the policy over a reply;
the cases about the transport itself — the capture a request leaves and the
environment it refuses — run the real ``inference.call_chat``, against the
loopback stub where a request is made. Two things are asserted about writes:
that the route wrote exactly where its step row declares, and that nothing else
under the repository changed.

The step rows are the real ones from ``steps.py`` — what the run loop will pass
— while the templates are local stand-ins named for the real ones, because the
shipped templates are the prompt engineer's and their prose is not what this
suite is about.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from kb_tools import inference, kb_pipeline
from kb_tools.kb_driver import baton, call, config, prompt_templates, runlog, steps
from kb_tools.tests import _chat_stub
from kb_tools.tests import _fake_model as fake_model
from kb_tools.tests._chat_stub import StubServer, served_fixture, server_fixture  # noqa: F401 — fixtures

DOCS = steps.STEPS_BY_ID["ov.docs"]

# --- the templates a call composes against ----------------------------------

SYSTEM_PROMPT = "Write prose from the excerpts.\n"

CORRECTION_SLOT, CORRECTION = DOCS.correction or ("", "")

TEMPLATES: Mapping[str, str] = {
    DOCS.template or "": f"Excerpts:\n@!dyn.excerpts!@\nWrite the passage.@!{CORRECTION_SLOT}!@\n",
    prompt_templates.FRAGMENTS[DOCS.system or ""]: SYSTEM_PROMPT,
    prompt_templates.ALTERNATIVES[CORRECTION]: f"\nNot allowed:\n@!dyn.{call.REJECTED_LINES_SLOT}!@",
}

DOCS_SLOTS: Mapping[str, str] = {"excerpts": "==> A Volume <==\nIt argues one thing."}

#: The first ask's brief over :data:`TEMPLATES`, byte for byte.
FIRST_BRIEF = "Excerpts:\n==> A Volume <==\nIt argues one thing.\nWrite the passage.\n"

PASSAGE_TEXT = "This corpus argues one thing, and the place to start is its introduction.\n"


# --- harness ----------------------------------------------------------------


@dataclass(frozen=True)
class Harness:
    """One caller, plus the evidence a test needs to look at afterwards."""

    caller: call.Caller
    chat: fake_model.FakeChat
    sleeps: list[float]
    paths: runlog.RunPaths
    root: Path

    def brief(self, seq: int, label: str) -> Path:
        return self.paths.briefs / f"{seq:03d}-{label}.md"

    def capture(self, seq: int, label: str, attempt: int) -> Path:
        return runlog.call_stream_path(self.paths, seq=seq, label=label, attempt=attempt)


def _config(*, attempts: int = 3, silence: int = 30) -> config.DriverConfig:
    return config.DriverConfig(
        path=Path("driver-run.toml"),
        invocation="--config driver-run.toml",
        run=config.RunSection(
            sources=("AcmeWidgets.tex",),
            charter_file=Path(kb_pipeline.CHARTER_RELPATH),
            runner=None,
        ),
        timeouts=config.TimeoutSection(silence_seconds=silence),
        retry=config.RetrySection(transport_attempts=attempts, backoff_seconds=(5, 30)),
        log=config.LogSection(level="INFO", run_dir=Path(".claude-temp/kb-driver")),
        decisions={},
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo root with the scratch layout root and a kb-root the driver may never write."""
    root = tmp_path / "repo"
    (root / kb_pipeline.scratch_relroot()).mkdir(parents=True)
    (root / "kb-root").mkdir()
    return root


@pytest.fixture
def build(tmp_path: Path, repo: Path) -> Callable[..., Harness]:
    """A caller over the local template set and a laid-out run directory."""
    templates = tmp_path / "templates"
    (templates / prompt_templates.FRAGMENTS_DIRNAME).mkdir(parents=True)
    for name, text in TEMPLATES.items():
        (templates / name).write_text(text, encoding="utf-8")
    paths = runlog.prepare(tmp_path / "kb-driver", "run-0001")

    def _build(scenario: fake_model.Scenario, *, real_transport: bool = False, **overrides: int) -> Harness:
        sleeps: list[float] = []
        chat = fake_model.FakeChat(scenario)
        caller = call.Caller(
            config=_config(**overrides),
            repo_root=repo,
            paths=paths,
            prompt_templates_dir=templates,
            sleep=sleeps.append,
            **({} if real_transport else {"transport": chat}),
        )
        return Harness(caller=caller, chat=chat, sleeps=sleeps, paths=paths, root=tmp_path)

    return _build


def _snapshot(root: Path) -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in root.rglob("*") if path.is_file()}


def _changed(before: Mapping[Path, str], after: Mapping[Path, str]) -> set[Path]:
    return {path for path, text in after.items() if before.get(path) != text}


def _passage(repo: Path) -> Path:
    """``ov.docs``' one declared artifact: the prose answer, under the scratch layout."""
    return repo / kb_pipeline.scratch_relroot() / steps.overview_prose(stage=DOCS.stage)


def _docs(repo: Path, *, seq: int = 3, target: Path | None = None) -> call.CallRequest:
    return call.CallRequest(step=DOCS, seq=seq, slots=DOCS_SLOTS, outputs=(target or _passage(repo),))


# ---------------------------------------------------------------------------
# The persistence route, and the guarantee nothing else under the repo changes
# ---------------------------------------------------------------------------


def test_the_driver_persists_the_returned_text_and_writes_nowhere_else(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean(PASSAGE_TEXT))
    passage = _passage(repo)
    before = _snapshot(harness.root)

    outcome = harness.caller.execute(_docs(repo))

    assert outcome.ok
    assert outcome.written == (passage,)
    assert passage.read_text(encoding="utf-8") == PASSAGE_TEXT
    # The artifact and the composed brief — and nothing else, anywhere. **This
    # is where "the driver process never writes under kb-root/" is asserted**:
    # the changed set is stated exhaustively rather than as a negative about one
    # directory, so a write anywhere it does not name fails here.
    assert _changed(before, _snapshot(harness.root)) == {passage, harness.brief(3, "ov.docs")}


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


def test_a_dying_persist_leaves_no_partial_artifact_under_the_final_name(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean(PASSAGE_TEXT))
    target = _passage(repo)

    with pytest.raises(UnicodeEncodeError):
        harness.caller._persist(_docs(repo, target=target), text=UNWRITABLE_TEXT)

    assert not target.exists(), "a write that died left a file under the name a resume reads as finished work"


def test_a_dying_persist_leaves_the_artifact_already_there_untouched(repo: Path, build: Callable[..., Harness]) -> None:
    """The target is the previous file or the whole new one, and there is no third state."""
    harness = build(fake_model.clean(PASSAGE_TEXT))
    target = _passage(repo)
    harness.caller._persist(_docs(repo, target=target), text=PASSAGE_TEXT)

    with pytest.raises(UnicodeEncodeError):
        harness.caller._persist(_docs(repo, target=target), text=UNWRITABLE_TEXT)

    assert target.read_text(encoding="utf-8") == PASSAGE_TEXT


def test_a_driver_persist_target_outside_the_scratch_root_is_a_boundary_error(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean(PASSAGE_TEXT))
    stray = repo / "kb-root" / "overview-prose.md"

    with pytest.raises(runlog.BoundaryError, match="scratch layout root"):
        harness.caller.execute(_docs(repo, target=stray))
    assert not stray.exists()


def test_an_empty_return_never_becomes_an_artifact(repo: Path, build: Callable[..., Harness]) -> None:
    harness = build(fake_model.clean("   \n"))
    target = _passage(repo)

    outcome = harness.caller.execute(_docs(repo, seq=20, target=target))

    assert outcome.exit_code == baton.EXIT_CONTRACT
    assert not target.exists()


# ---------------------------------------------------------------------------
# Composition: the system prompt and the brief
# ---------------------------------------------------------------------------


def test_a_call_carries_its_rows_fragment_as_the_system_prompt_and_its_brief_as_the_prompt(
    repo: Path, build: Callable[..., Harness]
) -> None:
    harness = build(fake_model.clean(PASSAGE_TEXT))

    assert harness.caller.execute(_docs(repo, seq=1)).ok

    (seen,) = harness.chat.seen
    assert seen.system_prompt == SYSTEM_PROMPT
    assert seen.prompt == harness.brief(1, "ov.docs").read_text(encoding="utf-8")


def test_a_step_that_makes_no_call_is_a_boundary_error(build: Callable[..., Harness]) -> None:
    harness = build(fake_model.clean("ok"))

    with pytest.raises(runlog.BoundaryError, match="makes no call"):
        harness.caller.execute(call.CallRequest(step=steps.STEPS_BY_ID["p3a.record"], seq=4))


# ---------------------------------------------------------------------------
# Transport retry, and the environment refusal
# ---------------------------------------------------------------------------


def test_a_request_that_did_not_complete_is_retried_until_one_does(repo: Path, build: Callable[..., Harness]) -> None:
    harness = build(fake_model.sequence(fake_model.transport_die(), fake_model.transport_die(), fake_model.clean()))

    outcome = harness.caller.execute(_docs(repo))

    assert outcome.ok
    assert outcome.attempts == 3
    assert harness.chat.calls == 3
    assert harness.sleeps == [5.0, 30.0]
    # Every attempt is handed a capture of its own.
    assert [seen.capture_path for seen in harness.chat.seen] == [
        harness.capture(3, "ov.docs", attempt) for attempt in (1, 2, 3)
    ]


def test_exhausted_transport_retries_exit_12(repo: Path, build: Callable[..., Harness]) -> None:
    harness = build(fake_model.transport_die())
    passage = _passage(repo)

    outcome = harness.caller.execute(_docs(repo))

    assert outcome.exit_code == baton.EXIT_TRANSPORT
    assert harness.chat.calls == 3
    assert outcome.detail[0] == f"ov.docs: {inference.Outcome.TRANSPORT_FAILURE.value} after 3 attempt(s)"
    assert not passage.exists()
    # A transport death is not a contract failure: the step is never re-asked.
    assert not harness.brief(3, f"ov.docs{call.REASK_SUFFIX}").exists()


def test_an_environment_naming_no_server_is_exit_14_and_never_retried(
    repo: Path, build: Callable[..., Harness]
) -> None:
    """The real transport, with no server named: the refusal is the environment's, not the driver's."""
    harness = build(fake_model.clean(PASSAGE_TEXT), real_transport=True)

    outcome = harness.caller.execute(_docs(repo))

    assert outcome.exit_code == baton.EXIT_ENVIRONMENT
    assert harness.sleeps == [], "the same refusal three times is not a retry"
    assert inference.liaison_tools.BASE_URL_ENV in outcome.detail[0]
    assert outcome.detail[1].startswith("restore:")
    assert not _passage(repo).exists()


def test_a_request_to_the_server_leaves_a_capture_the_cadence_reads(
    repo: Path, build: Callable[..., Harness], served: StubServer
) -> None:
    """One tool-less request per attempt, and its capture closed by the transport's own record."""
    served.body = _chat_stub.sse(
        _chat_stub.chunk({"content": PASSAGE_TEXT}),
        _chat_stub.chunk({}, "stop"),
        {"object": "chat.completion.chunk", "choices": [], "usage": _chat_stub.USAGE},
    )
    harness = build(fake_model.clean(), real_transport=True)

    outcome = harness.caller.execute(_docs(repo))

    assert outcome.ok
    assert _passage(repo).read_text(encoding="utf-8") == PASSAGE_TEXT
    (request,) = served.requests
    assert "tools" not in request["body"]
    assert [message["role"] for message in request["body"]["messages"]] == ["system", "user"]
    closing = json.loads(harness.capture(3, "ov.docs", 1).read_text(encoding="utf-8").splitlines()[-1])
    assert closing["type"] == inference.REQUEST_RECORD

    (record,) = runlog.read_cadence(harness.paths, stages={DOCS.id: DOCS.stage})
    assert (record["step"], record["stage"], record["prompt_tokens"]) == (
        DOCS.id,
        DOCS.stage,
        _chat_stub.USAGE["prompt_tokens"],
    )


# ---------------------------------------------------------------------------
# Contract validation and the one re-ask (exit 17)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("# A Heading", id="heading"),
        pytest.param("- a list item", id="list-item"),
        pytest.param("2. a numbered item", id="numbered-item"),
        pytest.param("| a | table |", id="table-row"),
        pytest.param("```", id="code-fence"),
        pytest.param("Start at [the overview](overview.md).", id="link"),
        pytest.param("Start at entry-point.md first.", id="md-path"),
    ],
)
def test_a_reply_holding_a_construct_a_passage_may_not_is_re_asked_quoting_it(
    repo: Path, build: Callable[..., Harness], line: str
) -> None:
    reply = f"This corpus argues one thing.\n{line}\n"
    harness = build(fake_model.sequence(fake_model.clean(reply), fake_model.clean(PASSAGE_TEXT)))

    outcome = harness.caller.execute(_docs(repo, seq=5))

    assert outcome.ok
    assert _passage(repo).read_text(encoding="utf-8") == PASSAGE_TEXT, "only the answer that stood is the artifact"
    assert harness.brief(5, "ov.docs").read_text(encoding="utf-8") == FIRST_BRIEF
    re_ask = harness.brief(5, f"ov.docs{call.REASK_SUFFIX}").read_text(encoding="utf-8")
    assert re_ask == f"Excerpts:\n==> A Volume <==\nIt argues one thing.\nWrite the passage.\nNot allowed:\n{line}\n"


def test_prose_naming_the_corpus_own_parts_and_figures_is_a_passage(repo: Path, build: Callable[..., Harness]) -> None:
    """Counts and part numbers are the corpus's facts, so nothing structural refuses them."""
    prose = "Part 4 derives three mechanisms; start with *The Lifetime*, then read its 2 companions.\n"
    harness = build(fake_model.clean(prose))

    assert harness.caller.execute(_docs(repo)).ok
    assert harness.chat.calls == 1


def test_an_empty_reply_is_re_asked_with_the_unchanged_brief(repo: Path, build: Callable[..., Harness]) -> None:
    """No line was rejected, so the correction has nothing to quote and the same question is asked again."""
    harness = build(fake_model.sequence(fake_model.clean("   \n"), fake_model.clean(PASSAGE_TEXT)))
    passage = _passage(repo)

    outcome = harness.caller.execute(_docs(repo, seq=5))

    assert outcome.ok
    assert harness.chat.calls == 2
    assert passage.read_text(encoding="utf-8") == PASSAGE_TEXT
    assert harness.brief(5, f"ov.docs{call.REASK_SUFFIX}").read_text(encoding="utf-8") == FIRST_BRIEF


@pytest.mark.parametrize(
    "reply", [pytest.param("   \n", id="empty"), pytest.param("# Overview\nProse.\n", id="structured")]
)
def test_a_second_contract_failure_exits_17_naming_the_step_and_the_complaint(
    repo: Path, build: Callable[..., Harness], reply: str
) -> None:
    harness = build(fake_model.clean(reply))
    passage = _passage(repo)

    outcome = harness.caller.execute(_docs(repo, seq=5))

    assert outcome.exit_code == baton.EXIT_CONTRACT
    assert harness.chat.calls == 2  # one ask, one re-ask, and no third
    assert outcome.detail[0].startswith("ov.docs:")
    assert len(outcome.detail) > 1
    assert not passage.exists()
