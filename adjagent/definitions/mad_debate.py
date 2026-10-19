"""mad-review and mad-design: the two commands that launch a debate, one per mode.

The modes diverge in two places beyond their nouns: design resolves its first token against a topic
library and review has none, and design's run name comes from the prose, after a topic, while
review's first token is the run name.
"""

from adjagent import clauses
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

_PREREQUISITES = """## Prerequisites

Before doing anything else, verify:
- `python3` is available (`command -v python3`)

If the prerequisite is missing, halt with an error."""

_PARSING_ARGUMENTS = """## Parsing Arguments

Parse the arguments as follows:"""

_KEYED_ARGUMENTS = """- **Seat roster** (`SEATS=`): the seats staffing this run — a comma-separated subset of `a`,
  `b`, `c`, `d`, `guest`, at most one of each, at least two. **Required.**
- **Env file** (`ENV_FILE=`): path to the guest model's env file (containing `API_BASE_URL=`,
  `API_KEY_FILE=`, and `MODEL=`). Required if and only if `SEATS=` includes `guest`.
- **Constraints doc** (`CONSTRAINTS=`): path to a requirements/invariants/conventions document.
  Optional."""

_REFEREE_REFUSES = """Settle the roster here, before dispatch. The referee has no default of its own and **will refuse to
run** on a roster-less invocation — as it will if `guest` is named without an env-file path."""

_RELAY_EXCEPTION = """The only exception: text explicitly marked as an aside to the referee with a `REFEREE NOTE:` prefix
(or equivalent unambiguous marker) is for the referee's consumption and is NOT relayed.

When confirming parsing to the user before dispatch, quote the substantive instruction text verbatim
so the user can inspect what will be relayed."""

DEFINITIONS = (
    Definition(
        name="mad-review",
        kind=Kind.COMMAND,
        body=f"""@{clauses.PROJECT_HARNESS_DIR}/agents/mad-review-referee.md
@{clauses.PROJECT_HARNESS_DIR}/agents/mad/participant-contract.md
@{clauses.PROJECT_HARNESS_DIR}/agents/mad-alignment-assessor.md

You are the MAD Review Referee. Start a multi-agent review debate.

{_PREREQUISITES}

{_PARSING_ARGUMENTS}
- **Review name**: the first token — a bare slug naming this review (`auth-flow`, `installer-rewrite`). It names the output folder and the documents. Review mode has no topic library: the first token resolves to no file, and the charter carries the whole methodology.
{_KEYED_ARGUMENTS}
- **Target** (`TARGET=`): path to the artifact under review (file or directory).
- **Remaining text**: free-form description of the review target, minus the `KEY=` tokens. The
  keyed forms win wherever present; extract from what remains only what they did not supply:
  - The review target and the constraints doc, when named in prose rather than by
    `TARGET=`/`CONSTRAINTS=`

### Seats are the invoker's call

There is no default roster. If the invocation names no seats, do not choose some — ask the user, and
**suggest `b` + `c` as a reasonable default for most review jobs**: two strong local
pins whose blind spots differ. Widen with `a` or `d` when the material rewards more independent looks; add `guest`
(with `ENV_FILE=`) to bring in a model from outside this harness.

{_REFEREE_REFUSES}

## Verbatim relay of instructions

The user's free-form instruction text — the substantive review charter — MUST be
passed through verbatim when dispatching every seat on the roster and the alignment assessor. Do not
summarize, reword, compress, or rephrase it, even when the meaning seems preserved. Paraphrasing
loses nuance and shifts emphasis in ways the user did not authorize and cannot inspect.

{_RELAY_EXCEPTION}

## Proceeding

Confirm your parsing of these inputs to the user before proceeding, then run the full MAD
review process.""",
    ),
    Definition(
        name="mad-design",
        kind=Kind.COMMAND,
        body=f"""@{clauses.PROJECT_HARNESS_DIR}/agents/mad-design-referee.md
@{clauses.PROJECT_HARNESS_DIR}/agents/mad/participant-contract.md
@{clauses.PROJECT_HARNESS_DIR}/agents/mad-alignment-assessor.md

You are the MAD Design Referee. Start a multi-agent design debate.

{_PREREQUISITES}

{_PARSING_ARGUMENTS}
- **Topic name**: the first token — matches a file in `{clauses.PROJECT_HARNESS_DIR}/agents/mad/design-topics/[topic-name].md`. Load that file as the topic. If the file does not exist, list available topics from `{clauses.PROJECT_HARNESS_DIR}/agents/mad/design-topics/` and halt.
{_KEYED_ARGUMENTS}
- **Target** (`TARGET=`): path to the problem statement. Either (a) an existing brief defining the open problem (file or directory), or (b) an empty/not-yet-created output location — in case (b) the referee will elicit the problem statement from the user interactively before dispatching participants.
- **Remaining text**: free-form description of the design target, minus the `KEY=` tokens. The
  keyed forms win wherever present; extract from what remains only what they did not supply:
  - The design target and the constraints doc, when named in prose rather than by
    `TARGET=`/`CONSTRAINTS=`
  - A short design name (for output folder and document titles) — this one has no key

### Seats are the invoker's call

There is no default roster. If the invocation names no seats, do not choose some — ask the user, and
**suggest `b` + `c` as a reasonable default for most design jobs**: two strong local
pins whose blind spots differ. Widen with `a` or `d` when the problem rewards more independent constructions; add `guest`
(with `ENV_FILE=`) to bring in a model from outside this harness.

{_REFEREE_REFUSES}

## Verbatim relay of instructions

The user's free-form instruction text — the substantive design brief — MUST be
passed through verbatim when dispatching every seat on the roster and the alignment assessor. Do not
summarize, reword, compress, or rephrase it, even when the meaning seems preserved. Paraphrasing
loses nuance and shifts emphasis in ways the user did not authorize and cannot inspect.

{_RELAY_EXCEPTION}

## Proceeding

Confirm your parsing of these inputs to the user before proceeding, then run the full MAD
design process.""",
    ),
)
