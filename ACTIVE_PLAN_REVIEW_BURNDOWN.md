# Review burndown — adjagent 0.12.7

Merged from the post-sprint review reports in `.claude-temp/review/`: `architect.md` (A), `python-coder.md` (P),
`generalist-coder.md` (G), `tech-writer.md` (T). Duplicates are merged into one item that cites each source.

Every 0.12.7 item was re-checked against the tree at `b4eec3e` plus the working tree. The cited line holds the
claimed text in each case, and no 0.12.7 candidate was dropped.

Dispositions:
- **0.12.7**: small, low-risk fixes in this release.
- **0.12.8**: larger or behaviour-changing work, picked up with the packaging release.
- **won't-fix**: not acted on, for the stated reason.
- **out of scope**: local development tooling, not part of the release.

---

## 0.12.7

### R1. Warning: guardrail header comments overstate the `.index/` scope
- **Where:** `adjagent/harnesses/resources/claude/hooks/guardrail.pl:6`, `adjagent/harnesses/resources/opencode/plugins/guardrail.ts:5`
- **Finding:** both headers say the hook "keeps every call out of kb-root/.index/". The documented scope is narrower:
  - file-tool calls on a path in `kb-root/.index/`;
  - shell words that name such a path;
  - recursive searches, Grep and Glob rooted in `kb-root/`.

  The documented scope is in ARCHITECTURE *Guardrail hook* and SPEC *Shipped files*, `PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md:44-50`. A search rooted above `kb-root/`, or a path reached through `cd`, passes.
- **Fix:** comment only, no code change. Replace the line in both files (behind `#` or `//`) with this exact text: `On a kb install, also refuses a call that names a path in kb-root/.index/ or searches from kb-root/ without excluding it.`
- **Sources:** G W1, G W2.

### R2. Warning: TEST_SURFACE_MAP selects nothing for `kb-tools/`
- **Where:** `justfile:156-167`
- **Finding:** `tests/test_adjagent_install.py:416` and `:436` read `kb-tools/runner-snippets/kb.just`, but no map row covers `kb-tools/`. A change there makes `just test-changed` report nothing to run.
- **Fix:** add the row `kb-tools/ adjagent`. Because the edit touches `justfile`, it selects every surface and so validates itself.
- **Sources:** G W8.

### R3. Warning: README describes `just test` as it was before the docs surface
- **Where:** `README.md:479-480`, `README.md:549-551`
- **Finding:** README says `just test` runs "the `adjagent` and `dupe_sweep` surfaces". It now also runs the `docs` surface, the link and tree check `just check-links`: see `devtools/scripts/test.sh:15-17` and `:79-81`. Separately, Third Party Acknowledgements lists `pytest`, `black` and `isort` but not `flake8`, which `python.just:22` also installs.
- **Fix:**
  - Name all three surfaces and `just check-links`.
  - Add `flake8` to the `pytest`, `black` and `isort` list at `README.md:549-551`. Those entries carry no owner or license, so neither does this one.
- **Sources:** A W6, T W2. The docdicer half of T W2 is in O1.

### R4. Warning: the docs tree and the docs gate are absent from the layout and convention docs
- **Where:**
  - `PROJECT_DOCS/ARCHITECTURE/repo-layout.md`
  - README `### Repository Layout` (`README.md:417`)
  - `PROJECT_DOCS/CONVENTIONS/project-documents.md`
  - `PROJECT_DOCS/CONVENTIONS/planning-and-execution/the-gate-after-a-change.md:3-5`
- **Finding:**
  - Neither layout listing has `PROJECT_DOCS/`, the root pointer files, `devtools/scripts/` or `agent-sandboxing/`. `agent-sandboxing/` exists at the root.
  - The project-documents convention tells a contributor to add a leaf to two Contents lists. It does not say that `just check-links` checks this, or that `just test` and `just test-changed` (the `docs` surface for `PROJECT_DOCS/` and top-level `*.md`) run that check.
  - The gate leaf does not name the `docs` surface.
- **Fix:**
  - Add `PROJECT_DOCS/` (the contract trees, one `entry-point.md` per volume, root `*.md` as pointers), `devtools/scripts/` and `agent-sandboxing/` to both listings.
  - Add one sentence to *Project Documents* naming `just check-links` and what it verifies.
  - Name the `docs` surface in the gate leaf.
- **Sources:** A W6, T W6 (layout half), T W7.

