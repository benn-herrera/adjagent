### Renders and copies

An install renders every definition its plugin ships — for a skill, its skill entry file and then
each supporting file it lists — and every harness-rendered file whose owner ships (the plugin
manifest and `.mcp.json` under claude and mage, `registry.json` under opencode), bar a definition the
harness declares it renders nothing for (`Harness.omits`), replaces
the destination of each `SHIPPED_PACKAGES` row whose owner ships whole with a copy — a `.venv` directly
below it kept — copies each
harness resource the installing harness ships into the install directory as it stands — bar a
guardrail script whose probe fails (below) — writes the rendered definitions over what is there,
and removes each file under the install directory's `agents/`, `commands/` or `skills/` that this
run did not write, that would ship, and that is ours by its own carrier: frontmatter holding a
`!GENERATED!` line, or a comment line opening with it, which is how a skill's supporting file holds
its banner. `prune` walks the three surfaces (`_files_below`) of the install directory and nothing
else, and the upward walk visits only a stale file's ancestors and stops at the install directory.
What moves between plugins is the install directory: under claude another plugin's install directory
(`.claude/skills/kbase/`) sits inside the harness directory's `skills/`, so a walk wider than the
install directory would delete a different plugin. That walk needs no carve-out for a package
destination: the three `SHIPPED_PACKAGES` rows, the docdicer tools package, the development scripts
package and the kb-tools package, all sit inside the install directory's `skills/` —
`skills/docdicer/tools/`, `skills/development/scripts/` and `skills/kbase/kb-tools/`, each in its
skill's own directory — where every file they hold is stamped installed or left unstamped, never
generated, so every file under those trees is still either ours or untouched. A `.venv` the
docdicer script builds under its destination is outside what `_shipped` admits too, so its files
never enter the stale list. A definition of ours that this run did not write, such as one its plugin
does not ship, is stale and goes — every one of its files, a skill's included. Every definition is
rendered before the first write. A file at a rendered-definition destination that has lost the
generated banner, or is a directory, refuses the install.

The package copy skips the copy exclusions, names matched at any depth (test directories, caches,
`.venv` directories, `.DS_Store`, `.bak` files, the project documents), and copies each file's mode
(`copymode`). A copied file takes the installed banner when its suffix is in `STAMPED_SUFFIXES` (`.py`,
`.sh`, `.mk`, `.just`) or its name is in `STAMPED_NAMES` (`docdicer`, the one extensionless
launcher); `stamped` places the banner below a shebang. Any other file — the package's `.gitignore`
among them — is copied byte-verbatim.

The docdicer package lands inside the `docdicer` skill's own directory, so the skill names its script
`tools/docdicer`, relative to that directory. That is the one body path not written against the
harness directory (SPEC.md, Deployed Surfaces, Installed tree), because the skill's
directory differs by harness.

The development scripts package, `devpro/development-tools/`, takes the same package copy and adds
no code path: one row, `("development-tools", DEVELOPMENT_SCRIPTS_PACKAGE, "development")`, in
`SHIPPED_PACKAGES`. Its one file, `cold-read.sh`, is stamped by suffix and keeps its mode, and the
package is replaced whole and never pruned. It is one script for both harnesses, never rendered. It
finds its harness by name, from the nearest ancestor of its own resolved path called `.claude` or
`.opencode`. Under claude its run directory stays empty and the plugin loads by `--plugin-dir`, from
the nearest ancestor holding `.claude-plugin/`; under opencode it finds the nearest ancestor holding
`registry.json`, reads the named agent's record there with `python3 -I`'s `json` module, never by
matching the JSON text, and composes the run directory's agent file, `.opencode/agents/<plugin>-<name>.md`:
frontmatter holding the record's description, its model where present, the mode and
`permission: "*": deny`, then the body file with its banner lines stripped. It restates the two
directory names and the instruction names; `tests/test_cold_read_tools.py` holds the names against
`Harness.project_harness_dir` and every harness's `agents_file`. Mage's install of the devpro plugin ships the
file too, since `development` ships there, and there it refuses.

The harness resource copy borrows those copy exclusions and nothing else from the package path:
`harness_resource_copies` reads `resources/<harness>/` and writes each file into the install
directory with `copyfile` and `copymode`, so it lands as the harness ships it — no suffix is
stamped, whatever the file's type, and an installed banner a file already holds travels with it as
the file's own text. A guardrail script is the exception to copying every file: it joins the
copies, and its registration the rendered definitions, only when the probe below passes. A
user-level install copies one resource only, the harness's entry (`Harness.entry_resource`,
opencode's `index.ts`): the plugin cannot register without it, and the entry imports the guardrail
only where `guardrail.ts` stands beside it. Before the
first write, `_RESOURCE_BANNER` (`!INSTALLED! .* devpro`) is matched against the first ten lines
of an existing destination. Package destinations are exempt from the banner and marker checks.
`_clear_package_destination` empties the directory a destination is, all but a `.venv`
(`VENV_DIR`) directly under it, and unlinks any other file
there. No error is swallowed: an `OSError` from the clear propagates. The harness resources join the same `copies` list as the packages', so the prune's
`keep` holds them and the install report counts them: a harness resource never reads as a stale
rendered definition. The copy is one-way, not a mirror — `prune` owns the install directory's
`agents/`, `commands/` and `skills/` and nothing outside them. A harness-rendered file is checked a
third way, by its `HarnessFile.marker`.

