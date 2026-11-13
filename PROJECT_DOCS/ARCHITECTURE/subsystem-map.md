## Subsystem Map

Every entry below but the last is rendered from the definition module under `devpro/definitions/`
named for its output path, or for its group module (Rendering). A shared-text name given
here is a constant or function in `devpro/clauses.py`, and an anchor is spelled `fam-<key>`.

- **Coder group** — generalist-coder, language coders (c, cpp, go, lua, python, rust, typescript),
  shell-dsl-coder, platform experts (android/ios/linux/macos/web/windows-app-expert,
  linux-kernel-driver-expert), architect, and — sharing the coding-review domain — security-reviewer
  and tech-writer, which is both the authoring and the reviewing agent for READMEs and human-facing guides.
- **kbase plugin + kbase** — the `kbase` skill alone: the definition the devpro plugin excludes by name
  and the kbase plugin delivers with the others SPEC.md, Deployed Surfaces, Plugins lists
  (`devpro/plugins/kbase.py`). `kbase.py` owns a directory,
  `skills/kbase/SKILL.md` routing by request and `skills/kbase/references/reading.md`,
  `building.md`, `maintaining.md`, `scoring.md`, `scoring-system.md` and `installing.md` carrying
  what each route needs; the skill entry file is the only text every session pays for, and the rule
  that a supporting file is read only when its route is reached is the skill entry file's own — its
  *Route by the request* section says so, and nothing but that text stops a read.
  `clauses.kb_orientation`, carrying the KB system model with a per-supporting-file `role=` clause,
  goes to the two supporting files that work a KB the build has finished with — reading, which
  reports, and maintaining, which modifies; `building.md` and `scoring.md` carry what their own job
  needs. The skill and its supporting files are project-portable — per-project facts live in the
  consuming project's `kb-root/AGENTS.md`, under every harness. The kbase plugin reaches kbase, the
  executable the operator installs (no install writes it), only through the harness's `kbase` MCP
  server, offered under that harness's `mcp_tool_prefix`. The minimum version and the formula are
  written once, as `KBASE_MIN_VERSION` and `KBASE_TAP_FORMULA` in `kbase.py`, and filled into the
  skill entry file and `installing.md`. `clauses.KB_RUNNER_TARGETS` goes to the maintaining
  supporting file. The consuming project's runner targets are the `kb-`-prefixed recipes of this
  repository's `devpro/kb-tools/runner-snippets/kb.just` and `kb.mk`, prefixed so they cannot
  collide with a consuming project's own targets.
- **Specialists** — applied-mathematician, biz-dev-strategist, economic-historian, literature-scout,
  marketing-comms-expert, ml-engineer, prompt-engineer, prose-architect, theoretical-economist:
  single-purpose, invoked directly rather than as part of a coding pipeline.
  applied-mathematician carries the `fam-ask-vs-stipulate` anchor; `fam-gap-aversion` renders
  nowhere.
- **Tool-driving skill:** `docdicer`, one `SKILL.md` with no supporting files, delivered with its
  tools package by both plugins.
  `docdicer.py` names its script `tools/docdicer`, relative to the skill's directory, and says its
  first run installs docdicer beside it; the script's `--help` is the command list, which the skill
  does not restate. The skill carries no runner-snippet advice and no install step; its one
  runner instruction is that where the project's runner includes the docdicer snippet, docdicer is
  run through the recipes (`docdicer`, `docdicer-check-plan`, `docdicer-kanban`, `docdicer-help`).
  It names `check-design` and `check-roadmap` beside `check-plan`; neither has a recipe of its
  own, and each runs through `docdicer` (`just docdicer check-design <design>`,
  `just docdicer check-roadmap ROADMAP.md`).
  It also carries a paragraph, an optional reference to `kbase` (Rendering, Placeholders), saying
  `kb-root/` belongs to kbase and docdicer leaves it alone unless the user directs otherwise; it
  renders only where kbase ships. The docdicer version the script
  installs is written once, as `VERSION` in `devpro/docdicer-tools/docdicer`.