### R5. Warning: two citations point to a "version bullet" that no longer exists
- **Where:** `README.md:497`, `PROJECT_DOCS/ARCHITECTURE/why-there-is-no-verification-verb.md:22`
- **Finding:** both cite "CONVENTIONS.md, the version bullet". That bullet is now the leaf *Version has one home*. README release step 1 also never says what to bump.
- **Fix:**
  - Cite "CONVENTIONS.md, Version has one home" in both places.
  - README step 1: "bump `__version__` in `adjagent/__init__.py`".
- **Sources:** T W3.

### R6. Warning: the release tag is described as lightweight
- **Where:** `PROJECT_DOCS/ARCHITECTURE/sanctioned-invocation.md:16`, `devtools/scripts/tag.sh:6`
- **Finding:** both say `just tag` creates a lightweight tag. `tag.sh:33` runs `git tag -s "${tag}" -m…`, which makes a signed annotated tag, and `:34` verifies it.
- **Fix:**
  - `sanctioned-invocation.md:16`: change "the lightweight tag" to "the signed annotated tag".
  - `tag.sh:6-7`: replace both lines with exactly:
    ```
    # `__version__` in `adjagent/__init__.py` holding the one copy. The tag is signed and annotated
    # (`git tag -s`), so it needs a gpg secret key and a TTY, and nothing is pushed: the operator pushes.
    ```
  - README: in the release step that runs `just tag`, state that it needs a gpg secret key and a TTY.
- **Sources:** T W4.

### R7. Warning: README names the wrong scratch directory for opencode
- **Where:** `README.md:140-141`
- **Finding:** "Writes into `.claude-temp/` and `test-data/transient` are allowed" is stated for both harnesses. opencode's guardrail allows `.opencode-temp`, not `.claude-temp/` (`guardrail.ts:15`).
- **Fix:** give the scratch directory per harness.
- **Sources:** T W5.

### R8. Warning: a guardrail case that runs under neither implementation passes silently
- **Where:** `tests/test_guardrail.py:193-201`
- **Finding:** a case can pass the field check yet sit in neither `_PL_INDEXES` nor `_TS_INDEXES`, so it never runs. Two examples: `harness: opencode` with `NotebookEdit`, and `harness: claude` with `patch`.
- **Fix:** add one line to the loop: `assert i in _PL_INDEXES or i in _TS_INDEXES, i`.
- **Sources:** P W2.

### R9. Warning: no case pins which refusal wins when both checks fire
- **Where:** `tests/guardrail_cases.json`, in the `.index/` block
- **Finding:** ARCHITECTURE *Guardrail hook* says the `.index/` refusal is reported when both checks would refuse. Both implementations do this today (`guardrail.pl:250`; `guardrail.ts:223-224`), but no case pins it.
- **Fix:** add one row: `{"command": "echo x > kb-root/.index/nodes.yaml", "files": ["@harness@/skills/kbase/SKILL.md", "kb-root/.index/nodes.yaml"], "reason": "kb-root/.index/ holds kbase's records: read them with kbase's `query` tool and change them with its `write` tool"}`.
- **Sources:** P W3, G W4 (precedence half).

### R10. Note: ARCHITECTURE lists an incomplete set of kb runner targets
- **Where:** `PROJECT_DOCS/ARCHITECTURE/subsystem-map.md:48`
- **Finding:** the leaf lists `kb-verify`, `kb-update-format` and `kb-stats`. The snippets also define `kb-help`, `kb-init`, `kb-score` and `kb-export-latex` (`kb-tools/runner-snippets/kb.just:31-55`, `kb.mk:24-30`).
- **Fix:** replace lines 47-49 with exactly:
  ```
    `kb-stats`, run only on the user's direction. The consumer's runner targets are the `kb-`-prefixed
    recipes of this repository's `kb-tools/runner-snippets/kb.just` and `kb.mk`, prefixed so they cannot
    collide with a consuming project's own targets, each running `kbase` from `PATH`.
  ```
  The list on lines 46-47 (`kb-update-format`, `kb-verify`, `kb-stats`) stays. It restates `KB_RUNNER_TARGETS`, which names exactly those three, and the replacement does not cover it.
- **Sources:** A W7 (stale-list half; the restructure is S6).

### R11. Note: SPEC states the existence-check exemption too broadly
- **Where:** `PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md:46`
- **Finding:** SPEC says "existence checks (`test`, `[`, `stat`) excepted". The code exempts only `stat`, and `test`/`[` with `-e`, `-d` or `-f` (`guardrail.pl:199`, `guardrail.ts:175`). `test -r` on a record is refused.
- **Fix:** "existence checks (`stat`, and `test` or `[` with `-e`, `-d` or `-f`) excepted".
- **Sources:** T N2.

