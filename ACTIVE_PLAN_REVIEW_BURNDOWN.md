# Post-plan review burndown: 1049e2f (0.14.0) to 01a27e9

This list merges four reviews: `.claude-temp/p5-python.md` (PY), `p5-architect.md` (AR), `p5-docs.md`
(DOC) and `p5-prompt.md` (PR). A tag in parentheses names the review an item came from. Every
source, test and contract-document file:line below was re-read at `01a27e9`, unless it is marked
"(DOC cite)". A cite into rendered output names its slot.

**Key**
- **fix**: lands in this release.
- **defer → ROADMAP**: too wide to be a hardening fix. Item D5-9 records it in ROADMAP.
- **pending owner ruling**: a recommended outcome is written in. The item runs in its dispatch only
  once the owner has ruled. If the ruling differs from the recommendation, the item is revised first.
  If the ruling has not arrived when the dispatch starts, the item is left out and dispatched later.

**Symlink rule (R8), applied to every item below**
- A link is what it names.
- A dangling link AT a target has what it names created.
- A dangling link ON THE WAY to a target, or AT a target whose named parent is missing, refuses
  before the first write, and the dry run predicts that refusal.
- A removal unlinks the link and never touches what it names.

**Dispatch order**: every dispatch runs serially, D4 included, because all of them share one build.
1. Step 0, before the first fix, at `01a27e9`, take the render baselines:
   - `just render p5-base`
   - `just render p5-base-oc --harness=opencode`
   - `just render p5-base-mage --harness=mage`
2. Then D1 → D2 → D3 → D4 → D5 → D6.
3. D6-7 is outside D6. It runs at release.

**Edit gate**: each dispatch brief states `just test-changed <hash at dispatch>`, run after each
edit.

**Done-lines**
- Python items: `just format-python` is clean and `just test adjagent` passes, including the tests
  each item names.
- Prompt items, and any item that changes rendered text:
  - render the after-slots with the same flags as the baselines: `just render p5-after`,
    `just render p5-after-oc --harness=opencode`, `just render p5-after-mage --harness=mage`;
  - `just render-diff p5-base p5-after` (and `-oc`/`-mage` where the item names that harness) shows
    only the item's intended lines;
  - `just test adjagent` passes (it includes the cross-reference guard);
  - the `reference-*` slots are not diffed. They are retaken only after the fixes land.
- Doc items: `just check-links` passes.

**Doc edits within one file**: apply them bottom-up, so an earlier edit does not shift a later
item's line numbers. Each doc item also quotes an anchor phrase to locate it by.

**Settled: an obstacle on the way to the MCP settings file is reported and left alone**
- `PROJECT_DOCS/SPEC/write-safety.md:57` governs: the kb settings file is "left alone where a
  non-directory or non-regular file stands in the way". The install's behaviour stands. Only the
  dry run's prediction is wrong, and D1-5 fixes it.

---

## D1 — python-coder: write safety in `install.py`, `install_target.py`, `preflight.py` and `tests/test_adjagent_install.py`

### D1-1 [Critical, fix] A dangling `Makefile` link turns a kb install into a half-written traceback
- **Defect**: `_runner_file` reads a dangling link as absent. The create-Makefile branch then
  writes through the link and raises `FileNotFoundError` after the renders have landed. The dry run
  had predicted "created". This breaks R8 and "every check before the first write". (PY 1)
- **Where**: `adjagent/install.py:1129-1139`, `:1048-1053` (`_check_runner`) and `:1373-1374`.
- **Reference search**: `git grep -n "_check_runner("` finds `install.py:1048` (the definition) and
  `:1374` (the only caller).
- **Fix**:
  - Give `_check_runner` a `real_project` parameter. The caller passes
    `project if real_project is None else real_project`.
  - Where `_runner_file` finds nothing, run
    `_dangling_on_path(real_project / "Makefile", base=real_project)`. On a hit, raise `InputError`
    naming the link.
- **Done**: `just test adjagent` passes with a project-level case added to
  `test_a_link_nothing_can_be_written_through_is_refused_with_nothing_written`: a `Makefile` linking
  to `missing/Makefile` with `--with-kb`, run with and without `--dry-run`.

