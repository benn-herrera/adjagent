"""Two model calls, each made directly to the server ``liaison_tools``' environment names.

:func:`call_chat`: a system prompt, a user prompt, and the reply text back,
through ``liaison_tools.openai_chat`` — the chat-completions request
``post-openai.py`` is built on. :func:`call_decision`: a state and one
closed-set question, and the server's answer back, through one JSON request to
the base URL's ``/systemone``.

**The environment is ``post-openai.py``'s**, the format a ``reaper-*.env`` file
holds: :data:`BASE_URL_ENV` is the API root, ``/v1`` included, and the request
goes to its ``/chat/completions``; :data:`MODEL_ENV` is the chat model;
:data:`KEY_FILE_ENV` names the file holding the key, which is read and
validated by ``openai_chat.read_api_key``, as ``post-openai.py``'s is; and
:data:`ALLOW_HTTP_ENV` set to exactly ``1`` accepts plaintext http to a
non-loopback host, as it does there. ``TEMPERATURE`` is not read: the request
always carries temperature 0. Beside them, :data:`DECISION_MODEL_ENV` names the
decision model, which ``post-openai.py`` does not read. Each model is required
only where the caller will make that call: :func:`check_environment` is the
one validation of the environment, and each call runs it on every call, asking
for its own model alone.

The chat request offers no tools, sends ``chat_template_kwargs.enable_thinking:
false`` and temperature 0, and asks for the usage chunk. ``liaison_tools`` is
imported at the call, not at import, so this package imports where it is not
installed and only a call needs it.

**The chat capture** appends, per call, every SSE data payload verbatim, one JSON
object per line, then one line closing the attempt:
``{"type": REQUEST_RECORD, "duration_ms": <the request's measured time>,
"outcome": <Outcome value>}``. Neither the key nor the base URL is ever
written to either capture or logged. :func:`read_capture` is its one reader.

**How a chat call ended**: a stream that failed before, during or short of
``[DONE]`` is ``TRANSPORT_FAILURE``, and a stream that reached ``[DONE]`` is
``OK`` — an empty reply, and a reply the server cut off at its token limit,
included; the cut is logged. The reply text is the content the turn wrote,
whatever tool call a server injected beside it. ``timeout_seconds`` bounds
each blocking socket operation — the connect and each read of the stream — and
nothing bounds the call as a whole.

**A decision call** sends exactly ``model``, ``state`` and ``questions`` — the
one question under its key — and nothing else: no system message, no
temperature, no stream. It ends ``OK`` with the answers the 2xx body carries,
unknown keys ignored; ``TRANSPORT_FAILURE`` — the class worth an identical
re-issue — on a failed connection or read, a 429, any 5xx, or a 2xx body that
does not decode; and ``REFUSED`` on any other non-2xx status, or an answer under
a key the request did not ask. Its capture appends one
:data:`DECISION_RECORD` line per attempt: the request's model, the state's
SHA-256 and never the state, the response body verbatim, the measured time, the
HTTP status and the outcome. :func:`read_decision_capture` is its one reader.

Stdlib only.
"""

import hashlib
import http.client
import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import NoReturn

_log = logging.getLogger(__name__)

#: The ``type`` of the line closing each attempt in a chat capture.
REQUEST_RECORD = "liaison-request"
#: The ``type`` of the one line each attempt writes to a decision capture.
DECISION_RECORD = "liaison-decision"

#: ``post-openai.py``'s variables, by its names.
BASE_URL_ENV = "API_BASE_URL"
MODEL_ENV = "MODEL"
KEY_FILE_ENV = "API_KEY_FILE"
ALLOW_HTTP_ENV = "ALLOW_HTTP"
#: The decision model, which ``post-openai.py`` does not read.
DECISION_MODEL_ENV = "DECISION_MODEL"

#: What the chat request always carries, whatever ``TEMPERATURE`` the environment sets.
TEMPERATURE = 0.0

#: The decision endpoint, beside ``chat/completions`` under the base URL.
DECISION_PATH = "/systemone"


