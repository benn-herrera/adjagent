# SPEC – liaison_tools

`liaison_tools/` is the shipped package of helpers that let an agent relay a conversation with an
external, non-Claude model without that model's credentials or wire protocol ever entering the
agent's own context. This document states the observable contract each helper holds today,
independent of how it is implemented — see ARCHITECTURE.md for mechanism. **Draft status**:
distilled from the code, not yet ruled. Where a behaviour is left open, an "Unspecified" note says
so rather than assert a guarantee.

This document specializes root `SPEC.md`'s "Deployed Surfaces" (shipped-package class) for this
package specifically; on any conflict, the root document governs and this one is the defect.

## Components

| Command | Contract role |
|---|---|
| `post-openai.py` | The wire transport: one OpenAI-compatible chat-completions call, SSE-streamed, reassembled to a canonical stdout shape. |
| `msg-util.py` | The sole sanctioned mutator of a messages-file: `init` / `append` / `validate`. |
| `relay-driver.py` | A scripted corpus-relay eval instrument, invoked directly rather than by a liaison agent. |

One module is imported rather than invoked: `openai_chat`, the chat-completions request
`post-openai.py` is built on, for a caller that wants it in-process (Importable Request, below).

**Runtime requirement.** A consumer needs a `python3` on `PATH` and nothing else — no install step
is ever a precondition for these commands running.

## Wire Transport (`post-openai.py`)

**Invocation.** `post-openai.py [--allow-http] [<messages.json>]`, parameterised by environment
variables. The messages-file path is required by one of two routes, and `MESSAGES_FILE` wins when
both are given. A missing or malformed parameter is a usage error, exit 1.

| Variable | Required | Value | Default |
|---|---|---|---|
| `API_BASE_URL` | yes | OpenAI-compatible base URL, under the transport rules below | — |
| `API_KEY_FILE` | yes | path to the key file (API Key Handling, below) | — |
| `MODEL` | yes | model id (Model resolution, below) | — |
| `MESSAGES_FILE` | one route | the messages-file path | — |
| `ALLOW_HTTP` | no | exactly `1` opts in to plaintext http to a non-loopback host; `--allow-http` is the same opt-in, and either alone suffices | unset |
| `MAX_TOKENS` | no | integer, sent as `max_tokens` | `32768` |
| `ENABLE_THINKING` | no | `true` in any case enables and any other value disables; sent as `chat_template_kwargs.enable_thinking` | `true` |
| `TEMPERATURE` | no | plain decimal in [0.0, 2.0] | `1.0` |
| `DEBUG_POST` | no | `true` in any case writes the request payload to stderr | off |
| `DEBUG_RESPONSE` | no | `true` in any case writes the raw SSE stream and the reassembled output to stderr | off |
| `USAGE_STATS_FILE` | no | path for the usage side channel (below) | unset |

**Output contract.** On success, stdout carries exactly one of two shapes: the reassembled response
text, or `TOOL_CALLS\n<json>` where `<json>` is an ordered array of
`{"id", "type", "function": {"name", "arguments"}}` objects. Nothing else is ever written to stdout;
warnings and errors go to stderr only.

**Exit codes** — the contract a caller branches on:

| Code | Meaning | Caller obligation |
|---|---|---|
| 0 | A complete reply; stdout carries the output contract above. | Treat as substantive. |
| 1 | Usage, configuration, or transport failure. | Retryable. |
| 3 | The endpoint completed the call but the reply is incomplete (`finish_reason` is not `stop`, `tool_calls`, or `function_call` — e.g. `"length"`). Whatever arrived is still written to stdout for the audit trail. | Never record as complete; never retry the identical request — retrying will not help. |
| 4 | The endpoint returned an empty completion with a normal finish reason — a protocol-level empty result, not a transport failure. stdout is empty. | Never retry the identical request. |

Exit 3 and 4 are protocol events, not transport failures — a caller retries neither, but both still
append to `USAGE_STATS_FILE` when it is set, because the tokens were spent regardless of the reply's
usability.

**Transport rules that protect the API key** (see also API Key Handling, below):
- `API_BASE_URL` must be `https`, except for loopback hosts (`localhost`, `127.0.0.1`, `::1`), where
  `http` is accepted for local inference, or any host when `ALLOW_HTTP=1` or `--allow-http` is given
  — an explicit, off-by-default opt-in for an operator who knows their endpoint is on a trusted
  private network.
