# README – Adjagent: An Agent and Command Set Generator

This repository generates agents rather than collecting them — a single-sourced generation system
paired with the multi-capability agent and command set it renders. Definitions are produced to
order: written as Python modules, tuned per model family, rendered into consuming projects that
commit the result and never edit it. The generator owns the guarantees — one source for every shared
span of text, additive-only model tuning, drift visible as the consumer's `git diff`; the rendered
set does the work — coder and platform specialists, multi-agent debate processes, knowledge-base
construction and tooling, guest-model liaisons.

## Usage

This section is for installing the product into your own project and using what it delivers. For
working on this repository itself, see Development, below.

### Agent sandboxing (recommended, not required)

Running a coding agent under your own account hands it your privileges, keys and remote credentials.
[agent-sandboxing/README.md](agent-sandboxing/README.md) presents one sandboxing approach. It is a
checklist with file and snippets for running an agent harness as a separate, unprivileged local
user. It's accident protection, not hack-proofing, but can prevent painful mishaps.

### Install

Requires **Python 3.11 or later** on the host (`python3` on `PATH`) — the tooling reads TOML with
the standard library's `tomllib`, which first shipped in 3.11.

Clone this repo anywhere, then install both deployed surfaces into the consuming project — from
**this** repo's root:

```sh
just install ~/projects/foo
```

That produces `agents/` and `commands/` inside `~/projects/foo/.claude/` in full: every definition,
the MAD design-topic set, `kb_tools/`, `liaison_tools/`, and the slash commands. The definitions are
rendered by that invocation and the tool packages are copied. Test suites and caches stay behind.
`--harness=opencode` installs into `.opencode/` instead (the harness's project directory;
`--subdir=` overrides). Every `--*` flag after the target forwards verbatim to
`python3 -m adjagent`, so tuning the render is one more flag, not a different command —
`just install ~/projects/foo --family=gemma-4` tunes the generated definitions for that model family
(see "Model Tuning" below).

The installed tree is **committed by the consuming project and not for local edit**. A change
request comes to this project, which evaluates it, implements it and makes it available to every
consumer; a consumer's own needs go in its `CONVENTIONS.md`. Every rendered file's first banner line
says so. Re-running the install overwrites the tree and removes definitions this project no longer
produces; the consumer's `git diff` is the review of what changed. Re-installing an unchanged
source changes nothing.

Claude Code reads agent and command definitions from `.claude/`; nothing outside `agents/` and
`commands/` is installed, so nothing else is visible to a session.

### Harness Agents File