class Outcome(Enum):
    """How a call ended, before any policy is applied."""

    OK = "ok"
    #: Worth an identical re-issue: a chat stream short of ``[DONE]``; a decision
    #: call's failed transport, 429, 5xx or undecodable body.
    TRANSPORT_FAILURE = "transport-failure"
    #: Not worth one: a decision call's other non-2xx status, or an answer to a question it did not ask.
    REFUSED = "refused"

    @property
    def ok(self) -> bool:
        return self is Outcome.OK


@dataclass(frozen=True)
class ChatEnvironment:
    """The server a call goes to, as :func:`check_environment` read and validated it.

    ``model`` and ``decision_model`` are each ``None`` unless the check was asked for it.
    """

    base_url: str
    model: str | None
    token: str = field(repr=False)
    decision_model: str | None = None


def _refuse(complaint: str) -> NoReturn:
    _log.error("chat call refused: %s", complaint)
    raise ValueError(complaint)


def _api_key(chat: ModuleType, key_file: str) -> str:
    """The key :data:`KEY_FILE_ENV` names, read and validated by ``openai_chat.read_api_key``. The path is no secret."""
    key_path = Path(key_file)
    if not key_path.is_file():
        _refuse(f"{KEY_FILE_ENV} not found: {key_file}")
    key = chat.read_api_key(key_path)
    if key is None:
        _refuse(f"{KEY_FILE_ENV} has invalid format: {key_file}")
    return key


def check_environment(*, chat: bool, decision: bool) -> ChatEnvironment:
    """The server the environment names, or :class:`ValueError` naming the variable that does not.

    Asked by what the caller will call: ``chat`` for a chat call, which needs
    :data:`MODEL_ENV`, and ``decision`` for a decision call, which needs
    :data:`DECISION_MODEL_ENV`. Refuses where :data:`BASE_URL_ENV` or
    :data:`KEY_FILE_ENV` is unset, or a model asked for is; where the key file is
    missing or not one key; and where the base URL is not an acceptable API root.
    A refusal names the variable and never echoes the URL or the key.
    """
    from liaison_tools import openai_chat

    base = os.environ.get(BASE_URL_ENV, "").rstrip("/")
    model = os.environ.get(MODEL_ENV, "")
    key_file = os.environ.get(KEY_FILE_ENV, "")
    decision_model = os.environ.get(DECISION_MODEL_ENV, "")
    if not base:
        _refuse(f"{BASE_URL_ENV} is unset, so there is no server to call")
    required = (
        ([(MODEL_ENV, model)] if chat else [])
        + [(KEY_FILE_ENV, key_file)]
        + ([(DECISION_MODEL_ENV, decision_model)] if decision else [])
    )
    for variable, value in required:
        if not value:
            _refuse(f"{BASE_URL_ENV} is set but {variable} is not")
    if openai_chat.validate_base_url(base, allow_http=os.environ.get(ALLOW_HTTP_ENV, "") == "1") is not None:
        _refuse(f"{BASE_URL_ENV} is not an absolute https URL, nor http to a loopback host or with {ALLOW_HTTP_ENV}=1")
    return ChatEnvironment(
        base_url=base,
        model=model if chat else None,
        token=_api_key(openai_chat, key_file),
        decision_model=decision_model if decision else None,
    )


def call_chat(
    *,
    system_prompt: str,
    prompt: str,
    timeout_seconds: float,
    capture_path: Path | None = None,
) -> tuple[str, Outcome]:
    """Pose ``prompt`` under ``system_prompt`` to the environment's model and return the reply text and how the call ended.

    Raises :class:`ValueError` for an empty system prompt or prompt, and for
    an environment :func:`check_environment` refuses; every way the request
    itself can end is a returned :class:`Outcome`.
    """
    if not system_prompt.strip():
        _refuse("the system prompt is empty")
    if not prompt.strip():
        _refuse("the prompt is empty")
    server = check_environment(chat=True, decision=False)
    from liaison_tools import openai_chat as chat

    started = time.monotonic()
    chunks, payloads, _raw, status = chat.post_chat_streaming(
        model=server.model,
        base_url=server.base_url,
        token=server.token,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        enable_thinking=False,
        temperature=TEMPERATURE,
        include_usage=True,
        timeout_seconds=timeout_seconds,
    )
    duration_ms = round((time.monotonic() - started) * 1000)

    text = chat.reassemble_content(chunks)
    outcome = Outcome.OK if status == chat.STREAM_CLEAN else Outcome.TRANSPORT_FAILURE
    finish_reason = chat.extract_finish_reason(chunks)
    if outcome.ok and chat.classify_reply(text, finish_reason) is chat.Reply.INCOMPLETE:
        _log.warning("chat call reply was cut off: finish_reason=%s", finish_reason)

    if capture_path is not None:
        closing = {"type": REQUEST_RECORD, "duration_ms": duration_ms, "outcome": outcome.value}
        with capture_path.open("a", encoding="utf-8") as capture:
            capture.writelines(f"{line}\n" for line in (*payloads, json.dumps(closing)))
    _log.info(
        "chat call finished: outcome=%s stream-status=%d chunks=%d duration=%.1fs capture=%s",
        outcome.value,
        status,
        len(chunks),
        duration_ms / 1000,
        capture_path,
    )
    return text, outcome


