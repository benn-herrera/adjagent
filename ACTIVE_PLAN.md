# ACTIVE PLAN: quick ROADMAP fixes

Base commit: `eedcd52` (branch `develop`). Item numbers are `ROADMAP.md`'s at that commit; each item
is named by its bold title as well, since numbers shift only when Q5 renumbers.

## Status

| Package | What | Rating | Lifetime | Runs on | State |
|---|---|---|---|---|---|
| Q1 | Guardrail scripts and tests: items 10, 13, 23, 24, 25; checks: items 30, 32 | mechanical | shipped | python-coder (sonnet) | done (4a22f36) |
| Q2 | Docs: items 14, 16, 17 (report only), 20 | mechanical | shipped | tech-writer (sonnet) | done (29efff5); item 17 ruled: every Must-see bullet stays |
| Q3 | Definition text: item 21 | mechanical | shipped | prompt-engineer (sonnet) | done |
| Q5 | One home for the decisions `install` and `_install_managed_paths` both make: item 5 | expert | shipped | python-coder (opus) | done |
| — | Plan review | — | — | prompt-engineer, architect | done |
| Q4 | Post-plan review | review | — | python-coder, tech-writer, prompt-engineer | not started |

Q1–Q3 are mechanical: every edit is enumerated below. Q5 is expert.

## Gates

From `PROJECT_DOCS/CONVENTIONS/planning-and-execution/the-gates.md`:
- **Edit gate:** `just test-changed <start>`, `<start>` the HEAD hash at dispatch, stated in the brief.
- **Checkpoint gate:** `just test`, then `just sweep-python`, once before each package's commit.
- A test failing on behaviour the package does not state it changes is a finding to report, never
  edited to pass.
- Packages run serially in this order: Q1, Q2, Q3, Q5, Q4.
- **ROADMAP.** Each package deletes the items it finishes, found by title, and does not renumber.
  Q5, the last to delete, also renumbers the whole list (`ROADMAP.md`, List conventions).
- **Render baselines.** A package with a render done-line runs `just render <pkg>-base` (and each
  `--harness=` variant it names) at its own start commit, before its first edit. It never diffs
  against a `reference-*` slot.

---

## Q1: Guardrail scripts and tests (python-coder)

Scope: `adjagent/harnesses/resources/claude/hooks/guardrail.pl`,
`adjagent/harnesses/resources/opencode/plugins/guardrail.ts`, `tests/guardrail_cases.json`,
`tests/test_guardrail.py`, `tests/test_adjagent.py`, `tests/test_clause_groups.py`, `ROADMAP.md`.
CONVENTIONS `guardrails-change-together.md` applies. No document changes: SPEC
`deployed-surfaces/shipped-files.md:75` refuses only a filter that "could match a record".

Every new case row carries the kb fixture of row 110 (`tests/guardrail_cases.json`), without which
neither script judges a Grep, Glob or `.index` search:
`"files": ["@harness@/skills/kbase/SKILL.md", "kb-root/a.md", "kb-root/.index/nodes.yaml"]`. Rows
omit `harness`, so they run on both. An expected pass is `"reason": null`; an expected refusal is row
110's `reason` string, copied.

- **Item 10, "The two guardrails handle a malformed filter glob differently".** Outcome: a Grep or
  Glob filter whose glob does not compile lets the call through in both guardrails, exit 0 and no
  stderr, so the search tool reports the real error.
  - Perl: `guardrail.pl:186` `my $re = glob_re($filter =~ s{.*/}{}sr);`. Wrap the call in `eval { }`
    and `return undef` when it yields no regex. Today the `die` reaches the outer `eval`, which exits 1
    with stderr (`guardrail.pl:254-256`).
  - TS: `guardrail.ts:163` `const re = globRegExp(filter.replace(/^.*\//s, ""))`. Wrap it in
    `try`/`catch` and `return null` in the `catch`.
  - Rows, expected pass: Grep `{"pattern": "claim", "path": "kb-root", "glob": "[z-a]"}`; Glob
    `{"pattern": "kb-root/[z-a]"}`.
- **Item 13, "Stated guardrail behaviours with no case row".** Rows:
  - `find kb-root -path '*/.index' -prune -o -name '*.md' -print`: pass.
  - `grep -r --exclude-dir .index foo kb-root`: pass.
  - Glob `{"pattern": "**/*.yaml", "path": "kb-root"}`: refused.
  - A harness whose result differs from the row is a finding to report.
