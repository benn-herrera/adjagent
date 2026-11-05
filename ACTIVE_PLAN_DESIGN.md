# Design — the claude set in plugin form

Companion to `ACTIVE_PLAN.md`. It states the invariants the work must hold, the skeleton that holds
them, and the acceptance criteria. The plan cites sections here as D-n.

## D-0 Outcome

Under the claude harness the install writes the whole set as one Claude Code skills-directory
plugin. A project install writes it to `<project>/.claude/skills/adjagent/`, and a user-level
install to `~/.claude/skills/adjagent/`. The plugin holds:
`.claude-plugin/plugin.json`, `agents/`, `commands/`, `skills/` with each tool package inside its
skill as today, `hooks/guardrail.pl` and `hooks/hooks.json` (project installs whose probe passes),
and `.mcp.json` carrying `kbase` (every kb install, user-level included).
Every cross-reference in definition text renders as `adjagent:<name>` under claude and mage, and
as the bare name under opencode. Tuning is unchanged: the plugin is rendered per install.

What the install no longer writes: `.claude/agents/`, `.claude/commands/`, `.claude/skills/<name>/`
(except the plugin), the guardrail element in `.claude/settings.json`, and the `kbase` entry in the
project's `.mcp.json`. When an install writes the replacement for one of these, it removes the
older install's copy (D-6).

## D-1 Invariants

1. **One reference spelling per render.** Definition text names another definition only through
   a reference hole. The render fills each hole with the harness's `reference_prefix` followed by
   the name. Text is never rewritten by pattern-matching rendered prose. `kbase`, `docdicer` and
   `adjagent` are also the names of an executable, a tool and a CLI, so a substitution that
   matched on the name would rewrite those mentions too.
2. **A reference names something that exists.** A reference hole whose name no discovered
   definition has is refused at render, the same refusal an unknown placeholder gets. Whether the
   referenced definition ships in a given install is not checked here (the agents file is allowed
   to name a skill the install has not written), except by the agents-file guard test (D-7).
3. **Exhaustiveness is a test, not a reading.** A guard test fails when definition text names a
   definition outside a reference hole: body, description, skill supporting file, agents file and
   family overlay text. It has a teeth case. Role nouns ("hand that to the architect") are prose,
   not references, and the guard's rule says exactly which spellings it treats as references
   (D-7).