### R12. Note: SPEC states guardrail parity as a runtime fact
- **Where:** `PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md:35`
- **Finding:** "Both guardrails block the same calls" reads as a description of what both do today, yet a known divergence exists (S2). SPEC should state the requirement, and stay free of test-suite structure: the case-table fact already lives in CONVENTIONS *Guardrails change together*.
- **Fix:** replace line 35 with exactly:
  ```
  guardrails are to block the same calls but one spelling, which only the claude guardrail reads: a path word
  ```
  Lines 34 and 36 are unchanged, so the `$CLAUDE_PROJECT_DIR` exception stays as written.
- **Sources:** T N3(a).

### R13. Note: two test docstrings say "every Bash call"
- **Where:** `tests/test_guardrail.py:275`, `tests/test_adjagent_install.py:1581`
- **Finding:** both say perl's exit 2 "would block every Bash call". The matcher now also names the file tools.
- **Fix:** "every call the matcher names".
- **Sources:** A N7.

### R14. Note: root pointer files call PROJECT_DOCS "the project KB"
- **Where:** `SPEC.md:3`, `ARCHITECTURE.md:3`, `CONVENTIONS.md:3`, `THESIS.md:3`
- **Finding:** each says the document "now lives in the project KB". In this repository "KB" means a kbase knowledge base.
- **Fix:** "lives under `PROJECT_DOCS/`: start at …".
- **Who:** the user makes this edit; it is excluded from both dispatches. CONVENTIONS *Project Documents* forbids agents editing root pointer files.
- **Sources:** A N8, T N5.

### R15. Note: one line in claude.py exceeds the formatter width
- **Where:** `adjagent/harnesses/claude.py:75`
- **Finding:** the line is 121 columns; black is set to 120.
- **Fix:** `just format-python adjagent/harnesses/claude.py`.
- **Sources:** P N4.

### R16. Note: two recipes use two-space indentation
- **Where:** `justfile:177-178` (`install-agents-here`), `kb-tools/runner-snippets/kb.just:52` (`kb-score`)
- **Finding:** these bodies are indented 2 spaces; every other recipe uses 4.
- **Fix:** use 4 spaces.
- **Sources:** G N3.

### R17. Note: heading and spacing inconsistencies in the docs tree
- **Where:**
  - `PROJECT_DOCS/CONVENTIONS/section-and-rule-heading-brevity.md:1`
  - `PROJECT_DOCS/CONVENTIONS/entry-point.md:53`
  - `PROJECT_DOCS/ARCHITECTURE/entry-point.md:5-6`
  - `PROJECT_DOCS/SPEC/entry-point.md:13-14`
- **Finding:**
  - The brevity leaf uses `###` where its top-level sibling `project-documents.md` uses `##`.
  - The entry-point link text "Section and Rule Heading Brevity" does not match the heading's case.
  - ARCHITECTURE's entry point has no blank line after "Must-see:".
  - SPEC's entry point has a double blank line before "Contents:".
- **Fix:** use `##`, and make the link text match the heading. In both entry points, put one blank line after `Must-see:` and one before `Contents:`, as `CONVENTIONS/entry-point.md` has.
- **Sources:** T N4 (part), T N8.

### R18. Note: README examples pin an old release tag
- **Where:** `README.md:186`, `README.md:203`
- **Finding:** the `AGENTS_VER` examples use `v0.12.5`.
- **Fix:** use `v0.12.7`.
- **Sources:** T N7 (part).

### 0.12.7 dispatch split

**python-coder:** R1, R2, R6 (the `tag.sh` comment), R8, R9, R13, R15, R16.
- Done when `just test-changed` passes. The justfile edit selects every surface.

**tech-writer:** R3, R4, R5, R6 (`sanctioned-invocation.md:16` and README), R7, R10, R11, R12, R17, R18.
- Done when `just check-links` passes.

**Neither dispatch:** R14, which the user makes.

---

## 0.12.8

### S1. Warning: verify opencode tool names against v2.2.3
- **Where:** `guardrail.ts:12`, `guardrail.ts:197-210`, `tests/test_guardrail.py:44-54`
- **Finding:** it is unverified which tool names reach `execute.before`. Open questions:
  - `patch` versus `apply_patch`: only `patch` is matched.
  - a `list` tool taking `path`: not handled.
  - the `shell` alias: accepted but never sent by the runner.
