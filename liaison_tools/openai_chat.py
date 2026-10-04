"""One OpenAI-compatible chat-completions request, SSE-streamed, as an importable API.

The transaction ``post-openai.py`` runs as a command, for a caller in-process:
POST one streaming request, demux the SSE stream, reassemble ``delta.content``
and ``delta.tool_calls``, and classify the reply (:func:`classify_reply`).
Beside it, one embeddings batch (:func:`post_embeddings`) over the same transport. The
key is a value the caller hands in, read from its key file by
:func:`read_api_key` — the one read of that file, for every caller — and it
leaves process memory only as the ``Authorization`` header.

INVARIANT: stdlib only. No third-party dependencies. Ever.

Transport rules that protect the key, for every request made here:
  - :func:`validate_base_url` accepts https, http to a loopback host, and http
    to any host only when the caller opts in.
  - Redirects are never followed. urllib copies request headers — including
    Authorization — across a redirect, so a 3xx from the endpoint would hand
    the key to whatever host the Location header names. A 3xx is a hard error
    naming the refused target.

Diagnostics go to stderr, never stdout: a command built on this keeps stdout for
its own output contract.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from enum import Enum
from pathlib import Path
from typing import IO

DEFAULT_MAX_TOKENS = 1024 * 32

#: Seconds a blocking socket operation may wait — the connect, or one read of the stream.
DEFAULT_TIMEOUT_SECONDS = 600.0

# finish_reason values that mean the endpoint stopped of its own accord.
# Anything else (notably "length") means the reply was cut off.
COMPLETE_FINISH_REASONS = frozenset({"stop", "tool_calls", "function_call"})

# http is accepted only for these — local inference has no key to protect on
# the wire, and requiring https there would break every localhost endpoint.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

_MODEL_ERROR_CODE_RE = re.compile(r"model_not_found|invalid_model|model_not_allowed", re.I)
_MODEL_ERROR_MSG_RE = re.compile(r"does not exist|not available|no such model", re.I)
_MODEL_ERROR_FALLBACK_RE = re.compile(
    r"model_not_found|invalid_model|model_not_allowed|" r"does not exist|not available|no such model",
    re.I,
)

#: :func:`post_chat_streaming`'s status: a clean stream, ``[DONE]`` received.
STREAM_CLEAN = 0
#: A pre-stream HTTP or connection error; the returned raw text may hold the body.
STREAM_FAILED = 1
#: A mid-stream SSE error event, already reported to stderr.
STREAM_ERROR_EVENT = 2
#: The stream ended before ``[DONE]``, after some data.
STREAM_DROPPED = 3


class RedirectRefused(urllib.error.URLError):
    """A 3xx response from the configured endpoint, refused rather than followed."""

    def __init__(self, url: str, code: int, location: str) -> None:
        super().__init__(
            f"endpoint returned an HTTP {code} redirect from {url} to '{location}'; "
            "refused — following it would carry the Authorization header, and "
            "with it the API key, to the redirect target"
        )
        self.code = code
        self.location = location


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect. Installed in place of urllib's default handler,
    which copies request headers (Authorization included) to the new host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRefused(req.full_url, code, newurl)


# The one opener every request in this module goes through.
_OPENER = urllib.request.build_opener(_NoRedirectHandler)


class Reply(Enum):
    """How a completed call's reply reads, given its reassembled text and finish reason."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"  # the endpoint cut it off: a finish_reason outside COMPLETE_FINISH_REASONS
    EMPTY = "empty"  # nothing came back, under a normal finish reason


def read_api_key(key_path: Path) -> str | None:
    """Read the API key file and return the key, or None on invalid format.

    The file must contain a single contiguous string. Leading and trailing
    whitespace is trimmed; the result is the key. The key is invalid (None) if
    it is empty after trimming or contains any internal whitespace.
    """
    try:
        text = key_path.read_text(encoding="utf-8")
    except OSError:
        return None
    key = text.strip()
    if not key or any(ch.isspace() for ch in key):
        return None
    return key