### D1-2 [Critical, fix] A symlinked `.claude` or `.claude/skills` is refused, and the dry run predicts success
- **Defect**: `_harness_relpath` compares `root.resolve()` with the resolved project root. A ROOT
  reached through a linked surface therefore resolves outside the project and is refused, which
  breaks R8 ("a link is what it names"). The preflight copy dereferences links, so the dry run
  predicts success. (PY 2)
- **Where**:
  - `adjagent/install_target.py:28-34` (`InstallTarget`), `:111-122`;
  - `adjagent/cli.py:115-121`;
  - `adjagent/install.py:1100-1109` (`_harness_relpath`), `:1180-1186` (`_installs_agents_file`),
    `:1313`, `:1320`, `:1387`, `:1475-1482` and `:1516` (`_install_managed_paths`), and `:1561`,
    `:1563`, `:1573-1574` (`preflighted_install`).
- **Reference search**:
  - `git grep -n "resolve_install_target\|InstallTarget\|\.project_root"` finds `cli.py:27`, `:115`,
    `:121` and `install_target.py:28`, `:95`, `:122`. No test reads `.project_root`.
  - `git grep -n "_harness_relpath(\|_installs_agents_file(\|_install_managed_paths("` finds
    `install.py:1320`, `:1387`, `:1516`, `:1563`, `:1573` and `:1574`.
- **Fix**:
  - `InstallTarget.project_root` becomes the lexical project path: the target normalised without
    following links, or its lexical parent where the target is the harness directory. Update the
    docstring to match. `cli.py` keeps passing `project_root=target.project_root`.
  - `install()` and `preflighted_install()` keep their signatures. Each keeps resolving
    `project_root` into `project` (`:1313`, `:1561`) for every current use. Each also keeps the
    lexical form, `Path(os.path.normpath(<project_root, or harness_dir where None>.absolute()))`.
  - `_harness_relpath` compares `os.path.normpath(root.absolute())` with the lexical project path.
    The "outside the project" refusal stays, and is judged lexically.
  - `_installs_agents_file` compares the lexical harness directory with the lexical project path.
    `_install_managed_paths` gains the lexical path as a keyword argument to pass on.
  - The test helper at `tests/test_adjagent_install.py:397` does not change, because `install()`'s
    signature does not.
  - SPEC `install-destination.md:25`, "The project root is resolved through symlinks.", holds as
    written: the project root is still resolved, and only ROOT's relpath is lexical. D5-9 records the
    mechanism in ARCHITECTURE.
- **Done**: `just test adjagent` passes with `_assert_dry_run_predicts` cases for a project whose
  `.claude/skills` is a link, and one whose `.claude` is a link. Both install, and the dry run
  matches the real run.

### D1-3 [Warning, fix] A dangling link at a package destination creates every missing parent of the path it names
- **Defect**: `_clear_package_destination` runs `destination.resolve().mkdir(parents=True)`, and no
  pre-write check covers destinations. Under R8, a dangling link whose named parent is missing must
  refuse. (PY 3)
- **Where**: `adjagent/install.py:1206-1215` and `:1359-1369`. Note that `_refuse_foreign_targets`'
  `real_root` is the harness directory (`:1361`), while destinations are relative to ROOT (`:1407`).
- **Reference search**: `git grep -n "_refuse_foreign_targets("` finds `install.py:343` (the
  definition) and `:1359` (the only caller).
- **Fix**:
  - Before `root.mkdir`, for each destination in `_packages(kb_included=kb_included)` (none on a
    user-level install), run `_dangling_on_path(real_plugin_root / destination,
    base=real_plugin_root)`, where `real_plugin_root` is
    `(harness_dir if real_harness_dir is None else real_harness_dir) / ctx.harness.plugin_dir`.
  - Add each hit to the one refusal that `_refuse_foreign_targets` raises.
  - Line 1215 then becomes `mkdir(parents=False)`.
