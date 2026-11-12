# Definition sets

Every definition below is **generated**: there are no hand-maintained definitions and nothing to edit
in an installed tree. Each is rendered from a module under `devpro/definitions/`
([Development](development.md#generated-definitions)). An install delivers one **plugin**, a named
selection of definitions; [SPEC's Plugins page](../PROJECT_DOCS/SPEC/deployed-surfaces/plugins.md) lists each plugin's members
([Installing, Plugins](installing.md#plugins)). Entries are named by where they land in the
install directory (`<project>/.claude/skills/<plugin>/` under claude): every entry lives under
`agents/` unless noted as a skill. Under claude and mage an agent is invoked as `<plugin>:<name>`, and
under opencode as `<plugin>-<name>`.

## The devpro plugin

Everything in this section except the `kbase` skill.

### Coding agents

- `architect.md`: architecture review and design
- `security-reviewer.md`: security-specific reviewer
- `generalist-coder.md`
- `tech-writer.md`: README and human-facing guide author and review seat
- Language-specific coders: `c-coder.md`, `cpp-coder.md`, `go-coder.md`, `lua-coder.md`,
  `python-coder.md`, `rust-coder.md`, `shell-dsl-coder.md`, `typescript-coder.md`
- Platform-specific coders: `android-app-expert.md`, `ios-app-expert.md`, `linux-app-expert.md`,
  `linux-kernel-driver-expert.md`, `macos-app-expert.md`, `web-app-expert.md`,
  `windows-app-expert.md`

### Specialists

Single-purpose agents invoked directly for non-coding work.

- `prose-architect.md`: rhythm and structural review of long-form prose
- `marketing-comms-expert.md`: messaging, positioning, copywriting, competitive framing
- `biz-dev-strategist.md`: business strategy, market analysis, go-to-market, monetization
- `applied-mathematician.md`: rigorous derivation, model construction, dimensional analysis, claim
  classification (identity, manifestation, consistency check, derived prediction). Takes given axioms
  at face value and derives consequences honestly. Use when working inside a formal system and the
  task requires careful step-by-step reasoning rather than retrieval of textbook results.
- `ml-engineer.md`: ML technique research and development: designing and diagnosing inference,
  training, sampling and optimization mechanisms, and delivering the design with the measurement that
  would falsify it
- `economic-historian.md`: stress-tests historical claims, analogies and "laws of history" against
  the record; the history lens in an adversarial panel
- `literature-scout.md`: finds the citations a manuscript should include, especially the omissions a
  referee would flag; verifies real references via web search rather than inventing them
- `theoretical-economist.md`: stress-tests production and growth, market-structure and
  mechanism-design claims; the economics lens in an adversarial panel
- `prompt-engineer.md`: authors and revises model-facing text: agent definitions, commands, skills,
  definition bodies, tuning text, agent-facing docs, the project documents and ROADMAP.md

### Skills

Three skills, `install`, `docdicer` and `development`, ship in both plugins under every harness,
except that mage omits `install`.

- **`install`** (`skills/install/SKILL.md`): how a session changes, updates and inspects the
  installed set. It tells the session never to edit the installed definitions or the installed
  package, to put a project's behavior in its `CONVENTIONS.md` or `AGENTS.md`, and to change the
  definitions persistently only through a vendored copy or a fork
  ([Installing, Customizing](installing.md#customizing-the-set)). It also covers running devpro (the
  project's runner recipe where there is one, else the release tag installed into a venv and that
  venv's `devpro`), updating (raise the pinned version, preview with `devpro install
  --plugin=devpro --dry-run`, then install) and inspecting (`devpro --version`, `--dry-run`). Under claude it also
  says what to do when the new agents are not offered after an install: run `/reload-plugins`.
- **`docdicer`** (`skills/docdicer/SKILL.md`): dicing markdown into a tree of small linked files under
  one `entry-point.md`, and undicing a tree back into one document, so a session loads only the
  leaves a task needs. Both plugins deliver it, so a kbase project has the `kanban` board,
  `check-plan` and plan dicing. It runs through `tools/docdicer` in its own directory, whose first
  run installs docdicer beside the script (it needs `python3` 3.9 or later with its `venv` module,
  `git` and the network); no install runs it. Where kbase ships, the skill says `kb-root/` and
  everything under it belongs to kbase and is not diced, undiced or link-checked unless you direct
  it. A user-level install delivers the skill without the script ([Install
  reference](install-reference.md)).

  **Runner snippets.** The tools package also carries `runner-snippets/docdicer.just` and
  `docdicer.mk`. A project install of either plugin under claude or opencode adds the include line
  for them to the project's runner file, naming where the install put them (below
  `.claude/skills/<plugin>/` under claude, `.opencode/plugins/<plugin>/` under opencode):

  ```just
  import? '.claude/skills/devpro/skills/docdicer/tools/runner-snippets/docdicer.just'
  ```

  ```make
  -include .claude/skills/devpro/skills/docdicer/tools/runner-snippets/docdicer.mk
  ```

  Each gives the recipes `docdicer`, which passes its arguments to `tools/docdicer` (in make, as
  `DOCDICER_ARGS`), `docdicer-check-plan`, `docdicer-kanban` and `docdicer-help`. Where the runner
  includes the snippet, the skill runs docdicer through them. The just form needs just 1.33 or
  later.

  A link check depends on the project's layout, so the snippets carry none; the project writes its
  own recipe from `docdicer`. This repository's `check-links` is one:

  ```just
  check-links:
    @just docdicer check-links PROJECT_DOCS docs *.md
    @just docdicer check-tree PROJECT_DOCS
  ```
- **`development`** (`skills/development/SKILL.md`, with `references/`): one development process for
  the main session, covering design, planning, dispatching agents, accepting their work,
  checkpoint commits, post-plan review and releases as sequences of plans. Every commit message and
  pull-request description the session writes carries an attribution line naming devpro and the
  harness, and no model, as its own paragraph directly before any trailer block and otherwise last;
  it is the only attribution. A project's own rule in
  its `CONVENTIONS.md` overrules the skill's. Where a rule needs a value the project has not
  recorded, such as the runner targets that verify an edit, the session asks you and records the
  answer in `CONVENTIONS.md` rather than guessing. The supporting files cover starting a new
  project (`new-project.md`), writing or revising the contract documents (`project-documents.md`),
  recording those values (`project-setup.md`), taking up a project whose process is already written
  (`adopting.md`) and running a release (`release.md`). Mage carries it. The agents file points the
  session at it ([Agents file](agents-file.md)).

## The kbase plugin

The **`kbase`** skill, the knowledge-base skill ([Knowledge base](knowledge-base.md)), and the agents
and skills a knowledge-base project works with, described above; [SPEC's Plugins page](../PROJECT_DOCS/SPEC/deployed-surfaces/plugins.md)
lists them. Its `development` skill carries the dicing guidance, since the plugin carries `docdicer`.
