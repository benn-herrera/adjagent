### Renders and copies

An install renders every included definition — its own output, then each supporting file a skill
lists — and every file the harness itself renders (the plugin manifest, under claude and mage), bar a definition the harness
declares it renders nothing for (`Harness.omits`), replaces each destination `_packages` names
whole with a copy — a `.venv` below it included — copies each file the installing harness ships into ROOT as it stands
— bar a guardrail script whose probe fails (below) — writes the renders over what is there, and
removes each file under the harness directory's `agents/`, `commands/` or `skills/` that this run did
not write, that would ship, and that is ours by its own carrier: a frontmatter block holding a
`!GENERATED!` line, or a comment line opening with it, which is how a skill's supporting file holds its
banner. ROOT sits below the harness directory inside its `skills/` surface, so this one walk reaches
ROOT's stale renders and the generated files a flat layout left directly under the harness directory.
Before it, a project install under a harness with a `plugin_dir` removes whole each package
destination `_packages(kb_included=True)` names directly under the harness directory, the flat
layout's, printing each; one that is a link has the link removed (`_remove_entry`) and what it names
stays. A user-level install removes none. `prune` walks through linked directories (`_files_below`,
ending at a cycle), judges a file by the file it names and compares what it keeps by resolved path,
and removes a link, never its target, where a stale entry or an emptied directory is one. The walk then
removes each directory that leaves empty, upward from the removed file to the first directory that
still holds anything — the surface itself included, the harness directory never. Only a stale file's
ancestors are visited, so a directory that held nothing before the install stays. That walk needs no carve-out for a
package destination: the table's one row, the docdicer tools package, and the kb toolchain's
destination both sit inside a surface — `skills/docdicer/tools/` and `skills/kbase/kb-tools/`, each
in its skill's own directory — where every file they hold is stamped installed or left unstamped,
never generated, so every file under a surface is still either ours or untouched. A `.venv` the
docdicer script builds under its destination is outside the would-ship vocabulary too, so its files
never enter the stale list. A kb-set name is
inside that would-ship vocabulary, so under a base install one this run did not write is stale and
goes — every one of its files, a skill's included. Every install also removes each tree in
`LEGACY_TREES` under the harness directory (a link removed as a link), naming each it removed: `agents/kb_tools/` (the pre-1.0 kb helper tree),
`adj-tools/kb-tools/` (where v0.11.x installed the kb toolchain), `agents/kb-tools/` (written only
by an unreleased build) and `agents/liaison_tools/`. A run that excludes kb reports the removal of
`agents/kb_tools/` with the advice to install with kb. A render that fails writes nothing. There is no hash or backup of a modified
file: a local edit that keeps the banner lives only until the next install, which rewrites the file
it touched or prunes it, while a file at a render target that has lost the banner, or is a directory,
refuses the install; where the consuming project tracks the installed set, its git is
the record of what an install changed.

The package copy skips a vocabulary of names matched at any depth (test directories, caches, `.venv`
directories, `.DS_Store`, `.bak` files, the project documents) and carries the executable bit. A
copied file takes the installed banner when its suffix is in `STAMPED_SUFFIXES` (`.py`, `.sh`, `.mk`,
`.just`) or its name is in `STAMPED_NAMES` (`docdicer`, the one extensionless launcher); `stamped`
places the banner below a shebang. Any other file — the package's `.gitignore` among them — is copied
byte-verbatim.

The docdicer package lands inside the `docdicer` skill's own directory, so the skill names its script
`tools/docdicer`, relative to that directory. That is the one body path not written against the
harness project directory (SPEC.md, Deployed Surfaces, Installed artifacts), because the skill's
directory differs by harness.

The harness resource copy borrows that vocabulary and nothing else from the package path:
`harness_resource_copies` reads `resources/<harness>/` and writes each file into ROOT with
`copyfile` and `copymode`, so it lands as the harness ships it — no suffix is stamped, whatever the
file's type, and a header a file already holds travels with it as the file's own text. A guardrail
script is the exception to copying every file: it joins the copies, and its registration the
renders, only when the probe below passes. Before the first write, a target that exists must be a regular file, links followed, with a
line matching `!INSTALLED! .* adjagent` among its first ten; one unreadable or without it refuses
the install. No component between ROOT and any render or resource target may be a non-directory,
links followed (`_blocked_component`); one that is refuses the install in the same refusal, and
components at or above ROOT are not examined. So does a dangling link on the way to a target, or at
one whose named path sits in a missing directory (`_dangling_on_path`); a dangling link at a target
otherwise is written through. Package destinations are exempt from these checks:
this repository owns those entire and replaces them whole. `_clear_package_destination` empties a
destination that is a link to a directory and leaves the link, and makes the directory a dangling
link names; the copy then writes through it. The resource
files join the same `copies` list as the packages', so the prune's `keep` holds them and the report
counts them: a harness file never reads as a stale render, and the report line says `copied files`
for the lot. The copy is one-way, not a mirror — `prune` owns the three rendered surfaces and nothing
outside them — so a resource this repository stops shipping stays in a consumer until that project
removes it. A harness-rendered file is a third target class beside those two: recognised by the
marker it states about itself, and refused where a file at its path does not hold it.

#### Preflight and the tool re-run

The CLI reaches `install` through `install.preflighted_install`, which runs the unchanged install
into a scratch copy of the paths it manages and compares the copy with the target
(`adjagent/preflight.py`). The install decides what is written, run where its writes cannot reach
the target; `_install_managed_paths` is a hand-kept list of where it may write, and the dry-run
prediction tests (`_assert_dry_run_predicts`, which has a user-level case) hold that list against
the install. No version marker or stamp file takes part.

