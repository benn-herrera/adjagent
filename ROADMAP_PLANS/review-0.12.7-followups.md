# Follow-ups from the 0.12.7 post-sprint review

Findings the 0.12.7 review raised and the release left for later. None is scheduled; each is picked
up by a later plan or dropped. Line numbers are as of the 0.12.7 release and may have moved.

## Open

### S1. Warning: verify opencode tool names against v2.2.3
- **Where:** `guardrail.ts:12`, `guardrail.ts:197-210`, `tests/test_guardrail.py:44-54`
- **Finding:** it is unverified which tool names reach `execute.before`. Open questions:
  - `patch` versus `apply_patch`: only `patch` is matched.
  - a `list` tool taking `path`: not handled.
  - the `shell` alias: accepted but never sent by the runner.
- **Fix:** probe opencode v2.2.3. Accept every name the hook receives, add `list` to the single-path cases if it reaches the hook, and add case rows for each.

### S2. Warning: the two guardrails handle a malformed filter glob differently
- **Where:** `guardrail.pl:166`/`:186`, `guardrail.ts:147`/`:163`
- **Finding:** Grep `glob: "[z-a]"` under `kb-root`: Perl fails open (exit 1), while TS throws a block without the `Blocked:` prefix.
- **Fix:** both treat a filter whose regex does not compile as no filter, which gives the search refusal. Add the case.

### S3. Warning: nothing checks that the kbase names the skill cites exist
- **Where:** `adjagent/definitions/kbase.py` (every `kbase://` URI, tool and op it names); `PROJECT_DOCS/CONVENTIONS/adding-definitions/skill-references-omit-offered-surface.md`
- **Finding:** nothing checks those names against kbase's offered surface. "Re-read on a `KBASE_MIN_VERSION` change" relies on someone remembering.
- **Fix:** add a test that runs `kbase mcp` (`initialize`, `tools/list`, `resources/list`) and asserts every name the skill cites is offered. It fails, not skips, without `kbase`, the same way the `bun` requirement works.

### S4. Warning: the guardrails hard-code kbase's private record names
- **Where:** `guardrail.pl:23`, `:186-187`; `guardrail.ts:22`, `:162-165`
- **Finding:** the Grep/Glob judgement depends on kbase's private record file names (`nodes.yaml`, `edges.yaml`, `format.yaml`). A record file added by a later kbase would pass silently.
- **Fix:** pass a Grep/Glob rooted in `kb-root/` only when its filter's last segment ends in the literal `.md`, and drop both record lists. A behaviour change: edit both scripts and the case table together.

### S5. Warning: more stated guardrail behaviours have no case
- **Where:** `tests/guardrail_cases.json`, beside the `--exclude-dir=.index` and `-g` rows
- **Finding:** three behaviours have no case:
  - `find kb-root -path '*/.index' -prune …`, an exclusion the refusal message itself recommends;
  - `grep -r --exclude-dir .index …`, the space form;
  - the Glob search root built from `path` plus the pattern's literal segments (`{pattern:"**/*.yaml", path:"kb-root"}`, refused).
- **Fix:** add the three rows.

### S6. Warning: ARCHITECTURE retells the kbase skill's text
- **Where:** `PROJECT_DOCS/ARCHITECTURE/subsystem-map.md`
- **Finding:** the leaf retells the router and `installing.md` behaviour, and `KB_RUNNER_TARGETS`'s sentence: a second home for definition prose.
- **Fix:** keep the mechanism only — the constants, which clause goes to which reference, and the route→reference map — and cite `adjagent/definitions/kbase.py` for the content.

### S7. Warning: how a work contributes to strength is stated three times in one reference
- **Where:** `adjagent/clauses.py` (`kb_orientation`); `adjagent/definitions/kbase.py`, `reading.md`'s *Claim rigor and strength* and works paragraphs, and `scoring-system.md`
- **Finding:** the rendered `reading.md` states the contribution and pending rule three times. The *how the scoring system works* route only links out.
- **Fix:** keep the clause's statement and cut the works paragraph down to the reading actions; make *Claim rigor and strength* the one scoring explanation, and decide whether `scoring-system.md` points into it.

### S8. Note: reading.md restates the server's rule on rigor values
- **Where:** `adjagent/definitions/kbase.py`, `reading.md`'s third constraint
- **Fix:** keep only the routing it alone carries (`score` grades; `references/maintaining.md` writes).