- Redirects are never followed. A `3xx` from the endpoint is a hard error naming the refused target,
  because following it would carry the `Authorization` header — and with it the key — to whatever
  host the `Location` header names.

**Model resolution.** If a request fails with what looks like a model-not-found error, the script
queries `GET /models` and retries once against an exact or unambiguous-substring match, emitting a
warning either way. This retry consumes a second live call; it is not a dry-run check.

**Usage side channel.** When `USAGE_STATS_FILE` is set, one JSON line —
`{"prompt_tokens", "completion_tokens", "total_tokens", "model"}`, fields `null` where the endpoint
omitted them — is appended per successful call (any of exit 0, 3, or 4). A write failure there is a
stderr warning only and never fails the transport call itself. This channel never carries key
material, and nothing about it reaches stdout.

**Unspecified:** behaviour on a key file containing non-whitespace control bytes, beyond the
internal-whitespace check (API Key Handling). The model-resolution query is made once, and a
transient failure of that query is not retried.

## Importable Request (`openai_chat`)

`liaison_tools.openai_chat` makes the request `post-openai.py` makes, for a Python caller with
`liaison_tools`' parent directory on its import path. Stdlib only, like every command here.

- **One request, no tools.** `post_chat_streaming` POSTs one SSE-streamed request to
  `<base_url>/chat/completions` carrying the caller's messages, model, `max_tokens`, temperature
  and, where given, `chat_template_kwargs.enable_thinking`; `include_usage` adds
  `stream_options.include_usage`. No `tools` are ever offered. It returns the parsed chunks, their
  payloads verbatim, the raw text and one of four stream statuses: clean, failed before any data,
  a mid-stream error event, or ended short of `[DONE]`.
- **The key is a value.** Every request takes it from the caller, and the module reads no
  environment variable. `read_api_key` reads it from a key file by the rule API Key Handling
  states, returning nothing for a missing file or an invalid key. The transport rules above hold for every request it makes: no redirect is followed,
  and `validate_base_url` is the https-or-loopback check, its http opt-in the caller's argument.
- **The reply's reading is shared with the command.** `reassemble_stream` gives the stdout
  contract's text, `reassemble_content` the content text alone whatever tool call rode beside it,
  and `classify_reply` complete, incomplete or empty by the same `finish_reason` rule as exits 0, 3
  and 4.
- **One embeddings batch.** `post_embeddings` POSTs the caller's model and texts to
  `<base_url>/embeddings` and returns one vector per text, in the order given. A reply carrying
  any other number of vectors is an error, as is a transport or HTTP failure; both raise.
- Diagnostics go to stderr only, never stdout.

## API Key Handling

`API_KEY_FILE` names a file whose entire content, leading/trailing whitespace trimmed, is the key.
The key is invalid — a usage error, exit 1 — if it is empty after trimming or contains any internal
whitespace.

- The key is never placed on a command line or in an environment variable, so it is not exposed
  through `argv` or through process-environment inspection.
- The key leaves process memory only as the `Authorization: Bearer <token>` header, sent on the
  `/chat/completions`, `/models` and `/embeddings` requests over the transport rules stated above
  (https-or-loopback, no redirects followed). No command in this package writes key material to
  stdout, stderr, a messages file, a usage file, or `relay-driver.py`'s output directory.
- `openai_chat` takes the key as a value from its caller and holds the previous bullet for it:
  where that caller got the key is the caller's to state, unless it read the key with
  `read_api_key`.

## Messages-File Format and Legal Mutations (`msg-util.py`)

**Format.** A messages file is a JSON array of turn objects
`{"role": <string>, "content": <string>}`. A well-formed session (checkable by `validate`)
additionally requires: the array is non-empty, every turn's `role` is one of `system`, `user`,
`assistant`, every turn's `content` is a string, and turn 0's role is `system`.

**The three modes are the only legal mutations:**
- `init --system-prompt=<file> --instructions=<file> <messages.json>` — overwrites the target
  unconditionally with exactly a 2-turn array:
  `{"role": "system", "content": <system-prompt file content>}`, `{"role": "user", "content": <instructions file content>}`.
