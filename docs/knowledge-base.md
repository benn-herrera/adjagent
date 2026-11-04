# Knowledge base

The `kbase` skill and portable tooling for building, navigating and maintaining a knowledge base: a
navigable, verbatim Markdown distillation of a canonical corpus with a queryable claim-graph metadata
spine. The set is one skill, `kbase`, with the references its router routes to. It is project-portable:
per-project facts live in the consuming project's `kb-root/AGENTS.md`, not in the skill's text. The
set is **generated** from its definition module.

A base install omits it. `adjagent install --with-kb` (`just install-with-kb` in a clone) delivers it.
Under mage it is always delivered; a plain mage install without a kbase source refuses instead.

## Requirements

- **kbase 0.10.0 or later**, installed by you; no install writes it. On macOS or Linux:
  `brew install benn-herrera/kbase/kbase`. `kbase --version` prints the bare version, and
  `brew upgrade benn-herrera/kbase/kbase` brings an older one up. The harness's `kbase` MCP entry runs
  the bare command `kbase`, so it has to be on `PATH`, and the MCP server has to be (re)started after
  an install or upgrade before its tools appear. Nothing checks the version. Native Windows is
  unsupported for the kb set for now. An agent session can walk you through all of this: the `kbase`
  skill's `references/installing.md`.
- **pandoc 3.12**, LaTeX to Markdown, a host tool that is not shipped; a build refuses one out of
  range.
- **git**: a KB lives in a git repository, and a build records each stage boundary as a commit.
- **graphviz**, optional, for rendering claim graph diagrams as SVG.
- **A way to reach a model.** A build that spends inference needs one; today that is a provider
  configuration. `kbase score` always spends inference; a `--no-inference` build needs none.

## Using it

You don't invoke a command to use it. Ask about the knowledge base (what it says, how to get around
it, what a claim rests on) and the session loads the `kbase` skill and routes from there. The skill's
description is what makes that work, so it also covers the case where there is no KB yet but there are
LaTeX sources to build one from: ask it to build the KB and it identifies the volume root, confirms it
with you, and follows the build reference.

A build derives the KB from the LaTeX corpus, and the corpus is the only thing that exists at that
point. Once you have edited the KB by hand (a leaf's prose, a claim minted or wired), that work exists
nowhere else, and a fresh build over the same `kb-root/` would overwrite it. Point a fresh build at a
KB you have been working in and you lose the work; continue an interrupted one and you do not.

- Using and navigating a knowledge base
  - The `kbase` skill: `skills/kbase/SKILL.md` locates the KB and routes the request, with
    `references/reading.md` carrying navigation, claim rigor and strength, and cross-references.
- Building and modifying a knowledge base
  - `references/building.md` drives kbase's `build` tool: it relays the launch or its refusal, and
    runs the `wait` line a launch returns in the background to hear the build end; then `status` on
    request, `cancel` on your word.
  - kbase, the builder itself: a Go binary you install with Homebrew; this repository neither ships
    nor installs it. `kbase build` runs the stages in order, spends inference through its own
    provider configuration, and makes each stage boundary a commit in your repository.
  - `references/maintaining.md` is the write side: leaf edits, claim-graph wiring and the `verify`
    loop, for a correction or a migration a session lands by hand.
  - `references/scoring.md` scores the KB's rigor and bearings: the `score` tool walks the KB's
    scoring set itself, one question per item, and records a run ledger it resumes from. A work's
    rigor and a `founds` edge's bearing are yours to author, never a run's.
  - `references/scoring-system.md` gives access to links explaining the scoring system's
    methodology.

## The toolchain

The kb set drives **kbase**, a Go binary, not a Python package. You install it yourself and the
install does not touch it. What the install delivers is the two runner fragments, to
`.claude/skills/kbase/kb-tools/runner-snippets/` by default
(`.opencode/skills/kbase/kb-tools/runner-snippets/` under opencode;
`skills/kbase/kb-tools/runner-snippets/` at the plugin root under mage), inside the skill's own
directory; they run `kbase` from `PATH`. kbase's own documentation is its repository,
[benn-herrera/kbase](https://github.com/benn-herrera/kbase); its README's section "Using kbase from
an agent harness (MCP)" is the wiring guide. The same install:

1. Registers a `kbase` MCP server in the harness's own settings file: `.mcp.json` under Claude Code
   and at the plugin root under mage; under opencode the first of `.opencode/opencode.json`,
   `opencode.jsonc`, `opencode.json`, else `.opencode/opencode.jsonc` created. The entry's command is
   the bare `kbase` from `PATH`, run as `kbase mcp` (`kbase mcp --project-dir-required` under mage); it
   names no KB path. Each of its tools is offered under the harness's own prefix: kbase's `query` tool
   is `mcp__kbase__query` under Claude Code and `kbase_query` under opencode. A settings file carrying
   JSONC comments, or a settings path that is a symlink or not a regular file, is reported with the
   entry printed for you to merge by hand.
2. Appends one include line to the project's justfile or Makefile, creating a `Makefile` where there
   is neither: `import? '<harness-dir>/skills/kbase/kb-tools/runner-snippets/kb.just'` (just 1.33 or
   later) or the `-include` form naming `kb.mk`. Both are non-fatal, so a consumer's runner keeps
   working if the tree is absent, and `just`/`make` then carry `kb-verify`, `kb-update-format` and
   `kb-stats`. Under mage this step does not run: no include line and no `Makefile`, because a plugin
   is not a repo project.

Add `.mcp.json` to the project's `.gitignore` if you install the kb set.

The route is MCP-only for every verb, scoring among them: the `score` tool starts its run detached and
answers once it has started; the session follows the run with `status` and `cancel`, and runs the
`wait` command line the answer carries in the background. When you ask for KB work and the server's
tools are not offered, the skill looks for `kbase` on `PATH` (it runs nothing) and tells you which it
is: not installed, with how to install it, or installed with its MCP server not running here, which
you enable, restart or reconnect in your harness. If a restart does not bring the tools back, the
harness process may not find `kbase` on its own `PATH`, which can differ from your shell's;
`references/installing.md` walks through both cases. It never reaches for a second interface.

The KB lives in `kb-root/` at the repository root, and the entry names no path to it: `kbase mcp`
locates the KB from the working directory it is started in, as every kbase subcommand does, so the
server must be started in the project directory. Under mage, an application serving many projects, the
server is started with `--project-dir-required` instead: each tool call names its project with
`project-dir`.

## Staying a kb install

The choice is sticky: a directory already holding a kb install is one, so a later `adjagent install`
into it refreshes the kb set rather than dropping it. The signal is the generated `kbase` skill file,
never the `kb-tools/` directory. A kb install replaces `skills/kbase/kb-tools/` whole, so a `kbase`
binary and `.asc` an earlier version put there are removed, and any install removes the other trees an
earlier version installed, naming each. A plain `adjagent install` into a directory holding no kb
install writes nothing of the kb set (no `skills/kbase/` tree, no kb-tools tree, no MCP entry and no
include line) and removes each file of one it finds as stale.

While the harness directory holds the kbase skill's `SKILL.md`, the guardrail also keeps sessions out
of `kb-root/.index/` ([Guardrail](guardrail.md)).