### S9. Warning: README links land on root pointer stubs
- **Where:** README's links to `SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` and `THESIS.md`
- **Fix:** link each to the volume entry point or leaf it cites.

### S10. Warning: `_venv` breaks the three-line recipe rule as written
- **Where:** `python.just` `_venv`, against `PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/long-recipe-bodies-are-scripts.md`
- **Finding:** `_venv` is a shebang body of about six commands, while the rule says a body over three lines is a script.
- **Fix:** choose one: state a shebang-recipe exemption in the rule, or move the body to `devtools/scripts/`.

### S11. Note: README opening and section names
- **Finding:** the opening runs three sentences against the two-sentence convention, and the sections are named Developer/Usage/Development rather than Requirements and Quick Start.
- **Fix:** restructure.

### S12. Note: Must-see lists repeat boundary boilerplate
- **Where:** the SPEC, ARCHITECTURE and CONVENTIONS `entry-point.md` files
- **Fix:** keep content that would hurt to miss.

### S13. Note: the claude matcher runs perl on every file-tool call on base installs
- **Where:** `adjagent/harnesses/claude.py`, `_guardrail_entry`
- **Finding:** base installs spawn perl on every file-tool call, and the call always passes. Kb installation is sticky, so the matcher could be conditioned on it.
- **Fix:** measure perl startup per call first; narrow the matcher to `Bash` on base installs only if that cost matters.

### S14. Note: the guardrail's behaviour is restated in four documents
- **Where:** SPEC *Shipped files*, ARCHITECTURE *Guardrail hook*, CONVENTIONS *Guardrails change together*, README §Guardrail
- **Fix:** ARCHITECTURE cites SPEC for what is blocked, and CONVENTIONS keeps only the process rules.

### S15. Note: SPEC names a code constant
- **Where:** `PROJECT_DOCS/SPEC/deployed-surfaces/shipped-files.md`
- **Finding:** SPEC names `SHIPPED_PACKAGES`, against its entry point's "no code structure" rule.
- **Fix:** state the outcome in SPEC and move the constant's name to ARCHITECTURE.

### S16. Note: the router's KB probe does not name its form
- **Where:** `adjagent/definitions/kbase.py`, the router's KB probe
- **Finding:** a Glob or Read probe for `kb-root/.index` is refused; `test -d` passes.
- **Fix:** name `test -d` as the probe.

### S17. Note: mage has no guardrail
- **Where:** SPEC *Shipped files* ("mage ships none")
- **Finding:** a mage install is always a kb install, so its `.index/` protection rests on kbase's prose instruction alone.
- **Fix:** check whether mage's plugin format can carry a hook; if it cannot, record the gap in SPEC.

### S18. Note: one guardrail test duplicates a case-table row
- **Where:** `tests/test_guardrail.py`, `test_guardrail_pl_passes_a_tool_other_than_bash`
- **Finding:** it never reaches the mutation check: with no kb signal, the script exits before it.
- **Fix:** plant the kb signal so the test reaches the check, or delete it; the table row survives.

### S19. Note: `_OPENCODE_TOOLS` names the wrong side
- **Where:** `tests/test_guardrail.py`
- **Finding:** `_OPENCODE_TOOLS` is used as the set of Claude tools.
- **Fix:** rename it, or bind `_CLAUDE_TOOLS` and use that.

### S20. Note: the test re-derives the staged script's path
- **Where:** `tests/test_guardrail.py`
- **Fix:** use `script.relative_to(HARNESS_RESOURCES_SOURCE / harness.name)` instead of a directory depth.

## Settled, not reopened

- **The guardrail's reach:** searches rooted above `kb-root/`, `rg`/`tree`/`ls -R` refusals, an
  untracked `cd kb-root && …`, and `"$CLAUDE_PROJECT_DIR"/…` with the quote closed before `/` all
  stand. The hook is known imperfect and is not a boundary.
- **The maintaining reference's `commit` paragraph** states the project's rule: the user decides,
  and `commit` is strongly encouraged.
- **THESIS has no "Must-see:" section:** the rule covers subtree entry points, and
  `PROJECT_DOCS/entry-point.md` is the primary entry point.
- **docdicer** (its pin, an existing `.venv`, the docs-tooling recipes) is local development
  tooling, outside a release's review.
