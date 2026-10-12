"""guest-start and guest: the two commands that open and continue a guest-model session through the
guest liaison, and relay its return to the user untouched.
"""

from adjagent import text as t
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

_LOAD_LIAISON = """@{harness_dir}/agents/guest-liaison.md"""

_PREREQUISITES_LEAD = """## Prerequisites

Before doing anything else, verify:"""

_RELAY_DISCIPLINE = """Relay everything the liaison returned, verbatim — the guest's response and every warning, error, refusal, round-cap report or note it emitted alongside.

**Your entire message this turn is that return and nothing else**: no preface, no closing line, no addition of your own, and no offer to supply one. That covers summarising it, evaluating it, noting what it asserted, comparing it to anything else, and supplying a fact it omitted. Volunteering a reading is not help, it is standing over the user's shoulder; offer yours when asked for it.

This holds most where it is hardest. The guest may be underpowered, out of date, or confidently wrong — still not your cue. And the reverse is the same intrusion wearing a compliment: that it held its ground, that it agrees with you, that it caught something."""

DEFINITIONS = (
    Definition(
        name="guest-start",
        kind=Kind.COMMAND,
        body=rf"""{_LOAD_LIAISON.format(harness_dir=t.PROJECT_HARNESS_DIR)}

You are starting a new guest-model session via the `guest-liaison` subagent.

{_PREREQUISITES_LEAD}
- `python3` is available (`command -v python3`)
- The `guest-liaison` subagent contract was loaded above

If a prerequisite is missing, halt with an error listing what is missing.

## Parsing Arguments

Parse `$ARGUMENTS` as follows:
- **Topic name**: the first whitespace-delimited token. If empty, halt with:
  `"Usage: /guest-start <topic>"`.
- Reject topic names containing `/`, `\`, leading dots, or whitespace. If invalid, halt with a
  diagnostic.

## Pre-flight Checks

1. If `guest-session/<topic>/messages.json` exists and is non-empty, ask the user whether to
   **resume** the existing session or pick a different topic name. If the user chooses resume, skip
   system-prompt collection in step 4 and skip the initial-message step (the session already has its
   first user turn).

2. If `guest-session/active-topic.txt` exists and names a different topic, warn the user that
   switching will redirect `/guest` away from the prior session. Confirm before continuing. The
   prior session's directory is preserved either way; only the active-topic pointer changes.

## Onboarding

3. Collect connection parameters from the user:
   - `API_BASE_URL` — e.g. `https://api.example.com/v1`
   - `API_KEY_FILE` — path to a file containing only the API key (entire content trimmed of
     leading/trailing whitespace, no internal whitespace). **Do not read or display this file's
     contents** — only confirm presence with `test -f`.
   - `MODEL` — the model identifier
   - `READ_ROOT` — optional; the directory every file request from the guest model is bounded to.
     Offer the project root as the default, or a narrower corpus directory if the user names one.

4. **New session only** — collect the system-prompt source:
   - **Agent identity**: a path under `{t.PROJECT_HARNESS_DIR}/agents/` (e.g.
     `{t.PROJECT_HARNESS_DIR}/agents/applied-mathematician.md`). The liaison will extract the
     definition's body, frontmatter stripped.
   - **Default**: if the user declines to pick an agent, the liaison will use the literal string
     `You are a helpful assistant.`

5. **New session only** — collect the **initial message** to send to the guest model.

## Persist Session State

6. **Ignore `guest-session/` before creating it.** If the project root's `.gitignore` has no
   `guest-session/` line, append one; if there is no `.gitignore`, create it holding that line. Tell
   the user which of the three happened — appended, created, or already present. `messages.json` is
   a plaintext record of everything relayed to the third-party endpoint and `params.env` carries the
   base URL and the key-file path; neither is ever committed.

7. Create the session directory: `mkdir -p guest-session/<topic>/tmp`.

8. Write the connection params to `guest-session/<topic>/params.env` as KEY=VALUE lines (one per
   line, no quoting, no secrets — only the API key file *path*, which is not itself a secret):

   ```
   API_BASE_URL=<url>
   API_KEY_FILE=<path>
   MODEL=<model>
   READ_ROOT=<path>
   ```

   If the user picked an agent identity, append `SYSTEM_PROMPT_AGENT=<path>` on a further line.
   Otherwise omit (default identity is implied).

9. Write `<topic>` to `guest-session/active-topic.txt` (overwrite any existing pointer).

## Dispatch

10. Invoke the `guest-liaison` subagent. Pass it:
   - Session topic
   - `API_BASE_URL`, `API_KEY_FILE`, `MODEL`, `READ_ROOT`
   - System-prompt source (agent path or literal default)
   - Initial user message (skip if resuming)

11. {_RELAY_DISCIPLINE}""",
    ),
    Definition(
        name="guest",
        kind=Kind.COMMAND,
        body=f"""{_LOAD_LIAISON.format(harness_dir=t.PROJECT_HARNESS_DIR)}

You are continuing the active guest-model session via the `guest-liaison` subagent.

{_PREREQUISITES_LEAD}
- `guest-session/active-topic.txt` exists. If missing, halt with:
  `"No active guest session — run /guest-start <topic> to begin."`
- The `guest-liaison` subagent contract was loaded above.

## Resolve Active Session

1. Read `guest-session/active-topic.txt` to obtain `<topic>`. Strip surrounding whitespace.

2. Verify `guest-session/<topic>/messages.json` exists and is non-empty. If missing, halt with:
   `"Active topic '<topic>' has no session log at guest-session/<topic>/messages.json — run /guest-start <topic> to initialize."`

3. Read connection params from `guest-session/<topic>/params.env`. Expected keys: `API_BASE_URL`,
   `API_KEY_FILE`, `MODEL`, optionally `SYSTEM_PROMPT_AGENT`. Treat `API_KEY_FILE` as an opaque path
   — do not read its contents. If the file is missing or any required key is absent, halt with a
   diagnostic asking the user to re-supply via `/guest-start <topic>`.

## Parsing Arguments

4. The full `$ARGUMENTS` string (all tokens, joined) is the user's message to the guest model. If
   empty, halt with: `"Usage: /guest <message>"`.

## Dispatch

5. Invoke the `guest-liaison` subagent in **continuation mode**. Pass it:
   - Session topic (`<topic>`)
   - `API_BASE_URL`, `API_KEY_FILE`, `MODEL` (from params.env)
   - User message (from `$ARGUMENTS`)

   The liaison will detect the existing `messages.json`, append the user message as a new turn, send
   to the guest model, service any file or tool requests, and return the substantive reply.

6. {_RELAY_DISCIPLINE}""",
    ),
)
