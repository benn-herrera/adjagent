#!/usr/bin/env python3
"""POST a messages array to an OpenAI-compatible
chat completions endpoint using SSE streaming, reassemble delta content /
tool_calls, and emit the canonical stdout contract (text body, or
"TOOL_CALLS\\n<json>").

INVARIANT: stdlib only. No third-party dependencies. Ever.
Adding `pip install` of anything is not on the table — if you reach for one,
stop and find a stdlib path, or talk it through with the maintainer first.

usage:
  API_BASE_URL=<url> API_KEY_FILE=<api-key-file> MODEL=<model> \\
      post-openai.py [--allow-http] <messages.json>

env vars:
  API_BASE_URL       (required) OpenAI-compatible base URL, e.g. https://api.openai.com/v1
  API_KEY_FILE       (required) path to a file containing only the API key. Its
                                entire content, with leading and trailing
                                whitespace trimmed, is the key; the key must
                                contain no internal whitespace.
  MODEL              (required) model id; substring resolution is attempted on
                                pre-stream model-not-found errors.
  ALLOW_HTTP         (optional) "1" to accept a plaintext http URL to a
                                non-loopback host, for a known-trusted private
                                network; any other value, including unset or
                                empty, means no (default: unset). The
                                --allow-http command-line flag is the other
                                spelling of the same opt-in; either alone is
                                enough.
  MAX_TOKENS         (optional) integer max response tokens (default: 32768)
  ENABLE_THINKING    (optional) "true" in any case enables, any other value
                                disables; sent as
                                chat_template_kwargs.enable_thinking
                                (default: true)
  TEMPERATURE        (optional) float in [0.0, 2.0] (default: 1.0)
  DEBUG_POST         (optional) "true" to dump the request payload to stderr
  DEBUG_RESPONSE     (optional) "true" to tee the raw SSE stream + reassembled output to stderr
  USAGE_STATS_FILE   (optional) path to a token-usage side-channel file. When
                                set, one JSON line is appended per successful
                                call (any of exit 0, 3, or 4): {"prompt_tokens": ...,
                                "completion_tokens": ..., "total_tokens": ...,
                                "model": ...} — token fields from the
                                response's `usage` object, model from the
                                response object; null where the API omits a
                                field. Usage never goes to stdout. A failed
                                write is a stderr warning only, never a
                                transport failure. Unset: no file is touched
                                and behavior is unchanged.

The API key is read from API_KEY_FILE into process memory. It is never placed
on the command line or into an environment variable, so it is not exposed
through argv or the process environment.

Transport rules that protect that containment:
  - API_BASE_URL must be https, except for loopback hosts (localhost,
    127.0.0.1, ::1), where http is accepted for local inference, or any host
    when ALLOW_HTTP=1 or --allow-http is given — an explicit opt-in for an
    operator who knows their endpoint is on a trusted private network.
  - Redirects are never followed. urllib copies request headers — including
    Authorization — across a redirect, so a 3xx from the endpoint would hand
    the key to whatever host the Location header names. A 3xx is a hard error
    naming the refused target.

exit codes:
  0  a complete reply; stdout carries the stdout contract above
  1  usage / configuration / transport failure (retryable by the caller)
  3  the endpoint completed the call but the reply is incomplete — a
     finish_reason other than stop/tool_calls/function_call (e.g. "length"). Whatever
     arrived is still written to stdout for the audit trail, but it must not
     be recorded as a complete reply. Retrying the same request will not help
  4  the endpoint returned an empty completion with a normal finish reason: a
     protocol-level empty result, not a transport failure. stdout is empty
Exit 3 and 4 are protocol events, not transport failures: a caller retries
neither. Both still append to USAGE_STATS_FILE — the tokens were spent.

The request itself is ``openai_chat``'s (its sibling in this directory); this
command reads the key file and the environment, and owns the stdout contract,
the exit codes and the usage side channel.
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    # Run as a command: this file's own directory leads sys.path.
    import openai_chat as chat
except ModuleNotFoundError:
    # Loaded by path from a process that imports the package (the test suite).
    from liaison_tools import openai_chat as chat

# Exit codes. 0/1 are the historical contract; 3 and 4 are protocol events the
# caller must not retry (see the module docstring).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INCOMPLETE = 3
EXIT_EMPTY = 4

_TEMPERATURE_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")
DEFAULT_TEMPERATURE = 1.0


def _usage(msg: str = "") -> None:
    script = Path(sys.argv[0]).name or "post-openai.py"
    if msg:
        sys.stderr.write(f"error: {msg}\n")
    sys.stderr.write(
        f"usage: API_BASE_URL=<url> API_KEY_FILE=<api-key-file> " f"MODEL=<model> {script} <messages.json>\n"
    )
    sys.stderr.write(
        f"optional envar param MAX_TOKENS=<max-response-token-count> " f"(default: {chat.DEFAULT_MAX_TOKENS})\n"
    )
    sys.stderr.write(f"optional envar param TEMPERATURE=<float in [0.0, 2.0]> (default: {DEFAULT_TEMPERATURE})\n")
    sys.stderr.write(
        "API_KEY_FILE file format: the file contains only the API key "
        "(leading/trailing whitespace trimmed; no internal whitespace).\n"
    )
    sys.exit(1)


def _parse_temperature(raw: str) -> float:
    if not _TEMPERATURE_RE.match(raw):
        sys.stderr.write(f"error: TEMPERATURE must be a non-negative number (got '{raw}')\n")
        sys.exit(1)
    v = float(raw)
    if v > 2.0:
        sys.stderr.write(f"error: TEMPERATURE must be in [0.0, 2.0] (got '{raw}')\n")
        sys.exit(1)
    return v


def write_usage_stats(stats_path: str, stats: dict) -> None:
    """Append one JSON line to the USAGE_STATS_FILE side channel.

    Advisory only: any write failure is a stderr warning, never a transport
    failure, and nothing about the side channel ever reaches stdout.
    """
    try:
        with open(stats_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(stats) + "\n")
    except OSError as e:
        sys.stderr.write(f"warning: could not write USAGE_STATS_FILE '{stats_path}': {e}\n")


def _emit(reassembled: str) -> None:
    """Match the bash stdout contract: trailing newline either way."""
    sys.stdout.write(reassembled + "\n")


def main() -> int:
    api_base_url = os.environ.get("API_BASE_URL", "")
    api_key_file = os.environ.get("API_KEY_FILE", "")
    model = os.environ.get("MODEL", "")

    args = sys.argv[1:]
    allow_http_flag = "--allow-http" in args
    if allow_http_flag:
        args = [a for a in args if a != "--allow-http"]
    allow_http = allow_http_flag or os.environ.get("ALLOW_HTTP", "") == "1"

    if not api_base_url:
        _usage("API_BASE_URL must be set")
    url_error = chat.validate_base_url(api_base_url, allow_http=allow_http)
    if url_error:
        _usage(url_error)
    if not api_key_file:
        _usage("API_KEY_FILE must be set")
    key_path = Path(api_key_file)
    if not key_path.is_file():
        _usage(f"API_KEY_FILE not found: {api_key_file}")

    token = chat.read_api_key(key_path)
    if token is None:
        _usage(f"API_KEY_FILE has invalid format: {api_key_file}")
        token = ""  # shut the linter up. it's not catching that _usage exits.

    if not model:
        _usage("MODEL must be set")

    messages_arg = os.environ.get("MESSAGES_FILE") or (args[0] if args else "")
    if not messages_arg or not Path(messages_arg).is_file():
        _usage(f"messages file not found: {messages_arg}")
    messages_file = Path(messages_arg)

    max_tokens_raw = os.environ.get("MAX_TOKENS", str(chat.DEFAULT_MAX_TOKENS))
    try:
        max_tokens = int(max_tokens_raw)
    except ValueError:
        _usage(f"MAX_TOKENS must be an integer (got '{max_tokens_raw}')")
        return 1

    temperature = _parse_temperature(os.environ.get("TEMPERATURE", str(DEFAULT_TEMPERATURE)))
    enable_thinking = os.environ.get("ENABLE_THINKING", "true").lower() == "true"

    debug_post = os.environ.get("DEBUG_POST", "false").lower() == "true"
    debug_response = os.environ.get("DEBUG_RESPONSE", "false").lower() == "true"
    usage_stats_file = os.environ.get("USAGE_STATS_FILE", "")

    try:
        messages = json.loads(messages_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.stderr.write(f"error: messages file is not valid JSON: {e}\n")
        return 1

    chunks, chunk_payloads, raw_text, rc = chat.post_chat_streaming(
        model=model,
        base_url=api_base_url,
        token=token,
        messages=messages,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
        temperature=temperature,
        debug_post=debug_post,
        debug_response=debug_response,
    )

    if rc == chat.STREAM_FAILED and raw_text and chat.is_model_error_text(raw_text):
        sys.stderr.write(f"warning: model '{model}' not found — attempting substring resolution\n")
        resolved = chat.resolve_model(model, api_base_url, token)
        if resolved is None:
            sys.stderr.write("error: update MODEL to a valid model name\n")
            return 1
        sys.stderr.write(f"warning: resolved '{model}' → '{resolved}' — " "update MODEL to avoid this fallback\n")
        chunks, chunk_payloads, raw_text, rc = chat.post_chat_streaming(
            model=resolved,
            base_url=api_base_url,
            token=token,
            messages=messages,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
            temperature=temperature,
            debug_post=debug_post,
            debug_response=debug_response,
        )

    if rc != chat.STREAM_CLEAN:
        return 1

    if debug_response:
        sys.stderr.write("--- raw SSE stream ---\n")
        sys.stderr.write(raw_text if raw_text.endswith("\n") else raw_text + "\n")
        sys.stderr.write("--- chunks ---\n")
        for cp in chunk_payloads:
            sys.stderr.write(cp + "\n")

    reassembled = chat.reassemble_stream(chunks)

    if debug_response:
        sys.stderr.write("--- reassembled ---\n")
        sys.stderr.write(reassembled if reassembled.endswith("\n") else reassembled + "\n")

    finish_reason = chat.extract_finish_reason(chunks)

    # The call completed and the tokens were spent, whatever the verdict below
    # says about the reply's usability — so the side channel records it first.
    if usage_stats_file:
        write_usage_stats(usage_stats_file, chat.extract_usage(chunks))

    incomplete = chat.classify_reply(reassembled, finish_reason) is chat.Reply.INCOMPLETE

    if not reassembled:
        # A protocol event, not a transport failure: retrying an empty
        # completion burns the caller's retries and halts its run.
        sys.stderr.write(f"error: endpoint returned an empty completion (finish_reason={finish_reason!r})\n")
        if raw_text:
            sys.stderr.write("--- raw body ---\n")
            sys.stderr.write(raw_text if raw_text.endswith("\n") else raw_text + "\n")
        return EXIT_INCOMPLETE if incomplete else EXIT_EMPTY

    if incomplete:
        # Emitted anyway: the caller needs the partial text for the audit
        # trail, and the exit code is what stops it being read as complete.
        sys.stderr.write(
            f"error: reply is incomplete — finish_reason={finish_reason!r} "
            "(expected one of " + ", ".join(sorted(chat.COMPLETE_FINISH_REASONS)) + "); "
            "the text on stdout is a partial reply\n"
        )
        _emit(reassembled)
        return EXIT_INCOMPLETE

    _emit(reassembled)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
