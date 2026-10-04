# HARNESS_INFERENCE_DRIVER_PLAN.md — a harness-headless inference driver for the build

**Status: parked. Blocked until the inference passes reach their final shape.** Problem and
constraints only; no design.

## The problem

A build's every model call is one tool-less chat-completions request to the server the environment
names, and a build that will spend inference refuses before its first stage when the environment
names none (`kb_tools/SPEC.md`, The Driver's Contract; `kb_tools/kb_driver/run.py`'s
`_require_server`, exit 14). So "clone, `just install <dir>`, get to work" holds only for a user who
also runs a local inference server. A user with a harness and a subscription — Claude Code's `claude
-p`, opencode's headless run — has a model and no way to spend it on a build.

The toolchain once had that route: the inference passes dispatched a seat through the harness
command line, with an agent definition as the system prompt. That path was deleted when the passes
moved to `inference.liaison_tools.call_chat` (`kb_tools/CONVENTIONS.md`, "A model call is
`inference.liaison_tools.call_chat` and nothing else" — "the CLI path this package deleted"). The
deletion was right for the reason given there: the call's bounds, tool set and model were the
harness's and the definition's, not anything the build states. What is wanted back is not that
path but a second **transport** behind the same seams, so a headless harness answers the same one-
letter asks the local server answers, with the same bounds.

## Constraints

- **Beside the local driver, not instead of it.** Local compute is a first-class deployment
  (`kb_tools/ROADMAP.md`, Policy direction). The harness transport is selected, never defaulted
  to, and a build with neither configured refuses as it does today.
- **One seam, two transports.** The claim-graph asks reach a model through `letters.LetterReader`
  (`kb_claimgraph/ask.py`, `ask_without_tools`) and the driver's own call through `call.Caller`'s
  injected `transport` (`kb_driver/call.py`). A harness transport plugs in there and nowhere else;
  no stage learns which transport answered it.
- **Same bounds as the local call.** Thinking off; one turn; no tools offered; no agents file or
  project instructions injected into the call — the settings fixes found when the path was last
  live, re-applied as the harness now spells them. A call that reads the consumer's `AGENTS.md` or
  `CLAUDE.md` judges on evidence the ask excludes.
- **The system prompt is the fragment, never a definition.** `reader-system` and `overview-system`
  (`kb_driver/prompt-templates/fragments/`) are what a call carries; a seat definition as system
  prompt is the deleted shape.
- **Contract first.** Two sentences forbid this today and must change before any code does:
  `kb_tools/SPEC.md`, The Driver's Contract — "Nothing a build runs spawns a process to obtain a
  model's answer" — and the `kb_tools/CONVENTIONS.md` rule quoted above. Behaviour routes SPEC →
  ARCHITECTURE → code; the CONVENTIONS rule is rewritten to name the one sanctioned spawn and the
  seam it sits behind.
- **Recoverable, not reinvented.** The deleted `claude` path is in this branch's unsquashed history;
  the design step starts by reading it back for the settings it needed, not by rediscovering them.
- **Measured like the local driver.** Whatever the transport returns must feed `letters.CallStats`
  (`kb_claimgraph/letters.py`) — wall time at least; token and cache figures where the harness
  reports them, `None` where it does not — so a build's `stage-*-asks` lines stay honest about what
  they could not measure.

## Why it is parked

The ask templates and the shortlist are still moving
(`ROADMAP_PLANS/UNMARKED_ASK_PRECISION_PLAN.md`, `ROADMAP_PLANS/ANAPHOR_SHORTLIST_HANDOFF.md`). A
transport built against a reader seam whose question shape is about to change is built twice. When
the passes settle, the design step is: name
the harness invocations and their flags per harness (`templates/harness/<name>.toml` is where a
per-harness spelling lives), decide how a build selects the transport without a config key that
duplicates the environment's, and show one bounded local build and one headless build producing
the same ledger shape.
