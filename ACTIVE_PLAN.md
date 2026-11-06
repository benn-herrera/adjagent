# ACTIVE PLAN: the claude set in plugin form (ROADMAP item 4)

Design: `ACTIVE_PLAN_DESIGN.md`, cited here as D-n. The plan's work starts at `3d36ff6` (branch
`develop`). P1–P3a have landed; HEAD is `eafe371`.

## Status

| Package | What | Rating | Lifetime | Runs on | State |
|---|---|---|---|---|---|
| — | Rulings R1–R8 (below) | owner | — | — | settled |
| — | Baseline slots at `b835f6d` | coordinator | throwaway | — | done: four `reference-*` slots |
| — | This plan: `prompt-engineer` usability review, then `architect` revision | — | — | — | done |
| P0 | Live check of the plugin mechanisms | user-run | throwaway | scratch | done |
| P1 | Reference holes; scratch `HOME`; R6 | expert | shipped | python-coder, then tech-writer | done: `ba67127` |
| P2 | Install root inside the plugin directory | expert | shipped | python-coder, then tech-writer | done: `58d68b3` |
| P3 | Guardrail registration in the plugin; retired settings entries removed | expert | shipped | python-coder, then tech-writer | done: `be18345` |
| P3a | The agents file follows the set | expert | shipped | python-coder, then tech-writer | done: `eafe371` |
| P3b | A symlink is what it names (R8) | expert | shipped | python-coder, then tech-writer | done (P3b checkpoint commit) |
| P4 | Pre-release testing | user-run, with agent-run parts | throwaway | scratch | done: A–C pass (fix `01a27e9`); D unverified, mage ships namespaced |
| P5 | Post-plan review, revision, burndown | review | — | reviewers | four reviewers dispatched on `1049e2f..HEAD` |

Packages share one build and one test suite, so they run **serially**: one dispatch at a time, each
on the agent's own model. No package is mechanical, so none runs on the step-down model.

## Kickoff decisions

- Under claude, the install writes the set as one skills-directory plugin:
  `<harness_dir>/skills/adjagent/`, which is ROOT. Under claude and mage, a cross-reference renders
  `adjagent:<name>` through an explicit reference hole; under opencode it renders bare.
- The agents file is never written inside the plugin. Under claude and opencode it follows the set
  per D-10.
- No test, render slot, `check-wheel` run or P4 install reads or writes the operator's real home.
  `HOME` points at scratch for all of them (D-1.11).
- The docdicer venv stays at `tools/.venv` inside its skill, now inside the plugin (D-6).
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
      every other byte kept (`render.appended_paragraph`).
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
  matching its own plugin directory.
- **R7. Mage namespaces plugin components as Claude Code does.**
  - A mage plugin agent is invoked as `adjagent:<name>`, and a command as `/adjagent:<cmd>`.
  - Mage's `reference_prefix` is `adjagent:`, from the same plugin-name constant as claude's.
- **R8. A symlink is the file or directory it names.** The install reads and writes through it,
  and never refuses, skips or reports a path because it is a symlink.
  - Removing a path that is a symlink, dangling or not, removes the link itself, never what it
    names.
  - A dangling link **at** a target, file or directory, is followed: what it names is created
    (the file written, or the directory made).
  - A dangling link **on the way** to a target (a parent component) refuses, because nothing can
    be written through it. So does any other non-directory where a directory is needed.
  - The install never creates a symlink into live operator configuration.
  - Agents-file paths are covered in P3a; everything else in P3b.

## Gates

From `PROJECT_DOCS/CONVENTIONS/planning-and-execution/the-gates.md`:
- **Edit gate:** `just test-changed <start>`, where `<start>` is `git rev-parse HEAD` at dispatch.
  Each brief states the hash and has it run after every edit.
- **Checkpoint gate:** `just test`, then `just sweep-python`. Run once before each package's
  checkpoint commit. The sweep's list is read, not only run.
- Contract documents move with each package: its tech-writer step lands in the same checkpoint as
  its code.

---

## Landed packages

**P0 (live check, Claude Code 2.1.311).** It satisfied D-1.6 and `clauses.PROVE_REPLACEMENT_RULE`
before anything was retired. Still relied on by P4:
- A plugin agent registers only as `adjagent:<name>`, which is the `subagent_type`. Commands are
  `/adjagent:<cmd>`.