def validate_base_url(url: str, *, allow_http: bool) -> str | None:
    """Return an error message if `url` is not an acceptable API root, else None.

    `allow_http` is the caller's opt-in: when set, an http URL to a non-loopback
    host validates too.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https":
        return None
    if not parts.scheme or not parts.netloc:
        return f"API_BASE_URL must be an absolute http(s) URL (got '{url}')"
    if parts.scheme == "http" and (parts.hostname or "") in LOOPBACK_HOSTS:
        return None
    if parts.scheme == "http" and allow_http:
        return None
    return (
        f"API_BASE_URL must use https (got scheme '{parts.scheme}' for host "
        f"'{parts.hostname or ''}'); plain http is accepted only for loopback "
        f"({', '.join(sorted(LOOPBACK_HOSTS))}), where the key stays on the machine"
        "; set ALLOW_HTTP=1 or pass --allow-http to accept that risk for a "
        "known-trusted private network"
    )


def demux_sse(
    line_iter: Iterable,
    debug_sink: IO | None = None,
    raw_buffer: list[str] | None = None,
    chunk_payloads: list[str] | None = None,
) -> tuple[list[dict], int]:
    """Read SSE bytes/text from `line_iter`, return (parsed_chunks, status).

    Status codes mirror the bash demux_sse return values:
        0 — clean: ≥1 data event AND [DONE] seen
        1 — no data events
        2 — mid-stream error event (already reported to stderr by this fn)
        3 — stream ended without [DONE] but had data events

    `debug_sink` (if set) receives every raw line in real time.
    `raw_buffer` (if set) collects every raw line text for later error reporting.
    `chunk_payloads` (if set) collects each `data:`-prefix-stripped payload
    string verbatim, matching the bash chunks-file format used for DEBUG dumps.
    """
    chunks: list[dict] = []
    saw_data = False
    saw_done = False
    for raw in line_iter:
        if isinstance(raw, bytes):
            raw_str = raw.decode("utf-8", errors="replace")
        else:
            raw_str = raw
        if raw_buffer is not None:
            raw_buffer.append(raw_str)
        if debug_sink is not None:
            out = raw_str if raw_str.endswith("\n") else raw_str + "\n"
            debug_sink.write(out)
            debug_sink.flush()
        line = raw_str.rstrip("\r\n")
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].lstrip(" ")
        if payload == "[DONE]":
            saw_done = True
            break
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(obj.get("error"), dict):
            sys.stderr.write("error: mid-stream error event:\n")
            sys.stderr.write(payload + "\n")
            return chunks, 2
        if chunk_payloads is not None:
            chunk_payloads.append(payload)
        chunks.append(obj)
        saw_data = True
    if not saw_data:
        return chunks, 1
    if not saw_done:
        return chunks, 3
    return chunks, 0


def reassemble_stream(chunks: list[dict]) -> str:
    """Reassemble SSE delta chunks into either text or 'TOOL_CALLS\\n<json>'.

    Direct port of the bash embedded-python reassembler: accumulate
    `delta.content` strings into a content buffer, accumulate `delta.tool_calls`
    by index into a slot map, then emit content text OR (if any tool_calls
    were seen) a TOOL_CALLS marker + JSON-serialized ordered list.
    """
    tc_map: dict[int, dict] = {}
    for delta in _deltas(chunks):
        for tc in delta.get("tool_calls") or []:
            idx = tc.get("index")
            if idx is None:
                continue
            slot = tc_map.setdefault(
                idx,
                {
                    "id": None,
                    "type": "function",
                    "function": {"name": None, "arguments": ""},
                },
            )
            if tc.get("id"):
                slot["id"] = tc["id"]
            if tc.get("type"):
                slot["type"] = tc["type"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["function"]["name"] = fn["name"]
            if isinstance(fn.get("arguments"), str):
                slot["function"]["arguments"] += fn["arguments"]
    if tc_map:
        ordered = [tc_map[k] for k in sorted(tc_map.keys())]
        return "TOOL_CALLS\n" + json.dumps(ordered)
    return reassemble_content(chunks)


def _deltas(chunks: list[dict]) -> Iterable[dict]:
    """Each chunk's ``choices[0].delta``, skipping the chunks that carry no choices."""
    for obj in chunks:
        choices = obj.get("choices") or []
        if choices:
            yield choices[0].get("delta") or {}