4. **Harness directory vs ROOT.** The *harness directory* (`.claude`, `~/.claude`, `.opencode`,
   mage's `adjagent/`) is where the harness looks. *ROOT* is where the set is written:
   `harness_dir / harness.plugin_dir`. Decisions about where the install is read the harness
   directory: whether it is user-level, where the agents file goes, the legacy kb sticky signal,
   and where retired-layout cleanup walks. Writes of the set read ROOT. For opencode and mage
   `plugin_dir` is empty, so the two directories are the same and nothing they produce changes.
5. **Opencode definitions are unchanged, and mage's change only at reference sites.**
   - opencode: every package's done-line includes a `render-diff` between `reference-opencode` and
     the new slot that reports no difference.
   - mage: from P2 on, its definitions differ from `reference-mage` only where a reference hole now
     fills `adjagent:<name>` (R7). P2 checks this with a render-level test, and P3 diffs `p2-mage`
     against `p3-mage` for no difference.
   - The exception is P3a, which diffs `p3-<h>` against `p3a-<h>`. P3a changes the agents file's
   begin-fence line under every harness, and its project-fallback path adds a project `AGENTS.md`
   to each claude and opencode slot (under claude, `CLAUDE.md` as well). P3a's done-line allows
   only those differences (D-10).
6. **A retired copy goes only when its replacement is written.** The settings-file guardrail
   element and the legacy hook script are removed only by an install whose probe passed, so the
   plugin's own hook is written. The project `.mcp.json` `kbase` entry is removed only by a kb
   install, which writes the plugin's own entry. Retired generated files are removed by every
   claude install. Retired package destinations are removed by every claude **project** install,
   since only a project install writes their replacements. A user-level install ships no packages,
   so it removes none.
7. **One prune.** Retired flat files are removed by the existing `prune`, whose walk starts at the
   harness directory's surfaces instead of ROOT's. There is no second walker. The plugin directory
   lies inside `<harness_dir>/skills/`, so a single walk with a single `keep` set covers the
   plugin's stale renders and the retired flat layout, including the flat layout's
   `skills/adjagent/SKILL.md`, which sits at the plugin's own root.
8. **install.py knows no Claude layout.** The settings paths, containers, command shapes and
   recognisers for the retired entries live in `harnesses/claude.py`. `install.py` holds only the
   generic machinery: splice, remove, the one/ambiguous decision, and reporting. This is the same
   split the guardrail merge has today.
9. **Write Safety holds for every new edit.** A removal keeps every byte outside the removed slot.
   It reports, prints the entry and leaves the file untouched when the file is JSONC, ambiguous
   (more than one claimed element, or ours sharing an element with another command), or an
   obstacle (`_settings_obstacle`). The pre-write checks run before the first write.
10. **The agents file is not in the plugin.** Claude Code does not load a `CLAUDE.md` at a plugin
    root (`claude plugin validate` warns about one). The agents file is never written under ROOT.
    Under claude and opencode, a project install (P3a, D-10) writes the block to exactly one place:
    the user-global agents file where that file already holds the block, else the project's
    `AGENTS.md`.
11. **No run reads the operator's real home unless an operator asked for it.** The global agents
    file's path is resolved only through `HOME`
    (`Path(harness.user_harness_dir).expanduser()`), and nothing else spells it. Every test, every
    render slot, `check-wheel` and every P4 install runs with `HOME` pointed at scratch. There is
    no test-only switch: `HOME` is the operating system's own contract.

## D-2 Skeleton

| Unit | Change | Must not |
|---|---|---|
| `vocabulary.py` | a reference hole spelling, `@!ref-<name>!@`, beside `hole()` (P1); `OptionalHarnessText.RELOAD_RULE` (P2); `AgentsFileText.VERSION` (P3a) | know any definition name |
| `agents_file.py` | global-first placement, removal of the project copy, version rule (P3a, D-10) | resolve home other than through `expanduser` |
| `clauses.py` | `ref(name)` returns that spelling, for definition bodies and descriptions | hold a list of names |
| `render.py` | fill reference holes in bodies, supporting files, the agents file **and descriptions** (a description is not filled today: `render.py:117`, `agent_fields`); refuse an undiscovered name | rescan filled text; special-case any harness |
| `harness.py` | new `Harness` fields `reference_prefix: str = ""`, `plugin_dir: str = ""` and `reload_rule: str = ""`; `GuardrailHook` reshaped to `script` plus a rendered `registration: HarnessFile`; a retired-entry record type (settings path, container, recogniser); the plugin-manifest builder moved here from `mage.py` (one builder, two callers); `is_plugin` renamed for what it means, a harness whose harness directory *is* the plugin (mage) | carry instance values |
| `harnesses/claude.py` | `plugin_dir="skills/adjagent"`, `reference_prefix="adjagent:"`, `mcp_tool_prefix="mcp__plugin_adjagent_kbase__"`, MCP site at ROOT, the manifest, the hooks.json registration naming `${CLAUDE_PLUGIN_ROOT}/hooks/guardrail.pl`, and the retired entries (old settings element, old project `kbase` member) with their recognisers | hold install logic |
| `harnesses/mage.py` | calls the shared manifest builder (manifest bytes unchanged); `reference_prefix` from `harness.PLUGIN_NAME` (R7) | change any other value |
| `install_target.py` | resolves the **harness directory**, renaming the `InstallTarget.root` field to `harness_dir`; `--subdir` names the harness directory, as it does today | append `plugin_dir`; `install` does that |
| `install.py` | `install(harness_dir, …)` with `ROOT = harness_dir / plugin_dir`; user-level, agents file and sticky signal on the harness directory; registration written only when the probe passes; `prune` walks the harness directory's surfaces; retired package destinations and the retired resource removed (D-6); retired settings entries removed through a removal splice; include-line rule (D-5); shadow report (D-8); the MCP write decided apart from the runner line (an MCP site at ROOT writes on a user-level kb install too; the runner line stays project-only); the reload sentence printed after a run that wrote under ROOT; `_install_managed_paths` covers all of it | hold a Claude path or command shape |
| `preflight.py` | none: it is generic over the bases it is given | — |
| `cli.py` | passes `target.harness_dir` | — |
| `devtools/scripts/_render-slot.sh`, `check-wheel.sh` | export `HOME` to a fresh scratch home, removed on exit (P1, D-1.11) | read the real home |
| `devtools/scripts/_render-slot.sh`, `render.sh` | comments on the plugin path: a claude slot holds the plugin at `<slot>/skills/adjagent/` (P2) | change the flags |

Dependency direction is unchanged: `vocabulary ← clauses ← definitions`, `harness ← harnesses/*`,
`render → harness, vocabulary`, and `install → render, harness, install_target, preflight,
agents_file`.

**Incumbents searched.**
- The plugin manifest builder: `mage._plugin_json` / `mage.FILES` (`adjagent/harnesses/mage.py:12-24`)
  does the job. Reuse it, moved to `harness.py`.
- JSON settings editing: `_splice` / `_splice_element` (`install.py:649-685`) add and replace but do
  not remove. Extend that scanner with a remove operation; write no second parser.
- The old guardrail recogniser: `claude._guardrail_claim` and `_GUARDRAIL_COMMAND`
  (`claude.py:55-90`). They stay as the retired element's recogniser. `_guardrail_entry` is
  deleted.
- File removal: `prune` (`install.py:344-378`). Widen its walk; no new walker.
- Name substitution: `git grep -n -i 'prefix\|namespace' -- adjagent/render.py adjagent/vocabulary.py adjagent/context.py adjagent/harness.py`
  answered only with `mcp_tool_prefix` and the hole-namespace map. No reference mechanism exists.

## D-3 How the plugin form is expressed

Two plain fields on `Harness`: `plugin_dir`, a path below the harness directory, and
`reference_prefix`. The design does **not** add a layout mode or a nested plugin record. With ROOT
moved into the plugin directory, everything the install already resolves against ROOT lands in
the plugin unchanged: surfaces, package destinations, resource copies, rendered files, and an MCP
site at ROOT. That is the mechanism mage already uses. Mage's harness directory *is* its plugin,
so its `plugin_dir` is empty.

`plugin_dir` is not `plugin_parent_dir` (`harness.py:128`, set only at `mage.py:65`):
- `plugin_parent_dir` is the trailing path of the directory a standalone plugin's harness
  directory sits in (`Mage/Skills`). Target detection reads it.
- `plugin_dir` is the path *below* the harness directory that the set is written into
  (`skills/adjagent`). ROOT is computed from it.

Mage sets the first and leaves the second empty; claude does the reverse.

The only claude-specific decisions are data in `claude.py`. The fill, the install and the
resolution have no `if claude` and no `if plugin`.

Mage namespaces plugin components as Claude Code does, so mage's `reference_prefix` is also
`adjagent:`. Both harnesses derive it from one constant, `harness.PLUGIN_NAME`, which also gives
the manifest name, claude's `plugin_dir` and claude's MCP prefix. That makes four derived
spellings of a single source.

## D-4 Cross-references

- Sites: the hyphenated agent names in descriptions ("Prefer over generalist-coder …", 16
  definitions), and the backticked or dispatch-role names in bodies: `dev_process.py` 62, 100,
  122, 191, 218, 221, 223; `prompt_engineer.py` 17 (description), 32; `tech_writer.py` 221;
  `architect.py` 170; `harness_agents_file.py` 25, 52. Plan P1 carries the full list with the
  command that produced it.
- Not references, so they stay bare:
  - role nouns: "software architect" (`architect.py:20`); "the architect" and "architect's job"
    (`security_reviewer.py` 12, 18, 38, 128, 130; `tech_writer.py:142`);
  - the `kbase` executable and server, the `adjagent` CLI ("Every other `adjagent` command",
    `adjagent.py:34`), the `docdicer` tool and its recipe names;
  - module docstrings and code comments.
- Holes do not reach family overlay text, because filled text is never rescanned. An overlay that
  needs to name a definition is caught by the guard (D-1.3) and goes into the base text through a
  hole.
- The agents file is rendered from `harness_named(<name>)`, so under claude it reads
  `adjagent:dev-process` and `adjagent:prompt-engineer` wherever it is installed. Every claude
  install is now the plugin.
- One prefix for every kind: an agent is `adjagent:<name>`, a skill is `adjagent:<name>`, and a
  command is `/adjagent:<name>`, where the slash is part of the prose. A plugin agent registers
  only under its namespaced name, so `subagent_type` must be `adjagent:<name>`.
- This covers ROADMAP item 5's purpose under claude. A `--name-prefix` flag for the other harnesses
  is item 5's remainder: the holes exist, and the flag would set `reference_prefix`.

## D-5 kb runner include line

The include line names `<ROOT relative to the project>/skills/kbase/kb-tools/runner-snippets/<snippet>`,
which is `.claude/skills/adjagent/skills/kbase/kb-tools/…` under claude. `kb_include_line` already
builds it from `harness_relpath`, which is ROOT-relative.

The current recognition is wrong for a multi-segment `harness_relpath`. It compares the line's
first segment with the whole relpath (`install.py:1019`), and on rewrite it keeps only the first
segment (`install.py:1029-1030`). New rule: a line is this install's when its first segment equals
the first segment of `harness_relpath`. The rewrite replaces the whole path token with the
canonical `<harness_relpath>/<KB_TOOLS_SNIPPETS>/<snippet>`. A line that names another harness
directory is reported and left, as today.

The sticky kb signal also reads `<harness_dir>/skills/kbase/SKILL.md` where `plugin_dir` is
non-empty. Otherwise the first install after upgrade would drop kb.

## D-6 Migration from the flat layout (claude; `plugin_dir` non-empty)

| What the older install wrote | Removed when | By |
|---|---|---|
| generated files under `<hd>/{agents,commands,skills}` outside `keep`, the flat `skills/adjagent/SKILL.md` included | every install | `prune` walking the harness directory (D-1.7) |
| `<hd>/skills/docdicer/tools/`, `<hd>/skills/kbase/kb-tools/` | every **project** install with a non-empty `plugin_dir` (never user-level) | removed whole, as package destinations are today |
| `LEGACY_TREES` under `<hd>` | every install | the existing loop, on the harness directory |
| `<hd>/hooks/guardrail.pl` carrying the installed header | probe passed | resource removal, then `<hd>/hooks/` if empty; Write Safety amended to allow it |
| guardrail element in `.claude/settings.json` (`_guardrail_claim` ALONE) | probe passed | removal splice; SHARED, several, JSONC or an obstacle is reported and left |
| `mcpServers.kbase` in the project `.mcp.json` whose command is `kbase` or a path ending `/kbase` | kb install | removal splice; same reporting |

A docdicer `.venv` standing at either the old or the new destination before the install makes the
install run `tools/docdicer --install` on the new script afterwards. The dry-run note says so. The
venv's place relative to its skill is unchanged (`tools/.venv`).

## D-7 Guard tests that change

- `test_every_skill_the_agents_file_cites_ships_in_the_harness_default_install`
  (`tests/test_adjagent_install.py:494-502`) parses `` `name` skill`` from rendered prose. That fails
  on `adjagent:dev-process`. It is rewritten to read the reference holes in the agents-file
  definition's source and to check that each named skill ships in each harness's default install.
- New guard: no definition text names a definition outside a hole, with a teeth case. Reference
  spellings:
  - a hyphenated agent or command name as a whole word;
  - `` `architect` `` in backticks;
  - any other definition name in backticks followed by ` skill`, ` agent` or ` command`, except
    the three names that are also an executable, tool or CLI (`adjagent`, `docdicer`, `kbase`).
    Only ` skill` makes those three a reference, so "Every other `adjagent` command"
    (`adjagent.py:34`, the CLI) stays out without a per-line exemption.
- New: an undiscovered reference name is refused.
- New: a description's hole is filled.
- Harness-text table (`tests/test_adjagent.py:533-540`): the claude MCP prefix becomes
  `mcp__plugin_adjagent_kbase__`.
- Settings-merge tests (`test_adjagent_install.py` around 1714-1921) become removal tests.
  Hook-command tests run the hooks.json command with `CLAUDE_PLUGIN_ROOT` set. `test_guardrail.py:205`
  reads the matcher from the registration.
- Install-layout assertions on `root/agents/…` under claude move to the plugin. Mage and opencode
  assertions do not move.

## D-8 Shadowing: reported, never refused

Claude Code drops a project's `.claude/skills/adjagent` when `~/.claude/skills/adjagent` loads
under the same manifest name
(<https://code.claude.com/docs/en/plugins/loading>, "Name conflicts", rule 4). The project's
tuning, version, guardrail and kbase server go with it. The install reports this and never
refuses.

- A project install whose user-level `<user_harness_dir>/<plugin_dir>/.claude-plugin/plugin.json`
  holds the manifest marker reports one stderr line naming both paths and the consequence.
- A user-level install always reports that it takes precedence over every project's adjagent
  plugin.
- The check is generic: any harness with a non-empty `plugin_dir`.
- It runs on the real filesystem, so it reports on dry-run and up-to-date runs.

## D-9 Acceptance criteria

1. A claude project install writes no file outside `.claude/skills/adjagent/` except:
   - the project runner include line, or a created `Makefile`;
   - the agents-file block (D-10), written either to the global agents file or to the project's
     `AGENTS.md`, with that file's backup, plus a created `CLAUDE.md` holding only `@AGENTS.md`;
   - where the global file holds the block, that block's removal from the project's `AGENTS.md`,
     with its backup;
   - the removals D-6 lists.
2. A fresh Claude Code session at the project root, after trust and `/reload-plugins`, lists
   `adjagent@skills-dir`. It dispatches every agent by the form the rendered text names, loads
   `adjagent:dev-process`, and runs `/adjagent:imgread`.
3. In that session the guardrail blocks an in-place `sed -i` and allows a write into
   `.claude-temp/`. On a kb install the `kbase` tools are offered as
   `mcp__plugin_adjagent_kbase__*` and answer for the project's `kb-root/`.
4. `claude plugin validate .claude/skills/adjagent` reports no error.
5. An install over a 0.14.0 claude install leaves no generated file, package destination, settings
   element or project `kbase` entry of the flat layout, except those D-6 conditions keep. It
   reports each path it removed, and the project's own files and hooks are byte-identical.
6. Every cross-reference renders `adjagent:<name>` under claude and mage, and the bare name under
   opencode. The guard test fails on a planted bare reference.
7. Against the `reference-*` slots:
   - opencode (`--harness=opencode --model-tier-map=all=inherit`) shows no difference;
   - mage (`--harness=mage`) shows differences only at reference sites. A render with the prefix
     removed equals the bare render.
   - Neither shows any difference beyond what P3a introduces: the agents file's begin-fence line
     and, for opencode, the slot's project `AGENTS.md` (D-10).
8. Re-running an install changes nothing (up to date). `--dry-run` predicts every created, changed
   and removed path, including the migration's.
9. A docdicer venv that stood before an install over the flat layout is rebuilt at the plugin's
   `skills/docdicer/tools/.venv`, and `tools/docdicer --help` runs from there in a session.
10. Under claude and opencode, a project install leaves the agents-file block in exactly one
    place (D-10). Where the global file holds a block, the block is current there and no project
    copy of the fenced span remains; the project's `AGENTS.md` itself stays. Otherwise the
    project's `AGENTS.md` holds a current block. Re-installing identical content writes nothing,
    whatever the version. Per D-1.11, no test, render or `check-wheel` run reads or changes the
    real `~/.claude` or `~/.config/opencode`.

## D-10 The agents file follows the set (P3a)

Applies to every claude and opencode project install. Mage's agents-file placement is unchanged: it
lives in its plugin. A user-level install is unchanged: it writes the agents file only when given
`--install-global-agents-file`.

- **Global holds the block.** The user-global agents file (`~/.claude/CLAUDE.md`,
  `~/.config/opencode/AGENTS.md`) holds one adjagent fenced block. The install keeps that block
  current there. If the project's `AGENTS.md` also holds a block, the install removes that span,
  keeps every other byte, and makes the rolling backup. The file stays, even if empty: it holds
  the project's own additions. It reports what it removed and why. This branch never reads or
  writes the project's `CLAUDE.md`.
- **Global holds no block.** The install keeps the block current in the project's `AGENTS.md`:
  - creating the file if absent;
  - appending the block after one blank line, every other byte kept, where the file has no
    marker lines (existing behaviour, `render.appended_paragraph`);
  - replacing the one ordered pair where it has one;
  - refusing any other marker layout, as today.

  The block never goes into a pointer file. On this branch only, a harness that reads another
  name gets that file as the one-line redirect `@AGENTS.md` where it is absent (SPEC
  `harness-agents-file.md`, the existing `agents_file.py` redirect write). A redirect the project
  already has is left as it stands. A file of that name holding anything else refuses the install
  with nothing written, as SPEC already says for that file.
- **Uncommitted sources** (plan R6, landed in P1). The refusal while `adjagent/` has uncommitted
  changes guards live operator configuration only. It applies to:
  - a user-level install;
  - `install-agents-file` whose destination is a user-global directory, decided by
    `user_dir_harnesses`, which matches absolute user directories only.

  It never keys on `_in_user_dir`. No project install is refused for it, a mage plugin below a
  project included. Here that means: the global-first write is refused under uncommitted sources,
  while the project `AGENTS.md` and its redirect are not. So render slots and `check-wheel`, which
  run under a scratch home with no global block, write the project `AGENTS.md` from an uncommitted
  tree.
- **Sticky.** Once the fenced region exists in the global file, every later project install keeps
  it there. It first gets there by explicit act only: `--install-global-agents-file` on a
  user-level install, or `install-agents-file ~/.claude` (or `~/.config/opencode`).
- **Version stamp.** The begin fence carries a new agents-file hole, `@!agf-version!@`, spelled at
  `harness_agents_file.py:14` and filled by the renderer from `adjagent.__version__`. An update
  compares the block's content with the fence lines excluded:

  | Content vs. existing block | Installing version vs. the existing stamp | Action |
  |---|---|---|
  | identical | any | nothing; the stamp stays |
  | different | newer or same | rewrite the block, stamping the installing version |
  | different | older | leave it; report "not downgraded" with both versions |
  | different | no stamp, or a token that does not parse as a release version (e.g. `version[abc1234]`) | rewrite and stamp |

  A change that would alter only the fence lines is never made.
- Every write outside the project (the global file and its backup) is named in the install's
  report and in `--dry-run`. The global file's directory is a managed base in preflight.
- `--dry-run` also predicts the project's `AGENTS.md`, its backup, and under claude `CLAUDE.md`.
- Isolation follows D-1.11. A render slot's scratch `HOME` holds no global file, so each claude
  or opencode slot gains a project `AGENTS.md`, and a claude slot also gains `CLAUDE.md` holding
  only `@AGENTS.md`. Those files are the visible change of the project-fallback path.
