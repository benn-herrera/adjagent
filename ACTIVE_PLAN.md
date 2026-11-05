# ACTIVE PLAN: the claude set in plugin form (ROADMAP item 4)

Design: `ACTIVE_PLAN_DESIGN.md`, cited here as D-n. Base commit: `3d36ff6` (branch `develop`). Every
line number cited below was re-taken at `3d36ff6`.

## Status

| Package | What | Rating | Lifetime | Runs on | State |
|---|---|---|---|---|---|
| — | Rulings R1–R6 (below) | owner | — | — | settled |
| — | Baseline slots at `b835f6d` (Planning-time actions) | coordinator | throwaway | — | done: four `reference*` slots, `just retake-reference` exit 0 |
| — | This plan: `prompt-engineer` usability review, then `architect` revision | — | — | — | done |
| P0 | Live check of the plugin mechanisms | user-run | throwaway | scratch | done; its consequences are in the P0 section |
| P1 | Reference holes and every cross-reference converted | expert | shipped | python-coder, then tech-writer | done (P1 checkpoint commit) |
| P2 | Install root inside the plugin directory | expert | shipped | python-coder, then tech-writer | not started |
| P3 | Guardrail registration in the plugin; retired settings entries removed | expert | shipped | python-coder, then tech-writer | not started |
| P3a | The agents file follows the set | expert | shipped | python-coder, then tech-writer | not started |
| P4 | Pre-release testing | user-run, with agent-run parts | throwaway | scratch | not started |
| P5 | Post-plan review, revision, burndown | review | — | reviewers | not started |

Packages share one build and one test suite, so they run **serially**: one dispatch at a time, each
on the agent's own model. No package is mechanical, so none runs on the step-down model.

## Kickoff decisions

- The claude harness carries two new data fields: `plugin_dir="skills/adjagent"` and
  `reference_prefix="adjagent:"`. ROOT becomes `harness_dir / plugin_dir`, so everything already
  resolved against ROOT lands inside the plugin (D-3).
- Cross-references are explicit reference holes, never a pattern rewrite of rendered prose
  (D-1.1, D-4).
- The agents file is never written inside the plugin. Under claude and opencode it follows the set
  per D-10.
- No test, render slot, `check-wheel` run or P4 install reads or writes the operator's real home.
  `HOME` points at scratch for all of them from P1 on (D-1.11). That is before P2's shadow check,
  the first code that reads a file under home.
- The docdicer venv stays at `tools/.venv` inside its skill, which is now inside the plugin. An
  install over the flat layout that found a venv rebuilds it there (D-6).
- opencode definitions are unchanged. mage's output changes at reference sites from P2 on (R7)
  and at the agents-file fence in P3a; otherwise it is unchanged. mage shares the manifest builder
  and the plugin-name constant (D-2).
- A retired copy is removed only by an install that writes its replacement (D-1.6).
- Do **not** run `just install-agents-here` before this plan lands. `.claude/` here is gitignored
  install output (`.gitignore:3` reads `.claude/`), and re-installing it mid-plan would rename
  every agent this session dispatches from `python-coder` to `adjagent:python-coder`.

## Rulings (settled; the work implements them)

- **R1. Claude is always the plugin, user level included.** One rendered form. Shadowing is
  **reported, never refused** (D-8): an install the user asked for is made in full.
- **R2. A user-level kb install writes the plugin's `.mcp.json`.** This is a SPEC change to
  Install destination's "no MCP entry". The file lies inside the plugin, and no user settings file
  is touched.
- **R3. The flat layout's `.claude/hooks/guardrail.pl` is removed.** SPEC Write Safety, which
  today says a harness-shipped file "is never removed", is amended. A harness file at a path a
  retired layout used is removed when it carries the `!INSTALLED! … adjagent` header and the same
  install writes its replacement (that is, when its probe passes).
- **R4. The agents file follows the set** (D-10).
  - On every claude or opencode project install: if the user-global agents file holds the
    adjagent fenced block, the install keeps that block current there and removes any project copy,
    reporting what and why.
  - If the global file holds no block, the install keeps the block current in the project's
    `AGENTS.md`, creating it if absent.
    - An existing `AGENTS.md` with no marker lines gets the block appended after one blank line,
      every other byte kept. This is the behaviour `install-agents-file` already has
      (`agents_file.py:197-198`, `render.appended_paragraph`).
    - The block never goes into a pointer file.
    - On this fallback branch only, under claude: an absent `CLAUDE.md` is created as the one-line
      redirect `@AGENTS.md`, as SPEC `harness-agents-file.md` already requires. An existing
      `@AGENTS.md` redirect is left as it stands. A `CLAUDE.md` holding anything else refuses the
      install with nothing written.
    - The global-first branch never reads or writes the project's `CLAUDE.md`.
  - The uncommitted-changes refusal follows R6.
  - Once the fenced region exists in the global file, it is sticky: project installs keep it there.
  - `--install-global-agents-file` and `install-agents-file ~/.claude` are how it first gets there.
- **R5. The install message.** A claude install that writes or changes the plugin, and the
  `adjagent` skill, both say exactly: "If the new agents are not available after using
  `adjagent install`, use `/reload-plugins` to rescan the agent list." The sentence names the
  symptom and the remedy only; the cause is Claude Code's and may change.
- **R6. The uncommitted-changes refusal guards live operator configuration only.** It applies to:
  - the agents-file write of a user-level install (`--install-global-agents-file`), whose ROOT is
    in the operator's real home; the rest of a user-level install is not refused;
  - `install-agents-file` whose destination is a harness's user-global directory.

  It does not apply to any project install, for any harness, a mage plugin below a project
  included. It never keys on `_in_user_dir`, which reads mage's relative user directory `.` as
  matching its own plugin directory. Landed in P1.
- **R7. Mage namespaces plugin components as Claude Code does.**
  - A mage plugin agent is invoked as `adjagent:<name>`, and a command as `/adjagent:<cmd>`.
  - Mage's `reference_prefix` is `adjagent:`, from the same plugin-name constant as claude's.
  - Landed in P2.

## Planning-time actions

