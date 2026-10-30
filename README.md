# README – Adjagent: An Agent, Command and Skill Set Generator

This repository generates agents rather than collecting them — a single-sourced generation system
paired with the multi-capability agent, command and skill set it renders. Definitions are produced to
order: written as Python modules, tuned per model family, rendered into consuming projects and never
edited there. The generator owns the guarantees — one source for every shared span of text,
additive-only model tuning, the whole tree regenerated on each install; the rendered set does the
work — coder and platform specialists, knowledge-base construction and tooling.

## Developer
<https://keyoxide.org/wkd/benn@bennherrera.dev>

## Usage

This section is for installing the product into your own project and using what it delivers. For
working on this repository itself, see Development, below.

### Agent sandboxing (recommended, not required)

Running a coding agent under your own account hands it your privileges, keys and remote credentials.
[agent-sandboxing/README.md](agent-sandboxing/README.md) presents one sandboxing approach. It is a
checklist with file and snippets for running an agent harness as a separate, unprivileged local
user. It's accident protection, not hack-proofing, but can prevent painful mishaps.

### Install

Base requirements: 

- **Python 3.11 or later** on the host (`python3` on `PATH`) — the tooling reads TOML with the 
  standard library's `tomllib`, which first shipped in 3.11.
- `perl` with core `JSON::PP` — optional, for the claude guardrail; without it the install
  skips that hook and installs everything else ([Guardrail](#guardrail)).

For the kb set (`just install-with-kb`):

- kbase 0.9.0 or later, installed by you — no install writes it. On macOS or Linux:
  `brew install benn-herrera/kbase/kbase`; `kbase --version` prints the bare version, and
  `brew upgrade benn-herrera/kbase/kbase` brings an older one up. The harness's `kbase` MCP entry
  runs the bare command `kbase`, so it has to be on `PATH`, and the MCP server has to be
  (re)started after an install or upgrade before its tools appear. Nothing checks the version.
  Native Windows is unsupported for the kb set for now. An agent session can walk you through all of
  this: the `kbase` skill's `references/installing.md`.
- pandoc 3.12 - LaTeX <-> Markdown, host tool, not shipped; a build refuses one out of range
- git - a KB lives in a git repository, and a build records each stage boundary as a commit
- graphviz - optional, for rendering claim graph diagrams as SVG
- a way to reach a model - a build that spends inference needs one; today that is a provider
  configuration; `kbase score` always spends inference; a `--no-inference` build needs none

Clone this repo anywhere, then install the deployed surfaces into the consuming project — from
**this** repo's root:

```sh
just install ~/projects/foo
```

That produces `agents/` and `commands/` inside `~/projects/foo/.claude/` — every definition a base
install carries, the agent set and the slash commands — and copies each package the installer ships
beside them under `adj-tools/`; no such package is shipped today. Files a harness ships come along
too, copied unchanged and unstamped: they are not renders of this project's definitions. Claude and
opencode ship one, a guardrail, claude's only where `perl` passes the install's check
("Guardrail", below); mage ships none. The kb set is not in a base install: `just
install-with-kb ~/projects/foo` adds the `kbase` skill under `skills/`, with the runner snippets in
`skills/kbase/kb-tools/` beneath it ("Knowledge Base Set", below) — except mage, whose plugin always
installs with it. The definitions are rendered by that invocation and the tool packages are copied.
Test suites and caches stay behind.
`--harness=opencode` installs into `.opencode/` instead (each harness's project directory;
`--subdir=` overrides). `--harness=mage` installs the plugin shape instead:
`just install <plugins-parent> --harness=mage` creates `<plugins-parent>/adjagent`, and the names and
paths inside the plugin are unchanged — the surfaces at its top level, with the manifest under
`.claude-plugin/` beside them. Every `--*` flag after the target forwards verbatim to
`python3 -m adjagent`, so tuning the render is one more flag, not a different command —
`just install ~/projects/foo --family=gemma-4` tunes the generated definitions for that model family
(see "Model Tuning" below).

The installed tree is **an artifact, not for local edit**. A change request comes to this project,
which evaluates it, implements it and makes it available to every consumer; a consumer's own needs
go in its `CONVENTIONS.md`. Every rendered file's first banner line says so. Re-running the install
overwrites the tree and removes definitions this project no longer produces, so a local edit is
replaced with no diff to show it; a project that tracks the tree reviews what changed in its
`git diff`, and one that does not has the install's report — how many files it wrote and each path
it pruned — and the version its runner pins. Re-installing an unchanged source changes nothing. An
install refuses, writing nothing, to overwrite a file at one of its paths that carries no banner of
this project's, such as your own `agents/python-coder.md`, or to write below a symlink or a
non-directory on the way to one; the refusal names each such path, and you move or remove them and
install again. A harness's shipped file is replaced on each install, unless its install-time run
fails (see "Guardrail"), and never pruned, so one this project stops shipping stays in your
tree until you remove it.

Claude Code reads agent definitions from `.claude/agents/`, slash commands from `.claude/commands/`
and skills from `.claude/skills/`; a base install writes `agents/` and `commands/` there and no
`skills/`. A claude install whose guardrail check passes also writes `.claude/hooks/guardrail.pl`
and one entry in `.claude/settings.json`, and nothing else is visible to a session. An opencode install writes one
file more, `.opencode/plugins/guardrail.ts`, copied as it stands. A mage install writes the same
trees at the top level of its own `adjagent` directory under the target — `<plugins-parent>/adjagent`
— with the manifest at `.claude-plugin/plugin.json` beside them, rendered rather than copied, and no
hook: mage ships none.
A kb install adds the `kbase` skill at `skills/kbase/`, with the runner snippets in
`skills/kbase/kb-tools/` beneath it (the skill carries its own tooling), the `kbase` MCP entry,
whose command is the bare `kbase` — at the project root, or, under mage, at the plugin root — and
one include line in the project's justfile
or Makefile. A mage install writes no include line and creates no `Makefile`: a plugin is not a repo
project, so there is no consumer runner to append one to.

### Mage plugin release

The mage plugin is also published as a release: a tarball and its detached signature. The tarball
holds the plugin only; the plugin's `kbase` MCP command is the bare `kbase`, so you install kbase
yourself (see Install, above). Contract: [SPEC.md](SPEC.md), Mage Plugin Distribution.

#### Installing a release

1. Download `adjagent-mage-v<version>.tgz` from the release `v<version>` of
   [benn-herrera/adjagent](https://github.com/benn-herrera/adjagent/releases), and optionally its
   `adjagent-mage-v<version>.tgz.asc`.
2. Optionally check the tarball against the signature. Fetch the release signer's public key over
   WKD (the developer's key is linked under Developer, above), then verify:

   ```sh
   gpg --auto-key-locate wkd --locate-external-keys benn@bennherrera.dev
   gpg --verify adjagent-mage-v<version>.tgz.asc adjagent-mage-v<version>.tgz
   ```

3. Unpack it into Mage's skills directory, removing any earlier copy first:

   ```sh
   rm -rf ~/Mage/Skills/adjagent
   tar -xzf adjagent-mage-v<version>.tgz -C ~/Mage/Skills/
   ```

   The tarball has one top-level `adjagent/` directory, so this leaves `~/Mage/Skills/adjagent`.
4. Install kbase if you have not: the Homebrew command and the minimum version are under Install,
   above. Native Windows is unsupported for the kb set, which a mage plugin always carries.
5. Restart Mage so it starts the plugin's `kbase` MCP server; the plugin's entry finds `kbase` on
   `PATH`. Do the same after installing or upgrading kbase while Mage is running.

### Guardrail

Claude and opencode each ship a hook that blocks shell commands which change a file behind the Edit
and Write tools: in-place `sed`, `perl` or `ruby` edits, redirects (`>`, `>>`), `tee`, `cp` and `mv`
onto an existing file, and inline `python`, `node`, `perl` or `ruby` scripts that write. Writes into
`.claude-temp/` and `test-data/transient` are allowed. A relative path is judged against the
directory the command runs in, and a heredoc's body is not read as shell. The hook catches the forms
agents habitually use; it is not a boundary against a command written to evade it. opencode's is a
plugin that registers itself.

On a kb install, the hook also keeps sessions out of `kb-root/.index/`, where kbase keeps its
records: read them with kbase's `query` tool and change them with its `write` tool. It refuses a
file-tool call on a path there, a shell command naming one, and a recursive search rooted in
`kb-root/` that could reach one; the refusal says how to exclude `.index` from the search. A path is
judged where its symlinks lead. `test -e`, `test -d`, `test -f`, `[ -e … ]` and `stat` on those paths
are allowed. The check is on only while the harness directory holds the kbase skill's `SKILL.md`, and
the hook looks for it on every call, so a base install never sees it.

Claude's is `.claude/hooks/guardrail.pl`, which needs `perl` on `PATH` with core `JSON::PP` when a
session runs it. The install runs it once to check, and without perl or the module, or if the run
takes more than a few seconds, it skips the hook, reports the reason in one line and installs
everything else; a script and entry from an earlier install are left in place and named. The install
adds one `PreToolUse` entry for Bash and the file tools (Read, Write, Edit, NotebookEdit, Grep, Glob)
to `.claude/settings.json`, the file Claude Code reads whatever `--subdir` is; an entry an earlier
install wrote for Bash alone is replaced by it. The entry runs the script under `$CLAUDE_PROJECT_DIR`
only if it is a readable file: where it is missing, for example because you committed `settings.json`
but not `.claude/hooks/`, a call prints `guardrail hook: no readable script at <path>` and goes ahead, rather than being
blocked. An existing file keeps every other byte, including your own hooks, and a re-install
replaces that one entry in place; only an entry written by an install is replaced, so a hook of
yours that runs some other `guardrail.pl` is left alone. A project has one entry: installing under
a different `--subdir` replaces it. A settings file with comments, or with more than one of our
entries, or a settings path that is a symlink or sits behind one, or is not a regular file, is
reported with the entry printed for you to merge by hand and is left untouched. A settings file that
is not UTF-8, or whose `hooks` or `PreToolUse` has the wrong shape (`null` included), refuses the
install with nothing written, as does a harness directory whose path holds a `"`, `$`, backtick or
`\`.

### Runner snippets for adding to a project

Add `.claude/`, `.opencode/` to `.gitignore`

The examples below use the `install` recipe. 

The `install-with-kb` recipe installs the [kbase](https://github.com/benn-herrera/kbase) knowledge base tool
and the skill to use it. Add `.mcp.json` to `.gitignore` if you use this recipe.

#### Justfile
```just
AGENTS_REPO := "https://github.com/benn-herrera/adjagent.git"
AGENTS_DIR := "." + file_stem(AGENTS_REPO)
AGENTS_VER := "v0.12.5"
[doc("updates and installs agent set from adjagents public repo")]
agents:
  @mkdir -p "{{parent_directory(AGENTS_DIR)}}"
  @[[ -d "{{AGENTS_DIR}}" ]] && git -C "{{AGENTS_DIR}}" fetch --tags || git -C {{parent_directory(AGENTS_DIR)}} clone "{{AGENTS_REPO}}" "{{AGENTS_DIR}}"
  @git -c "advice.detachedHead=false" -C "{{AGENTS_DIR}}" checkout "{{AGENTS_VER}}"
  just --justfile "{{AGENTS_DIR}}/justfile" install "$(pwd)" --harness=claude
  just --justfile "{{AGENTS_DIR}}/justfile" install "$(pwd)" --harness=opencode --model-tier-map=default
  just --justfile "{{AGENTS_DIR}}/justfile" install-agents-file ~/.claude
	just --justfile "{{AGENTS_DIR}}/justfile" install-agents-file ~/.config/opencode	
```

#### Makefile
```make
.PHONY: agents
AGENTS_REPO := https://github.com/benn-herrera/adjagent.git
AGENTS_DIR := .$(basename $(notdir $(AGENTS_REPO)))
AGENTS_VER := v0.12.5
agents:
	@mkdir -p $(dir $(AGENTS_DIR))
	@[[ -d "$(AGENTS_DIR)" ]] && git -C "$(AGENTS_DIR)" fetch --tags || git -C "$(dir $(AGENTS_DIR))" clone "$(AGENTS_REPO)" "$(AGENTS_DIR)"
	@git -c "advice.detachedHead=false" -C "$(AGENTS_DIR)" checkout "$(AGENTS_VER)"
	just --justfile "$(AGENTS_DIR)/justfile" install "$(CURDIR)" --harness=claude
	just --justfile "$(AGENTS_DIR)/justfile" install "$(CURDIR)" --harness=opencode --model-tier-map=default
	just --justfile "$(AGENTS_DIR)/justfile" install-agents-file ~/.claude
	just --justfile "$(AGENTS_DIR)/justfile" install-agents-file ~/.config/opencode	
```

### Harness Agents File

The agent definitions assume a set of operator-level working rules, published as one definition
(`adjagent/definitions/harness_agents_file.py`) rendered per harness. Install it with
`just install-agents-file <dir> [harness]`, where `<dir>` is `~/.claude`, `~/.config/opencode`, a
project root, or a plugin directory under mage. The harness is inferred when `<dir>` is a harness's
user-global directory; for a project root (or anything else) name it:
`just install-agents-file ~/projects/foo opencode`. Inference covers only a harness whose user
directory is absolute, so mage is always named: `just install-agents-file <dir> mage`. The directives
live in `AGENTS.md`: into the harness's user-global directory the install writes the file that harness
reads there (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`); anywhere else it writes
`<dir>/AGENTS.md`, and for a harness that reads another name it creates that file as the one-line
redirect `@AGENTS.md` (Claude Code's `CLAUDE.md`), leaving an existing one alone. A `CLAUDE.md` there
holding anything else is refused with nothing written — move its content into `AGENTS.md` and replace
it with `@AGENTS.md` yourself. Under mage the destination is its own directory, so
`just install-agents-file <dir> mage` takes the plugin directory — `<plugins-parent>/adjagent` — and
writes `<dir>/CLAUDE.md` directly, never an `AGENTS.md` redirect;
`just install <plugins-parent> --harness=mage` writes it too, so a normal install needs no second
step.

The install replaces only the block between the `adjagent` marker lines and keeps everything outside
it; put your own rules outside the markers. Edits inside the block are not preserved. An absent file
is written whole. If the destination holds nothing but a single `@<path>` import, the install goes
into that target and leaves the redirect alone; a redirect to another redirect, or to a file outside
`<dir>`, is refused for you to merge by hand. A file without exactly one begin marker line followed
by one end marker line is refused with nothing written, as is any run while `adjagent/` has
uncommitted changes. A write that changes the file keeps one rolling `backup.<name>` of what it
replaced.

`agents/`, `commands/` and `skills/` are the three deployed surfaces install produces inside
`<project>/.claude/`; the catalogs below name entries by where they land there — every entry lives
under `agents/` unless noted as a command or a skill.

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
place of each tier's member. Under opencode, `--model-tier-map=inherit` or `=default` — two words
that render alike there — means "the project's own model for every tier": each agent renders with no
`model:` line and runs on whatever that project has configured. `--harness=opencode` with the
default family needs the tier map overridden, its tier texts being Claude model names opencode does
not accept, and a bare value is the whole map in one word. The alias map takes no bare value, and
under claude a bare one is refused as no `tier=value` pair.
`just install <target> [--family=NAME] [--model-tier-map=SPEC] [--model-pin-tier-alias-map=SPEC] [--harness=NAME]`
applies the same mechanism to an install (see "Install" above), and `just install-with-kb` takes the
same flags — every one forwards verbatim to `python3 -m adjagent`.

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

Every definition in this catalog is **generated** — the coder and platform files, the `kbase` skill
with its references, the specialists, and every slash command.
There are no hand-maintained definitions and nothing to edit directly; see Development → Generated
Definitions for how a definition maps to its source module.

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

### Knowledge Base Set

The `kbase` skill and portable tooling for building, navigating, and maintaining a knowledge base —
a navigable, verbatim Markdown distillation of a canonical corpus with a queryable claim-graph
metadata spine. The set is one skill, `kbase`, with four references, project-portable: per-project
facts live in the consuming project's `kb-root/AGENTS.md`, not in the skill's text. The set is
**generated** from its definition module, and a base install omits it — `just install-with-kb` is
what delivers it. Under mage it is always delivered; a plain mage install without a kbase source
refuses instead.

You don't invoke a command to use it. Ask about the knowledge base — what it says, how to get
around it, what a claim rests on — and the session loads the `kbase` skill and routes from there.
The skill's description is what makes that work, so it also covers the case where there is no KB
yet but there are LaTeX sources to build one from: ask it to build the KB and it identifies the
volume root, confirms it with you, and follows the build reference.

A build derives the KB from the LaTeX corpus, and the corpus is the only thing that exists at that
point. Once you have edited the KB by hand — a leaf's prose, a claim minted or wired — that work
exists nowhere else, and a fresh build over the same `kb-root/` would overwrite it. Point a fresh
build at a KB you have been working in and you lose the work; continue an interrupted one and you do
not.

* Using/navigating a knowledge base
  * `kbase` skill — `skills/kbase/SKILL.md` locates the KB and routes the request, with
    `references/reading.md` carrying navigation, claim rigor and strength, and cross-references

* Building/Modifying Knowledge Base
  * `kbase` skill, `references/building.md` - drives kbase's `build` tool: reports the refusal, or the
    launch that entered a stage — its `state-dir`, `pid`, `resume` and `wait` lines, `wait` run in
    the background to hear the build end; then `status` on request, `cancel` on your word
  * kbase - the builder itself, a Go binary you install with Homebrew; this repository neither ships nor installs it:
    `kbase build` runs the stages in order, spends inference through its own provider configuration,
    and makes each stage boundary a commit in your repository
  * `kbase` skill, `references/maintaining.md` - the write side: leaf edits, claim-graph wiring and
    the refresh→verify loop, for a correction or a migration a session lands by hand
  * `kbase` skill, `references/scoring.md` - scoring the KB's rigor and bearings: the `score` tool
    walks the KB's scoring set itself, one question per item, and records a run ledger it resumes
    from; a work's rigor and a `founds` edge's bearing are yours to author, never a run's
  * `kbase` skill, `references/scoring-system.md` - provides access to links for explaining
    the details of the scoring system's methodology.

#### KB toolchain

The kb set drives **kbase**, a Go binary, not a Python package. You install it yourself
(see Install, above) and `just install-with-kb` does not touch it. What the install delivers is the two runner fragments, to
`.claude/skills/kbase/kb-tools/runner-snippets/` by default (`.opencode/skills/kbase/kb-tools/runner-snippets/`
under opencode; `skills/kbase/kb-tools/runner-snippets/` at the plugin root under mage), inside the
skill's own directory; they run `kbase` from `PATH`. kbase's own documentation is its repository, [benn-herrera/kbase](https://github.com/benn-herrera/kbase);
`INTEGRATING_KBASE_VIA_MCP.md` there is the wiring guide. The same install:

1. Registers a `kbase` MCP server in the harness's own settings file — `.mcp.json` under Claude Code
   and at the plugin root under mage; under opencode the first of `.opencode/opencode.json`,
   `opencode.jsonc`, `opencode.json`, else `.opencode/opencode.jsonc` created. The entry's command is
   the bare `kbase` from `PATH`, run as `kbase mcp` (`kbase mcp --project-dir-required` under mage); it
   names no KB path. Every query, write op, `refresh`,
   `verify`, `build` and `score` the set names is a tool of that server, offered under the harness's
   own prefix — `mcp__kbase__stats` under Claude Code, `kbase_stats` under opencode. A settings file
   carrying JSONC comments, or a settings path that is a symlink or not a regular file, is reported
   with the entry printed for you to merge by hand.
2. Appends one include line to the project's justfile or Makefile — creating a `Makefile` where there
   is neither: `import? '<harness-dir>/skills/kbase/kb-tools/runner-snippets/kb.just'` (just 1.33 or
   later) or the `-include` form naming `kb.mk`. Both are non-fatal, so a consumer's runner keeps
   working if the tree is absent, and `just`/`make` then carry `kb-verify`, `kb-refresh` and
   `kb-stats`. Under mage this step does not run: no include line and no `Makefile`, because a plugin
   is not a repo project.

The route is MCP-only for every verb, scoring among them: the `score` tool starts its run detached
and answers once the run's ledger and pid stand, and the run is followed with `status`, `wait` and
`cancel`. When you ask for KB work and the server's tools are not offered, the skill looks for
`kbase` on `PATH` (it runs nothing) and tells you which it is: not installed, with how to install it,
or installed with its MCP server not running here, which you enable, restart or reconnect in your
harness. If a restart does not bring the tools back, the harness process may not find `kbase` on its
own `PATH`, which can differ from your shell's; `references/installing.md` walks through both cases.
It never reaches for a second interface. The KB lives in `kb-root/` at the repository
root, and the entry names no path to it: `kbase mcp` locates the KB from the working directory it
is started in, as every kbase subcommand does, so the server must be started in the project
directory. Under mage, an application serving many projects, the server is started with
`--project-dir-required` instead: each tool call names its project with `project-dir`.

The choice is sticky: a directory already holding a kb install is one, so a later `just install`
into it refreshes the kb set rather than dropping it (the signal is a file, never the `kb-tools/`
directory; [ARCHITECTURE.md](ARCHITECTURE.md), Install Consumption Model, names it). A kb install
replaces `skills/kbase/kb-tools/` whole, so a `kbase` binary and `.asc` an earlier version put there
are removed, and any install removes the other trees an earlier version installed, naming each. A
plain `just install` into a directory holding no kb install writes nothing of the kb set — no
`skills/kbase/` tree, no kb-tools tree, no MCP entry and no include line — and removes each file of
one it finds as stale.

## Development

This section is for working on this repository itself — the generator, its definitions, and the
shipped tool packages. If you are installing the product into a project, see Usage, above.

Beyond the install requirements, the test suite needs `bun` and `perl` on `PATH`: the
guardrail parity test (`tests/test_guardrail.py`) runs one case table through both guardrails and
fails, not skips, without `bun`. The two guardrails change together ([CONVENTIONS.md](CONVENTIONS.md)).

### Repository Layout

```
adjagent/                 the generator and every definition, run as `python3 -m adjagent`
  clauses.py              shared text: named string constants, small functions for slotted text
  definitions/            one module per definition, or per set that shares text and ships together
  harnesses/              one module per harness (claude, mage, opencode), each defining HARNESS
    resources/            one directory per harness — the files it ships, copied into the install's
                          harness directory as they stand (opencode/plugins/guardrail.ts,
                          claude/hooks/guardrail.pl)
  families/               one module per model family, each defining FAMILY
kb-tools/                 shipped KB runner fragments (runner-snippets/kb.just, kb.mk), delivered by
                          a kb install only as skills/kbase/kb-tools/, inside the kbase skill's own
                          directory
dist/                     gitignored — what `just mage-dist` writes (see "Releasing the mage plugin")
devtools/render_diff.py   compares two rendered slots by text; reads only rendered output
rendered/                 gitignored build product — `just render [slug]` puts a render here per
                          slot; the three `reference*` slots are the baseline `just render-diff`
                          compares against, written only by `just retake-reference`
ROADMAP_PLANS/            tracked home for planned work not yet ready to execute
```

In `adjagent/`, a definition module registers by existing in `definitions/`; its `kind` and
`folder` decide where it lands, and a skill's `files` add the supporting files beneath its own
directory. Mechanism is in the package and module docstrings, and in
[ARCHITECTURE.md](ARCHITECTURE.md).

`agents/`, `commands/` and `skills/` are not directories in this repository. They are the three
deployed surfaces of the *product*, produced into `<project>/.claude/` by an install (or into
`rendered/` by `just render`), and the catalogs in Usage name entries by where they land there:
every entry lives under `agents/` unless noted as a command or a skill.

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

Other targets: `just render [slug]` renders the full install product — kb set included, so the slot
carries the `kbase` skill under `skills/` with the runner snippets in `skills/kbase/kb-tools/`
beneath it, the harness's MCP entry and, for claude and opencode, a `Makefile` include line — into
`rendered/<slug>/` (slug defaults to `latest`), plus the harness agents file under
`rendered/<slug>/harness/<name>/` — `CLAUDE.md` by default, or another harness's with
`--harness=NAME`. Under mage it lands at the slot root instead, `rendered/<slug>/CLAUDE.md` beside
`.mcp.json`, with no `harness/` directory and no `Makefile`: the slot is installed with `--subdir=`,
so the plugin's root is the slot itself, and a plugin writes no include line. A slug starting with
`reference` is refused.
`just render-diff [a] [b]` compares two slots — reference against latest by default — by text, with
each file's banner replaced by one constant line, and reports differences without failing on them.
`just test` runs the full tooling
test suite (the `adjagent` and `dupe_sweep` surfaces, auto-provisioning a `.venv`).
`just test-changed [base]` runs only the surfaces the uncommitted tree (plus, given `base`, the
commits since it) touches, and says which paths chose each.

### Releasing the mage plugin

`just mage-dist` writes two files to `dist/`: `adjagent-mage-v<version>.tgz` and its detached
`.asc` signature. What the consumer does is under Usage, "Mage plugin release"; the contract is
[SPEC.md](SPEC.md), Mage Plugin Distribution.

The build needs `gpg` holding your signing key as its default secret key; it signs with that key
and pins no fingerprint, so a rotated key needs no code change. It removes the previous outputs and
its `stage/`, and builds from the working tree as it stands, with no git check. A build that fails,
signing included, leaves neither output and no `stage/`.

To release:

1. Bump the version and commit it ([CONVENTIONS.md](CONVENTIONS.md), the version bullet).
2. `just test`.
3. `just mage-dist`.
4. `just tag`, which creates the local tag `v<version>` and pushes nothing; push it yourself.
5. Create the release `v<version>` on GitHub and upload the two files. The recipe uploads, tags
   and pushes nothing.
6. Smoke check: from an empty scratch directory, download the uploaded tarball and its `.asc` from
   the release, `gpg --verify` the one against the other, and list the tarball (`tar -tzf`).

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

Every definition in the Usage catalogs — the coder and platform files, the `kbase` skill with its
references, the specialists, and every slash command — is **generated**. There are no
hand-maintained definitions and nothing to edit directly in a rendered tree; the source is the
definition's module (see "Working In This Repo"). A rendered
definition carries a two-line banner inside its frontmatter: a generated-from line naming its
definition module and stating that the file is not for local edit, and a tuning line recording the
family, seat, tier map and harness it was rendered for. A skill's supporting file has no
frontmatter, so it carries the same two lines as HTML comments on its first two lines. There is no
content hash; a project that tracks the rendered output sees drift in its `git diff`, and one that
does not loses any local edit to the next install. See
[CONVENTIONS.md](CONVENTIONS.md#adding-definitions) for how to add one.

## Third Party Acknowledgements

The deployed runtime (`agents/`, `commands/`, `skills/`) is stdlib-only Python and shell with no
third-party dependencies. `pytest`, `black`, and `isort` are dev/test-only tools, installed into a
local `.venv` by the `just test` and `just format-python` recipes.

pandoc (John MacFarlane and contributors) and Graphviz `dot` (Graphviz authors) are run as external programs and are not bundled.