def reassemble_content(chunks: list[dict]) -> str:
    """The ``delta.content`` strings concatenated: the text the reply wrote, whatever tool calls rode beside it."""
    return "".join(c for delta in _deltas(chunks) if isinstance(c := delta.get("content"), str))


def extract_usage(chunks: list[dict]) -> dict:
    """Extract token usage and model id from parsed response objects.

    Covers both response shapes with one scan: a non-streaming full completion
    object (usage at the top level beside `choices`), and SSE streams — where
    usage typically rides a late chunk with empty `choices` (the shape
    `reassemble_stream` skips) or on the final delta chunk. The last object
    carrying each field wins; fields the API never provided are None.
    """
    usage: dict = {}
    model = None
    for obj in chunks:
        u = obj.get("usage")
        if isinstance(u, dict):
            usage = u
        m = obj.get("model")
        if isinstance(m, str) and m:
            model = m
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "model": model,
    }


def extract_finish_reason(chunks: list[dict]) -> str | None:
    """Return the last non-empty ``choices[0].finish_reason``, or None.

    None means the endpoint never said why it stopped, which is treated as
    complete: some servers omit the field entirely.
    """
    reason = None
    for obj in chunks:
        choices = obj.get("choices") or []
        if not choices:
            continue
        value = choices[0].get("finish_reason")
        if isinstance(value, str) and value:
            reason = value
    return reason


def classify_reply(reassembled: str, finish_reason: str | None) -> Reply:
    """Whether a completed call's reply is usable: a cut-off reply is incomplete even when empty."""
    if finish_reason is not None and finish_reason not in COMPLETE_FINISH_REASONS:
        return Reply.INCOMPLETE
    return Reply.COMPLETE if reassembled else Reply.EMPTY