**Preflight.** The CLI reaches `install` through `install.preflighted_install`,
which runs the unchanged install into a scratch copy of the paths it manages and compares the
scratch copy with the real paths (`devpro/preflight.py`). The install decides what is written,
run where its writes cannot reach the real paths; `_install_managed_paths` is a hand-kept list of
where it may write, and the dry-run prediction tests (`_assert_dry_run_predicts`, which has a
user-level case) hold that list against the install. Nothing recorded from an earlier install takes
part.

- **The managed set** (`_install_managed_paths`) is named from what the install writes by, never from
  a listing of a directory, which in a user harness directory holds the operator's own trees. The
  bases are the project root, the harness directory, the install directory and the harness's user
  harness directory, the install directory keeping its position below the harness directory. Under
  the user harness directory, on a claude or opencode project install: the paths of the
  `checked_followed_agents_file` decision that fall outside the project (Agents File, Placement).
  Under the harness directory: where
  the run writes an agents file, the `path`, `destination`, `backup` and `native` of a non-writing
  `checked_agents_file` call. Under the install directory: the three deployed surfaces, which the
  prune walks, the destination of every `SHIPPED_PACKAGES` row whichever definitions the plugin
  ships, the harness's resource destinations (at user level, the entry alone), every
  harness-rendered file — the manifest, `.mcp.json`, `registry.json` — and the guardrail registration.
  Under the project root, on a project install: the justfile and Makefile names unless the harness
  is a harness-directory plugin. The project's own settings files are not named: no install writes one.
- **The scratch copy** (`preflight.preflight`) lives in a `tempfile.TemporaryDirectory`, each
  managed path at its position below its base. Every `.venv` (`VENV_DIR`) is omitted. A base nested in another keeps its position below the outer
  one.
- **The run** calls `install` on the scratch copy with `real_harness_dir` and `real_project` naming
  the real paths, because three decisions compare a written path with a fixed location and a
  scratch copy would decide them differently: whether the harness directory is user-level, whether
  the project is `REPO_ROOT` (the include lines are skipped there), and the agents file's
  user-harness-directory test and title, which `checked_agents_file` and `install_agents_file` read
  from their `real_directory` parameter. Its stdout, the write log, is discarded. What the install
  leaves alone or skips goes to stderr, which the run captures and prints again, each scratch base
  replaced by the real one, on the up-to-date and dry-run outcomes. An `InputError` or `OSError` from the scratch copy or the run is raised as an
  `InputError` with each scratch base replaced by the real one, so no refusal and no printed path
  names the scratch copy.
- **The comparison** is of files. A path in the scratch copy
  only is created, in the real paths only is removed, and in both is changed when
  `filecmp.cmp(shallow=False)` is false or `stat.S_IMODE` differs. Directories are compared for
  removal alone: one in the scratch copy before the run and gone after it is removed. `.venv`
  directories (`VENV_DIR`) are outside it.
- **The outcome** (`run_preflighted`): with no difference it returns before the real install, and
  with `--dry-run` it prints the comparison and the
  captured reports, then returns. Otherwise the real install runs as `install` always has.
- **Obstacles.** A regular file where a directory on the way to a managed path should be
  (`.opencode` as a file) is copied in the directory's place (`_copy_managed`), so the scratch
  install meets the obstacle the real one does.

**No tool install.** `install` runs no shipped package's script and takes no callable for one. The docdicer
tools package's destination is replaced like any other, and the `.venv` the launcher built beside
itself is kept. On its next run the launcher rebuilds that venv where its python does not run, and
reinstalls the docdicer it names where the venv's docdicer reports another version (SPEC.md, Deployed Surfaces, Shipped files). The install manages no dependencies across
packages, and needs no network.

**Shadow report and reload sentence.** The last two steps of `install`, for a harness whose
`user_plugin_shadows` is set — claude alone, the one whose user-level plugin loads in place of a
project's of its name — (`_report_shadowing`) and for `reload_rule`. `_report_shadowing` reports
through `report_left_alone`. A user-level plugin counts as present when every harness-rendered file
this install renders is at `<user_harness_dir>/<plugin_dir>`, carrying its marker. The check
reads the operator's real home, so it runs inside the preflight's scratch copy as it does for real,
and its stderr line reaches the up-to-date and dry-run outcomes. `Harness.reload_rule`, where
non-empty, is printed to stdout after the writes; an up-to-date run returns at the preflight before
the real install and prints none.