- **Item 23, "One guardrail test never reaches the check it names".** In
  `test_guardrail_pl_passes_a_tool_other_than_bash` (`tests/test_guardrail.py:247`), stage the
  script with the signal:
  `root, cwd, staged, _ = _case_root(tmp_path / "root", {"command": "sed -i 's/a/b/' x.txt", "files": ["@harness@/skills/kbase/SKILL.md"]}, CLAUDE, _PERL_HOOK)`,
  then
  `_run_perl(_hook_input("Edit", {"command": "sed -i 's/a/b/' x.txt"}, cwd), project_dir=root, script=staged)`.
  The assertion stays `(0, "")`.
- **Item 24, "`_OPENCODE_TOOLS` names the wrong side".** Rename `_OPENCODE_TOOLS` to
  `_CLAUDE_TO_OPENCODE_TOOLS`. `git grep -n _OPENCODE_TOOLS -- tests` at `eedcd52` lists
  `tests/test_guardrail.py:46, :68, :72, :198, :207`, every site.
- **Item 25, "A guardrail test re-derives the staged script's path by directory depth".**
  `tests/test_guardrail.py:114` `script.relative_to(script.parents[1])` becomes
  `script.relative_to(_RESOURCES / harness.name)`. `_RESOURCES` is
  `PACKAGE_ROOT / HARNESS_RESOURCES_SOURCE` (`tests/test_guardrail.py:34`). The harness names are
  `claude` and `opencode`, the same as the directories under `adjagent/harnesses/resources/`.
- **Item 30, "The double-delivery check follows `@` lines one level deep only".** `_loaded`
  (`tests/test_adjagent.py:1326`) also follows the `@` lines of each output it reaches whose `loads`
  is true, transitively. It returns each output once, in first-reached order, and never returns the
  output it was called with, so a cycle terminates. Signature unchanged; one caller, `:1323`. Add two
  tests that build `_PromptOutput`s directly (`loads=True`, `roots=()`, `path` `commands/<x>.md`):
  - a chain a→b→c, for which `_loaded(a, [a, b, c])` is `[b, c]`;
  - a cycle a→b→a, for which `_loaded(a, [a, b])` is `[b]`.

  If `test_no_prompt_delivers_a_span_twice` then fails on a shipped definition, report it; do not
  edit definitions.
- **Item 32, "Exemption reasons quote definition text that nothing checks".** In
  `tests/test_clause_groups.py`, add `check_exemption_quotes(exemptions, sources) -> list[str]`, where
  `sources` maps a module file name (`shell_dsl_coder.py`) to its text. `check_clause_groups` is
  unchanged. For each quote matching `(\w+\.py) \("(.+?)"\)` in a reason:
  - a module absent from `sources` gives one message;
  - otherwise the quote splits on ` ... `, and each fragment must occur in the module's text after
    `" ".join(text.split())`; each fragment that does not gives one message.

  Each message names the definition, the clause and the fragment or module. Add these tests:
  - real data: `sources` from `_DEFINITIONS.glob("*.py")`, expecting `[]`;
  - a fixture whose fragment is absent, expecting one message;
  - a fixture whose fragment spans a line break in the source, expecting `[]`.

  The real-data case at `eedcd52`: running that regex and split over `EXEMPTIONS` finds 9 fragments
  in 5 reasons, and every one occurs in its module after the collapse.

**Done:** checkpoint gate passes; `git grep -n _OPENCODE_TOOLS -- tests` is empty; items 10, 13, 23,
24, 25, 30 and 32 deleted from `ROADMAP.md`.

## Q2: Docs (tech-writer)

Scope: the files named below and `ROADMAP.md`. Do not reflow text around the edits.