1. Baseline slots, already taken by `just retake-reference` at `b835f6d`: `reference-claude`,
   `reference-mage`, `reference-opencode`, `reference-gemma`. No package re-takes them before
   P3a is accepted.
2. Plan review: Status row 3.

## Gates

From `PROJECT_DOCS/CONVENTIONS/planning-and-execution/the-gates.md`:
- **Edit gate:** `just test-changed <start>`, where `<start>` is `git rev-parse HEAD` at dispatch.
  Each brief states the hash and has it run after every edit.
- **Checkpoint gate:** `just test`, then `just sweep-python`. Run once before each package's
  checkpoint commit. The sweep's list is read, not only run.
- Contract documents move with each package: its tech-writer step lands in the same checkpoint as
  its code.

---

## P0: Live check of the plugin mechanisms (done)

Verified on Claude Code 2.1.311, with the old mechanisms still in place. This satisfies D-1.6 and
`clauses.PROVE_REPLACEMENT_RULE` (`adjagent/clauses.py:34`). The consequences:

- **Namespace required everywhere.** A plugin agent registers only as `<plugin>:<name>`, so the
  `subagent_type` is `adjagent:<name>`. A bare name is refused, and commands are namespaced the
  same way. D-4's single prefix stands: every reference renders `adjagent:<name>`.
- **`/reload-plugins` after trust or install.** A newly trusted workspace, or a freshly written
  plugin, registers its components only after a restart or `/reload-plugins`. R5's sentence
  carries this.
- **Plugin hooks work.** `${CLAUDE_PLUGIN_ROOT}` expands in a plugin hook command, and
  `guardrail.pl` blocks from there. P3's command form stands.
- **Plugin MCP works.** Tools are named `mcp__plugin_<plugin>_kbase__<tool>`. P2's claude prefix
  `mcp__plugin_adjagent_kbase__` stands.
- `claude plugin validate` accepts the layout. Its one warning is the missing icon.

---

## P1: Reference holes (expert; shipped)

**Outcome.**
- Every cross-reference in definition text is a reference hole, filled as
  `harness.reference_prefix + name`.
- Descriptions are filled as bodies are.
- An undiscovered name is refused.
- A guard test keeps the set exhaustive.
- Every harness's `reference_prefix` is `""` in this package, so every render is text-identical
  to the base.

**Scope: code.**
- `adjagent/vocabulary.py`: the reference spelling `@!ref-<name>!@` beside `hole()`. It matches
  `render.PLACEHOLDER`, `@![a-z0-9.-]+!@`.
- `adjagent/clauses.py`: `ref(name)`, returning that spelling.
- `adjagent/harness.py`: `Harness.reference_prefix: str = ""`.
- `adjagent/render.py`:
  - `filled_text` fills `@!ref-<name>!@` for every discovered definition name, the agents file
    included.
  - `_field_lines` and `agent_fields` fill `description` through the same fill. Today they pass it
    raw: `render.py:117` (`f"description: {quoted(cast(str, defn.description))}"`) and
    `render.py:72` (`description=defn.description,`).
- **Definition sites.**
  - Command A, the agent and command names plus `dev-process`:
    `git grep -n -E "(^|[^a-z0-9_/.-])(android-app-expert|applied-mathematician|architect|biz-dev-strategist|c-coder|cpp-coder|economic-historian|generalist-coder|go-coder|ios-app-expert|linux-app-expert|linux-kernel-driver-expert|literature-scout|lua-coder|macos-app-expert|marketing-comms-expert|ml-engineer|prompt-engineer|prose-architect|python-coder|rust-coder|security-reviewer|shell-dsl-coder|tech-writer|theoretical-economist|typescript-coder|web-app-expert|windows-app-expert|imgread|dev-process)([^a-z0-9_-]|$)" -- adjagent/definitions adjagent/clauses.py adjagent/families | grep -v -E ':1:"""|name="'`
  - Command B, the three names that are also an executable, tool or CLI:
    `` git grep -n -E '`(docdicer|kbase|adjagent)` (skill|agent|command)' -- adjagent/definitions adjagent/clauses.py ``
  - **Convert** (from A):
    - descriptions:
      - `generalist-coder` in `android_app_expert.py:13`, `c_coder.py:11`, `cpp_coder.py:11`,
        `go_coder.py:12`, `ios_app_expert.py:13`, `linux_app_expert.py:13`, `lua_coder.py:13`,
        `macos_app_expert.py:13`, `python_coder.py:12`, `rust_coder.py:12`,
        `shell_dsl_coder.py:13`, `typescript_coder.py:13`, `web_app_expert.py:13`,
        `windows_app_expert.py:13`
      - `go-coder` in `shell_dsl_coder.py:13`
      - `web-app-expert` in `typescript_coder.py:14`
      - `typescript-coder` in `web_app_expert.py:14`
      - `applied-mathematician` in `ml_engineer.py:14`
      - `tech-writer` twice in `prompt_engineer.py:17`
    - bodies:
      - `architect.py:170` (`security-reviewer`)
      - `dev_process.py` 62, 122, 191, 218, 221
      - `prompt_engineer.py:32`
      - `tech_writer.py:221`
      - `harness_agents_file.py:25` (`dev-process`) and `:52` (prompt-engineer)
  - **Convert** (from B): `dev_process.py` 100 and 223 (the `docdicer` skill).
  - **Stay bare** (D-4):
    - from A: `architect.py:20` ("software architect"); `security_reviewer.py` 12, 18, 38, 128,
      130; `tech_writer.py:142`; and the `families/gemma_4.py` 26 and 76 comments;
    - from B: `adjagent.py:34` (the CLI).
- `devtools/scripts/_render-slot.sh` and `devtools/scripts/check-wheel.sh` export `HOME` to an
  empty scratch home: `.claude-temp/render-home/<slug>` and `${scratch}/home` respectively. Each
  is created fresh and removed on exit (D-1.11). Before P2 an install only compares its target
  with `Path.home()` (`install_target.py:106`), so a scratch home changes no render. It lands here
  with the test fixture below so that P2's shadow check, the first code that reads a file under
  home, never reaches the real one.
