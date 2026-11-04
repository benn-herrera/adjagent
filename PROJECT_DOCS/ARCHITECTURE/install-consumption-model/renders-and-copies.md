### Renders and copies

An install renders every included definition — its own output, then each supporting file a skill
lists — and every file the harness itself renders (mage's manifest), bar a definition the harness
declares it renders nothing for (`Harness.omits`), replaces each destination `_packages` names
whole with a copy — a `.venv` below it included — copies each file the installing harness ships into ROOT as it stands
— bar a guardrail script whose probe fails (below) — writes the renders over what is there, and
removes each file under `agents/`, `commands/` or `skills/` that this run did not write, that would
ship, and that is ours by its own carrier: a frontmatter block holding a `!GENERATED!` line, or a
comment line opening with it, which is how a skill's supporting file holds its banner. It then
removes each directory that leaves empty, up to its surface. That walk needs no carve-out for a
package destination: the table's one row, the docdicer tools package, and the kb toolchain's
destination both sit inside a surface — `skills/docdicer/tools/` and `skills/kbase/kb-tools/`, each
in its skill's own directory — where every file they hold is stamped installed or left unstamped,
never generated, so every file under a surface is still either ours or untouched. A `.venv` the
docdicer script builds under its destination is outside the would-ship vocabulary too, so its files
never enter the stale list. A kb-set name is
inside that would-ship vocabulary, so under a base install one this run did not write is stale and
goes — every one of its files, a skill's included. Every install also removes each tree in
`LEGACY_TREES`, naming each it removed: `agents/kb_tools/` (the pre-1.0 kb helper tree),
`adj-tools/kb-tools/` (where v0.11.x installed the kb toolchain), `agents/kb-tools/` (written only
by an unreleased build) and `agents/liaison_tools/`. A run that excludes kb reports the removal of
`agents/kb_tools/` with the advice to install with kb. A render that fails writes nothing. There is no hash or backup of a modified
file: a local edit that keeps the banner lives only until the next install, which rewrites the file
it touched or prunes it, while a file at a render target that has lost the banner, or is a directory
or symlink, refuses the install; where the consuming project tracks the installed set, its git is
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
script is the exception to copying every file: it joins the copies only when the probe below
passes. Before the first write, a target that exists must be a regular file, not a symlink, with a
line matching `!INSTALLED! .* adjagent` among its first ten; one unreadable or without it refuses
the install. No component between ROOT and any render or resource target may be a symlink or a
non-directory (`_blocked_component`); one that is refuses the install in the same refusal, and
components at or above ROOT are not examined. Package destinations are exempt from both checks:
this repository owns those entire and replaces them whole. The resource
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
  a listing of ROOT, which in a user harness directory holds the operator's own trees. Under ROOT: the
  three surfaces, the destination of every package `_packages(kb_included=True)` names, each
  `LEGACY_TREES` entry, the harness's resource targets and rendered files, and, where the run writes
  an agents file, the `path`, `destination`, `backup` and `native` of a non-writing
  `checked_agents_file` call. Under the project root, on a project install: the justfile and Makefile
  names, the guardrail settings file, and the MCP settings candidates (`Harness.mcp.canonical` and
  `.alternatives`), which sit under ROOT instead for a harness whose `McpSettings.site` is `HARNESS`.
- **The copy** (`preflight.preflight`) lives in a `tempfile.TemporaryDirectory`, each managed path at
  its position below its base. A managed path that is a symlink, dangling included, is reproduced as a
  symlink, so the install's own checks see what they see on the target: to its counterpart in the copy
  where the link reaches another managed path, else to a stand-in under the scratch directory
  holding a copy of what it reaches and nothing where it dangles. Every other symlink is
  dereferenced (`copy2`, `copytree(symlinks=False)`), so nothing in the copy points back into the
  target. Every `.venv` (`VENV_DIR`) is omitted. A base nested in another keeps its position below
  the outer one.
- **The run** calls `install` on the copy with `real_root` and `real_project` naming the real paths,
  because three decisions compare a written path with a fixed location and a copy would decide them
  differently: whether ROOT is user-level, whether the project is `REPO_ROOT` (the include line is
  skipped there), and the agents file's user-directory test and title, which
  `checked_agents_file` and `install_agents_file` read from their `real_directory` parameter. Its
  stdout, the write log, is discarded. What the install leaves alone or skips goes to stderr, which
  the run captures and prints again, each scratch base replaced by the real one, on the up-to-date
  and dry-run outcomes. `tool_install` is passed and never reached, the copy holding no `.venv`.
  `_refuse_root` runs on the real ROOT first, and an `InputError` or `OSError` from the copy or the
  run is raised as an `InputError` with each scratch base replaced by the real one, so no refusal
  and no printed path names the copy.
- **The comparison** is of files, and of symlinks by what they point to; directories are not
  compared. A path in the copy only is created, in the target only is removed, and in both is changed
  when `filecmp.cmp(shallow=False)` is false or `stat.S_IMODE` differs. `.venv` directories are
  outside it, so a present venv alone never makes an install proceed.
- **The outcome** (`run_preflighted`): with no difference, `up to date: <ROOT> — nothing written` and
  a return, the target untouched — no file, no package destination, no `tools/.venv`, no re-run;
  the captured reports follow. With `--dry-run`, the paths grouped `created`, `changed` and
  `removed`, relative to the project root, then the notes `preflighted_install` passes — where a
  project install finds a docdicer `tools/.venv`, that the install would replace it and run
  `tools/docdicer --install`, which needs the network — then the captured reports, and a return.
  Otherwise the real install runs as `install` always has.
- **What the copy does not predict.** The copy dereferences every symlink that is not itself a
  managed path, so the refusal or left-alone report the real install makes for a symlink or
  non-directory on the path to a target, such as the directory above a settings file, is not
  foreseen; a dry run may not show it, and the install still judges it. A symlink at a managed path
  is reproduced, so a symlinked surface or package destination is refused at preflight, dry run
  included, and a symlinked settings file the install leaves alone reads as up to date.

**The tool re-run.** `install` takes `tool_install`, a keyword-only callable from a script path to
`None` on success or a one-line failure description, shaped like `uncommitted`. On a project install,
before its first write, it records whether `<ROOT>/skills/docdicer/tools/.venv` is a directory; the
package replacement then removes it with the rest of the destination. After every other write it calls
`tool_install` with `<ROOT>/skills/docdicer/tools/docdicer` if the venv was there, and prints one line
naming the command and the description when one comes back. The install's exit status and its
other writes are unaffected. `cli.py` passes `install.run_tool_install`, a `subprocess.run` of
`[script, "--install"]` whose non-zero exit or `OSError` becomes the description; `install.py`
reimplements neither venv creation nor pip. A test passes a recording runner, so none reaches the
network.