- **Guide skill** — `guide` (`definitions/guide.py`): one `SKILL.md` and two supporting files,
  `references/installing.md` and `references/using.md`, carried as `SkillFile`s, delivered by both
  plugins under every harness. The description names the uses SPEC.md, Guide and README lists, and
  says it is not for a change to the consuming project's own code. `SKILL.md` is a route, as the
  `development` skill's *Route* table is: one row per starting place SPEC.md, Guide and README
  lists, under the never-edit rule it states. The `development` and `docdicer` rows name their skill
  by a plain reference (`clauses.ref`), safe because both plugins ship both.
  `references/installing.md` carries everything else about the installed set. That includes three
  paragraphs of its own, each dropped where its value is empty:
  - the `reload_rule` placeholder (Rendering, Placeholders), which says to run `/reload-plugins`
    when the agents an install wrote are not offered. It is kept under claude alone;
  - the `side_by_side_rule` placeholder, which says how to stop opencode loading a claude
    install's skills. It is kept under opencode alone;
  - an optional reference to `kbase` (`clauses.optional_ref`), which hands installing kbase itself
    to that skill. It is kept in the kbase plugin alone.

  The plugin is named through `clauses.PLUGIN_NAME`, and the repository through
  `clauses.REPOSITORY_URL`.
- **Development skill** — `development` (`definitions/development.py`): one `SKILL.md` and six
  supporting files (`references/new-project.md`, `project-documents.md`, `project-setup.md`,
  `adopting.md`, `release.md`, `design.md`), carried as `SkillFile`s, delivered by both plugins under every
  harness, mage included. Beside them in the skill's directory sits the development scripts
  package, `scripts/cold-read.sh`, owned by `development`: a shipped package, not one of the
  `SkillFile`s (Install, Renders and copies). The skill states one development process for the main
  session; the agents file's *Task management* points the session at it. `development.py` writes
  the roadmap's tickets, plan, review document, design and set-aside locations and the forms stated
  in SPEC.md, Plan Status Form, at seven sites: the *Terms* section's fixed table (the locations),
  the entry body's `## Plan status`, `## Roadmap tickets` and `## Design` sections, its `## Plans`
  section (a diced design split at its `##` and `###` headings only), `references/design.md` (a
  design's final form, its fixed line one constant) and `references/release.md`. The *Design*
  section has the session run `check-design` before a design is offered for acceptance and again
  on an entry added to an accepted design, and *Roadmap tickets* has it run `check-roadmap` after
  each edit to `ROADMAP.md`. Each term the process names (active plan, step-down model and the
  rest), and a design's fixed summary line, is one module-level `*_TERM` constant that every mention
  in `SKILL.md` and its six supporting files interpolates; a test reads `development.py` and fails
  where a term's value is written literally in a body string, so no two mentions can name a term
  differently. Its
  `docdicer` references are optional references (Rendering, Placeholders), and `docdicer` ships
  with both plugins, so each fills. The *Plan status* and *Roadmap tickets* sections render whole
  under every plugin; each one's `check-plan` or `check-roadmap` instruction is a paragraph of its
  own, so an optional reference that fills to nothing drops that paragraph alone. The sentence
  naming the default step-down model is
  `clauses.STEP_DOWN_MODEL`, the `tun` placeholder (Rendering, Placeholders), so that sentence alone
  renders only where the rendering assigns a model for the step-down tier. The entry body's
  `## Commits and pull requests` section gives the attribution line every commit message and
  pull-request description carries; it names the harness by `clauses.DISPLAY_NAME`, the
  harness's `display_name` (Rendering, Placeholders), and no model, and links the repository by
  `clauses.REPOSITORY_URL`.
- **Install machinery** — the one entry not rendered from a definition: `install.py` renders, copies
  and prunes; `install_base.py` holds what the install modules share (the package and checkout
  paths, the kb-tools package paths, `VENV_DIR`, the path checks, UTF-8 text reading and the report of what an
  install left alone); `runner_file.py` writes the runner include lines, one per `SnippetSet` the install passes it; `preflight.py` runs that
  install into a scratch copy and compares (Install, Renders and copies); `agents_file.py`
  does the same for the agents file (Agents File). The imports layer: `install_base.py`, `preflight.py` and `install_target.py` import
  no other install module; `runner_file.py` imports `install_base.py`; `agents_file.py` imports
  `install_base.py`, `install_target.py` and `preflight.py`; `install.py` imports all of them.