- R6, the uncommitted-changes refusal:
  - Move the refusal out of `checked_agents_file` (`agents_file.py:170-174`) into its two callers.
  - `install` applies it only when `user_level` is true (`install.py:1123`; the
    `checked_agents_file` call at `install.py:1174`).
  - `install_agents_file` and `preflighted_agents_file_install` apply it only when
    `install_target.user_dir_harnesses(directory)` is non-empty. That predicate matches absolute
    user directories only, so mage's relative `.` never matches.
  - `install.py:1092`'s docstring ("refused while `uncommitted` names a change") and the
    `agents_file.py:12` module docstring change to match.
- **Tests.**
  - `tests/test_adjagent_install.py:494-502`
    (`test_every_skill_the_agents_file_cites_ships_in_the_harness_default_install`): read the
    reference holes from the agents-file definition's source, not rendered prose (D-7).
  - New `tests/test_cross_references.py`: the D-7 guard, covering bodies, descriptions, `SkillFile`
    bodies, the agents file and family overlay texts, plus a teeth case. Use the shape of
    `tests/test_manifest_views_in_definitions.py`.
  - `tests/test_adjagent.py`: an undiscovered reference is refused naming the definition, and a
    description's hole is filled. Each holds under `dataclasses.replace(<harness>, reference_prefix="x:")`.
  - New `tests/conftest.py`: an autouse fixture that sets `HOME` to a per-test scratch home
    (D-1.11). It generalises the `_home` fixtures at `tests/test_install_target.py:40` and
    `tests/test_adjagent_install.py:75`, which then build on it. A test asserts that, during the
    suite, `Path.home()` differs from `pwd.getpwuid(os.getuid()).pw_dir`.
  - R6, with uncommitted sources:
    - a mage install below its project root writes its `CLAUDE.md`;
    - `install-agents-file` into a project directory writes;
    - a user-level install given `--install-global-agents-file` is refused with nothing written;
    - `install-agents-file` into a user-global directory is refused with nothing written.
  - Existing tests that pin the old refusal are adjusted to R6:
    `tests/test_install_target.py:145` (`test_a_mage_install_with_uncommitted_sources_writes_nothing`)
    and `tests/test_adjagent_install.py:210` (`test_uncommitted_sources_refuse_the_install`, which
    installs into a project directory).

**Scope: docs (tech-writer, same checkpoint).**
- `PROJECT_DOCS/ARCHITECTURE/composition-model/holes.md`: the `ref` hole, its closed set and that
  it fills descriptions.
- New leaf `PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/cross-references-are-holes.md`,
  with its line added to the CONVENTIONS entry-point Contents.
- R6:
  - SPEC `harness-agents-file.md:33-34`: "Installation from a clone is refused while the
    generator's sources carry uncommitted changes" narrows to the agents-file write of a
    user-level install and to `install-agents-file` into a user-global directory. No project install is refused, mage below
    a project included.
  - CONVENTIONS `code-definitions-and-install/harness-agent-file-changes-explicitly.md`: the same
    narrowing.
  - ARCHITECTURE `agents-file.md` and `install-consumption-model/install-entry.md`: where the
    refusal is applied.

**Facts.**
- No reference mechanism exists. Command:
  `git grep -n -i 'prefix\|namespace' -- adjagent/render.py adjagent/vocabulary.py adjagent/context.py adjagent/harness.py`.
  Answer: only `mcp_tool_prefix` (`harness.py:112`, `vocabulary.py:75`) and the hole-namespace map
  (`vocabulary.py:109-116`).
- Calls belong inside `DEFINITIONS`. `definition-modules-hold-only-constants.md`: "A definition
  module holds nothing but imports, string constants and `DEFINITIONS`." So `{clauses.ref("…")}`
  goes inside the f-strings, and a plain-string description becomes an f-string.
- Filled text is never rescanned (`composed-text-is-never-rescanned.md`), so overlays cannot carry
  references.

**Changed signatures and reference searches.**
- `Harness` gains a defaulted field. Command: `git grep -n 'Harness(' -- adjagent tests`. Answer:
  `claude.py:93`, `mage.py:56`, `opencode.py:34`. No edit is needed at any of them.

**Done-line.**
1. `just test`.
2. `just render p1-claude`; `just render p1-mage --harness=mage`;
   `just render p1-opencode --harness=opencode --model-tier-map=all=inherit`;
   `just render p1-gemma --family=gemma-4 --model-pin-tier-alias-map=all=sonnet`.
3. `just render-diff reference-claude p1-claude`, `just render-diff reference-mage p1-mage`,
   `just render-diff reference-opencode p1-opencode` and `just render-diff reference-gemma p1-gemma`:
   each reports no differing file.
4. After step 2, `command ls .claude-temp/render-home/` lists no slot directory, because each was
   removed on exit.
5. `just sweep-python`, its list read.

---

## P2: Install root inside the plugin directory (expert; shipped)

**Outcome.**
- A claude install writes the set to `<harness_dir>/skills/adjagent/`, with
  `.claude-plugin/plugin.json` and, on any kb install (user-level included, R2), the plugin's
  `.mcp.json`.
- References render `adjagent:<name>` under claude and mage (R7), and the claude MCP prefix is
  `mcp__plugin_adjagent_kbase__`. Mage's MCP prefix is unchanged.
- The flat layout's generated files and, on a project install, its package destinations are
  removed.
- The kb include line names the new path.
- Shadowing is reported.
- R5's sentence is printed and rendered.
- The guardrail is still registered in `.claude/settings.json` until P3, now naming
  `.claude/skills/adjagent/hooks/guardrail.pl`. The existing recogniser matches any harness
  relpath (`claude.py:55-57`), so it replaces an earlier entry in place.

**Scope: code.**
- `adjagent/vocabulary.py`: `OptionalHarnessText.RELOAD_RULE = "reload_rule"`.
- `adjagent/harness.py`:
  - `Harness.plugin_dir: str = ""` (distinct from `plugin_parent_dir`, D-3).
  - `Harness.reload_rule: str = ""`.
  - Rename `is_plugin` to `is_standalone_plugin`.
  - Move the plugin-manifest builder here from `mage.py:12-24`. It becomes one builder taking a
    description and returning the `HarnessFile` with marker `"name": "<PLUGIN_NAME>"`.
  - `PLUGIN_NAME = "adjagent"` moves here from `mage.py:12` (`_PLUGIN_NAME`). It is the one
    spelling of the plugin name: the manifest name, every `reference_prefix`
    (`f"{PLUGIN_NAME}:"`), claude's `plugin_dir` and claude's MCP prefix all derive from it.