- `append --role=<user|agent> <messages.json> <content-file>` — appends exactly one turn to the end
  of the array, `content` equal to the full content of `<content-file>`. `--role=user` maps to JSON
  role `user`; `--role=agent` maps to JSON role `assistant`. (`agent` is a CLI-only spelling — it
  never appears as a role value inside the file.)
- `validate <messages.json>` — reads only; exits 0 and prints `valid: <N> turns` for a well-formed
  session per the Format rule above, otherwise exits 1 with a diagnostic naming the specific defect
  (not valid JSON, wrong top-level type, empty array, a turn missing a legal role, non-string
  content, or turn 0 not `system`).

**Concurrency.** `init` and `append` are mutually exclusive on the same file: two concurrent
mutators never lose a turn, and one waits up to 10 seconds for the other before failing. A mutator
that dies mid-write leaves nothing behind that blocks the next one. A mutation creates
`<messages-file>.lock` beside its target and leaves it there; it is empty, and its presence says
nothing about whether a mutation is in progress. `validate` takes no lock and needs none: a reader
observes a messages file either as it was before a mutation or as it is after, in full, never partly
written. A scratch directory (`TMPDIR`) on a different filesystem from the target is refused rather
than degraded to a copy.

**Exit codes.** Unlike `post-openai.py`, `msg-util.py` carries only a binary contract: 0 is success,
any non-zero (in practice always 1) is failure — there is no finer-grained code for "usage error"
vs. "lock timeout" vs. "validation failure" beyond what the stderr text names. The help forms
(`help`, `-h`, `--help`) print the usage block and exit 1 like any other usage error.

**Unspecified:** turn `content` has no upper bound on size, `user`/`assistant` turns are not
required to alternate after the initial system turn, and the format carries no version — a caller
cannot distinguish "this file's shape predates a future format change" from "this file is simply
well-formed" beyond the fields checked above.

**Encoding is UTF-8, uniformly.** Every file all three modes touch — the system-prompt, instructions
and content files, and the messages file itself — is read and written as UTF-8 explicitly, so the
three modes cannot disagree about whether the same file is well-formed text on a platform whose
default encoding is something else. A source file that is not valid UTF-8 is a failure naming the
file, not a silent substitution.

## `relay-driver.py` — CLI Contract

`relay-driver.py` is invoked directly (not dispatched as an agent). Its contract:

- **Required flags:** `--corpus-root`, `--system-prompt`, one of `--question`/`--questions-file`,
  `--output-dir`.
- **Connection parameters** (`API_BASE_URL`, `API_KEY_FILE`, `MODEL`, and `post-openai.py`'s
  optional connection parameters) are inherited from the process environment, or injected via
  `--env-file` (`KEY=VALUE` lines). An `--env-file` may set only `API_BASE_URL`, `API_KEY_FILE`,
  `MODEL`, `ALLOW_HTTP`, `MAX_TOKENS`, `ENABLE_THINKING`, `TEMPERATURE`, `DEBUG_POST`,
  `DEBUG_RESPONSE` — any other key is a hard refusal naming the offending key(s), never a silent
  pass-through.
- **Path confinement is a trust boundary.** Every `READ`/`LIST`/`GREP` request the guest model
  issues must stay inside the corpus root, symlinks included; a path that cannot even be resolved
  (embedded NUL, over `PATH_MAX`) is refused the same way a traversal or symlink escape is. This
  holds per-file during a `GREP` walk as well, not only at the top-level path argument.
- **Output layout**, entirely under `--output-dir`:
  ```
  session/qNN/messages.json    full conversation (audit-permanent)
  session/qNN/usage.jsonl      USAGE_STATS_FILE side channel, one line per call
  session/qNN/tmp/             scratch (msg-util.py content files, TMPDIR)
  answers/qNN.md               the guest's FINAL report, or a liaison note if none was produced
  answers/stats.csv            per-question round trips, token totals, outcome
  ```
  This driver creates no files anywhere else.
- **Exit codes:** 0 if every question completed without a halting transport failure; 1 if any
  question halted the run (transport failure exhausted its retries — remaining questions are
  skipped); 2 for an argument error.

## Paths

`msg-util.py` and `post-openai.py` operate on whatever paths they are given and assume no directory
layout or file name. The one name derived from a given path is `<messages-file>.lock`, which a
mutation creates beside its target and leaves there (Concurrency, above). A caller chooses its own
session layout without touching this package.
