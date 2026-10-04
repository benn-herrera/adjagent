"""The chat call: what it refuses, the request it sends, how it ends, and what its capture says.

Every call runs against the loopback stub in ``_chat_stub``; the environment a
test reads is set per test, after ``conftest.no_reader_server`` cleared it.
"""

import json
import socket
from pathlib import Path

import pytest

from kb_tools import inference
from kb_tools.inference import liaison_tools
from kb_tools.tests._chat_stub import (  # noqa: F401 - fixtures
    SERVED_MODEL,
    TOKEN,
    USAGE,
    StubServer,
    chunk,
    served_fixture,
    server_fixture,
    sse,
)


def _call(
    prompt: str = "q\n", *, system_prompt: str = "s", capture_path: Path | None = None
) -> tuple[str, inference.Outcome]:
    return inference.call_chat(system_prompt=system_prompt, prompt=prompt, timeout_seconds=5, capture_path=capture_path)


# --- what is refused before any request ---------------------------------------------


@pytest.mark.parametrize(("system_prompt", "prompt"), [("", "q"), (" \n", "q"), ("s", ""), ("s", "\n\t")])
def test_an_empty_system_prompt_or_prompt_is_refused_before_any_request(
    system_prompt: str, prompt: str, served: StubServer
) -> None:
    with pytest.raises(ValueError, match="empty"):
        _call(prompt, system_prompt=system_prompt)

    assert served.requests == []


def test_with_no_api_base_url_the_check_and_the_call_refuse_naming_it(server: StubServer) -> None:
    with pytest.raises(ValueError, match=liaison_tools.BASE_URL_ENV):
        inference.check_environment()
    with pytest.raises(ValueError, match=liaison_tools.BASE_URL_ENV):
        _call()

    assert server.requests == []