- **Item 14, "ARCHITECTURE retells the kbase skill's text".** In
  `PROJECT_DOCS/ARCHITECTURE/subsystem-map.md`, lines 11–20 stay as they are. Replace lines 21–49,
  from "The skill and its references are project-portable" through "each running `kbase` from
  `PATH`.", with:

  ```
    The skill and its references are project-portable — per-project facts live in the consuming
    project's `kb-root/AGENTS.md`, under every harness. The set reaches kbase, the executable the user
    installs (no install writes it), only through the harness's `kbase` MCP server, offered under that
    harness's `mcp_tool_prefix`. The minimum version and the formula are written once, as
    `KBASE_MIN_VERSION` and `KBASE_TAP_FORMULA` in `kbase.py`, and filled into the router and
    `installing.md`. `clauses.KB_RUNNER_TARGETS` goes to the maintaining reference. The consumer's
    runner targets are the `kb-`-prefixed recipes of this repository's
    `adjagent/kb-tools/runner-snippets/kb.just` and `kb.mk`, prefixed so they cannot collide with a
    consuming project's own targets. What the router and each reference tell the session is
    `adjagent/definitions/kbase.py`'s text.
  ```
- **Item 16, "`_venv` breaks the three-line recipe rule".** In
  `PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/long-recipe-bodies-are-scripts.md`, after
  "moving it to a script buys only indirection." (lines 3–4), insert: "A recipe in a single-purpose
  runner file the justfile imports, such as `python.just`'s `_venv`, is already broken out of the
  justfile and stays where it is, whatever its length."
- **Item 17, "Must-see lists repeat boundary boilerplate".** Report only; edit nothing. For each
  Must-see bullet of `PROJECT_DOCS/SPEC/entry-point.md`, `PROJECT_DOCS/ARCHITECTURE/entry-point.md`
  and `PROJECT_DOCS/CONVENTIONS/entry-point.md`, give one line: the file, the bullet, keep or cut, and
  a one-clause reason. Item 17 stays in `ROADMAP.md`.
- **Item 20, "SPEC names a code constant".** Two replacements:
  - `PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md:10-14`, from "`SHIPPED_PACKAGES` is the
    table of those" through "It holds one row, the **docdicer tools package**," becomes "Every install
    delivers a set of shipped packages by explicit mapping, each to a destination under the install
    ROOT stated for that package — inside a skill's own directory and so inside the `skills/` surface.
    The set holds one package, the **docdicer tools package**,".
  - `PROJECT_DOCS/SPEC/deployed-surfaces/base-and-kb-installs.md:5-6`, "delivers each package
    `SHIPPED_PACKAGES` names (Deployed Surfaces, below) to its destination there:\nthe docdicer tools
    package, inside" becomes "delivers the docdicer tools package (Deployed Surfaces, below) to its
    destination there, inside".
  - ARCHITECTURE already names the constant (`packaging.md:15`,
    `install-consumption-model/base-and-kb-installs.md:29`) and stays as it is.

**Done:** `just test` passes (it includes the link check); items 14, 16 and 20 deleted from
`ROADMAP.md`; item 17's report returned.

## Q3: Definition text (prompt-engineer)

Scope: `adjagent/definitions/kbase.py`, `ROADMAP.md`.

- **Item 21, "The kbase router's KB probe does not name its form".** In `kbase.py:37-38`, the
  sentence "Each probe tests only that `.index/` exists, never what it holds." becomes "Each probe
  tests only that `.index/` exists, never what it holds: run it as
  `test -f <dir>/entry-point.md && test -d <dir>/.index`, `<dir>` being `./kb-root` or `.`, since a
  Glob or Read of `.index/` can be refused." Wrap at the paragraph's existing width. The guardrail
  passes `test -f` and `test -d` (`guardrail.pl` `shell_index_reason`; case row
  `test -d kb-root/.index`).

**Done:** `just test` passes; `just render q3-base` before the first edit and `just render q3`
after; `just render-diff q3-base q3` lists one pair, `skills/adjagent/skills/kbase/SKILL.md`, whose
`diff -u` changes only that paragraph; item 21 deleted from `ROADMAP.md`.

## Q5: One home for the shared install decisions (python-coder, expert)

Scope: `adjagent/install.py`, `tests/test_adjagent_install.py`,
`PROJECT_DOCS/ARCHITECTURE/install-consumption-model/renders-and-copies.md` (the managed-set bullet,
`:86`), `ROADMAP.md`.

`_install_managed_paths` keeps its name and signature. `git grep -n _install_managed_paths` at
`eedcd52` returns `adjagent/install.py:1459, :1553`, `adjagent/preflight.py:5`,
`PROJECT_DOCS/ARCHITECTURE/agents-file.md:37` and `renders-and-copies.md:82, :86`.