def list_models(base_url: str, token: str) -> list[str]:
    """GET /models — return the data[].id list. Raises on transport errors."""
    req = urllib.request.Request(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    with _OPENER.open(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    obj = json.loads(body)
    return [m["id"] for m in obj.get("data", [])]


def post_embeddings(
    *, base_url: str, token: str, model: str, texts: list[str], timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> list[list[float]]:
    """POST one batch to ``{base_url}/embeddings`` and return one vector per text, in ``texts`` order.

    Raises what :func:`list_models` raises on transport errors, ``urllib.error.HTTPError`` for a
    non-2xx reply, and ``ValueError`` when the reply does not carry exactly one vector per text.
    The caller validates ``base_url`` (:func:`validate_base_url`) before calling.
    """
    req = urllib.request.Request(
        f"{base_url}/embeddings",
        data=json.dumps({"model": model, "input": texts}).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with _OPENER.open(req, timeout=timeout_seconds) as resp:
        data = json.loads(resp.read().decode("utf-8")).get("data", [])
    vectors = [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]
    if len(vectors) != len(texts):
        raise ValueError(f"embeddings reply carried {len(vectors)} vectors for {len(texts)} texts")
    return vectors


def resolve_model(name: str, base_url: str, token: str) -> str | None:
    """Resolve `name` to an exact model id via /models. Accepts exact match
    or unambiguous substring. Returns None on failure (errors already on stderr).
    """
    try:
        models = list_models(base_url, token)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as e:
        sys.stderr.write(f"error: failed querying models: {e}\n")
        return None

    if name in models:
        return name

    matches = [m for m in models if name in m]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        sys.stderr.write(f"error: no model matching '{name}'. available models:\n")
        sys.stderr.write("\n".join(models) + ("\n" if models else ""))
        return None
    sys.stderr.write(f"error: '{name}' is ambiguous — {len(matches)} candidates:\n")
    sys.stderr.write("\n".join(matches) + "\n")
    return None


def is_model_error_text(raw: str) -> bool:
    """Return True if `raw` (a pre-stream HTTP body or non-SSE response body)
    looks like a model-name error. JSON-aware first, textual fallback after.
    """
    try:
        body = json.loads(raw)
        if isinstance(body, dict):
            err = body.get("error") or body.get("detail") or {}
            if isinstance(err, dict):
                code = err.get("code", "") or ""
                msg = err.get("message", "") or ""
                if isinstance(code, str) and _MODEL_ERROR_CODE_RE.search(code):
                    return True
                if isinstance(msg, str) and _MODEL_ERROR_MSG_RE.search(msg):
                    return True
    except (json.JSONDecodeError, ValueError):
        pass
    return bool(_MODEL_ERROR_FALLBACK_RE.search(raw))


def post_chat_streaming(
    *,
    model: str,
    base_url: str,
    token: str,
    messages: object,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    enable_thinking: bool | None,
    temperature: float,
    include_usage: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    debug_post: bool = False,
    debug_response: bool = False,
) -> tuple[list[dict], list[str], str, int]:
    """POST one streaming completions request to ``{base_url}/chat/completions``.

    No tools are offered. ``enable_thinking``, where not None, is sent as
    ``chat_template_kwargs.enable_thinking``. ``include_usage`` asks for the
    usage chunk (``stream_options``), which an OpenAI-compatible server sends
    only when asked.

    Returns (chunks, chunk_payloads, raw_text, status), status one of
    :data:`STREAM_CLEAN`, :data:`STREAM_FAILED`, :data:`STREAM_ERROR_EVENT`,
    :data:`STREAM_DROPPED`. The caller validates ``base_url``
    (:func:`validate_base_url`) before calling.
    """
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "top_p": 1.0,
        "temperature": temperature,
        "stream": True,
        "messages": messages,
    }
    if include_usage:
        payload["stream_options"] = {"include_usage": True}
    if enable_thinking is not None:
        payload["chat_template_kwargs"] = {"enable_thinking": enable_thinking}
    payload_str = json.dumps(payload)

    if debug_post:
        sys.stderr.write(f"POST {base_url}/chat/completions payload:\n")
        sys.stderr.write(payload_str + "\n")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload_str.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
    )

    raw_buffer: list[str] = []
    chunk_payloads: list[str] = []
    debug_sink = sys.stderr if debug_response else None

    try:
        with _OPENER.open(req, timeout=timeout_seconds) as resp:
            line_iter = (line.decode("utf-8", errors="replace") for line in resp)
            chunks, status = demux_sse(
                line_iter,
                debug_sink=debug_sink,
                raw_buffer=raw_buffer,
                chunk_payloads=chunk_payloads,
            )
    except RedirectRefused as e:
        sys.stderr.write(f"error: {e.reason}\n")
        return [], [], "", STREAM_FAILED
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        sys.stderr.write(f"error: HTTP {e.code} from {base_url}/chat/completions\n")
        if body:
            sys.stderr.write("--- raw body ---\n")
            sys.stderr.write(body if body.endswith("\n") else body + "\n")
        return [], [], body, STREAM_FAILED
    except (urllib.error.URLError, OSError) as e:
        sys.stderr.write(f"error: request failed before any SSE data: {e}\n")
        return [], [], "", STREAM_FAILED

    raw_text = "".join(raw_buffer)

    if status == 1:
        sys.stderr.write("error: no SSE data events received\n")
        if raw_text:
            sys.stderr.write("--- raw body ---\n")
            sys.stderr.write(raw_text if raw_text.endswith("\n") else raw_text + "\n")
        return chunks, chunk_payloads, raw_text, STREAM_FAILED

    if status == 2:
        return chunks, chunk_payloads, raw_text, STREAM_ERROR_EVENT

    if status == 3:
        sys.stderr.write("error: stream terminated before [DONE]\n")
        return chunks, chunk_payloads, raw_text, STREAM_DROPPED

    return chunks, chunk_payloads, raw_text, STREAM_CLEAN