The agent definitions assume a set of operator-level working rules, published as one definition
(`adjagent/definitions/harness_agents_file.py`) rendered per harness. Install it with
`just install-agents-file <dir> [harness]`, where `<dir>` is `~/.claude`, `~/.config/opencode`, or a
project root. The harness is inferred when `<dir>` is a harness's user-global directory; for a
project root (or anything else) name it: `just install-agents-file ~/projects/foo opencode`. The
directives live in `AGENTS.md`: into the harness's user-global directory the install writes the file
that harness reads there (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`); anywhere else it
writes `<dir>/AGENTS.md`, and for a harness that reads another name it creates that file as the
one-line redirect `@AGENTS.md` (Claude Code's `CLAUDE.md`), leaving an existing one alone. A
`CLAUDE.md` there holding anything else is refused with nothing written — move its content into
`AGENTS.md` and replace it with `@AGENTS.md` yourself.

The install replaces only the block between the `adjagent` marker lines and keeps everything outside
it; put your own rules outside the markers. Edits inside the block are not preserved. An absent file
is written whole. If the destination holds nothing but a single `@<path>` import, the install goes
into that target and leaves the redirect alone; a redirect to another redirect, or to a file outside
`<dir>`, is refused for you to merge by hand. A file without exactly one begin marker line followed
by one end marker line is refused with nothing written, as is any run while `adjagent/` has
uncommitted changes. A write that changes the file keeps one rolling `backup.<name>` of what it
replaced.

`agents/` and `commands/` are the two deployed surfaces install produces inside
`<project>/.claude/`; the catalogs below name entries by where they land there — every entry lives
under `agents/` unless noted as a command.

### Model Tuning

Model-specific defensive text is delivered through **overlay anchors and model families**. A
definition may expose an anchor at a spot where an observed failure mode needs a targeted note; with
no overlay for the anchor in the loaded family, it renders as nothing, so the base definitions are
identical to an anchor-free render. A family — a Python module under `adjagent/families/`, one per
model family, fields documented in the docstring of `adjagent/family.py` — fills anchors:
family-wide `text`, with per-model overrides inside the same module. Resolution, not accumulation:
at most one overlay renders per anchor, model scope winning over family scope, and the filled text
renders verbatim in place with no lead-in or wrapper — an author who wants one writes it into the
overlay text. A family can never replace, suppress, or modify base text — it only fills anchors.

Tuned sets are rendered to order, typically out of repo, with `--family NAME`, where `NAME` is a
module name under `adjagent/families/` — a bare model name is not a family name, and a path is not
accepted. Two independent flags carry the tuning further: `--model-tier-map` overrides which family
member each tier is tuned against, and the optional `--model-pin-tier-alias-map` renders an alias in
place of each tier's member.
`just install <target> [--family=NAME] [--model-tier-map=SPEC] [--model-pin-tier-alias-map=SPEC] [--harness=NAME]`
applies the same mechanism to an install (see "Install" above) — every flag forwards verbatim to
`python3 -m adjagent`.

Authoring a new family, or extending an existing one, is repository work — see Development →
Authoring a Family.

### Coding Agent Set

* architect.md - architecture review and design
* security-reviewer.md - security-specific reviewer
* generalist-coder.md
* tech-writer.md - technical documentation author and review seat
* language-specific coders
  * c-coder.md
  * cpp-coder.md
  * go-coder.md
  * lua-coder.md
  * python-coder.md
  * rust-coder.md
  * shell-dsl-coder.md
  * typescript-coder.md
* platform-specific coders
  * android-app-expert.md
  * ios-app-expert.md
  * linux-app-expert.md
  * macos-app-expert.md
  * web-app-expert.md
  * windows-app-expert.md

Every definition in this catalog is **generated** — the coder and platform files, the MAD agent set,
all three kb definitions, the specialists, the liaisons, and every slash command. There are no
hand-maintained definitions and nothing to edit directly; see Development → Generated Definitions
for how a definition maps to its source module.

### Specialists
Single-purpose agents invoked directly for non-coding work.
* prose-architect.md - rhythm and structural review of long-form prose
* marketing-comms-expert.md - messaging, positioning, copywriting, competitive framing
* biz-dev-strategist.md - business strategy, market analysis, GTM, monetization
* applied-mathematician.md - rigorous derivation, model construction, dimensional analysis, claim
  classification (identity / manifestation / consistency check / derived prediction). Takes given
  axioms at face value and derives consequences honestly. Use when working inside a formal system —
  established, novel, or mid-construction — and the task requires careful step-by-step reasoning
  rather than retrieval of textbook results.
* economic-historian.md - stress-tests historical claims, analogies, and "laws of history" against
  the record; the history lens in an adversarial panel
* literature-scout.md - finds the citations a manuscript should include, especially the omissions a
  referee would flag; verifies real references via web search rather than inventing them
* theoretical-economist.md - stress-tests production/growth, market-structure, and mechanism-design
  claims; the economics lens in an adversarial panel
* prompt-engineer.md - authors and revises model-facing text: agent definitions, commands, skills,
  definition bodies, model-tuning overlay entries, agent-facing docs.

### Multi-Agent Debate Agent Set
Uses Multi-Agent Debate Process. Two modes share the same participants but use different referees;
only design mode carries a topic library:
* **Review mode** — adversarial assessment of an *existing* artifact (architecture, code, math,
  agent definitions).
* **Design mode** — constructive proposal for an *open problem* (derivations, software designs,
  hardware designs, other problem-solving).

Both modes' liaison plumbing (`liaison_tools/`, shared with Guest Liaison below) is documented under
Development → Liaison Tooling.

#### Shared Agents
* mad/participant-contract.md - the model-neutral participant contract (reviewer in review mode,
  proposer in design mode); the body a guest model receives as its system prompt
* mad-participant-fable.md, mad-participant-opus.md, mad-participant-sonnet.md,
  mad-participant-haiku.md - the same contract as dispatchable agents, one per model pin; a run
  draws its participants from different pins so their blind spots differ
* mad-guest-liaison.md - a liaison that can loop in an external model via API base url, key, and
  model name
* mad-alignment-assessor.md - only assesses alignment/disagreement among participants

#### Review Mode

* mad-review-referee.md - runs multi-agent debate review process
* commands
  * mad-review.md - initiates a review process. you must provide:
    * a review name — a bare slug naming the output folder and documents; review mode has no topic
      library, so the invoker's charter carries the methodology
    * a seat roster (`SEATS=`) — comma-separated subset of `fable`, `opus`, `sonnet`, `haiku`,
      `guest`; at most one of each, at least two. No default: a roster-less invocation is refused.
      `opus,sonnet` is a reasonable pick for most review jobs. A `guest` seat additionally requires
      `ENV_FILE=` (path to the guest model's env file)
    * \[optional\] a requirements/constraints doc (e.g. coding invariants, math invariants, etc.)
    * a review target (path to document, file, or hierarchy)
* process
  * /mad-review \[your specifics\]
  * referee launches agents and reviews/debate/resolution occurs
  * output is a directory `./mad-review/<review-name>/` of documents containing
    * summary doc - burndown list, unresolved conflicts, resolved conflicts
    * audit trail of debate process and outcomes
    * all artifacts, temporary or otherwise, are produced under the review work directory
  * round cap: 5
  * examples
    * ```/mad-review src-review SEATS=opus,sonnet,guest ENV_FILE=~/.config/guest.env CONSTRAINTS=CONVENTIONS.md TARGET=src/ **IGNORE `src/third_party`**```

#### Design Mode

* mad-design-referee.md - runs multi-agent debate design process
* commands
  * mad-design.md - initiates a design process. you must provide:
    * a topic from .claude/agents/mad/design-topics/
      * architecture.md
      * math-derivation.md
      * ml-engineering.md (more topics can be added: software-design, hardware-design, etc.)
    * a seat roster (`SEATS=`) — same contract as review mode: subset of `fable`, `opus`, `sonnet`,
      `haiku`, `guest`, at most one of each, at least two, no default; `guest` requires `ENV_FILE=`
    * \[optional\] a requirements/constraints doc
    * a problem statement: either (a) a path to an existing brief defining the open problem, or (b)
      an empty/not-yet-created output location — in case (b) the referee elicits the brief from the
      user via interactive dialogue before dispatching participants
* process
  * /mad-design \[your specifics\]
  * referee launches agents and proposals/debate/convergence occurs
  * output is a directory `./mad-design/<design-name>/` of documents containing
    * SOLUTION.md - the constructed solution with full provenance (which participant proposed what,
      where it survived/failed), or a convergent under-determination diagnosis, or preserved
      candidates if unresolved
    * audit trail of debate process and outcomes
    * all artifacts, temporary or otherwise, are produced under the design work directory
  * round cap: 10 (construction is iterative; converging two independently-built proposals takes
    longer than retiring a list of flaws)
  * convergence criteria
    * **algebraic**: all participants reach the same closed-form result modulo trivial reformulation
    * **multi-path**: participants reach the same numerical answer via demonstrably independent
      paths (treated as strong-positive; multiple independent constructions reaching the same answer
      is mutual reinforcement)
    * **under-determined**: all participants converge on the same diagnosis of why the problem
      cannot be closed from the supplied axioms, identifying the specific missing
      axiom/principle/input
    * **unresolved**: candidates preserved for human arbitration if no convergence within round cap
  * examples
    * ```/mad-design math-derivation SEATS=fable,opus,sonnet CONSTRAINTS=SPEC.md TARGET=mad-design/my-derivation/```

### Guest Liaison

`guest-liaison.md` relays a multi-turn conversation between you and an external "guest" model
accessed via an OpenAI-compatible API. Distinct from `mad-guest-liaison.md`, which is the
MAD-process-only variant invoked by referees inside review/design debates. Both share
`liaison_tools/` (Development → Liaison Tooling).

Properties of the relay:
* **Verbatim relay** of the system prompt and each user message — no summarizing, paraphrasing, or
  topic-tailoring. Verified post-write by `diff` against the source; the liaison aborts before
  sending if the diff is non-empty.
* **Secrets containment** — the API key lives in a file read directly by `post-openai.py`. The
  liaison treats the file path as opaque and is forbidden from reading the contents.
* **Audit-permanent session log** — every turn (system, user, agent) is appended to
  `guest-session/<topic>/messages.json` and never deleted.
* **File and tool-call services** — when the guest model asks for a file's contents or emits a tool
  call, the liaison reads the file (using a fixed `Here is the content of <path>:` frame) or returns
  a "not available in this environment" stub, then re-invokes the model.

#### Slash commands

* `/guest-start <topic>` — initiate (or resume) a session: onboarding, persist session state, send
  the first user message, return the guest's reply.
* `/guest <message>` — append `<message>` as the next user turn in the active session and return the
  guest's reply.
* `/guest-end` — clear the active-topic pointer (`guest-session/active-topic.txt`). The session
  directory itself is preserved as audit history.

#### `/guest-start` arguments

`/guest-start` takes one argument: the **topic slug**, which names the session directory under
`guest-session/`. It must contain no path separators, leading dots, or whitespace.

Everything else is collected interactively after the command starts:

* `API_BASE_URL`, `API_KEY_FILE`, `MODEL` — the connection parameters. `API_BASE_URL` is the **API
  root**, not the chat-completions endpoint — `post-openai.py` appends `/chat/completions` itself.
  (Including `/chat/completions` in the URL produces a doubled path and a 404.)
* **System prompt source** *(new session only)* — either a path to an agent definition under
  `.claude/agents/` whose body (frontmatter stripped) is sent verbatim as the guest model's system
  prompt, or, if you decline to pick one, the literal default `You are a helpful assistant.` The
  agent body is not a Claude-only artifact — any agent body that reads as a coherent instruction set
  works (e.g. `applied-mathematician`, `architect`, `tech-writer`).
* **Initial message** *(new session only)* — the first prompt sent to the guest model.

The collected connection parameters are persisted to `guest-session/<topic>/params.env` so `/guest`
can reuse them on later turns.

#### API key file format (the file at `API_KEY_FILE`)

The file contains only the API key. Its entire content, with leading and trailing whitespace
trimmed, is the key; the key must contain no internal whitespace.

The liaison never reads this file. `post-openai.py` reads the key directly — the key does not appear
in argv, env, transcripts, or any tool output the liaison sees.

#### Session directory layout

```
guest-session/
  active-topic.txt              # one line: the currently active topic slug
  <topic>/
    messages.json               # full conversation (system + user + agent turns); permanent audit
    params.env                  # API_BASE_URL, MODEL, API_KEY_FILE, SYSTEM_PROMPT_AGENT
    tmp/                        # mktemp scratch space; safe to leave between turns
```

`guest-session/` is in `.gitignore` so audit logs and `params.env` (which references local API key
file paths) do not leak into commits.

#### Resuming and switching topics

Re-running `/guest-start` with an existing topic slug offers to resume — the prior `messages.json`
is preserved and new turns continue from it. To switch active sessions without deleting either, run
`/guest-end` then `/guest-start` with the new topic; both session directories survive.

#### Example

```
/guest-start solar-system
/guest how long does light take to get from the sun to the earth?
/guest now compute the same for Proxima Centauri.
/guest-end
```

### Knowledge Base Agent Set

Agents and portable tooling for building, navigating, and maintaining a knowledge base — a
navigable, verbatim Markdown distillation of a canonical corpus with a queryable claim-graph
metadata spine. All three kb-* definitions are project-portable: per-project facts live in the
consuming project's `kb-root/AGENTS.md`, not in the definitions. All three are **generated** from
their definition modules.

A build derives the KB from the LaTeX corpus, and the corpus is the only thing that exists at that
point. Once you have edited the KB by hand — a leaf's prose, a claim minted or wired — that work
exists nowhere else, and a fresh build over the same `kb-root/` would overwrite it. Point a fresh
build at a KB you have been working in and you lose the work; continue an interrupted one and you do
not.

* Using/navigating a knowledge base
  * kb-docent.md
  * commands/ - custom slash commands
    * kb-start.md (/kb-start)
    * kb-next.md  (/kb-next)

* Building/Modifying Knowledge Base
  * commands/ - custom slash commands
    * kb-build.md (/kb-build) - launches a build in the background, relays its status changes, and
      consumes the driver's relay card when it stops
  * kb_tools/kb_driver - the builder itself: walks a static step table, dispatches each row to the
    seat it names, and exits at a barrier rather than asking
  * kb-claim-scorer.md - grades written derivations; returns judgments and writes nothing
  * kb-maintainer.md - the write side: leaf edits, claim-graph wiring, refresh→verify loop

#### KB toolchain

`kb_tools/` is the stdlib-only, zero-config Python toolchain the kb agents drive — see
[kb_tools/CONVENTIONS.md](kb_tools/CONVENTIONS.md) for the full picture. An install delivers it to
`.claude/agents/kb_tools/`, which is the path the definitions and the runner snippets name. A
consuming project:

1. Installs `.claude/agents` as in [Install](#install) and keeps its KB in `kb-root/` at the repo
   root — the tools self-anchor by walking up from the cwd to `.git` and requiring `kb-root/` beside
   it.
2. Installs the runner targets once, from the project root:
   `PYTHONPATH=.claude/agents python3 -m kb_tools.kb_util install-targets` — this adds a single
   non-fatal include line to the project's justfile or Makefile.
3. Uses `just`/`make` `kb-verify`, `kb-refresh`, and `kb-stats` from then on.

## Development

This section is for working on this repository itself — the generator, its definitions, and the
shipped tool packages. If you are installing the product into a project, see Usage, above.

### Repository Layout

```
adjagent/                 the generator and every definition, run as `python3 -m adjagent`
  clauses.py              shared text: named string constants, small functions for slotted text
  definitions/            one module per definition, or per set that shares text and ships together
  harnesses/              one module per harness (claude, opencode), each defining HARNESS
  families/               one module per model family, each defining FAMILY
devtools/render_diff.py   compares two rendered slots by text; reads only rendered output
rendered/                 gitignored build product — `just render [slug]` puts a render here per
                          slot; the three `reference*` slots are the baseline `just render-diff`
                          compares against, written only by `just retake-reference`
ROADMAP_PLANS/            tracked home for planned work not yet ready to execute
```

In `adjagent/`, a definition module registers by existing in `definitions/`; its `kind` and
`folder` decide where it lands. Mechanism is in the package and module docstrings, and in
[ARCHITECTURE.md](ARCHITECTURE.md).

`agents/` and `commands/` are not directories in this repository. They are the two deployed surfaces
of the *product*, produced into `<project>/.claude/` by an install (or into `rendered/` by
`just render`), and the catalogs in Usage name entries by where they land there: every entry lives
under `agents/` unless noted as a command.

Project docs: [THESIS.md](THESIS.md) — purpose and intent, [SPEC.md](SPEC.md) — observable contract,
[ARCHITECTURE.md](ARCHITECTURE.md) — how the mechanism works, [CONVENTIONS.md](CONVENTIONS.md) —
house rules. [ROADMAP.md](ROADMAP.md) tracks open follow-on work, outside this set.

### Working In This Repo

A definition is `adjagent/definitions/<name>.py`: a `DEFINITIONS` tuple whose `body` is the rendered
text with holes, read top to bottom as the file it renders.

* A definition's own prose is in its module. Shared text is a named constant in
  `adjagent/clauses.py`, or a private constant of a group module whose definitions ship together.
* To change what shared text says for every definition, edit the constant; to change it for one,
  edit that definition's module.
* To see what a change does, run `just render`, then `just render-diff`. An unknown placeholder
  fails at render; a definition module holding anything but imports, string constants and
  `DEFINITIONS` fails the suite.
* The gate is `just test-changed`. Run `just retake-reference` only after a content change is
  accepted; it re-takes the baseline slots `render-diff` compares against.

Other targets: `just render [slug]` renders the full install product into `rendered/<slug>/` (slug
defaults to `latest`), plus the harness agents file under `rendered/<slug>/harness/<name>/` — Claude
Code's `CLAUDE.md` by default, or another harness's with `--harness=NAME`. A slug starting with
`reference` is refused. `just render-diff [a] [b]` compares two slots — reference against latest by
default — by text, with each file's banner replaced by one constant line, and reports differences
without failing on them. `just test` runs the full tooling test suite (the `kb_tools`,
`liaison_tools`, `adjagent` and `dupe_sweep` surfaces, auto-provisioning a `.venv`).
`just test-changed [base]` runs only the surfaces the uncommitted tree (plus, given `base`, the
commits since it) touches, and says which paths chose each.

### Authoring a Family

A family is a module under `adjagent/families/` defining `FAMILY`; the fields, and how tiers, member
overrides and `--model-tier-map` interact, are in the docstring of `adjagent/family.py`.

The mechanism is a response to a real phenomenon: agent definitions tend to accumulate defensive
language that's keyed to the *specific* model they were tested against. Defensive clauses that
*protect* one model can *smother* another — same clause, opposite effect, no error event. (Example:
probe data from 2026-04-29 showed Gemma 4 31B-it silently filling axiom gaps with textbook
conventions, while Gemini 3.1 Pro spontaneously surfaced the same gaps. A "do not fill gaps" clause
helps the first model and slows the second.)

The operating rule when porting an agent definition to a new model: **strip first, observe, patch.**
Run the base definitions with the new model on a known-shape probe set. Watch for failure modes;
only then author an anchor and an overlay targeted at the failure modes you actually observed.
Anchors are never pre-sprinkled speculatively. Heavy scaffolding hides the model's true tendencies;
you can't engineer for failure modes you never see.

When adding defensive clauses, record *what tendency the clause was added to correct, against which
model*. Without that record, future maintainers can't distinguish "still load-bearing" from "residue
from a model we don't use anymore." Comment overlays like code: not what the overlay says, but why
and against which observed behavior it was added.

(The earlier delivery vehicle — a parallel per-model definition file, e.g.
`applied-mathematician-strict.md`, a gap-aversion variant built for running the math agent on Gemma
4 — was retired 2026-08-21; the anchor mechanism replaces whole-definition forks.)

### Generated Definitions

Every definition in the Usage catalogs — the coder and platform files, the MAD agent set, all three
kb definitions, the specialists, the liaisons, and every slash command — is **generated**. There are
no hand-maintained definitions and nothing to edit directly in a rendered tree; the source is the
definition's module (see "Working In This Repo"). A rendered file carries a two-line banner inside
its frontmatter: a generated-from line naming its definition module and stating that the file is not
for local edit, and a tuning line recording the family, seat, tier map and harness it was rendered
for. There is no content hash; consuming projects track the rendered output, and their `git diff` is
the drift check. See [CONVENTIONS.md](CONVENTIONS.md#adding-definitions) for how to add one.

### Liaison Tooling
`liaison_tools/` contains the helpers used by both `mad-guest-liaison.md` (MAD process) and
`guest-liaison.md` (general guest-model sessions); an install delivers it to
`.claude/agents/liaison_tools/`, which is the path the definitions name. The liaison agents are the
primary callers; MAD referees set `TMPDIR` for liaison invocations to keep `mktemp` output contained
in the review/design directory.
* `post-openai.py` - posts a message history to an OpenAI-compatible API and prints the assistant
  reply. Reads the API key from a file so it never enters argv or env.
* `msg-util.py` - the only sanctioned path for creating or mutating the messages JSON (init / append
  / validate). Use this rather than ad-hoc jq or sed.
* `relay-driver.py` - the corpus-relay eval instrument: runs budgeted, fresh-history Q&A sessions
  against a guest model over a read-only corpus, appending its own READ/LIST/GREP relay protocol
  block to the caller's system prompt (callers supply navigation doctrine only) and servicing
  exactly what it appended. Per-question sessions, answers, and a `stats.csv` with real token totals
  (via `post-openai.py`'s `USAGE_STATS_FILE` side channel) land under `--output-dir`. Sketch:
  `relay-driver.py --corpus-root kb-root --system-prompt scout.md --questions-file questions.md --output-dir eval-out --env-file guest.env` (single questions via `--question`
  or `--question-number N`).
* `tests/` - fixtures for the above scripts.

## Third Party Acknowledgements

The deployed runtime (`agents/`, `commands/`) is stdlib-only Python and shell with no third-party
dependencies. `pytest`, `black`, and `isort` are dev/test-only tools, installed into a local `.venv`
by the `just test` and `just format-python` recipes.

pandoc (John MacFarlane and contributors) and Graphviz `dot` (Graphviz authors) are run as external programs and are not bundled.