- **Done**: `just test adjagent` passes with the missing-parent case added next to
  `test_a_symlinked_package_destination_stays_a_link_and_holds_the_fresh_package`. The case runs
  with and without `--dry-run`, so the dry run predicts the refusal.

### D1-4 [Warning, fix] `rmtree(ignore_errors=True)` hides a failed destination clear
- **Defect**: a failed clear is not reported, and stale files survive in a destination that the
  contract says is "replaced whole". This also breaks the house rule against swallowing exceptions.
  (PY 5)
- **Where**: `adjagent/install.py:1210`.
- **Fix**:
  - Drop `ignore_errors`.
  - A directory is cleared with `rmtree`. A non-directory at the destination (not a link) is
    unlinked, because the repository owns the destination whole.
  - Any `OSError` propagates. No pre-write refusal is added, since that would be a contract change.
- **Done**: `just test adjagent` passes with a case where a regular file sits at
  `skills/docdicer/tools` and is replaced by the package.

### D1-5 [Warning, fix] The dry run predicts an MCP settings file "created" where the install leaves it alone, and a test pins that
- **Defect**: `_copy_managed` copies a managed path only when its real parent is a directory. So the
  scratch install creates the file that the real install reports and leaves alone. SPEC requires the
  dry run to make the same judgment. (PY 4)
- **Where**: `adjagent/preflight.py:84-91`. The pin is in `tests/test_adjagent_install.py:2889-2906`.
- **Fix**:
  - For each managed path whose real parent chain holds a non-directory, copy the outermost such
    component (read through links) to its place in the copy, so the scratch install meets the same
    obstacle.
  - Rewrite the pinning test to assert that the dry-run groups and stderr equal the real run's, and
    drop its "Today's behaviour, pinned" docstring.
  - The install's report-and-leave behaviour stands (SPEC `write-safety.md:57`). The dry run must
    predict it, and the test pinning the mismatch changes to pin the match.
- **Done**: `just test adjagent` passes. The rewritten test passes for opencode with `tools` as a
  regular file.

---

## D2 — python-coder: tidy `install.py`, `install_target.py`, `harness.py`, `harnesses/claude.py`, `harnesses/mage.py`, `agents_file.py`, `harnesses/resources/claude/hooks/guardrail.pl` and `tests/test_adjagent_install.py`

### D2-1 [Note, fix] Two readers decide whether a settings file holds a retired entry
- **Defect**: `_earlier_guardrail` and `_remove_retired_entry` each pair their own reader with
  `_retired_claims`. Only the removal applies `_refuse_wrong_types`, so the two can classify the
  same file differently. (PY 7)
- **Where**: `adjagent/install.py:986-1009`, `:940-983` and `:912-921`.
- **Reference search**:
  `git grep -n "_earlier_guardrail(\|_remove_retired_entry(\|_editable_settings("` finds
  `install.py:912`, `:940`, `:959`, `:986`, `:1451` and `:1456`.
- **Fix**: add one helper, `_retired_items(project, entry)`, which returns
  `(target, text, claims) | None`, and call it from both.
- **Done**: the Python done-line.

### D2-2 [Note, fix] The user harness directory as a `Path` is computed in three places
- **Where**: `adjagent/agents_file.py:84-86`, `adjagent/install_target.py:125-129` and
  `adjagent/install.py:1230`. (AR N3, PY 8)
- **Reference search**: `git grep -n "user_dir("` finds `agents_file.py:84`, `:92`, `:376`, the
  `from adjagent.agents_file import (...)` block at `install.py:30-39`, and `install.py:1398`,
  `:1521`. There are no hits in tests.
- **Fix**:
  - Add a `Harness.user_dir` property in `harness.py`.
  - Move `agents_file.py:92`, `:376` and `install.py:1230`, `:1398`, `:1521` to it.
  - Drop `user_dir` from the import block, and delete `agents_file.user_dir`.
  - `_absolute_user_dir` keeps only its absolute-or-None test, applied to the property.
- **Done**: the Python done-line.