- `adjagent/harnesses/claude.py`, all from `PLUGIN_NAME`:
  - `plugin_dir="skills/adjagent"` and `reference_prefix="adjagent:"`.
  - `mcp_tool_prefix="mcp__plugin_adjagent_kbase__"`.
  - `mcp=McpSettings(canonical=".mcp.json", …, site=McpSite.HARNESS, …)`.
  - `rendered_files=(<shared manifest>,)`.
  - `reload_rule=` R5's sentence, verbatim.
- `adjagent/harnesses/mage.py`:
  - the shared builder, with identical manifest bytes and marker;
  - `reference_prefix=f"{PLUGIN_NAME}:"` (R7);
  - no other value changes.
- `adjagent/definitions/adjagent.py`: after the *Updating* paragraph, the reload-rule hole as a
  paragraph of its own. An empty optional text drops the paragraph it stands in, so it must not
  share *Updating*'s paragraph. mage omits this skill; under opencode the paragraph drops.
- `adjagent/install_target.py`:
  - `InstallTarget.root` becomes `harness_dir`; resolution is otherwise unchanged. `--subdir=<dir>`
    names `<target>/<dir>`, now the harness directory.
  - A target that is the harness's user directory stays user-level.
- `adjagent/cli.py:117`: pass `target.harness_dir`.
- `adjagent/install.py`, in `install`:
  - `install(harness_dir, …)` computes `ROOT = harness_dir / ctx.harness.plugin_dir`;
    `real_root` becomes `real_harness_dir`.
  - User-level is decided on the harness directory (`install.py:1123`, today on ROOT).
  - The plugin harness's agents file goes to the harness directory (`_installs_agents_file`,
    `checked_agents_file` at `install.py:1174`).
  - The sticky kb signal also reads `<harness_dir>/skills/kbase/SKILL.md` where `plugin_dir` is
    non-empty (D-5; `install.py:1127`).
  - `prune` walks `<harness_dir>`'s surfaces with the same `keep` (D-1.7). `LEGACY_TREES` are
    removed under `<harness_dir>`.
  - **On a project install where `plugin_dir` is non-empty**, the `_packages(kb_included=True)`
    destinations under `<harness_dir>` are removed whole, each named in the report. A user-level
    install never removes them.
  - The docdicer venv rebuild triggers on a venv at either destination
    (`_docdicer_venv_to_rebuild`).
  - The MCP write is split from the runner line. Today both are gated by
    `project_kb_files = kb_included and not user_level` (`install.py:1138`). New gates:
    - the MCP merge runs on a kb install that is either a project install, or user-level with
      `mcp.site is McpSite.HARNESS` (R2);
    - the include line stays project-only and non-standalone.
  - Include-line rule per D-5 (`install.py:1017-1041`).
  - Shadow report per D-8, through `_report_left_alone`.
  - After a run that wrote under ROOT, print `reload_rule` when it is non-empty. An up-to-date run
    prints nothing: the preflight returns before the real install.
- `adjagent/install.py`, in `preflighted_install` (`install.py:1271-1329`), which moves with
  `install`:
  - Its user-level decision at `install.py:1295` (`user_dir_harnesses(root)`) reads the harness
    directory.
  - Its dry-run note is built from `_harness_relpath(root, project)` (`install.py:1306`), with
    ROOT computed as `install` computes it.
  - It passes the harness directory to `_install_managed_paths`.
