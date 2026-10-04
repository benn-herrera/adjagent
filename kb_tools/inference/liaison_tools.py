"""One tool-less chat call, made directly to the server ``liaison_tools``' environment names.

A system prompt, a user prompt, and the reply text back, through
``liaison_tools.openai_chat`` — the chat-completions request ``post-openai.py``
is built on.

**The environment is ``post-openai.py``'s**, the format a ``reaper-*.env`` file
holds: :data:`BASE_URL_ENV` is the API root, ``/v1`` included, and the request
goes to its ``/chat/completions``; :data:`MODEL_ENV` is the model;
:data:`KEY_FILE_ENV` names the file holding the key, which is read and
validated by ``openai_chat.read_api_key``, as ``post-openai.py``'s is; and
:data:`ALLOW_HTTP_ENV` set to exactly ``1`` accepts plaintext http to a
non-loopback host, as it does there. ``TEMPERATURE`` is not read: the request
always carries temperature 0. :func:`check_environment` is the one validation
of it, and :func:`call_chat` runs it on every call.

The request offers no tools, sends ``chat_template_kwargs.enable_thinking:
false`` and temperature 0, and asks for the usage chunk. ``liaison_tools`` is
imported at the call, not at import, so this package imports where it is not
installed and only a call needs it.

**The capture** appends, per call, every SSE data payload verbatim, one JSON
object per line, then one line closing the attempt:
``{"type": REQUEST_RECORD, "duration_ms": <the request's measured time>,
"outcome": <Outcome value>}``. Neither the key nor the base URL is ever
written there or logged. :func:`read_capture` is its one reader.

**How a call ended**: a stream that failed before, during or short of
``[DONE]`` is ``TRANSPORT_FAILURE``, and a stream that reached ``[DONE]`` is
``OK`` — an empty reply, and a reply the server cut off at its token limit,
included; the cut is logged. The reply text is the content the turn wrote,
whatever tool call a server injected beside it. ``timeout_seconds`` bounds
each blocking socket operation — the connect and each read of the stream — and
nothing bounds the call as a whole.

Stdlib only.
"""

import json
import logging
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import NoReturn

_log = logging.getLogger(__name__)

#: The ``type`` of the line closing each attempt in a capture.
REQUEST_RECORD = "liaison-request"

#: ``post-openai.py``'s variables, by its names.
BASE_URL_ENV = "API_BASE_URL"
MODEL_ENV = "MODEL"
KEY_FILE_ENV = "API_KEY_FILE"
ALLOW_HTTP_ENV = "ALLOW_HTTP"

#: What the request always carries, whatever ``TEMPERATURE`` the environment sets.
TEMPERATURE = 0.0


class Outcome(Enum):
    """How a call ended, before any policy is applied."""

    OK = "ok"
    TRANSPORT_FAILURE = "transport-failure"  # the stream failed before, during or short of [DONE]

    @property
    def ok(self) -> bool:
        return self is Outcome.OK


@dataclass(frozen=True)
class ChatEnvironment:
    """The server a call goes to, as :func:`check_environment` read and validated it."""

    base_url: str
    model: str
    token: str = field(repr=False)


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


def check_environment() -> ChatEnvironment:
    """The server the environment names, or :class:`ValueError` naming the variable that does not.

    Refuses where :data:`BASE_URL_ENV`, :data:`MODEL_ENV` or :data:`KEY_FILE_ENV`
    is unset, where the key file is missing or not one key, and where the base
    URL is not an acceptable API root. A refusal names the variable and never
    echoes the URL or the key.
    """
    from liaison_tools import openai_chat as chat

    base = os.environ.get(BASE_URL_ENV, "").rstrip("/")
    model = os.environ.get(MODEL_ENV, "")
    key_file = os.environ.get(KEY_FILE_ENV, "")
    if not base:
        _refuse(f"{BASE_URL_ENV} is unset, so there is no server to call")
    for variable, value in ((MODEL_ENV, model), (KEY_FILE_ENV, key_file)):
        if not value:
            _refuse(f"{BASE_URL_ENV} is set but {variable} is not")
    if chat.validate_base_url(base, allow_http=os.environ.get(ALLOW_HTTP_ENV, "") == "1") is not None:
        _refuse(f"{BASE_URL_ENV} is not an absolute https URL, nor http to a loopback host or with {ALLOW_HTTP_ENV}=1")
    return ChatEnvironment(base_url=base, model=model, token=_api_key(chat, key_file))


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
    server = check_environment()
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