- Components register after a restart or `/reload-plugins` following trust or install.
- `${CLAUDE_PLUGIN_ROOT}` expands in plugin hooks. Plugin MCP tools are
  `mcp__plugin_adjagent_kbase__<tool>`.
- `claude plugin validate` accepts the layout, warning only on the missing icon.

**P1, `ba67127`.**
- Cross-references are `clauses.ref` holes, guarded by `tests/test_cross_references.py`.
- The scratch home is in place:
  - `tests/conftest.py` sets `HOME` per test;
  - `_render-slot.sh` and `check-wheel.sh` export it (`.claude-temp/render-home/<slug>`);
  - P3b's tests and slots rely on this.
- R6 landed.

**P2, `58d68b3`.**
- The claude set installs into the plugin, and `harness.PLUGIN_NAME` gives both prefixes (R7).
- The flat layout's generated files and project package destinations are removed (D-6), including
  the retired-destination removal P3b changes.
- The shadow report (D-8) and R5 landed.
- A render test pins that a prefix changes nothing but reference sites (D-9.7).

**P3, `be18345`.**
- The guardrail is registered by the plugin's `hooks/hooks.json`.
- The retired settings element and the project `kbase` member are removed. The retired guardrail
  script is removed (R3).
- These removal paths are among those P3b changes.

**P3a, `eafe371`.**
- The agents file follows the set (D-10, R4), version-stamped, with R8 already applied to its
  paths.
- Slots `p3a-claude`, `p3a-mage` and `p3a-opencode` are P3b's baseline. They are local render
  output under the gitignored `rendered/`; P3b renders them first if they are absent.
- `just retake-reference` follows P3a's acceptance, per
  `CONVENTIONS/planning-and-execution/reference-retakes-follow-acceptance.md`.

---

## P3b: A symlink is what it names (expert; shipped)

**Outcome.** R8 and D-11, outside the agents-file paths, which P3a already covers. Every
install-side check, write, removal and preflight copy treats a symlink as the file or directory it
names. No path is refused, skipped or reported for being a symlink. The guardrail scripts'
symlink-following is untouched: it resolves paths, it does not vet them (`guardrail.pl`,
`guardrail.ts`).

**Edit-gate base:** `eafe371`. Line numbers below are at `eafe371`. The symbol names are
authoritative.

**Before the first edit:** if any of `rendered/p3a-claude`, `rendered/p3a-mage` or
`rendered/p3a-opencode` is absent, render it while the tree is still `eafe371`:
`just render p3a-claude`; `just render p3a-mage --harness=mage`;
`just render p3a-opencode --harness=opencode --model-tier-map=all=inherit`. They are local render
output, and `rendered/` is gitignored.