@dataclass(frozen=True)
class DecisionQuestion:
    """One closed-set question, sent as its ``type``, ``instructions`` and ``criteria`` under ``key``, which the answer echoes."""

    key: str
    type: str
    instructions: str
    criteria: Mapping[str, str]


@dataclass(frozen=True)
class DecisionReply:
    """How a decision call ended and, where ``OK``, its answers and the usage the server reported.

    ``answers`` is keyed as asked, each answer the server's object read whole,
    and empty unless ``OK``. A count is ``None`` where the server sent none.
    """

    outcome: Outcome
    answers: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None


def _json_object(text: str) -> dict[str, object] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _decision_usage(body: Mapping[str, object]) -> tuple[int | None, int | None]:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None, None
    return _count(usage, "input_tokens"), _count(usage, "output_tokens")


def _post_decision(server: ChatEnvironment, payload: bytes, timeout_seconds: float) -> tuple[int | None, str]:
    """One POST of ``payload``: the HTTP status and the body text, or ``(None, "")`` where the transport failed."""
    from liaison_tools import openai_chat as chat

    request = urllib.request.Request(
        server.base_url + DECISION_PATH,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {server.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        # ``openai_chat``'s opener refuses redirects, which would carry the key to the redirect target.
        with chat.OPENER.open(request, timeout=timeout_seconds) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        with error:
            try:
                return error.code, error.read().decode("utf-8", errors="replace")
            except (OSError, http.client.HTTPException):
                return error.code, ""
    except (OSError, http.client.HTTPException) as error:
        # The error's text can carry the URL (a refused redirect names it), so only its kind is logged.
        _log.warning("decision call transport failed: %s", type(error).__name__)
        return None, ""


def _read_decision_reply(status: int | None, text: str, *, asked: str) -> DecisionReply:
    """How a decision call ended, from its HTTP status (``None``: the transport failed) and body text."""
    if status is None or status == 429 or 500 <= status < 600:
        return DecisionReply(Outcome.TRANSPORT_FAILURE)
    if not 200 <= status < 300:
        return DecisionReply(Outcome.REFUSED)
    body = _json_object(text)
    answers = body.get("answers") if body is not None else None
    if body is None or not (
        answers is None or isinstance(answers, dict) and all(isinstance(a, dict) for a in answers.values())
    ):
        _log.warning("decision call body does not decode as a decision response")
        return DecisionReply(Outcome.TRANSPORT_FAILURE)
    answers = answers or {}
    unasked = sorted(key for key in answers if key != asked)
    if unasked:
        _log.warning("decision call answered question keys it was not asked: %s (asked: %s)", unasked, asked)
        return DecisionReply(Outcome.REFUSED)
    input_tokens, output_tokens = _decision_usage(body)
    return DecisionReply(Outcome.OK, answers=answers, input_tokens=input_tokens, output_tokens=output_tokens)


def call_decision(
    state: str, question: DecisionQuestion, *, model: str, timeout_seconds: float, capture: Path | None
) -> DecisionReply:
    """Pose ``question`` over ``state`` to ``model`` at the environment's decision endpoint, once.

    Raises :class:`ValueError` for an environment :func:`check_environment`
    refuses with ``decision`` set; every way the request itself can end is the
    returned :class:`DecisionReply`'s :class:`Outcome`.
    """
    server = check_environment(chat=False, decision=True)
    # Criteria sorted by key: kbase's encoder writes a map's keys sorted, so this is the order it sends.
    criteria = dict(sorted(question.criteria.items()))
    asked = {"type": question.type, "instructions": question.instructions, "criteria": criteria}
    payload = json.dumps({"model": model, "state": state, "questions": {question.key: asked}}).encode("utf-8")

    started = time.monotonic()
    status, text = _post_decision(server, payload, timeout_seconds)
    duration_ms = round((time.monotonic() - started) * 1000)
    reply = _read_decision_reply(status, text, asked=question.key)

    if capture is not None:
        record = {
            "type": DECISION_RECORD,
            "model": model,
            "state_sha256": hashlib.sha256(state.encode("utf-8")).hexdigest(),
            "status": status,
            "duration_ms": duration_ms,
            "outcome": reply.outcome.value,
            "body": text,
        }
        with capture.open("a", encoding="utf-8") as lines:
            lines.write(f"{json.dumps(record)}\n")
    _log.info(
        "decision call finished: outcome=%s status=%s duration=%.1fs capture=%s",
        reply.outcome.value,
        status,
        duration_ms / 1000,
        capture,
    )
    return reply


@dataclass(frozen=True)
class CaptureStats:
    """What a capture says about its calls: reasoning over every attempt, the rest off the last.

    Each count is ``None`` where the server's chunks did not carry it.
    """

    duration_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cached_tokens: int | None
    reasoning_attempts: int


#: Where a chat-completions delta carries the reasoning a server streamed.
_REASONING_KEYS = ("reasoning_content", "reasoning")


def _count(mapping: Mapping[str, object], key: str) -> int | None:
    value = mapping.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _streamed_reasoning(chunk: Mapping[str, object]) -> bool:
    choices = chunk.get("choices")
    deltas = [c.get("delta") for c in choices if isinstance(c, dict)] if isinstance(choices, list) else []
    return any(isinstance(d, dict) and any(isinstance(d.get(k), str) and d[k] for k in _REASONING_KEYS) for d in deltas)


def read_capture(capture: Path) -> CaptureStats:
    """A capture's figures: how many attempts streamed reasoning, and the rest off the last closed attempt.

    Each attempt is its chunks then its closing :data:`REQUEST_RECORD` line;
    the duration is that line's, and the token counts are the attempt's usage
    chunk. The chunks are the server's, so every field is read where present
    and left ``None`` where not; a line that is not a JSON object is skipped.
    """
    reasoning = 0
    reasoned = False
    attempt_usage: Mapping[str, object] = {}
    usage: Mapping[str, object] = {}
    closing: Mapping[str, object] = {}
    for line in capture.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == REQUEST_RECORD:
            closing, usage = event, attempt_usage
            reasoning += reasoned
            reasoned, attempt_usage = False, {}
            continue
        if isinstance(event.get("usage"), dict):
            attempt_usage = event["usage"]
        reasoned = reasoned or _streamed_reasoning(event)
    details = usage.get("prompt_tokens_details")
    return CaptureStats(
        duration_ms=_count(closing, "duration_ms"),
        prompt_tokens=_count(usage, "prompt_tokens"),
        completion_tokens=_count(usage, "completion_tokens"),
        cached_tokens=_count(details, "cached_tokens") if isinstance(details, dict) else None,
        reasoning_attempts=reasoning,
    )


def read_decision_capture(capture: Path) -> CaptureStats:
    """A decision capture's figures, off its last :data:`DECISION_RECORD` line.

    The duration is that line's measured time; ``usage.input_tokens`` and
    ``output_tokens`` of the body it holds are the prompt and completion
    counts, each ``None`` where the body carries none. A decision call reports
    no cache reads and streams no reasoning. A line that is not a JSON object
    is skipped.
    """
    last: Mapping[str, object] = {}
    for line in capture.read_text(encoding="utf-8").splitlines():
        event = _json_object(line)
        if event is not None and event.get("type") == DECISION_RECORD:
            last = event
    text = last.get("body")
    body = _json_object(text) if isinstance(text, str) else None
    input_tokens, output_tokens = _decision_usage(body) if body is not None else (None, None)
    return CaptureStats(
        duration_ms=_count(last, "duration_ms"),
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        cached_tokens=None,
        reasoning_attempts=0,
    )