- **The managed set** (`_install_managed_paths`) is named from what the install writes by, never from
  a listing of a directory, which in a user harness directory holds the operator's own trees. The bases
  are the project root, the harness directory and ROOT, ROOT keeping its position below the harness
  directory. Under the harness directory: the three surfaces the prune walks, each `LEGACY_TREES`
  entry, the retired package destinations, and, where the run writes an agents file, the `path`,
  `destination`, `backup` and `native` of a non-writing `checked_agents_file` call. Under ROOT: the
  three surfaces, the destination of every package `_packages(kb_included=True)` names, the
  harness's resource targets, rendered files and guardrail registration, and the MCP settings
  candidates where `McpSettings.site` is `HARNESS` and the run may write them. Under the harness
  directory, on a project install: the flat layout's guardrail script path. Under the project root,
  on a project install: the justfile and Makefile names, each settings file a retired entry is
  removed from, and the MCP settings candidates (`Harness.mcp.canonical` and `.alternatives`) where
  `McpSettings.site` is `PROJECT`.
- **The copy** (`preflight.preflight`) lives in a `tempfile.TemporaryDirectory`, each managed path at
  its position below its base. Every symlink is dereferenced (`copy2`, `copytree(symlinks=False)`): a
  managed path is copied as what it names, a dangling link as nothing, so the copy holds no link and
  nothing in it points back into the target. Every `.venv` (`VENV_DIR`) is omitted. A base nested in another keeps its position below
  the outer one.
- **The run** calls `install` on the copy with `real_harness_dir` and `real_project` naming the real
  paths, because three decisions compare a written path with a fixed location and a copy would decide
  them differently: whether the harness directory is user-level, whether the project is `REPO_ROOT` (the include line is
  skipped there), and the agents file's user-directory test and title, which
  `checked_agents_file` and `install_agents_file` read from their `real_directory` parameter. Its
  stdout, the write log, is discarded. What the install leaves alone or skips goes to stderr, which
  the run captures and prints again, each scratch base replaced by the real one, on the up-to-date
  and dry-run outcomes. `tool_install` is passed and never reached, the copy holding no `.venv`.
  `_refuse_root` runs on the real ROOT first, and an `InputError` or `OSError` from the copy or the
  run is raised as an `InputError` with each scratch base replaced by the real one, so no refusal
  and no printed path names the copy.
- **The comparison** is of files, the real side read through its links. A path in the copy only is
  created, in the target only is removed, and in both is changed when `filecmp.cmp(shallow=False)` is
  false or `stat.S_IMODE` differs. Directories are compared for removal alone: one in the copy before
  the run and gone after it is removed, and the dry run lists it with a trailing `/`. `.venv` directories are
  outside it, so a present venv alone never makes an install proceed.
- **The outcome** (`run_preflighted`): with no difference, `up to date: <ROOT> — nothing written` and
  a return, the target untouched — no file, no package destination, no `tools/.venv`, no re-run;
  the captured reports follow. With `--dry-run`, the paths grouped `created`, `changed` and
  `removed`, relative to the project root, then the notes `preflighted_install` passes — where a
  project install finds a docdicer `tools/.venv`, that the install would replace it and run
  `tools/docdicer --install`, which needs the network — then the captured reports, and a return.
  Otherwise the real install runs as `install` always has.
- **Dangling links.** The copy holds nothing where a link dangles, so the copy cannot show the
  refusal for one. `_refuse_foreign_targets` and the MCP settings check therefore read each target's
  counterpart at the real path (`real_harness_dir`, `real_project`) with `_dangling_on_path`, and the
  dry run reports that refusal as the install does.
- **What the copy does not predict.** A regular file where a directory on the way to an MCP settings
  file should be (`.opencode` as a file): the install reports that it is not a directory and leaves
  it, while the dry run predicts the settings file created.

**The tool re-run.** `install` takes `tool_install`, a keyword-only callable from a script path to
`None` on success or a one-line failure description, shaped like `uncommitted`. On a project install,
before its first write, it records whether `skills/docdicer/tools/.venv` is a directory under ROOT or
under the harness directory (`_standing_docdicer_venvs`; the second is where a flat layout kept it,
and the retired-destination removal takes it); the package replacement then removes it with the rest
of the destination. After every other write it calls
`tool_install` with `<ROOT>/skills/docdicer/tools/docdicer` if a venv was there, and prints one line
naming the command and the description when one comes back. The install's exit status and its
other writes are unaffected. `cli.py` passes `install.run_tool_install`, a `subprocess.run` of
`[script, "--install"]` whose non-zero exit or `OSError` becomes the description; `install.py`
reimplements neither venv creation nor pip. A test passes a recording runner, so none reaches the
network.

**Shadow report and reload sentence.** The last two steps of `install`, for a harness with a
non-empty `plugin_dir` (`_report_shadowing`) and `reload_rule`. A user-level install reports through
`_report_left_alone` that it takes precedence over every project's plugin; a project install reports
that a plugin of the same name at `<user_harness_dir>/<plugin_dir>` shadows its own, when every file
the harness renders of its own (`rendered_files`) is there carrying its marker. Neither refuses. The
check reads the operator's real home, so it runs inside the preflight copy as it does for real, and its
stderr line reaches the up-to-date and dry-run outcomes. `Harness.reload_rule`, where non-empty, is
printed to stdout after the writes; an up-to-date run returns at the preflight before the real
install and prints none.