### D2-3 [Note, fix] `HookClaim` now classifies MCP entries as well as hooks
- **Where**: `adjagent/harness.py:101-107`. (AR W3, PY 9)
- **Reference search**: `git grep -n HookClaim` finds `harness.py:101`, `:141`; `claude.py:16`,
  `:91`, `:97`, `:105`, `:106`, `:109`, `:115`; and `install.py:42`, `:893`, `:909`, `:971`. There
  are no hits in tests or docs.
- **Fix**: rename it to `EntryClaim` at every site found. No other part of the AR W3 reshape is in
  this item (see DEF-3).
- **Done**: the Python done-line.

### D2-4 [Note, fix] Stale MCP-prefix example in a field comment
- **Where**: `adjagent/harness.py:155`, `# "mcp__kbase__" / "kbase_"`. Claude's prefix is now
  `mcp__plugin_adjagent_kbase__`. (AR N4)
- **Fix**: drop the examples from the comment.
- **Done**: the Python done-line.

### D2-5 [Note, fix] Docstrings that narrate a test or restate the contract
- **Where**: `adjagent/install.py:1125-1126` (the clause "the repository test reads it") and
  `:1252-1309` (`install`, about 57 lines). (PY 10)
- **Fix**:
  - Drop the clause.
  - Cut `install`'s docstring down to what the parameters mean and the ordering guarantee: every
    check, then the writes, then the removals.
- **Done**: the Python done-line.

### D2-6 [Note, fix] A test pins a full stderr sentence
- **Where**: `tests/test_adjagent_install.py:1779` (`_UNREAD`). (PY 11)
- **Reference search**: `git grep -n _UNREAD tests` finds `:1779` (the definition) and `:1890`,
  `:2413`, `:2939` (the assertions).
- **Fix**: at each assertion, assert the named path, plus "by hand" or the printed entry, in one
  stderr line. `:2939` asserts an absence and keeps asserting it.
- **Done**: the Python done-line.

### D2-7 [Note, fix] The backup-then-write sequence appears twice in `agents_file.py`
- **Where**: `adjagent/agents_file.py:272-290` and `:380-392`. (AR N5)
- **Reference search**: `git grep -n "write_agents_file(\|write_followed_agents_file("` finds
  `agents_file.py:199`, `:272`, `:380`, `:383` and `install.py:1421`, `:1423`. Callers are
  unaffected.
- **Fix**: add `_backed_up_write(path, backup, text)` and call it from both writers. Both records
  stay.
- **Done**: the Python done-line.

### D2-8 [Note, fix] The guardrail script's comment names the wrong directory for the kb signal
- **Where**: `adjagent/harnesses/resources/claude/hooks/guardrail.pl:18`, "the kbase skill in this
  script's own harness directory". Under claude, `$0` is in ROOT. (AR N2, DOC W7)
- **Fix**: change it to "the kbase skill in this script's ROOT, the directory above `hooks/`".
  Behaviour is unchanged.
- **Done**: `just test adjagent` (the guardrail tests).

### D2-9 [Note, fix — settled by R7: mage renders namespaced, skills included] mage's `reference_prefix` comment omits skills
- **Where**: `adjagent/harnesses/mage.py:50`, `# mage namespaces a plugin's agents and commands as
  Claude Code does`. The prefix also applies to skills: `rendered/p5-mage/CLAUDE.md:14`
  (`adjagent:dev-process`) and `rendered/p5-mage/skills/dev-process/SKILL.md:75`
  (`adjagent:docdicer`). (PR 6)
- **Outcome**: keep the prefix on skills, and change the comment to "mage namespaces a
  plugin's agents, commands and skills as Claude Code does".
- **Done**: the Python done-line, and `just render-diff p5-base-mage p5-after-mage` shows no change
  (the edit is a comment only).

---

## D3 — python-coder: references in `render.py` and `tests/test_adjagent_install.py`

### D3-1 [Warning, fix] A reference to a definition the install does not ship renders silently, and the reference map is rebuilt on every fill
- **Defect**:
  - The reference closed set is every discovered definition, so a reference to one that mage omits
    (`adjagent`, `imgread`), or that a base install excludes (`kbase`, `kb-*`), renders pointing at
    nothing.
  - Only the agents file's skill references are checked.
  - `filled_text` runs `discover()` and rebuilds the reference map on every body, description and
    supporting file.

  (AR W4, PY 6)
