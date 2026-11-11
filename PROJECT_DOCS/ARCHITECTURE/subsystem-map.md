## Subsystem Map

Every entry below but the last is rendered from the definition module under `adjagent/definitions/`
named for its output path, or for its group module (Rendering). A shared-text name given
here is a constant or function in `adjagent/clauses.py`, and an anchor is spelled `fam-<key>`.

- **Coder group** — generalist-coder, language coders (c, cpp, go, lua, python, rust, typescript),
  shell-dsl-coder, platform experts (android/ios/linux/macos/web/windows-app-expert,
  linux-kernel-driver-expert), architect, and — sharing the coding-review domain — security-reviewer
  and tech-writer, which is both the authoring and the reviewing agent for READMEs and human-facing guides.
- **kbase plugin + kbase** — the `kbase` skill alone: the definition the devpro plugin excludes by name
  and the kbase plugin delivers with the others SPEC.md, Deployed Surfaces, Plugins lists
  (`adjagent/plugins/kbase.py`). `kbase.py` owns a directory,
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
  repository's `adjagent/kb-tools/runner-snippets/kb.just` and `kb.mk`, prefixed so they cannot
  collide with a consuming project's own targets.
- **Specialists** — applied-mathematician, biz-dev-strategist, economic-historian, literature-scout,
  marketing-comms-expert, ml-engineer, prompt-engineer, prose-architect, theoretical-economist:
  single-purpose, invoked directly rather than as part of a coding pipeline.
  applied-mathematician carries the `fam-ask-vs-stipulate` anchor; `fam-gap-aversion` renders
  nowhere.
- **Tool-driving skills:** `adjagent` and `docdicer`, each one `SKILL.md` with no supporting files.
  `adjagent` is delivered by both plugins under every harness except mage, which omits it; `docdicer`
  and its tools package are delivered by both plugins.
  `docdicer.py` names its script `tools/docdicer`, relative to the skill's directory, and says its
  first run installs docdicer beside it; the script's `--help` is the command list, which the skill
  does not restate. The skill carries no runner-snippet advice and no install step; its one
  runner instruction is that where the project's runner includes the docdicer snippet, docdicer is
  run through the recipes (`docdicer`, `docdicer-check-plan`, `docdicer-kanban`, `docdicer-help`).
  It also carries a paragraph, an optional reference to `kbase` (Rendering, Placeholders), saying
  `kb-root/` belongs to kbase and docdicer leaves it alone unless the user directs otherwise; it
  renders only where kbase ships. `adjagent.py` states the rule for changing the
  installed tree — never edit it, put project behavior in CONVENTIONS.md or AGENTS.md, change the
  definitions only through a vendored copy or a fork — and how to update and inspect it, naming
  `adjagent install <plugin>` (the plugin spelled by the `@!plg-name!@` placeholder), `--dry-run` and `adjagent --version` and the runner's `ADJAGENT_VER` (the variable a consuming project's justfile or Makefile sets to pin the adjagent version). It also
  states how to run adjagent: the project's runner recipe where there is one, else the release tag
  installed into a venv and that venv's `adjagent`. Under claude a paragraph of its own, the
  `reload_rule` placeholder (Rendering, Placeholders), says to run `/reload-plugins` when
  the agents an install wrote are not offered; the paragraph drops where the harness supplies none.
  Under opencode a further paragraph, the `side_by_side_rule` placeholder, says how to stop
  opencode loading a claude install's skills. Mage omits the skill. The docdicer version the script
  installs is written once, as `VERSION` in `adjagent/docdicer-tools/docdicer`.
- **Development skill** — `development` (`definitions/development.py`): one `SKILL.md` and five
  supporting files (`references/new-project.md`, `project-documents.md`, `project-setup.md`,
  `adopting.md`, `release.md`), carried as `SkillFile`s, delivered by both plugins under every
  harness, mage included. Beside them in the skill's directory sits the development scripts
  package, `scripts/cold-read.sh`, owned by `development`: a shipped package, not one of the
  `SkillFile`s (Install, Renders and copies). The skill states one development process for the main
  session; the agents file's *Task management* points the session at it. `development.py` writes
  the plan, review document, design and set-aside locations and the form stated in SPEC.md, Plan
  Status Form, in three places: the *Terms* section's fixed table (the locations), the entry body's
  `## Plan status` section and `references/release.md`. Each term the process names (active plan,
  step-down model and the rest) is one module-level `*_TERM` constant that every
  mention in the six files interpolates; a test reads `development.py` and fails where a term's
  value is written literally in a body string, so no two mentions can name a term differently. Its
  `docdicer` references are optional references (Rendering, Placeholders), and `docdicer` ships
  with both plugins, so each fills. The *Plan status* section renders whole under every plugin;
  its `check-plan` bullet is a paragraph of its own, so an optional reference that fills to nothing
  drops that bullet alone. The sentence naming the default step-down model is
  `clauses.STEP_DOWN_MODEL`, the `tun` placeholder (Rendering, Placeholders), so that sentence alone
  renders only where the rendering assigns a model for the step-down tier.
- **Install machinery** — the one entry not rendered from a definition: `install.py` renders, copies
  and prunes; `install_base.py` holds what the install modules share (the package and checkout
  paths, the kb-tools package paths, the path checks, UTF-8 text reading and the report of what an
  install left alone); `runner_file.py` writes the runner include lines, one per `SnippetSet` the install passes it; `preflight.py` runs that
  install into a scratch copy and compares (Install, Renders and copies); `agents_file.py`
  does the same for the agents file (Agents File). The imports layer: `install_base.py`, `preflight.py` and `install_target.py` import
  no other install module; `runner_file.py` imports `install_base.py`; `agents_file.py` imports
  `install_base.py`, `install_target.py` and `preflight.py`; `install.py` imports all of them.