**Scope: code.**
- `adjagent/install.py`:
  - `_blocked_component` (307-315): a component blocks only where it exists and is not a
    directory, links followed: `os.path.lexists(c) and not c.is_dir()`.
    - A link to a directory passes.
    - A link to a file, or a dangling link, blocks: nothing can be written through it (R8).
    - The symlink clause goes, and so does the docstring's symlink clause (308).
  - `_foreign_on_path` (318-327):
    - `target` passes when it does not exist with links followed (absent, or a dangling link),
      or is a file, links followed, that `ours` accepts read through.
    - The `target.is_symlink()` clause goes, and so do the docstring's "a dangling symlink counts
      as something" and "not a symlink" (320-321).
  - `_refuse_foreign_targets` (330-354): the message (352) and the docstring (338) drop
    "a symlink or".
  - A dangling link at a render, resource or harness-file target is followed: the file it names is
    written.
  - Package destinations (the `shutil.rmtree(root / destination, ignore_errors=True)` loop,
    1340-1341):
    - A destination that is a link to a directory has that directory's contents removed, and the
      link stays. The copy then writes through it.
    - A dangling link at the destination is followed: the directory it names is made, and the
      copy writes into it (R8).
    - Today `rmtree` on a link raises, and `ignore_errors=True` hides it, so the old contents
      would survive beside the new copy.
    - `_standing_docdicer_venvs`'s `.venv` test (`venv.is_dir()`, 1157) already follows links.
  - Retired package destinations (1359-1369, P2's flat-layout removal):
    - A destination that is a symlink, dangling or not, has **the link** unlinked, reported as
      removed. The directory it names is never touched.
    - The `is_dir()` guard (1362) admits a link, dangling or not.
    - Otherwise it is removed with `rmtree` as today.
    - The `_blocked_component … or is_symlink` report goes, and so does the second sentence of the
      comment above the loop (1359-1360, "One reached through a symlink…").
  - `LEGACY_TREES` loop (1370-1376): the same rule. A link is unlinked; otherwise `rmtree`. The
    `is_dir()` guard (1372) admits a link, dangling or not.
  - `_remove_retired_script` (967-979): the `is_symlink()` skip at 972 goes, and so does the
    docstring's "reached through no symlink" (969-970).
    - A link whose named file carries the installed header has the link unlinked.
    - A regular file is removed as today.
    - The parent-directory cleanup follows the prune's link rule below.
  - `prune` (357-394):
    - The `not path.is_symlink()` clause (383) goes. A stale entry is judged by what it names
      (`_is_ours` reads through), and when it is a link, the link is unlinked.
    - The walk at 380 (`rglob`) reaches files below a symlinked directory under a surface. A
      directory whose resolved path it has already visited is not entered again, so a link cycle
      ends. The mechanism is the executor's.
    - The empty-directory cleanup removes the link where the emptied directory was reached
      through one.
  - `_settings_obstacle` (719-731): the two symlink clauses go. It names only a non-directory on
    the way (`_blocked_component`) and a target that exists, links followed, and is not a regular
    file.
    - Its docstring changes, and so do those of `_settings_to_read`, `_check_settings`,
      `mcp_merge`, `_remove_retired_entry` and `_earlier_guardrail`.
    - Those callers then read and splice through a symlinked MCP or settings file, write the
      named file through a dangling one where they write at all, and remove a retired entry through
      a link.
    - The comment at 915-916 ("a symlink read through and never written") goes.
  - `_names_text` docstring (880, "a symlink followed"): unchanged; it is resolution.
  - The `install` docstring (`def install` at 1180; symlink clauses at 1231-1234) and the
    `preflighted_install` docstring (1497-1499): every symlink clause goes; the non-directory
    clauses stay.
  - `_mcp_settings_file` (711-716): unchanged. `os.path.lexists` already picks a dangling
    alternative, which is now written through.
  - `_refuse_root` (248-263): unchanged. A ROOT that exists and is not a directory, links followed,
    stays refused.
- `adjagent/preflight.py` (unchanged since `be18345`: `git diff --stat be18345 eafe371 -- adjagent/preflight.py`
  prints nothing):
  - `_copy_managed` (74-120):
    - A managed path is copied as what it names: a directory with `_copy_tree`, a file with
      `copy2`, a dangling link as nothing.
    - The `links` list, the second pass with its `rmtree` (103), the `scratch / "links"`
      stand-ins and the `copy.symlink_to` call (120) go.
    - Docstring updated.
  - Unchanged:
    - `_tree_files` (123-129): it walks only the scratch bases, before and after the run
      (`preflight.py` 168, 180). Once `_copy_managed` dereferences everything, those hold no
      link to follow.
    - `_scratch_bases` docstring (46): resolution.
    - `_copy_tree` (62-71): it already dereferences (`symlinks=False`,
      `ignore_dangling_symlinks=True`).
  - `_differs` docstring (133-134): drop "Two dangling symlinks do not differ…". With no link in
    the copy, that case no longer arises.

**Tests** (`tests/test_adjagent_install.py`, lines at `eafe371`).
- Rewrite each case that pins a refusal, skip or report for a symlink, to the R8 outcome:
  - `test_prune_leaves_a_symlink_standing` (830): a link to a stale generated file is unlinked,
    and the named file is intact.
  - `test_a_symlink_or_directory_at_a_render_target_is_refused_with_nothing_written` (1676):
    - the `symlink` case: a link to rendered output is written through, the named file updated
      and the link kept.
    - the `directory` case stays refused.
  - `test_a_symlink_or_file_on_a_targets_path_is_refused_with_nothing_written` (2097):
    - the `symlink-on-a-resource-path` case (`_plant_directory_link`, 2079) is written through.
    - the `file-on-a-render-path` case stays refused.
  - `test_a_settings_path_a_merge_cannot_write_in_place_is_reported_and_left_standing` (2133):
    - `mcp-symlink`: the entry is spliced into the named file.
    - `mcp-dangling-symlink`: the named file is created holding the entry.
    - `mcp-directory` and `mcp-parent-file` stay as they are.
  - `test_settings_the_removal_cannot_edit_are_never_refused_and_reported_only_where_they_name_our_command`
    (1888), its `symlink` kind (1901): the retired entry is removed through the link, and nothing
    is reported.
  - `test_a_symlinked_settings_file_the_install_leaves_alone_is_up_to_date` (2439):
    - A claude install writes `.claude/settings.json` only to remove a retired entry. A link to
      `{}` holds none, so the install changes nothing and reports up to date. A dangling link has
      nothing to remove, so the install creates nothing.
    - Rename the test to that outcome, for example
      `test_a_symlinked_settings_file_holding_no_retired_entry_is_up_to_date`. Both cases still
      assert up to date and an empty dry run.
    - The docstring's "keeps the link a link" goes.
  - `test_a_dry_run_through_a_symlinked_skill_directory_writes_nowhere` (2403): assertions
    unchanged. Its docstring already reads "The copy dereferences the link".
- Add:
  - a retired package destination, a legacy tree and the retired guardrail script, each as a link
    and as a dangling link: the link is unlinked and reported, and what it names is byte-identical;
  - a package destination that links to a directory: its stale contents are gone, the new package
    is in it, and the link stays;
  - a package destination that is a dangling link: the directory it names is made and holds the
    package;
  - a dangling link on the way to a render target (a parent component) is refused with nothing
    written;
  - the prune following a symlinked directory below a surface, with a link cycle ending;
  - for each symlink case above, `_assert_dry_run_predicts` agrees with the install (D-9.8);
  - a guard test that no module under `adjagent/` calls `symlink_to` or `os.symlink`, with a teeth
    case. `just test` runs it, so it is the done-line's check (D-11).
- Unchanged:
  - `tests/test_install_target.py:223`
    (`test_a_user_directory_symlinked_out_of_home_installs_through_the_link`);
  - `tests/test_guardrail.py`;
  - the agents-file symlink cases P3a wrote (around 2779 and 2797).

**Scope: docs (tech-writer, same checkpoint).** The source is the command
`git grep -n -i symlink eafe371 -- PROJECT_DOCS docs README.md`. Its answer, line by line:
- **Change** (state R8, or drop the symlink clause, keeping any non-directory clause):
  - SPEC `write-safety.md`:
    - lines 7-8, 16, 29, 42-43, 48 and 71;
    - and a new sentence stating R8: a symlink is the file or directory it names; removing a
      symlink removes the link; the install never creates a symlink into live operator
      configuration.
  - ARCHITECTURE `install-consumption-model/guardrail-registration.md` 30, 47 and 53.
  - ARCHITECTURE `install-consumption-model/install-entry.md` 34 and 41.
  - ARCHITECTURE `install-consumption-model/renders-and-copies.md` 15, 32, 52-54, 88-92, 106 and
    117-122. The preflight bullets describe the dereferencing copy, and that the scratch copy then holds
    no link.
  - `docs/guardrail.md:45`; `docs/install-reference.md` 150-151 and 161; `docs/knowledge-base.md:77`.
- **Stay:**
  - P3a's agents-file R8 statements: ARCHITECTURE `agents-file.md` 48-49, SPEC
    `harness-agents-file.md:67`, `docs/agents-file.md` 89-91.
  - Resolution, not refusal: ARCHITECTURE `install-entry.md` 6, 8, 11 and 33; SPEC
    `install-destination.md` 25 and 86.
  - The guardrail's own link-following: `guardrail-hook.md:45`, `shipped-files.md:77` and
    `docs/guardrail.md:17`.

**Facts** (each command run at `eafe371`).
- The refusal sites. Command:
  `git grep -n -i -E 'symlink|is_symlink|lexists|_blocked_component|_settings_obstacle|islink' eafe371 -- adjagent ':!adjagent/harnesses/resources'`.
  Answer:
  - `agents_file.py` 101 and 137 (P3a's R8, unchanged);
  - `install.py` 252, 307-325, 338, 352, 383, 716, 719-736, 743, 783, 788, 880, 905-915, 970-972,
    1231-1234, 1261 (a resolution comment, unchanged), 1360-1366, 1497-1499;
  - `install_target.py` 10, 30 and 133 (resolution, unchanged);
  - `preflight.py` 46, 63-69, 78-120 and 133-134.
- Callers of the changed helpers, all in `install.py`. Command: `git grep -n -e <name> eafe371 -- adjagent`.
  - `_blocked_component`: 307, 320, 322, 724, 972, 1364.
  - `_settings_obstacle`: 719, 735-736, 743, 783, 788, 905, 912.
  - `_settings_to_read`: 734, 744, 956.
  - `_foreign_on_path`: 318, 338, 347.
- `rmtree` sites. Command: `git grep -n rmtree eafe371 -- adjagent`. Answer: `install.py` 1341,
  1368 and 1373, and `preflight.py:103`.
  - `shutil.rmtree` refuses a symlink ("Cannot call rmtree on a symbolic link", Python docs,
    `shutil.rmtree`).
  - So each `install.py` site needs the R8 link rule. `preflight.py:103` goes with the link pass.
- Symlink creation. Command: `git grep -n -e symlink_to -e os.symlink eafe371 -- adjagent`.
  Answer: `adjagent/preflight.py:120` alone.
- No signature changes. Every changed helper keeps its parameters, so no referencing file beyond
  those above is touched.

**Done-line.**
1. The checkpoint gate (Gates), which runs the suite and so the symlink-creation guard.
2. `just render p3b-claude`; `just render p3b-mage --harness=mage`;
   `just render p3b-opencode --harness=opencode --model-tier-map=all=inherit`.
3. `just render-diff p3a-<h> p3b-<h>` for each harness reports no differing file. R8 changes no
   render. The `p3a-<h>` slots are the ones confirmed or rendered before the first edit.

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
   `HOME="$PWD/.claude-temp/prerelease/home" just install-with-kb "$PWD/.claude-temp/prerelease/fresh" --harness=claude`.
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
   `HOME="$PWD/.claude-temp/prerelease/home-migrate" just --justfile "$PWD/.claude-temp/prerelease/v0.14.0/justfile" install-with-kb "$PWD/.claude-temp/prerelease/migrate" --harness=claude`.
2. User: `"$PWD/.claude-temp/prerelease/migrate/.claude/skills/docdicer/tools/docdicer" --install`.
3. Coordinator adds a project hook of its own to `.claude/settings.json` and an unrelated server to
   `.mcp.json`, then commits everything in the scratch repo.
4. Coordinator:
   `HOME="$PWD/.claude-temp/prerelease/home-migrate" just install-with-kb "$PWD/.claude-temp/prerelease/migrate" --harness=claude --dry-run`,
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

**Results so far:** A, B and C pass; C found empty directories left by prune, fixed in `01a27e9`.
A settings container emptied by retired-entry removal stays: nothing tells whether it predates the
install. D is **unverified**: the mage release with namespacing has not shipped.

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

- **Known item for the burndown list:** a regular file in place of the directory an MCP settings
  file goes in (`.opencode` as a file) is reported and left by the install, but `--dry-run` predicts
  the settings file created. Pinned by a test since P3b; a write target's obstacle should refuse
  before the first write, and the dry run predict it.

- **Reviewers** (dev-process default):
  - `python-coder`, for `adjagent/`, `tests/` and `devtools/scripts/`.
  - `architect`, since structure changed.
  - `tech-writer`, for `PROJECT_DOCS/`, `docs/` and `README.md`.
  - `prompt-engineer`, for definition descriptions, bodies, the agents file and R5's sentence in
    the `adjagent` skill.
- Each gets the contract documents and the diff `1049e2f..HEAD` (everything since 0.14.0), not this
  plan or the design.
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
