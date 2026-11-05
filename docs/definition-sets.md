# Definition sets

Every definition below is **generated**: there are no hand-maintained definitions and nothing to edit
in an installed tree. Each is rendered from a module under `adjagent/definitions/`
([Development](development.md#generated-definitions)). Entries are named by where they land in
`<project>/.claude/`: every entry lives under `agents/` unless noted as a command or a skill.

A base install carries everything here except the `kbase` skill ([Knowledge base](knowledge-base.md)).

## Coding agents

- `architect.md`: architecture review and design
- `security-reviewer.md`: security-specific reviewer
- `generalist-coder.md`
- `tech-writer.md`: technical documentation author and review seat
- Language-specific coders: `c-coder.md`, `cpp-coder.md`, `go-coder.md`, `lua-coder.md`,
  `python-coder.md`, `rust-coder.md`, `shell-dsl-coder.md`, `typescript-coder.md`
- Platform-specific coders: `android-app-expert.md`, `ios-app-expert.md`, `linux-app-expert.md`,
  `linux-kernel-driver-expert.md`, `macos-app-expert.md`, `web-app-expert.md`,
  `windows-app-expert.md`

## Specialists

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
  definition bodies, model-tuning overlay entries, agent-facing docs

## Commands

- `commands/imgread.md`: reads the image file a shell command saved from the clipboard, to work
  around broken image pasting in a terminal UI. Mage does not carry it.

## Skills

Three skills ship in the default set of every harness, except that mage omits `adjagent`.

- **`adjagent`** (`skills/adjagent/SKILL.md`): how a session changes, updates and inspects the
  installed set. It tells the session never to edit the installed definitions or the installed
  package, to put a project's behavior in its `CONVENTIONS.md` or `AGENTS.md`, and to change the
  definitions persistently only through a vendored copy or a fork
  ([README, Customizing](../README.md#customizing-the-set)). It also covers running adjagent (the
  project's runner recipe where there is one, else the release tag installed into a venv and that
  venv's `adjagent`), updating (raise the pinned version, preview with `adjagent install --dry-run`,
  then install) and inspecting (`adjagent --version`, `--dry-run`).
- **`docdicer`** (`skills/docdicer/SKILL.md`): dicing markdown into a tree of small linked files under
  one `entry-point.md`, and undicing a tree back into one document, so a session loads only the
  leaves a task needs. It runs through `tools/docdicer` in its own directory, and offers
  `tools/docdicer --install` only to run at your direction. A user-level install delivers the skill
  without the script ([Install reference](install-reference.md)).

  **Runner recipes.** The tools package also carries `runner-snippets/docdicer.just` and
  `docdicer.mk`. No install adds an include line for them; a project opts in by adding one to its
  runner file, naming its harness directory (`.claude` or `.opencode`), and the docdicer skill offers
  that line at your direction:

  ```just
  import? '.claude/skills/docdicer/tools/runner-snippets/docdicer.just'
  ```

  ```make
  -include .claude/skills/docdicer/tools/runner-snippets/docdicer.mk
  ```

  Each gives two recipes. `docdicer` passes its arguments to `tools/docdicer`. `docdicer-check` runs
  `check-links` over the roots (default `PROJECT_DOCS *.md`), then `check-tree` over a tree (default
  `PROJECT_DOCS`). In make the arguments are `DOCDICER_ARGS`, `DOCDICER_ROOTS` and `DOCDICER_TREE`.
  The just form needs just 1.33 or later. The recipes fail with install instructions until
  `tools/docdicer --install` has built the venv.
- **`dev-process`** (`skills/dev-process/SKILL.md`, with `references/`): one development process for
  the main session, covering planning, dispatching agents, accepting their work, checkpoint commits,
  post-plan review and releases as sequences of plans. A project's own rule in its `CONVENTIONS.md`
  overrules the skill's. Where a rule needs a value the project has not recorded, such as the
  runner targets that verify an edit, the session asks you and records the answer in `CONVENTIONS.md`
  rather than guessing. The references cover starting a new project (`new-project.md`), recording
  those values (`project-setup.md`), taking up a project whose process is already written
  (`adopting.md`) and running a release (`release.md`). Mage carries it. The agents file points the
  session at it ([Agents file](agents-file.md)).
- **`kbase`**: the knowledge-base skill, delivered by a kb install ([Knowledge base](knowledge-base.md)).
