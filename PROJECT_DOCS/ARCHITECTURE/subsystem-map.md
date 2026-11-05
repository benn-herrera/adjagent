## Subsystem Map

Every entry below but the last is rendered from the definition module under `adjagent/definitions/`
named for its output path, or for its set (Composition Model). A shared-text name given here is a constant or
function in `adjagent/clauses.py`, and an overlay anchor is spelled `fam-<key>`.

- **Coder family** — generalist-coder, language coders (c, cpp, go, lua, python, rust, typescript),
  shell-dsl-coder, platform experts (android/ios/linux/macos/web/windows-app-expert,
  linux-kernel-driver-expert), architect, and — sharing the coding-review domain — security-reviewer
  and tech-writer, which is both the author and the review seat for technical documentation.
- **kb set + kbase** — the `kbase` skill alone: the definition a base install excludes by name and
  a kb install delivers — except under mage, which always includes it. `kbase.py` owns a directory,
  `skills/kbase/SKILL.md` routing by request and
  `skills/kbase/references/reading.md`, `building.md`, `maintaining.md`, `scoring.md`, `scoring-system.md` and `installing.md` carrying what
  each route needs; the router is the only text every session pays for, and the rule that a
  reference is read only when its route is reached is the router's own — its *Route by the request*
  section says so, and nothing but that text stops a read.
  `clauses.kb_orientation`, carrying the KB system model with a per-reference `role=` clause, goes to the two
  references that work a KB the build has finished with — reading, which reports, and maintaining,
  which modifies; `building.md` and `scoring.md` carry what their own job needs.
  The skill and its references are project-portable — per-project facts live in the consuming
  project's `kb-root/AGENTS.md`, under every harness. The toolchain they drive is kbase, the executable the user installs
  with Homebrew (no install writes it), and the set's route to it is MCP-only: through the harness's
  `kbase` MCP server, offered under that harness's `mcp_tool_prefix`, and what the server offers is
  kbase's own surface. The router says so. When a request
  matches a route-table row other than installing and the server's tools are not offered, the router
  runs `command -v kbase` — a `PATH` lookup that runs nothing, so outside the rule that kbase runs
  only on the user's word — and reports what it found. No path: kbase is not installed, how it
  installs, and `references/installing.md` if the user wants the walkthrough. A path: kbase is
  installed and its MCP server is not running here, so the user enables, restarts or reconnects it
  in their harness, and `references/installing.md` covers a restart that does not bring the tools
  back. No other turn mentions installing kbase, and the installing row (`installing or upgrading
  kbase`) is the route that needs no tools. `installing.md` has the session show the Homebrew
  commands, read `kbase --version` against the minimum, name native Windows as unsupported, ask for
  a restart of the MCP server, and, for tools still not offered after one, tell the user the harness
  process may not find `kbase` on its own `PATH` and have them put Homebrew's `bin` directory on it;
  it runs a command only when the user asks it to. The minimum version and the formula are written
  once, as `KBASE_MIN_VERSION` and `KBASE_TAP_FORMULA` in `kbase.py`, and filled into the router
  and that reference. The executable and
  the `kb-` runner targets run only on the user's direction, and the skill defers to kbase's own text, and to
  `kb-root/AGENTS.md`, wherever it disagrees with them.
  Scoring is the one whose call outlives it: `score` starts the run detached and answers once the
  run has started, before its run ends. The loop is kbase's own, and `references/scoring.md`
  carries what kbase's own text does not.
  `clauses.KB_RUNNER_TARGETS` is the maintaining reference's: where the project's runner carries the
  installed `kb-` targets, `update-format`, `verify` and `stats` are `kb-update-format`, `kb-verify` and
  `kb-stats`, run only on the user's direction. The consumer's runner targets are the `kb-`-prefixed
  recipes of this repository's `adjagent/kb-tools/runner-snippets/kb.just` and `kb.mk`, prefixed so they cannot
  collide with a consuming project's own targets, each running `kbase` from `PATH`.
- **Specialists** — applied-mathematician, biz-dev-strategist, economic-historian, literature-scout,
  marketing-comms-expert, ml-engineer, prompt-engineer, prose-architect, theoretical-economist:
  single-purpose, invoked directly rather than as part of a coding pipeline.
  applied-mathematician carries the `fam-ask-vs-stipulate` overlay anchor; `fam-gap-aversion` was
  authored in the retired `kb-claim-scorer` module and now renders nowhere.
- **Tool-driving skills** — `adjagent` and `docdicer`, each one `SKILL.md` with no supporting
  files, in the default set under every harness, except that mage omits `adjagent` through
  `Harness.omits`, as it omits `imgread`; no install type excludes either. `docdicer.py` names its
  script `tools/docdicer`, relative to the skill's directory, and reads three states from running
  it: the script absent (a user-level install delivers no tools), the venv absent (offer
  `--install`, run only at the user's direction) and installed (the script's `--help` is the command
  list, which the skill does not restate). `adjagent.py` states the rule for changing the installed
  set — never edit it, put project behavior in CONVENTIONS.md or AGENTS.md, change the definitions
  only through a vendored copy or a fork — and how to update and inspect it, naming
  `adjagent install`, `--dry-run` and `adjagent --version` and the runner's `AGENTS_VER`. It also
  states how to run adjagent: the project's runner recipe where there is one, else the release tag
  installed into a venv and that venv's `adjagent`. Under claude a paragraph of its own, the
`reload_rule` hole (Composition Model, Holes), says to run `/reload-plugins` when the agents an
install wrote are not offered; the paragraph drops where the harness supplies none. Because mage omits
the skill and opencode supplies no rule, only claude renders it. The docdicer version the script installs is written once, as `VERSION` in
  `adjagent/docdicer-tools/docdicer`.
- **Process skill** — `dev-process` (`definitions/dev_process.py`): one `SKILL.md` and four
  references (`references/new-project.md`, `project-setup.md`, `adopting.md`, `release.md`), carried
  as `SkillFile`s, in the default set under every harness, mage included. It states one development
  process for the main session; the agents file's *Task management* points the session at it.
  Each term the process names (active plan, edit gate, step-down model and the rest) is one
  module-level `*_TERM` constant that every mention in the five files interpolates; a test reads
  `dev_process.py` and fails where a term's value is written literally in a body string, so no two
  mentions can name a slot differently. The skill is always delivered. The sentence naming the
  default step-down model is `clauses.STEP_DOWN_MODEL`, the `tun` hole (Composition Model, Holes),
  so that sentence alone renders only where the render pins a model for the step-down tier. The
  agents file and this skill are installed separately, so the pointer can name a skill the install
  has not written.
- **Install machinery** — the one entry not rendered from a definition: `install.py` renders, copies
  and prunes; `preflight.py` runs that install into a scratch copy and compares (Install
  Consumption Model, Renders and copies); `agents_file.py` does the same for the agents file
  (Agents File).