**Fact.** `_install_managed_paths` (`install.py:1459`) lists every path an install may read or write
before the run. It re-derives, in its own words, decisions that `install` (`install.py:1260`) makes:

| Decision | in `install` | in `_install_managed_paths` |
|---|---|---|
| guardrail in play | `:1313` `guardrail = None if user_level else ctx.harness.guardrail`; narrowed by the probe, `:1331` `registers_guardrail = guardrail is not None and guardrail_skipped is None`, and at script removal `:1436` | `:1489` `if harness.guardrail is not None and not user_level:` |
| MCP settings file's base | `:1294` `mcp_base = project if ctx.harness.mcp.site is McpSite.PROJECT else root`; `:1362` `real_mcp_base` is the same decision on the real paths | `:1494-1497` `if harness.mcp.site is McpSite.HARNESS: under_root += mcp_paths` / `elif not user_level: under_project += mcp_paths` |
| MCP write | `:1314` `writes_mcp = kb_included and (not user_level or ctx.harness.mcp.site is McpSite.HARNESS)` | the same `:1494-1497` |
| runner files | `:1315` `writes_include_line = kb_included and not user_level and not ctx.harness.is_standalone_plugin` | `:1498-1499` `if not user_level:` … `_JUSTFILE_NAMES, *_MAKEFILE_NAMES` |
| retired entries | `:1334` `retiring = [] if user_level else [entry for entry in ctx.harness.retired_entries if replaced[entry.replacement]]` | `:1500` every `entry.settings`, under `not user_level` |
| agents file, block current | already shared: `_installs_agents_file`, `_keeps_the_block_current` | same |

Out of scope: package destinations (`:1310`/`:1481`), resource copies (`:1312`/`:1486`) and retired
package destinations (`:1316-1320`/`:1482`). Each is a bare `user_level` or `plugin_dir` test in
`install` against a list `_install_managed_paths` gives unconditionally, and there is no decision
to share.

**Outcome.**
- Each in-scope decision is one named function both call, as the last row already is.
- Each takes only what both know before the run: the harness, `user_level` and, for the base, the
  two candidate paths. `_install_managed_paths` calls it bare.
- `install` adds at its own call, once each, what only it knows: `kb_included`, the probe result and
  the `replaced` filter.
- The MCP base is chosen in one place, which `:1294`, `:1362` and `_install_managed_paths` all use.
- The runner-files function includes `is_standalone_plugin`, so a standalone-plugin install stops
  listing runner files. Update the managed-set bullet in `renders-and-copies.md:86` to match. No
  other managed path changes.
- The docstring of `_install_managed_paths` shrinks to what the functions' names and docstrings do
  not say.

**Tests.** The dry-run prediction tests (`_assert_dry_run_predicts`,
`tests/test_adjagent_install.py:2185`) hold the managed set against the install
(`renders-and-copies.md:82-84`). Their only user-level case (`:2319`) installs without the kb set,
so the MCP and retired-entry decisions go unexercised at user level. Add a user-level `--with-kb`
case for claude and for opencode through `_assert_dry_run_predicts`, building home as
`_user_level_with_global_agents_file` does. Mage has no absolute user directory, so it has no
user-level case. Existing tests pass unchanged.

**Done:**
- Before the first edit, record the `install.py` candidates `just sweep-python` lists, then render
  `just render q5-base`, `just render q5-base-opencode --harness=opencode` and
  `just render q5-base-mage --harness=mage`.
- After the change, the checkpoint gate passes, and its `just sweep-python` lists no `install.py`
  candidate absent from that record.
- After the change, render `q5`, `q5-opencode` and `q5-mage` the same way. `just render-diff q5-base q5`,
  `just render-diff q5-base-opencode q5-opencode` and `just render-diff q5-base-mage q5-mage` each
  list no pair but an `AGENTS.md` whose only difference is the slot name in its heading.
- Item 5 deleted from `ROADMAP.md`, and the list renumbered.

## Q4: Post-plan review

Reviewers by what changed: `python-coder` (guardrail scripts, tests, `install.py`), `tech-writer`
(docs), `prompt-engineer` (the kbase skill text). Each gets the contract documents and
`git diff eedcd52..HEAD`, not this plan. Findings go to `ACTIVE_PLAN_REVIEW_BURNDOWN.md`, which
gets one `prompt-engineer` review and revision by its author before any fix is dispatched.

## Landing

Delete this plan and its burndown list.
