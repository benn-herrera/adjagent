# Design — the claude set in plugin form

Companion to `ACTIVE_PLAN.md`. It states the invariants the work must hold and the acceptance
criteria, with the sections P3b, P4, P5 and Landing still use. The plan cites sections here as D-n.
Structure that served only the landed packages P1–P3a lives in their commits (`ba67127`,
`58d68b3`, `be18345`, `eafe371`) and the contract documents they updated.

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
   to name a skill the install has not written), except by the agents-file guard test in
   `tests/test_adjagent_install.py`.
3. **Exhaustiveness is a test, not a reading.** `tests/test_cross_references.py` fails when
   definition text names a definition outside a reference hole: body, description, skill
   supporting file, agents file and family overlay text. It has a teeth case. Role nouns ("hand
   that to the architect") are prose, not references.
4. **Harness directory vs ROOT.** The *harness directory* (`.claude`, `~/.claude`, `.opencode`,
   mage's `adjagent/`) is where the harness looks. *ROOT* is where the set is written:
   `harness_dir / harness.plugin_dir`. Decisions about where the install is read the harness
   directory: whether it is user-level, where the agents file goes, the legacy kb sticky signal,
   and where retired-layout cleanup walks. Writes of the set read ROOT. For opencode and mage
   `plugin_dir` is empty, so the two directories are the same.
5. **Opencode definitions are unchanged, and mage's change only at reference sites.** Opencode
   slots match `reference-opencode`. Mage's differ from `reference-mage` only where a reference
   hole fills `adjagent:<name>` (R7); a render-level test pins this. P3a adds only the agents
   file's begin-fence line, and the project `AGENTS.md` (under claude, `CLAUDE.md` as well) a
   claude or opencode slot gains (D-10). P3b changes no render.
6. **A retired copy goes only when its replacement is written.** The settings-file guardrail
   element and the legacy hook script are removed only by an install whose probe passed, so the
   plugin's own hook is written. The project `.mcp.json` `kbase` entry is removed only by a kb
   install, which writes the plugin's own entry. Retired generated files are removed by every
   claude install. Retired package destinations are removed by every claude **project** install,
   since only a project install writes their replacements. A user-level install ships no packages,
   so it removes none.
7. **One prune.** Retired flat files are removed by the existing `prune`, whose walk starts at the
   harness directory's surfaces. There is no second walker. The plugin directory lies inside
   `<harness_dir>/skills/`, so a single walk with a single `keep` set covers the plugin's stale
   renders and the retired flat layout, including the flat layout's `skills/adjagent/SKILL.md`,
   which sits at the plugin's own root.
8. **install.py knows no Claude layout.** The settings paths, containers, command shapes and
   recognisers for the retired entries live in `harnesses/claude.py`. `install.py` holds only the
   generic machinery: splice, remove, the one/ambiguous decision, and reporting.
9. **Write Safety holds for every edit.** A removal keeps every byte outside the removed slot. It
   reports, prints the entry and leaves the file untouched when the file is JSONC, ambiguous (more
   than one claimed element, or ours sharing an element with another command), or an obstacle
   (`_settings_obstacle`: a non-directory on the way, or a non-regular file; never a symlink, per
   D-11). The pre-write checks run before the first write.
10. **The agents file is not in the plugin.** Claude Code does not load a `CLAUDE.md` at a plugin
    root (`claude plugin validate` warns about one). The agents file is never written under ROOT.
    Under claude and opencode, a project install writes the block to exactly one place: the
    user-global agents file where that file already holds the block, else the project's
    `AGENTS.md` (D-10).
11. **No run reads the operator's real home unless an operator asked for it.** The global agents
    file's path is resolved only through `HOME`
    (`Path(harness.user_harness_dir).expanduser()`), and nothing else spells it. Every test, every
    render slot, `check-wheel` and every P4 install runs with `HOME` pointed at scratch. There is
    no test-only switch: `HOME` is the operating system's own contract.

## D-6 Migration from the flat layout (claude; `plugin_dir` non-empty)

| What the older install wrote | Removed when | By |
|---|---|---|
| generated files under `<hd>/{agents,commands,skills}` outside `keep`, the flat `skills/adjagent/SKILL.md` included | every install | `prune` walking the harness directory (D-1.7) |
| `<hd>/skills/docdicer/tools/`, `<hd>/skills/kbase/kb-tools/` | every **project** install with a non-empty `plugin_dir` (never user-level) | removed whole, as package destinations are; a symlink there has the link removed (D-11) |
| `LEGACY_TREES` under `<hd>` | every install | the existing loop, on the harness directory |
| `<hd>/hooks/guardrail.pl` carrying the installed header | probe passed | resource removal, then `<hd>/hooks/` if empty; Write Safety amended to allow it |
| guardrail element in `.claude/settings.json` (`_guardrail_claim` ALONE) | probe passed | removal splice; SHARED, several, JSONC or an obstacle is reported and left |
| `mcpServers.kbase` in the project `.mcp.json` whose command is `kbase` or a path ending `/kbase` | kb install | removal splice; same reporting |

A docdicer `.venv` standing at either the old or the new destination before the install makes the
install run `tools/docdicer --install` on the new script afterwards. The dry-run note says so. The
venv's place relative to its skill is unchanged (`tools/.venv`).

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
    place (D-10).
    - Where the global file holds a block, the block is current there and no project copy of the
      fenced span remains; the project's `AGENTS.md` itself stays.
    - Otherwise the project's `AGENTS.md` holds a current block.
    - Re-installing identical content writes nothing, whatever the version.
    - Per D-1.11, no test, render or `check-wheel` run reads or changes the real `~/.claude` or
      `~/.config/opencode`.
11. No install refuses, skips or reports a path for being a symlink (D-11). Writes land in what
    the link names. Removals unlink the link and leave what it names byte-identical. A dry run
    predicts every write made through a link. No module under `adjagent/` creates a symlink.

## D-10 The agents file follows the set

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
    marker lines (`render.appended_paragraph`);
  - replacing the one ordered pair where it has one;
  - refusing any other marker layout.

  The block never goes into a pointer file. On this branch only, a harness that reads another
  name gets that file as the one-line redirect `@AGENTS.md` where it is absent (SPEC
  `harness-agents-file.md`). A redirect the project already has is left as it stands. A file of
  that name holding anything else refuses the install with nothing written.
- **Uncommitted sources** (plan R6). The refusal while `adjagent/` has uncommitted changes guards
  live operator configuration only. It applies to:
  - a user-level install's agents-file write;
  - `install-agents-file` whose destination is a user-global directory, decided by
    `user_dir_harnesses`, which matches absolute user directories only.

  No project install is refused for it, a mage plugin below a project included. So render slots
  and `check-wheel`, which run under a scratch home with no global block, write the project
  `AGENTS.md` from an uncommitted tree.
- **Sticky.** Once the fenced region exists in the global file, every later project install keeps
  it there. It first gets there by explicit act only: `--install-global-agents-file` on a
  user-level install, or `install-agents-file ~/.claude` (or `~/.config/opencode`).
- **Version stamp.** The begin fence carries `@!agf-version!@`, filled from `adjagent.__version__`.
  An update compares the block's content with the fence lines excluded:

  | Content vs. existing block | Installing version vs. the existing stamp | Action |
  |---|---|---|
  | identical | any | nothing; the stamp stays |
  | different | newer or same | rewrite the block, stamping the installing version |
  | different | older | leave it; report "not downgraded" with both versions |
  | different | no stamp, or a token that does not parse as a release version (e.g. `version[abc1234]`) | rewrite and stamp |

  A change that would alter only the fence lines is never made.
- Every write outside the project (the global file and its backup) is named in the install's
  report and in `--dry-run`, which also predicts the project's `AGENTS.md`, its backup, and under
  claude `CLAUDE.md`.
- Isolation follows D-1.11. A render slot's scratch `HOME` holds no global file, so each claude
  or opencode slot gains a project `AGENTS.md`, and a claude slot also gains `CLAUDE.md` holding
  only `@AGENTS.md`.

## D-11 A symlink is what it names (P3b; plan R8)

- **Checks, writes and edits** read and write through a link, at a target or on the way to one:
  - render, resource and harness-file targets;
  - package destinations;
  - MCP and project settings files, and the retired-entry removal;
  - the agents-file paths (landed in P3a).

  A dangling link **at** a target, file or directory, is followed: what it names is created (the
  file written, or the directory made). A package destination is such a target.
- **Removals unlink the link.** Prune, retired package destinations, legacy trees and the retired
  guardrail script never delete what a link names. That includes an emptied directory reached
  through a link.
- **What stays refused** is a non-directory where a directory is needed **on the way** to a
  target (a parent component): a regular file, a link to one, or a dangling link, since nothing
  can be written through it. So is a foreign file, read through any link
  at the target, for its content and not its link.
- **The preview matches the install.** The preflight copy dereferences every managed path, so the
  scratch copy holds no link and its before/after walk sees what the install writes through a
  link. The changed-file comparison reads the real side through its links.
- **No link is created.** No module under `adjagent/` calls `symlink_to` or `os.symlink`. A test
  holds this. The repository's own files are never linked into live operator configuration.
- **Out of scope:** the guardrail scripts' link-following resolves paths for `.index/`; it does
  not vet them.