- **Fix:** probe opencode v2.2.3. Accept every name the hook receives, add `list` to the single-path cases if it reaches the hook, and add case rows for each.
- **Sources:** A W4, P (seen, not acted on).

### S2. Warning: the two guardrails handle a malformed filter glob differently
- **Where:** `guardrail.pl:166`/`:186`, `guardrail.ts:147`/`:163`
- **Finding:** Grep `glob: "[z-a]"` under `kb-root`: Perl fails open (exit 1), while TS throws a block without the `Blocked:` prefix.
- **Fix:** both treat a filter whose regex does not compile as no filter, which gives the search refusal. Add the case.
- **Sources:** G W3.

### S3. Warning: nothing checks that the kbase names the skill cites exist
- **Where:** `adjagent/definitions/kbase.py` (every `kbase://` URI, tool and op it names); `PROJECT_DOCS/CONVENTIONS/adding-definitions/skill-references-omit-offered-surface.md:9-11`
- **Finding:** nothing checks those names against kbase's offered surface. "Re-read on a `KBASE_MIN_VERSION` change" relies on someone remembering.
- **Fix:** add a test that runs `kbase mcp` (`initialize`, `tools/list`, `resources/list`) and asserts every name the skill cites is offered. It fails, not skips, without `kbase`, the same way the `bun` requirement works.
- **Sources:** A W3, P (seen, not acted on).

### S4. Warning: the guardrails hard-code kbase's private record names
- **Where:** `guardrail.pl:23`, `:186-187`; `guardrail.ts:22`, `:162-165`
- **Finding:** the Grep/Glob judgement depends on kbase's private record file names (`nodes.yaml`, `edges.yaml`, `format.yaml`). A record file added by a later kbase would pass silently.
- **Fix:** pass a Grep/Glob rooted in `kb-root/` only when its filter's last segment ends in the literal `.md`, and drop both record lists. This is a behaviour change: edit both scripts and the case table together.
- **Sources:** A W5.

### S5. Warning: more stated guardrail behaviours have no case
- **Where:** `tests/guardrail_cases.json`, beside the `--exclude-dir=.index` and `-g` rows
- **Finding:** three behaviours have no case:
  - `find kb-root -path '*/.index' -prune …`, an exclusion the refusal message itself recommends;
  - `grep -r --exclude-dir .index …`, the space form;
  - the Glob search root built from `path` plus the pattern's literal segments (`{pattern:"**/*.yaml", path:"kb-root"}`, refused).
- **Fix:** add the three rows.
- **Sources:** G W4 (remainder).

### S6. Warning: ARCHITECTURE retells the kbase skill's text
- **Where:** `PROJECT_DOCS/ARCHITECTURE/subsystem-map.md:25-50`
- **Finding:** the leaf retells the router and `installing.md` behaviour, and `KB_RUNNER_TARGETS`'s sentence. That is a second home for definition prose.
- **Fix:** keep the mechanism only: the constants, which clause goes to which reference, and the route→reference map. Cite `adjagent/definitions/kbase.py` for the content.
- **Sources:** A W7.

### S7. Warning: how a work contributes to strength is stated three times in one reference
- **Where:** `adjagent/clauses.py:449`; `adjagent/definitions/kbase.py:146-153`, `:198-206`, `:478-482`
- **Finding:** the rendered `reading.md` states the contribution and pending rule three times. The *how the scoring system works* route only links out.
- **Fix:**
  - Keep the clause's statement and cut `reading.md:198-206` down to the reading actions.
  - Make reading.md's *Claim rigor and strength* the one scoring explanation, and decide whether `scoring-system.md` points into it.
- **Sources:** A W8.

### S8. Note: reading.md restates the server's rule on rigor values
- **Where:** `adjagent/definitions/kbase.py:227-229`
- **Finding:** reading.md's third constraint restates the server's rule on supplying rigor values.
- **Fix:** keep only the routing it alone carries (`score` grades; `references/maintaining.md` writes).
- **Sources:** P N5.

### S9. Warning: README links land on root pointer stubs
- **Where:** `README.md:108`, `401`, `415`, `442`, `449-450`, `488`, `497`; link text at `545`
- **Finding:** these links go to the root pointer files, which are stubs.
- **Fix:** link each to the volume entry point or leaf it cites.
- **Sources:** T W6 (link half).