- `_install_managed_paths`:
  - covers the project root, the harness directory (surfaces, `LEGACY_TREES`, retired package
    destinations, the agents-file paths) and the nested ROOT (ARCHITECTURE, Renders and copies: "A
    base nested in another keeps its position below the outer one");
  - at user level, lists the MCP candidates under ROOT where the site is `HARNESS` (today skipped
    at `install.py:1253`).
- Docstrings for the module, `install` and `preflighted_install`.
- `devtools/scripts/render.sh`, `devtools/scripts/_render-slot.sh`: comments on the plugin path;
  a claude slot holds the plugin at `<slot>/skills/adjagent/`.
- **Tests.**
  - `tests/test_adjagent_install.py`: claude layout assertions move into the plugin, and
    `_definition_install` passes the harness directory. Add cases for migration, include line,
    sticky signal, shadow report, user-level kb `.mcp.json`, no package removal at user level,
    reload sentence printed or not, and dry-run prediction (D-9.5, D-9.8).
  - `tests/test_install_target.py`: `harness_dir`; the user-level plugin path.
  - `tests/test_adjagent.py`: the harness-text table (`533-540`). The mage manifest tests
    (`440-470`) pass unchanged.
  - New, in `tests/test_adjagent.py`: **a prefix changes nothing but reference sites.** For each
    harness with a non-empty `reference_prefix` (claude, mage), take `render_all` (and
    `render_agents_file`) under the harness and under
    `dataclasses.replace(harness, reference_prefix="")`.
    - Every path's text with every `<prefix>` occurrence removed equals the bare render's text.
    - The bare render contains no `<prefix>` occurrence.
    - This is what makes D-9.7 checkable.

**Scope: docs (tech-writer, same checkpoint).** The source is the command
`git grep -n -E '\.claude/(agents|commands|skills|hooks|settings)|\.mcp\.json|settings\.json|mcp__kbase' 3d36ff6 -- docs README.md PROJECT_DOCS`.
Its answer is 27 lines, the same lines as at `1049e2f`. Each line's owner:
- P2:
  - `ARCHITECTURE/composition-model/harnesses-and-families.md:4`
  - `ARCHITECTURE/install-consumption-model/base-and-kb-installs.md:32`
  - `ARCHITECTURE/sanctioned-invocation.md:41`
  - `SPEC/deployed-surfaces/installed-artifacts.md:30`
  - `README.md:77`
  - `docs/definition-sets.md` 74, 78
  - `docs/development.md:40`
  - `docs/install-reference.md` 45, 46, 105, 106, 108, 110
  - `docs/knowledge-base.md` 63, 70, 75, 85
- P3:
  - `ARCHITECTURE/install-consumption-model/guardrail-hook.md` 7, 19
  - `ARCHITECTURE/install-consumption-model/install-entry.md:26`
  - `SPEC/deployed-surfaces/shipped-files.md:77`
  - `SPEC/write-safety.md:22`
  - `docs/guardrail.md` 23, 29, 32
- Stays: `SPEC/mage-plugin-distribution.md:23` (mage).

Leaves P2 also changes beyond those lines:
- SPEC `deployed-surfaces/`:
  - `surfaces-and-layout.md`: the manifest under claude;
  - `install-destination.md`: the ROOT table, harness directory vs ROOT, the user-level plugin,
    and R2's MCP change;
  - `base-and-kb-installs.md`: the MCP file at the plugin root, user-level included; the
    include-line path;
  - `shipped-files.md`: destinations in the plugin.
- SPEC `write-safety.md` (prune and the retired-layout removal), `generation-system.md` (a
  reference renders with the harness's prefix).
- ARCHITECTURE:
  - `install-consumption-model/install-entry.md`, `renders-and-copies.md` (managed set) and
    `installing-this-repository.md`;
  - `composition-model/holes.md` (`reload_rule`);
  - `agents-file.md`, `repo-layout.md`, `subsystem-map.md`.
- Docs note: a project plugin loads only when the session starts at the project root, after the
  trust dialog
  (<https://code.claude.com/docs/en/plugins/loading>, "Check why a repository plugin didn't load").

**Facts.**
- Prose names no installed path below the harness directory. Command:
  `git grep -n 'PROJECT_HARNESS_DIR\|MCP_TOOL_PREFIX' -- adjagent/definitions adjagent/clauses.py`.
  Answer: `clauses.py` 15, 18, 249; `harness_agents_file.py:19`; `kbase.py:179`. So
  `project_harness_dir` stays `.claude`.
- `guardrail.pl:20` reads `(my $kb_signal = $0) =~ s{[^/]*/[^/]*\z}{skills/kbase/SKILL.md};`. At
  `<plugin>/hooks/guardrail.pl` that is `<plugin>/skills/kbase/SKILL.md`, where the kb skill now
  sits.
- Mage's ROOT is its harness directory: `mage.py:61` `project_harness_dir="adjagent"`, `:64`
  `user_harness_dir="."`. `mage-dist.sh:35-36` installs with `--subdir= --harness=mage`.
  `plugin_dir=""` leaves it unchanged.
- Render slots run a project install. `_render-slot.sh:41`:
  `install "${out}" --subdir= --with-kb "${args[@]}"`. A claude slot's harness directory is the
  slot.
- Release tags exist (`git tag` lists `v0.14.0`), so migration is required.

**Changed signatures and reference searches.**
- `install(` and `real_root`. Command:
  `git grep -n -E '(^|[^_a-z.])install\(' -- adjagent tests devtools`. Answer:
  - `install.py` 1062 (def), 1313 (lambda);
  - `preflight.py` 170, 217 (generic, unchanged);
  - `tests/test_adjagent_install.py` 364, 992, 1313, 1333, 1341, 1348, 1416, 1467, 1487, 1517,
    1538, 1550, and 676 (a docstring).
  - `git grep -n real_root -- adjagent tests devtools` answers `install.py` 1072, 1114, 1123,
    1174, 1322.
- User-level decisions. Command: `git grep -n 'user_dir_harnesses(' -- adjagent`. Answer:
  `install.py` 1123, 1295; definitions at `install_target.py` 130 and 146 (unchanged).
- `InstallTarget.root`. Command:
  `git grep -n -E 'target\.root|InstallTarget' -- adjagent tests devtools`. Answer: `cli.py:117`;
  `install_target.py` 27, 94, 120.
- `is_plugin`. Command: `git grep -n is_plugin -- adjagent tests devtools`. Answer:
  `harness.py:172`; `install.py` 1052, 1127, 1214; `install_target.py` 47, 54, 115;
  `tests/test_adjagent_install.py:500`.
- Mage manifest. Command: `git grep -n '_plugin_json\|mage.FILES\|rendered_files=FILES' -- adjagent tests`.
  Answer: `mage.py` only.

**Done-line.**
1. `just test` (the `wheel` surface included).
2. `just render p2-claude`; `just render p2-mage --harness=mage`;
   `just render p2-opencode --harness=opencode --model-tier-map=all=inherit`.
3. `just render-diff reference-opencode p2-opencode` reports no differing file.
4. `just render-diff reference-mage p2-mage` reports differing files only, with none only on one
   side, and every one holds `adjagent:`:
   - `grep -L 'adjagent:' <each reported p2-mage file>` prints nothing.
   - That each difference is a reference site is pinned by step 1's prefix test (R7, D-9.7).
5. `rendered/p2-claude/skills/adjagent/.claude-plugin/plugin.json` and `.../.mcp.json` exist, and
   `rendered/p2-claude/agents/` does not.
6. `just sweep-python`, its list read.

---

## P3: Guardrail registration in the plugin; retired settings entries removed (expert; shipped)

**Outcome.**
- The plugin's `hooks/hooks.json` registers the guardrail. It is written only when the probe
  passes, and its command runs `${CLAUDE_PLUGIN_ROOT}/hooks/guardrail.pl` behind the existing
  missing-script guard.
- `.claude/settings.json` is no longer written to register anything. An earlier install's element
  is removed from it, as is an earlier kb install's `kbase` member in the project `.mcp.json`,
  under D-1.6 and D-1.9.
- The flat layout's `.claude/hooks/guardrail.pl` is removed (R3).

**Scope: code.**
- `adjagent/harness.py`:
  - `GuardrailHook` becomes `script` plus `registration`, a `HarnessFile`: path `hooks/hooks.json`,
    a text builder, and a marker that is a substring of the rendered command only this repository
    writes.
  - A retired-entry record: settings path relative to the project, container path,
    element-or-member, and a recogniser returning `HookClaim`.
  - `Harness` gains a tuple of retired entries, empty by default.
  - `__post_init__` validation updated.
- `adjagent/harnesses/claude.py`:
  - the registration builder, matcher `Bash|Read|Write|Edit|NotebookEdit|Grep|Glob` as today;
  - delete `_guardrail_entry` and its refusal;
  - keep `_GUARDRAIL_COMMAND` and `_guardrail_claim` as the retired element's recogniser;
  - add the retired `mcpServers.kbase` member's recogniser: command `kbase`, or a path whose last
    segment is `kbase`.
- `adjagent/install.py`:
  - Write the registration as a harness-file-class target. It is refused where a file at its path
    lacks the marker, and written only when the probe passes.
  - Delete `guardrail_merge`, the guardrail `_check_settings` call, and the harness-directory
    quoting refusal.
  - A removal operation beside `_splice`/`_splice_element`: one object member or one array
    element, every other byte kept, an emptied container left in place.
  - Each retired entry's removal runs behind `_check_settings` and `_settings_obstacle` and the
    existing one-or-ambiguous decision. One ALONE claim is removed. SHARED, several, JSONC or an
    obstacle is reported with the entry printed and left.
  - Conditions: the settings element when the probe passed; the project `kbase` member on a kb
    install.
  - `<harness_dir>/hooks/guardrail.pl` is removed when it carries the installed header and the
    probe passed, then `<harness_dir>/hooks/` if empty (R3).
  - `_earlier_guardrail`, on a failed probe, names the script and registration an earlier install
    left.
  - `_install_managed_paths`: the registration under ROOT, `hooks/guardrail.pl` under the harness
    directory, and both settings files under the project.
- **Tests.**
  - `tests/test_adjagent_install.py`: the settings-merge cases (helpers `_hook_entry` at 401 and
    `_claude_root` at 1714; cases about 419-431 and 1714-1921) become registration and removal
    cases, and the project's own hook survives byte-for-byte.
    `test_the_registered_command_runs_the_script_the_install_wrote` (1867) runs the hooks.json
    command with `CLAUDE_PLUGIN_ROOT` set, and a missing script exits 1, not 2.
  - `tests/test_guardrail.py:205`: the matcher from the registration.

**Scope: docs (tech-writer, same checkpoint).**
- The P3 lines of P2's 27-line list.
- SPEC `write-safety.md`: the settings edit becomes the removal of earlier entries; the quoting
  refusal goes; R3's amendment.
- ARCHITECTURE `install-consumption-model/guardrail-registration.md` (registration and removal,
  links kept valid), `composition-model/harnesses-and-families.md` (`guardrail`, retired entries).
- `CONVENTIONS/code-definitions-and-install/guardrails-change-together.md`: check only.
  `guardrail.pl` still reads `$CLAUDE_PROJECT_DIR` path words.
- `docs/guardrail.md:40`.

**Facts.**
- Hook processes receive `CLAUDE_PLUGIN_ROOT`, and a command with no `args` runs through a shell,
  so the path is quoted
  (<https://code.claude.com/docs/en/plugins/components>, "Environment, quoting, and matching MCP
  tools").
- Plugin hooks use `hooks/hooks.json` with a top-level `"hooks"` key in the settings shape (same
  page, "Hooks").
- `claude.py:55-57`:
  `_GUARDRAIL_COMMAND = re.compile(rf"{re.escape(_GUARDRAIL_COMMAND_HEAD)}(?:[^{_UNQUOTABLE}]+/)?{re.escape(_GUARDRAIL_COMMAND_TAIL)}")`.
  It recognises both the 0.14.0 entry and P2's.
- Older kbase entries vary by version. `git grep -n 'mcp.entry(' v0.12.0 -- adjagent/install.py`
  answers `entry(command=command, project_root=project)`, and v0.11.0 installed a `kbase` binary.
  So the recogniser reads the command alone.

**Changed signatures and reference searches.**
- `GuardrailHook`. Command: `git grep -n GuardrailHook -- adjagent tests devtools`. Answer:
  `harness.py` 88, 124; `claude.py` 10, 122; `install.py` 28, 819, 832, 879.
- Its fields. Command:
  `git grep -n -E 'guardrail\.(entry|settings|container|claim|script)' -- adjagent tests devtools`.
  Answer: `harness.py` 159-164; `install.py` 820-885, 1141, 1168-1169, 1220, 1261;
  `tests/test_adjagent_install.py:405`; `tests/test_guardrail.py:205`.
- Helpers. Command:
  `git grep -n 'guardrail_merge\|_guardrail_claims\|_earlier_guardrail\|_splice_element' -- adjagent tests`.
  Answer: `install.py` only.

**Done-line.**
1. `just test`.
2. `just render p3-claude`; `just render p3-mage --harness=mage`;
   `just render p3-opencode --harness=opencode --model-tier-map=all=inherit`.
3. `just render-diff p2-mage p3-mage` and `just render-diff reference-opencode p3-opencode` each
   report no differing file. Mage is compared with P2's slot, since P2 changed its reference sites.
4. `rendered/p3-claude/skills/adjagent/hooks/hooks.json` and `.../hooks/guardrail.pl` exist.
5. `just sweep-python`, its list read.

---

## P3a: The agents file follows the set (expert; shipped)

**Outcome.** D-10 and R4: on every claude and opencode project install, the block is kept current
in exactly one place, with the version stamp and no churn. Agents-file placement for mage (in its
plugin) and for user-level installs is unchanged. Mage's agents file gains only the version
stamp.

**Scope: code.**
- `adjagent/vocabulary.py`: `AgentsFileText.VERSION = "version"`, giving `@!agf-version!@`.
- `adjagent/render.py`: `filled_text` fills it, for the agents file only, from
  `adjagent.__version__`.
- `adjagent/definitions/harness_agents_file.py:14`: the begin fence becomes
  ` <!-- vvv-adjagent @!agf-version!@ do not edit at or between marker lines. adjagent-vvv -->`,
  leading space kept, spelled through the vocabulary.
- `adjagent/agents_file.py`:
  - global-first placement;
  - project-copy removal (span removed, other bytes kept, rolling backup, the file kept even if
    left empty);
  - content comparison with the fence lines excluded;
  - the D-10 version table;
  - reports.
  - The global path is resolved only as `Path(harness.user_harness_dir).expanduser()`, as
    `_in_user_dir` does at `agents_file.py:57`.
  - The uncommitted-changes refusal is P1's (R6). The global-first write is a user-global
    destination, so it is refused; the project `AGENTS.md` and its redirect are not.
- `adjagent/install.py`: call it on a claude or opencode project install, never for
  `is_standalone_plugin` or user-level.
- `_install_managed_paths`:
  - the global file and its backup, with the global file's directory as a base, so dry-run prints
    those paths whole;
  - the project's `AGENTS.md` and its backup;
  - under claude, the project's `CLAUDE.md` (the redirect R4's fallback branch creates).
- **Tests.**
  - every row of the version table, including the planted `version[abc1234]` fence at
    `tests/test_adjagent_install.py:111`;
  - the no-churn case (a version bump with identical content writes nothing);
  - global-first with project-copy removal and its report: the project's `AGENTS.md` stays, even
    when emptied, and its `CLAUDE.md` redirect stays valid;
  - project fallback creating `AGENTS.md`, and under claude the `CLAUDE.md` redirect where absent;
  - on the fallback branch, a project `CLAUDE.md` holding anything but the redirect refuses with
    nothing written; on the global-first branch the same file is neither read nor refused;
  - a project install with uncommitted sources writes the project `AGENTS.md` and redirect, while
    the global-first write under uncommitted sources is refused with nothing written;
  - stickiness;
  - a fence parse fed the real rendered fence (CONVENTIONS, *Recognizer spells rendered banner*).

**Scope: docs (tech-writer, same checkpoint).**
- SPEC `harness-agents-file.md`:
  - Replace "installed only by explicit act" with R4 as worded above.
  - Replace "for any other harness it never does" with the claude and opencode project-install
    case.
  - The existing redirect and refusal rule ("A file of that other name holding anything else is
    refused with nothing written") now governs project installs on the fallback branch.
  - The stamp is the version that last changed the content.
  - Mage's agents-file placement is unchanged: it stays in its plugin. Its block names
    `adjagent:<name>` per R7, a P2 change.
- CONVENTIONS `code-definitions-and-install/harness-agent-file-changes-explicitly.md`: R4's rule.
  - Publishing stays a manual edit, and the first global adoption stays explicit.
- SPEC `deployed-surfaces/install-destination.md:34-35` ("On a project install the flag is
  ignored, with no error and no write"): the flag stays ignored, but a claude or opencode project
  install now writes the agents file per R4.
- ARCHITECTURE `install-consumption-model/install-entry.md:13-14`: the sentence on where
  `install.py` writes the agents file adds the claude and opencode project-install case.
- ARCHITECTURE `agents-file.md`; `docs/agents-file.md`; `docs/install-reference.md`.
- `docs/agents-file.md`, a section for projects with several contributors.
  - Symptom: a tracked `AGENTS.md` flips between contributors. Whether the block sits in the
    project file depends on whether each contributor's global agents file holds it.
  - Remedy: each contributor runs `git update-index --skip-worktree AGENTS.md` in their own
    clone, so their copy may differ without showing as a change.
  - Limit: a pull that brings an upstream change to `AGENTS.md` stops with "would be
    overwritten". Clear the flag with `--no-skip-worktree`, merge, then set it again.
- `docs/development.md`: a slot now holds `AGENTS.md` and, under claude, `CLAUDE.md`, and slots
  run under a scratch `HOME`.

**Facts.**
- Fences are recognised by their fixed ends: `agents_file.py:26-27`,
  `BEGIN = ("<!-- vvv-adjagent", "adjagent-vvv -->")`, checked by `_is_marker` (`:34-36`). A
  version between the ends parses unchanged, and an unversioned fence still parses.
- `harness_agents_file.py:14`:
  ` <!-- vvv-adjagent do not edit at or between marker lines. adjagent-vvv -->`. No version hole
  exists (`grep -n -i version adjagent/agents_file.py` returns nothing).
- No claude or opencode project install writes an agents file today. `install.py:1047-1053`:
  `_installs_agents_file` returns `plugin_below_project or (user_level and global_agents_file)`.
- The resolver already reads `HOME` (`install_target.py:106`, `Path.home()`), and the existing
  `_home` fixtures set it (`tests/test_install_target.py:44`, `monkeypatch.setenv("HOME", …)`).

**Done-line.**
1. `just test`.
2. `just render p3a-claude`; `just render p3a-mage --harness=mage`;
   `just render p3a-opencode --harness=opencode --model-tier-map=all=inherit`.
3. `just render-diff p3-<h> p3a-<h>` for each harness.
   - mage: the agents file differs only in its begin-fence line.
   - claude and opencode: `harness/<h>/<agents file>` differs only in its begin-fence line, and
     `AGENTS.md` is reported only in `p3a-<h>`. Under claude, `CLAUDE.md` (holding only
     `@AGENTS.md`) is also reported only in `p3a-claude`.
   - No other file differs.
4. `just sweep-python`, its list read.

Steps 1-2 run before the checkpoint commit, with `adjagent/` uncommitted. They pass because the
render slots and `check-wheel` run under a scratch home with no global block, so they write only
the project `AGENTS.md`, which the uncommitted refusal (R6, landed in P1) does not reach.

**After P3a is accepted:** `just retake-reference`
(`CONVENTIONS/planning-and-execution/reference-retakes-follow-acceptance.md`).

---

## P4: Pre-release testing (user-run where a fresh session is needed; throwaway)

**Scope.**
- Scratch projects under `.claude-temp/prerelease/`, each with `git init`. Nothing is committed.
- Every command runs from the repository root and spells its paths absolutely through `$PWD`. A
  `just --justfile` recipe runs in its justfile's directory, so a relative path would resolve
  there instead.
- Scratch homes:
  - `$PWD/.claude-temp/prerelease/home` for A and B;
  - `$PWD/.claude-temp/prerelease/home-migrate` for C.
  - Each is created with `mkdir -p "$PWD/.claude-temp/prerelease/<home>/.claude"` before first
    use.
- The sessions run under the operator's real home, which no install here writes.
- Results go in the Status table, and a failure becomes a fix package before release.

**A. Fresh project** (`.claude-temp/prerelease/fresh/`, holding a `justfile` and one markdown file
of about 60 lines; the scratch home empty):
1. Coordinator:
   `HOME="$PWD/.claude-temp/prerelease/home" just install-with-kb "$PWD/.claude-temp/prerelease/fresh"`.
   - The output ends with R5's sentence.
   - A second run reports up to date and prints no sentence (D-9.8).
2. Coordinator, or the user where the sandbox refuses:
   `claude plugin validate "$PWD/.claude-temp/prerelease/fresh/.claude/skills/adjagent"`. No error.
3. User:
   `"$PWD/.claude-temp/prerelease/fresh/.claude/skills/adjagent/skills/docdicer/tools/docdicer" --install`
   (needs the network), then step 2 again with the venv present. Compare the outputs.
4. The project holds `AGENTS.md` with the stamped block, and `CLAUDE.md` holding only
   `@AGENTS.md` (R4).
5. User, in a fresh trusted session at the project root, then `/reload-plugins`:
   - `/plugin` lists `adjagent@skills-dir`. Check the Errors tab with the venv present.
   - Ask for the `adjagent:architect` agent; expect `subagent_type` `adjagent:architect`.
   - Load the `adjagent:dev-process` skill; run `/adjagent:imgread`.
   - `sed -i` on a tracked file → `Blocked:`; a write into `.claude-temp/` is allowed.
   - `/mcp`: approve `plugin:adjagent:kbase`, then call `mcp__plugin_adjagent_kbase__status`.
     Expect the project resolved.
   - Use the docdicer skill to dice the markdown file and undice it to a new file. Record any
     loader or tool error attributable to the venv inside the plugin.
   - The session also loads the real global block (0.14.0, bare names such as `dev-process`). A
     failure that traces to it is recorded as such, not as a plugin defect.
   - (D-9.2, D-9.3, D-9.9)

**B. Global-first** (same project, same scratch home):
1. Seed the scratch global file:
   `HOME="$PWD/.claude-temp/prerelease/home" just install-agents-file "$PWD/.claude-temp/prerelease/home/.claude" --harness=claude`.
2. Re-run A.1's install command.
   - Expect the project's fenced span removed and reported.
   - Expect the project's `AGENTS.md` still present, even if empty, and its `CLAUDE.md` still
     `@AGENTS.md`.
   - Expect the scratch global block current.
3. Run it a third time. Expect nothing written (D-9.10).

**C. Migration** (`.claude-temp/prerelease/migrate/`, scratch home `home-migrate`, empty):
1. Coordinator: `git worktree add "$PWD/.claude-temp/prerelease/v0.14.0" v0.14.0`, then
   `HOME="$PWD/.claude-temp/prerelease/home-migrate" just --justfile "$PWD/.claude-temp/prerelease/v0.14.0/justfile" install-with-kb "$PWD/.claude-temp/prerelease/migrate"`.
2. User: `"$PWD/.claude-temp/prerelease/migrate/.claude/skills/docdicer/tools/docdicer" --install`.
3. Coordinator adds a project hook of its own to `.claude/settings.json` and an unrelated server to
   `.mcp.json`, then commits everything in the scratch repo.
4. Coordinator:
   `HOME="$PWD/.claude-temp/prerelease/home-migrate" just install-with-kb "$PWD/.claude-temp/prerelease/migrate" --dry-run`,
   output recorded; then the same command without `--dry-run`; then
   `git -C "$PWD/.claude-temp/prerelease/migrate" status --porcelain` and
   `git -C "$PWD/.claude-temp/prerelease/migrate" diff`.
   - Expect every flat file gone per D-6, `hooks/guardrail.pl` included.
   - Expect the project's hook and server byte-identical.
   - Expect the venv rebuilt under the plugin.
   - Expect the dry run to have listed what the install did (D-9.5, D-9.8).
5. User, in a fresh session there with `/reload-plugins`: the plugin loads; `/mcp` shows exactly
   one kbase server; one guardrail block message per blocked call.
6. Coordinator: `git worktree remove "$PWD/.claude-temp/prerelease/v0.14.0"`.

**D. Mage namespacing** (R7). This step needs no scratch home: it touches only the Mage plugin
directory.
- The owner installs the set into their mage `Mage/Skills` and opens a mage session.
- In that session, a dispatch to `adjagent:architect` must resolve. Mage ships no command:
  `imgread` is in `mage.py`'s `omits`.
- If no mage session is available, record D as **unverified**. That does not block release.

**E. Shadowing.** No live step. It would need a real `~/.claude/skills/adjagent`. The install-side
report is pinned by P2's tests under the scratch home, and Claude Code's precedence is
documented.

**Done-line.** Every item recorded. Any failure is either fixed by a dispatched package with its
own done-line, or ruled by the owner.

---

## P5: Post-plan review, revision and burndown

- **Reviewers** (dev-process default):
  - `python-coder`, for `adjagent/`, `tests/` and `devtools/scripts/`.
  - `architect`, since structure changed.
  - `tech-writer`, for `PROJECT_DOCS/`, `docs/` and `README.md`.
  - `prompt-engineer`, for definition descriptions, bodies, the agents file and R5's sentence in
    the `adjagent` skill.
- Each gets the contract documents and the diff `3d36ff6..HEAD`, not this plan or the design.
- `prompt-engineer`'s brief adds:
  - whether `adjagent:<name>` reads naturally at each converted site;
  - whether the kbase skill's server wording holds when the server shows as
    `plugin:adjagent:kbase`.
- Findings go to `ACTIVE_PLAN_REVIEW_BURNDOWN.md`. It gets `prompt-engineer` usability review and
  revision by its author before any revision agent is dispatched.
- A revision that touches `install.py`, `agents_file.py`, `render.py`, the harness modules or
  definition text re-runs P4 A.5. A revision to `install.py` or `agents_file.py` also re-runs P4 B
  and C.4 before landing.

## Landing

- `tech-writer` updates `ROADMAP.md`:
  - delete item 4 (a finished item leaves nothing);
  - reword item 5 to its remainder: a `--name-prefix` install flag setting `reference_prefix` for
    opencode, the holes and guard existing.
- Delete this plan and its design, or replace them with the next plan.