- **Where**: `adjagent/render.py:146-152` and `tests/test_adjagent_install.py:541-553`.
- **Fix**:
  - Build the reference map once per render (in `render_all`, or behind `functools.cache` keyed on
    the harness).
  - Replace the agents-file-only test with one that checks every harness under both the base and kb
    default installs: every `@!ref-<name>!@` in the source text of each included definition names a
    definition in that same render.
  - The render-time refusal for undiscovered names stays.
- **Done**: `just test adjagent` passes with the generalized test, and `just render-diff p5-base
  p5-after` (plus `-oc`/`-mage`) shows no change.

---

## D4 — prompt-engineer: definition text in `harnesses/claude.py`, `definitions/dev_process.py`, `definitions/harness_agents_file.py` and `definitions/architect.py`

### D4-1 [Note, fix] Namespaced names left out of backticks in prose
- **Where**:
  - `adjagent/definitions/harness_agents_file.py:52`, which renders as "get
    adjagent:prompt-engineer review" (`rendered/p5-claude/harness/claude/CLAUDE.md:41`);
  - `adjagent/definitions/architect.py:170`, which renders as "when adjagent:security-reviewer"
    (`rendered/p5-claude/skills/adjagent/agents/architect.md:170`).

  (PR 7)
- **Fix**: wrap both `clauses.ref(...)` sites in backticks.
- **Done**: the prompt done-line, across all three harness pairs.

### D4-2 [Warning, fix — owner ruled: the recommended wording] The reload sentence tells the model to "use" a command only the user can type
- **Where**: `adjagent/harnesses/claude.py:27-30` (`_RELOAD_RULE`), wired at `:128`. It is printed by
  `adjagent/install.py:1471-1472` and placed in the skill at `adjagent/definitions/adjagent.py:32`.
  (PR 1, PR 5)
- **Recommended outcome**: one constant, at its current placement, worded: "If the new agents are not
  available after using `adjagent install`, `/reload-plugins` rescans the agent list."
  `adjagent.py:32` does not change.
- **Done**: the prompt done-line. The claude pair shows only that sentence, and the opencode and
  mage pairs show no change.