### S10. Warning: `_venv` breaks the three-line recipe rule as written
- **Where:** `python.just` `_venv`, against `PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/long-recipe-bodies-are-scripts.md`
- **Finding:** `_venv` is a shebang body of about six commands, while the rule says a body over three lines is a script.
- **Fix:** choose one: state a shebang-recipe exemption in the rule, or move the body to `devtools/scripts/`.
- **Sources:** T W9.

### S11. Note: README opening and section names
- **Where:** README opening and top-level sections
- **Finding:** the opening runs three sentences against the two-sentence convention, and the sections are named Developer/Usage/Development rather than Requirements and Quick Start.
- **Fix:** restructure.
- **Sources:** T N7 (remainder).

### S12. Note: Must-see lists repeat boundary boilerplate
- **Where:** the SPEC, ARCHITECTURE and CONVENTIONS `entry-point.md` files
- **Finding:** the Must-see lists mostly repeat the same boundary bullets.
- **Fix:** keep content that would hurt to miss.
- **Sources:** T N1.

### S13. Note: the claude matcher runs perl on every file-tool call on base installs
- **Where:** `adjagent/harnesses/claude.py:154`
- **Finding:** base installs spawn perl on every file-tool call, and the call always passes. Kb installation is sticky, so the matcher could be conditioned on it.
- **Fix:** measure perl startup per call first. Narrow the matcher to `Bash` on base installs only if that cost matters.
- **Sources:** A N5.

### S14. Note: the guardrail's behaviour is restated in four documents
- **Where:** SPEC *Shipped files*, ARCHITECTURE *Guardrail hook*, CONVENTIONS *Guardrails change together*, README §Guardrail
- **Finding:** the same behaviour is described in all four.
- **Fix:** ARCHITECTURE cites SPEC for what is blocked, and CONVENTIONS keeps only the process rules.
- **Sources:** A N6.

### S15. Note: SPEC names a code constant
- **Where:** `PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md:10-13`
- **Finding:** SPEC names `SHIPPED_PACKAGES`, against its entry point's "no code structure" rule.
- **Fix:** state the outcome in SPEC and move the constant's name to ARCHITECTURE.
- **Sources:** A N9.

### S16. Note: the router's KB probe does not name its form
- **Where:** `adjagent/definitions/kbase.py:32-37`
- **Finding:** the probe does not say which form to use. A Glob or Read probe for `kb-root/.index` is refused; `test -d` passes.
- **Fix:** name `test -d` as the probe.
- **Sources:** A N10.

### S17. Note: mage has no guardrail
- **Where:** SPEC *Shipped files* ("mage ships none")
- **Finding:** a mage install is always a kb install, so its `.index/` protection rests on kbase's prose instruction alone.
- **Fix:** check whether mage's plugin format can carry a hook. If it cannot, record the gap in SPEC.
- **Sources:** A N11.

### S18. Note: one guardrail test duplicates a case-table row
- **Where:** `tests/test_guardrail.py:248`
- **Finding:** `test_guardrail_pl_passes_a_tool_other_than_bash` never reaches the mutation check: with no kb signal, the script exits before it.
- **Fix:** plant the kb signal so the test reaches the check, or delete it; the table row survives.
- **Sources:** P N1.

### S19. Note: `_OPENCODE_TOOLS` names the wrong side
- **Where:** `tests/test_guardrail.py:44`, `:70`, `:201`, `:208`
- **Finding:** `_OPENCODE_TOOLS` is used as the set of Claude tools.
- **Fix:** rename it, or bind `_CLAUDE_TOOLS` and use that.
- **Sources:** P N2.

### S20. Note: the test re-derives the staged script's path
- **Where:** `tests/test_guardrail.py:112`
- **Finding:** the staged path is derived from a directory depth.
- **Fix:** use `script.relative_to(HARNESS_RESOURCES_SOURCE / harness.name)`.
- **Sources:** P N3.

---

## won't-fix

### X1. Guardrail searches rooted above `kb-root/`, and `rg`/`tree`/`ls -R` refusals
- **Source:** G W1
- **Reason:** the hook is known to be imperfect and is not a boundary, so its behaviour does not change. R1 corrects the header comment.

### X2. `cd kb-root && …` is not tracked
- **Source:** G W2
- **Reason:** the same as X1.

### X3. `"$CLAUDE_PROJECT_DIR"/…` with the quote closed before `/` is not expanded
- **Source:** G N1
- **Reason:** this matches ARCHITECTURE *Guardrail hook* ("its surrounding quote stripped"), and the hook is not a boundary.