@pytest.mark.parametrize("unset", [liaison_tools.MODEL_ENV, liaison_tools.KEY_FILE_ENV])
def test_a_server_with_no_model_or_no_key_file_is_refused_by_name_before_any_request(
    unset: str, served: StubServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(unset)

    with pytest.raises(ValueError, match=unset):
        inference.check_environment()
    with pytest.raises(ValueError, match=unset):
        _call()

    assert served.requests == []


@pytest.mark.parametrize(
    ("content", "complaint"),
    [(None, "not found"), ("", "invalid format"), ("two words", "invalid format")],
    ids=["missing", "empty", "internal-whitespace"],
)
def test_a_key_file_post_openai_would_refuse_is_refused_without_echoing_it(
    content: str | None, complaint: str, tmp_path: Path, served: StubServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    key_file = tmp_path / "bad-key.txt"
    if content is not None:
        key_file.write_text(content, encoding="utf-8")
    monkeypatch.setenv(liaison_tools.KEY_FILE_ENV, str(key_file))

    with pytest.raises(ValueError, match=complaint) as refused:
        _call()

    assert "words" not in str(refused.value)
    assert served.requests == []


def test_a_base_url_that_is_not_a_url_is_refused_without_echoing_it(
    served: StubServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(liaison_tools.BASE_URL_ENV, "not-a-url-secretish")

    with pytest.raises(ValueError) as refused:
        _call()

    assert "secretish" not in str(refused.value)
    assert served.requests == []


def test_http_to_another_host_needs_allow_http_set_to_one(served: StubServer, monkeypatch: pytest.MonkeyPatch) -> None:
    # ``.invalid`` never resolves, so an accepted URL fails at the connect and nothing is sent anywhere.
    monkeypatch.setenv(liaison_tools.BASE_URL_ENV, "http://reader.invalid/v1")
    for refused in (None, "true", "0"):
        if refused is not None:
            monkeypatch.setenv(liaison_tools.ALLOW_HTTP_ENV, refused)
        with pytest.raises(ValueError, match=liaison_tools.ALLOW_HTTP_ENV):
            _call()

    monkeypatch.setenv(liaison_tools.ALLOW_HTTP_ENV, "1")

    assert _call() == ("", inference.Outcome.TRANSPORT_FAILURE)


def test_the_checked_environment_never_shows_the_key(served: StubServer) -> None:
    checked = inference.check_environment()

    assert (checked.model, checked.token) == (SERVED_MODEL, TOKEN)
    assert TOKEN not in repr(checked)


# --- the request, and how a call ends -----------------------------------------------


def test_the_request_is_one_tool_less_call_on_the_envs_model_with_thinking_off(served: StubServer) -> None:
    assert _call("judge this\n", system_prompt="be a reader") == ("A", inference.Outcome.OK)

    (request,) = served.requests
    body = request["body"]
    assert request["path"] == "/v1/chat/completions", "API_BASE_URL already carries /v1"
    assert request["authorization"] == f"Bearer {TOKEN}", "the key file's content, trimmed"
    assert body["model"] == SERVED_MODEL
    assert body["messages"] == [
        {"role": "system", "content": "be a reader"},
        {"role": "user", "content": "judge this\n"},
    ]
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["temperature"] == 0
    assert "tools" not in body
    assert body["stream_options"] == {"include_usage": True}


def test_the_text_is_what_the_turn_wrote_beside_an_injected_tool_call(served: StubServer) -> None:
    call = {"index": 0, "id": "c1", "function": {"name": "Read", "arguments": "{}"}}
    served.body = sse(chunk({"content": "B"}), chunk({"tool_calls": [call]}), chunk({}, "tool_calls"))

    assert _call() == ("B", inference.Outcome.OK)


def test_a_cut_off_reply_is_ok_and_carries_what_was_written(served: StubServer) -> None:
    served.body = sse(chunk({"content": "The answer is"}, "length"), {"choices": [], "usage": USAGE})

    assert _call() == ("The answer is", inference.Outcome.OK)


@pytest.mark.parametrize(
    ("status", "body"),
    [
        (500, b'{"error": {"message": "out of memory"}}'),
        (200, sse(chunk({"content": "A"}), done=False)),
        (200, b'data: {"error": {"message": "mid-stream"}}\n\n'),
        (200, b""),
    ],
    ids=["http-error", "no-done", "error-event", "no-data"],
)
def test_a_stream_short_of_done_is_a_transport_failure(status: int, body: bytes, served: StubServer) -> None:
    served.status, served.body = status, body

    _text, outcome = _call()

    assert outcome is inference.Outcome.TRANSPORT_FAILURE
    assert len(served.requests) == 1, "the call retries nothing"


def _unused_port() -> int:
    """A loopback port nothing listens on: bound, read, and released."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_an_unreachable_server_is_a_transport_failure(served: StubServer, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(liaison_tools.BASE_URL_ENV, f"http://127.0.0.1:{_unused_port()}/v1")

    assert _call() == ("", inference.Outcome.TRANSPORT_FAILURE)


# --- the capture and its reader -----------------------------------------------------


def test_a_capture_closes_each_attempt_and_its_reader_gives_the_usage_and_measured_time(
    served: StubServer, tmp_path: Path
) -> None:
    capture = tmp_path / "c.capture.jsonl"

    _call(capture_path=capture)

    lines = capture.read_text(encoding="utf-8").splitlines()
    closing = json.loads(lines[-1])
    assert (closing["type"], closing["outcome"]) == (inference.REQUEST_RECORD, "ok")
    assert TOKEN not in "".join(lines) and str(served.port) not in "".join(lines)
    stats = inference.read_capture(capture)
    assert (stats.prompt_tokens, stats.completion_tokens, stats.cached_tokens) == (7718, 1, 7711)
    assert stats.reasoning_attempts == 0
    assert stats.duration_ms == closing["duration_ms"] and stats.duration_ms >= 0


def test_an_attempt_that_streamed_reasoning_counts_once(served: StubServer, tmp_path: Path) -> None:
    served.body = sse(
        chunk({"reasoning_content": "We need"}),
        chunk({"reasoning": " an answer."}),
        chunk({"content": "A"}, "stop"),
        {"choices": [], "usage": USAGE},
    )
    capture = tmp_path / "c.capture.jsonl"

    _call(capture_path=capture)

    assert inference.read_capture(capture).reasoning_attempts == 1


def test_a_reply_with_no_usage_leaves_its_counts_unreported(served: StubServer, tmp_path: Path) -> None:
    served.body = sse(chunk({"content": "A"}, "stop"))
    capture = tmp_path / "c.capture.jsonl"

    _call(capture_path=capture)

    stats = inference.read_capture(capture)
    assert (stats.prompt_tokens, stats.completion_tokens, stats.cached_tokens) == (None, None, None)


def test_retried_attempts_share_one_capture_reasoning_counts_over_all_and_the_last_decides_the_rest(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "c.capture.jsonl"
    first = [
        json.dumps(chunk({"reasoning_content": "hm"})),
        json.dumps({"type": inference.REQUEST_RECORD, "duration_ms": 9}),
    ]
    second = [
        "not json",
        json.dumps({"choices": [], "usage": USAGE}),
        json.dumps({"type": inference.REQUEST_RECORD, "duration_ms": 4}),
    ]
    unclosed = [json.dumps(chunk({"reasoning_content": "cut"}))]
    capture.write_text("\n".join(first + second + unclosed) + "\n", encoding="utf-8")

    stats = inference.read_capture(capture)

    assert stats.reasoning_attempts == 1
    assert (stats.duration_ms, stats.prompt_tokens) == (4, 7718)