### D4-3 [Warning, fix — owner ruled] Two edits to the new `dev-process` rules
- **Where**: `adjagent/definitions/dev_process.py:115-117` (the tests-in-scope bullet, anchor "lists
  every referencing file, with the {REFERENCE_SEARCH_TERM}") and `:131` (anchor "Each plan section
  gets one review"). (PR 2, PR 3)
- **Outcome**, and nothing else from PR 2 or PR 3:
  - Owner ruled: "one review" becomes "one `prompt-engineer` review", spelled through
    `clauses.ref(name="prompt-engineer")`.
  - Owner ruled: the tests-in-scope bullet returns to "a change to a type, signature or test double
    lists every referencing file, with the {REFERENCE_SEARCH_TERM} and its answer. *Purpose:* no
    referencing file is found broken after the package reports done;", and this bullet follows it,
    verbatim: "a package that changes a stated behaviour names the tests and fixtures pinning it, and
    updating them is in scope; a test failing on behaviour the package does not state it changes is
    reported as a finding, never edited to pass. *Purpose:* an expectation moves only with its
    requirement, so an invariant test still stops wrong work;".
- **Done**: the prompt done-line. Each pair shows only those two lines in `dev-process/SKILL.md`.

---

## D5 — tech-writer: PROJECT_DOCS and ROADMAP.md

### D5-1 [Critical, fix] "Version has one home" is false: the agents-file marker carries the version
- **Where**:
  - `PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/version-has-one-home.md:5-8`, anchor "No
    rendered file carries the version except the plugin manifest";
  - `PROJECT_DOCS/ARCHITECTURE/why-there-is-no-verification-verb.md:21` (DOC cite).

  The evidence is `adjagent/definitions/harness_agents_file.py:14` and `adjagent/render.py:155`.
  (AR W5, DOC C1)
- **Fix**: say that two rendered files carry the version: the manifest's `version` and the agents
  file's begin marker line. Say that after a bump, `render-diff` shows the manifest line in the
  claude and mage slots, the marker line in every slot, and nothing else.
- **Done**: the doc done-line.

### D5-2 [Note, fix] The holes leaf omits the version hole
- **Where**: `PROJECT_DOCS/ARCHITECTURE/composition-model/holes.md:12`, anchor "The agents file alone
  also carries". (AR N1)
- **Fix**: change "for its scope name" to "for its scope name and the package version".
- **Done**: the doc done-line.

### D5-3 [Warning, fix] The guardrail-hook leaf places claude's kb signal in the wrong directory, and gives a stale rationale
- **Where**: `PROJECT_DOCS/ARCHITECTURE/install-consumption-model/guardrail-hook.md`:
  - `:39`, anchor "runs only when `<harness-dir>/skills/kbase/SKILL.md` exists";
  - `:42`, anchor "`<harness-dir>/hooks/guardrail.pl`";
  - `:20`, anchor "the plugin is often committed".

  (AR N2, DOC W7, DOC N5)
- **Fix**:
  - Under claude, write `<ROOT>/hooks/guardrail.pl` and `<ROOT>/skills/kbase/SKILL.md`. Keep
    `<harness-dir>` for opencode's `guardrail.ts`.
  - Change "is often committed" to "may be committed or shared".
- **Done**: the doc done-line.

### D5-4 [Warning, fix] SPEC contradicts itself on rewriting an unstamped block
- **Where**: `PROJECT_DOCS/SPEC/harness-agents-file.md:50-51`, anchor "A block with no stamp, or one
  that is not a release version, is rewritten". It contradicts `:47`, "Identical content writes
  nothing, whatever the stamp". (DOC W4)
- **Fix**: end the sentence "is rewritten when its content differs".
- **Done**: the doc done-line.

### D5-5 [Warning, fix] The skip-on-failed-probe rule is scoped too widely, and `write-safety.md`'s long paragraph needs splitting
- **Where**:
  - `PROJECT_DOCS/SPEC/write-safety.md:61`, anchor "failed install-time run removes nothing";
  - `PROJECT_DOCS/ARCHITECTURE/install-consumption-model/guardrail-registration.md:7`, anchor "skips
    the retired-entry removal".

  (DOC W6, DOC N10)
- **Fix**:
  - Limit "removes nothing" and "skips" to the guardrail entry and the flat script.
  - State that the `kbase` member is removed whenever the kb MCP entry is written.
  - Split the `write-safety.md` paragraph that holds `:57` and `:61` by concern: symlinks, prune,
    retired entries, preflight. Make this split last in the file, after D5-6.
- **Done**: the doc done-line.

### D5-6 [Warning, fix] The dry run does not print every path relative to the project root
- **Where**: `PROJECT_DOCS/SPEC/write-safety.md:76`, anchor "relative to the project root, and exits
  0". (DOC W8)
- **Fix**: say "relative to the project root, or absolute for a file outside it, such as the global
  agents file".
- **Done**: the doc done-line.

### D5-7 [Warning, fix] SPEC says only agents and commands are namespaced, but skills are too
- **Where**: anchor "`adjagent:<name>` for an agent or a command" at:
  - `PROJECT_DOCS/SPEC/generation-system.md:45`;
  - `PROJECT_DOCS/SPEC/deployed-surfaces/installed-artifacts.md:30`;
  - `PROJECT_DOCS/SPEC/deployed-surfaces/install-destination.md:29`, anchor "its agents and commands
    are invoked as".

  (DOC W9)
- **Fix**: under the recommended ruling, change each to "an agent, a command or a skill" for claude
  and mage.
- **Done**: the doc done-line.

### D5-8 [Note, fix] Smaller contract-document corrections
- `ARCHITECTURE/install-consumption-model/installing-this-repository.md:3-6` (DOC cite):
  `install-agents-here` also keeps this repository's `AGENTS.md` block, and the sticky rule reads both
  ROOT and the harness directory. (DOC N4)
- `CONVENTIONS/code-definitions-and-install/cross-references-are-holes.md`, the bullet "An overlay
  cannot carry one.": add that an overlay therefore names no definition at all. (DOC N6)
- `SPEC/deployed-surfaces/surfaces-and-layout.md:17` (DOC cite): add claude's conditional
  `hooks/hooks.json`. In `SPEC/deployed-surfaces/install-destination.md:36` (DOC cite), "(below)"
  points at another page. (DOC N7)
- `SPEC/deployed-surfaces/shipped-files.md:13`, `:41` (DOC cite): remove the legacy `adj-tools/`.
  (DOC N8)
- `ARCHITECTURE/subsystem-map.md`:
  - fix the indent of the bullet continuation that opens "`reload_rule` hole";
  - correct "`install.py` renders, copies and prunes" to say it also edits settings files and writes
    the runner line.

  (DOC N9, AR W1)
- **Done**: the doc done-line.

### D5-9 [Note, fix] Record D1–D3 in ARCHITECTURE, and the deferrals in ROADMAP
- **Where**:
  - `ARCHITECTURE/install-consumption-model/renders-and-copies.md:62` (anchor "Package destinations
    are exempt from these checks") and `:127` (anchor "What the copy does not predict");
  - `ARCHITECTURE/install-consumption-model/install-entry.md`;
  - `ROADMAP.md`, appended above any `(KEEP LAST)` item.
- **Fix**:
  - In `renders-and-copies.md`, state that a dangling-link destination with a missing parent
    refuses, and that the destination clear propagates errors. Remove the "does not predict" bullet.
  - In `install-entry.md`, record the lexical relpath (D1-2) and the runner-file refusal (D1-1).
  - In `ROADMAP.md`, add one item each for DEF-1 to DEF-5, each stating the fact and where it lives.
- **Done**: the doc done-line.

---

## D6 — tech-writer: README.md and docs/

### D6-1 [Warning, fix] The upgrade from 0.14.0 is half-documented
- **Where**: `docs/install-reference.md:85-91` (DOC cite), the section "Upgrading from the flat
  layout". (DOC W1)
- **Fix**: name the release that introduces the plugin form. Then list, in this order:
  - the invocation rename to `adjagent:<name>`;
  - starting at the project root, the trust dialog, and the reload;
  - the edits to `.claude/settings.json` and `.mcp.json` and the removal of
    `.claude/hooks/guardrail.pl`, linking `guardrail.md`;
  - the include line rewritten in place, and that the `.mcp.json` `.gitignore` line is no longer
    needed;
  - the `AGENTS.md`/`CLAUDE.md` writes.
- **Done**: the doc done-line.

### D6-2 [Warning, fix] The README Quick Start is silent on agents-file writes, backups and the `CLAUDE.md` refusal
- **Where**: `README.md:17`, `:25-28` (anchor "The last two lines of the recipe write outside the
  project"), `:63-68`; `docs/install-reference.md:157-172` (Refusals). All are DOC cites.
  (DOC W2, DOC N1)
- **Fix**:
  - Say what the install writes in the project root and in the home directory, including
    `backup.AGENTS.md`.
  - Add the `CLAUDE.md` own-content refusal and the marker-pair refusal to Refusals, each with its
    remedy.
  - State what the first run and the second run of the recipe each do.
  - Add one sentence on where the plugin lands, `adjagent:<name>`, and the reload.
- **Done**: the doc done-line.

### D6-3 [Warning, fix] `docs/agents-file.md` corrections
- **Where**: `docs/agents-file.md`. All line numbers are DOC cites, and the edits apply bottom-up.
  (DOC W3, W4, W9, N2, N3)
- **Fix**:
  - `:76-87`: reorder the Limit snippet as follows: discard or commit the install difference, clear
    the flag, pull, re-run the install, set the flag.
  - `:56-59`: change to "rewritten when its content differs".
  - `:56`: link to SPEC rather than restating it.
  - `:50-51` (anchor "is never read"): change to "the install neither reads nor writes the project's
    `CLAUDE.md`".
  - `:3-8`: add a caveat that the global file names `adjagent:` definitions, which resolve only
    where the plugin loads.
- **Done**: the doc done-line.

### D6-4 [Warning, fix] `docs/guardrail.md` corrections
- **Where**: `docs/guardrail.md`. All line numbers are DOC cites, and the edits apply bottom-up.
  (DOC W5, W6, W7)
- **Fix**:
  - `:44-48` and `:30-31`: a stranded project entry prints "no readable script" with the old path,
    and the remedy is to delete that entry.
  - `:33-37`: the `.mcp.json` cleanup does not depend on the hook.
  - `:18` (anchor "while the harness directory holds the kbase skill's"): the kb signal is under
    ROOT for claude.
- **Done**: the doc done-line.

### D6-5 [Warning, fix] Plugin-load failures the user cannot diagnose
- **Where**: `docs/install-reference.md:52-55` (DOC cite). (DOC W11)
- **Fix**: add a symptom-and-remedy block covering:
  - managed settings that skip skills-directory plugins;
  - per-server approval for the plugin's `kbase`;
  - the `/plugin` Errors tab.

  Link https://code.claude.com/docs/en/plugins/loading.
- **Done**: the doc done-line.

### D6-6 [Note, fix] Smaller docs wording fixes
- `docs/install-reference.md:129-131` and `README.md:81`: dry-run paths can be absolute. (DOC W8)
- `docs/install-reference.md:95-97`: the antecedent of "names and paths inside the plugin are
  unchanged" is missing. At `:23-25`, `--subdir` under claude places the plugin at
  `<DIR>/skills/adjagent`. (DOC N9)
- `docs/development.md:63-66`: define "install's root". (DOC N9)
- `docs/knowledge-base.md:10`: delete "; a plain mage install without a kbase source refuses
  instead". No kbase source exists any more, and mage always includes kb. (DOC N8)
- All line numbers are DOC cites, and the edits apply bottom-up within each file.
- **Done**: the doc done-line.

---

## Release (outside D6)

### D6-7 [Warning, fix — at release] The README pins `v0.13.1`
- **Where**: `README.md:33`, `:48`, `:99` and `:109` (DOC cite). (DOC W10)
- **Fix**: bump the pins to the release tag, as release step 1 in `docs/development.md` requires.
- **Done**: `just check-links`.

---

## Deferred → ROADMAP

### DEF-1 [defer → ROADMAP] Split `install.py` into modules
- AR W1. The JSON text editor (`install.py:444-755`), the settings merge and retired-entry removal
  (`:758-853`, `:887-1025`) and the runner line (`:1028-1177`) would move into their own modules.
- This is a code move, too wide for hardening.

### DEF-2 [defer → ROADMAP] Shared predicates for the decisions `install` and `_install_managed_paths` both make
- AR W2. The guardrail, the MCP base and the retiring decisions (`install.py:1316`, `:1334-1355`
  against `:1504-1515`) would each become a helper both functions call.

### DEF-3 [defer → ROADMAP] Move retired entries onto `GuardrailHook` and `McpSettings`, and delete `Replacement`
- AR W3, without the rename that D2-3 already makes.
- Where: `harness.py:120-175` (`Replacement` through `Harness.retired_entries`) and
  `claude.py:157-174`.

### DEF-4 [defer → ROADMAP] State the minimum Claude Code version for skills-directory plugins
- DOC W10, second half. The version has not been established from any source yet.

### DEF-5 [defer → ROADMAP] Give the kbase router's not-offered branch the plugin reload remedy
- PR 4. Under claude, the plugin's `kbase` tools appear after a fresh install only once the plugins
  are reloaded. The "A path" branch (`adjagent/definitions/kbase.py:79-81`) and
  `references/installing.md` (`kbase.py:520`) say only to restart or reconnect.
- The reload sentence D4-2 recommends names agents, not tools, so reusing `RELOAD_RULE` here would
  misdirect the model. This needs a new harness hole, which is wider than hardening.