### X4. The maintaining reference's `commit` paragraph
- **Where:** `kbase.py:374-375`
- **Sources:** P W1, A W2
- **Reason:** the paragraph states the project's rule: the user decides, and `commit` is strongly encouraged. kbase's own instruction is to be worded as a recommendation upstream.

### X5. THESIS has no "Must-see:" section
- **Source:** T W1
- **Reason:** the rule covers subtree entry points. `PROJECT_DOCS/entry-point.md` is the primary entry point.

### X6. The `scoring-system.md` link to kbase `PROJECT_DOCS` returns 404 on kbase `main`
- **Source:** A C1
- **Reason:** this is a release-order dependency, not a defect: adjagent 0.12.7 ships after kbase 0.10.0 reaches `main`.

### X7. SPEC *Harness Agents File*, "install writes mage's agents file"
- **Source:** A W1
- **Reason:** there is no finding. The sentence is true: `just install` runs `devtools/scripts/install.sh`, and its line 92 runs `install-agents-file.sh` when the harness's user directory is relative (mage).

---

## out of scope

### O1. docdicer and the local docs tooling
This is local development tooling, not part of the release. The findings are recorded once here, for whoever takes up the docs tooling:
- **Unpinned install.** `python.just:22` installs docdicer from git HEAD. Pin it with `@v0.6.0`. (A C2, G W5)
- **Existing `.venv`.** A `.venv` built before docdicer was added never gains it, because `python.just:19` skips the install once the interpreter exists. (G W6)
- **Comment.** `python.just:12-14` claims every tool is pinned. (A C2)
- **README.** README does not say that the first venv build fetches docdicer from GitHub, and the acknowledgements omit docdicer (MIT). (T W2, docdicer half)
- **Dead map row.** `justfile:163` holds the row `devtools/dicer/ docs`, and `justfile:154-155` says "the dicer that runs it". The directory was removed in `0591ff6`. (A N1, G W7, T W8)
- **`dice-doc` / `dice-docs` recipes** (`justfile:91-98`):
  - CONVENTIONS *Project Documents* says the trees are never regenerated, so these recipes may no longer be needed. (A N2)
  - They pass arguments by textual interpolation rather than `"$@"`. (G W9)
  - Their doc strings lack `[dev]` and say `src-dir`/`work-dir` for the parameters `src`/`work`. (G N2)
- **`check-links` scope.** `check-links PROJECT_DOCS *.md` (`justfile:102`) also checks untracked top-level files. (A N3)
- **Unchecked structure.** Nothing checks these:
  - entry-point completeness for nested leaves (A N4);
  - leaf file name = title slug (T N3(b));
  - the slug rule for punctuation and code spans (T N4 remainder);
  - Must-see form limits (T N6).

---

## Summary

| Disposition | Count | Items |
| --- | --- | --- |
| 0.12.7 | 18 | R1–R18: 9 Warning, 9 Note |
| 0.12.8 | 20 | S1–S20 |
| won't-fix | 7 | X1–X7 |
| out of scope | 1 | O1, grouping 12 docdicer and docs-tooling findings |

The 0.12.7 list is all comments, documentation, test docstrings, one test assertion, one guardrail case row, one surface-map row and two formatting fixes. Nothing in it changes what ships to consumers.

- **R1:** guardrail header comments state the documented `.index/` scope.
- **R2:** add `kb-tools/ adjagent` to `TEST_SURFACE_MAP`.
- **R3:** README's `just test` surfaces and `flake8` acknowledgement.
- **R4:** `PROJECT_DOCS/`, `devtools/scripts/` and `agent-sandboxing/` in both layout listings, and the docs gate named in the conventions.
- **R5:** "the version bullet" becomes *Version has one home*, and README names `__version__`.
- **R6:** "lightweight tag" becomes signed annotated, with the gpg and TTY prerequisite.
- **R7:** per-harness scratch directory in README §Guardrail.
- **R8:** the case-table assertion that every case runs somewhere.
- **R9:** the refusal-precedence case row.
- **R10:** subsystem-map's incomplete kb target list.
- **R11:** SPEC's existence-check wording.
- **R12:** SPEC's guardrail-parity wording.
- **R13:** two stale "every Bash call" docstrings.
- **R14:** root pointer wording. The user makes this edit; it is in neither dispatch.
- **R15:** `claude.py:75` formatting.
- **R16:** two-space recipe indentation.
- **R17:** heading level and blank lines in the docs tree.
- **R18:** README's `AGENTS_VER` example tag.
