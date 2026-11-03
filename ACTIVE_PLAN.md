# ACTIVE_PLAN — adjagent

## Status

| package | dispatch | rating | seat | state |
|---|---|---|---|---|
| WP1 | WP1.1 | mechanical | `python-coder`, `model: sonnet` | landed |
| WP1 | WP1.2 | expert | `python-coder`, coordinator's model | landed |
| WP2 | WP2.1 | mechanical | `python-coder`, `model: sonnet` | landed |
| WP2 | WP2.2 | expert | `generalist-coder`, coordinator's model | landed |
| WP3 | WP3.1 | expert | `python-coder`, coordinator's model | landed |
| WP4 | WP4.1 | expert | `generalist-coder`, coordinator's model | landed |
| WP6 | WP6.1 | expert | `python-coder`, coordinator's model | landed |
| WP6 | WP6.2 | expert | `python-coder`, coordinator's model | landed |
| WP6 | WP6.3 | mechanical | `tech-writer`, `model: sonnet` | landed |

- **Landing unit.** WP1.1 and WP1.2 land as one commit, and WP2.1 and WP2.2 as another. No commit
  lands between the two dispatches of a package. WP3 lands as one commit, together with the
  stale-span fixes already in the working tree (`SPEC.md`, `adjagent/definitions/kbase.py`). WP3's
  own precondition table replaces the global one for that package.
- **Order.** WP1 and WP2 depend on nothing in each other, and either can land first. They never run
  at the same time, because both edit README.md, SPEC.md and ARCHITECTURE.md.
- **WP6.** WP6.1, WP6.2 and WP6.3 run in that order, one at a time, and land as one commit. No
  commit lands between them. WP6's own precondition table replaces the global one for that package.

## Preconditions for every package

Re-run each of these before a package's first dispatch. If any answer differs, stop and report it,
and dispatch nothing.

| check | must answer |
|---|---|
| `git status --porcelain --untracked-files=no` | nothing, or only ` M ACTIVE_PLAN.md` |
| `just test` | passes |

## Rule for every dispatch

Before editing, re-run every fact row the dispatch's brief carries. If a command's output does not
contain the row's quoted answer, stop and report that row, and edit nothing. A quoted answer
shortened with "…" is matched on the text it shows. An answer that says "and nothing else" also
fails when the output holds anything beyond what it quotes.

---

## WP1 — the kbase skill follows kbase 0.9.1's MCP surface

### Outcome

The `kbase` skill, its neighbours in `adjagent/clauses.py`, the tests that pin its text, README.md,
SPEC.md and ARCHITECTURE.md describe kbase 0.9.1's MCP surface and nothing older. A session driving
kbase through the skill calls tools that exist, and names operations and arguments that exist.

### Precondition — kbase 0.9.1 is tagged and installed

The kbase repository is not WP1's to edit. Commands run from the adjagent root, against the sibling
kbase checkout.

kbase 0.9.1 is installed as a release candidate from the kbase working tree at commit `916aaad`, through
the local tap. No `v0.9.1` tag exists yet, so the facts are pinned to that commit.

| check | must answer |
|---|---|
| `git -C ../kbase show 916aaad:internal/version/version.go \| grep -n 'const Current'` | `8:const Current = "0.9.1"` |
| `kbase --version` | `0.9.1` |
| every row of "What kbase 0.9.1 serves" | the answer recorded there |

### What kbase 0.9.1 serves

Each command reads the kbase repository at commit `916aaad`, the installed release candidate.

| fact | command → answer |
|---|---|
| Queries and `render-citation` are operations of one `query` tool, and write ops of one `write` tool | `git -C ../kbase show 916aaad:cmd/surface.go \| grep -n -E 'queryFamily = \|writeFamily = '` → `28:	queryFamily = "query"`, `29:	writeFamily = "write"` |
| A family tool takes `operation` and `arguments`; an argument is a flag's name without dashes | `git -C ../kbase show 916aaad:internal/mcp/mcp.go \| grep -n -E 'operationProperty = \|argumentsProperty = \|a flag by its name'` → `283:	operationProperty = "operation"`, `284:	argumentsProperty = "arguments"`, `307:` "…a positional by its Usage name, a flag by its name " + "without dashes; …" |
| Help is served per family and per operation | `git -C ../kbase show 916aaad:SPEC.md \| grep -n -E 'kbase://help/query\|kbase://help/<operation>'` → `2208:` names `kbase://help/query` or `kbase://help/write`, and `2209:` `kbase://help/<operation>` (also hits `2337:` and `2410:`) |
| `strength`'s arguments are `min`, `max` (strictly below), `min-dependents`, `sort` (`strength` or `dependents`) and `pending` | `git -C ../kbase show 916aaad:cmd/strength.go \| grep -n 'Var('` → lines 44–48: `"min"`, `"max"` ("only claims with strength strictly below this"), `"min-dependents"`, `"sort"` ("the order: strength or dependents"), `"pending"` |
| `drop-claim-node` deletes the record, the marker, and every edge and `demoted` record naming the claim, in one call. It is refused while a line under `kb-root/` outside the register pages, or a prose field of another record, mentions the id | `git -C ../kbase show 916aaad:cmd/drop-claim-node.go \| grep -n -E 'demoted record\|refused while'` → `9:` "marker in every leaf carrying one, every demoted record naming it, and every", `10:` "edge record naming it, in one call. The op is refused while a line under" |
| The volume-root rule is `build`'s help, served as `kbase://help/build` | `git -C ../kbase show 916aaad:cmd/build.go \| grep -n -E 'toplevel\|documentclass'` → `211:` "…00README.json's toplevel entry names,", `212:` "else the sole file containing \documentclass. …" |
| `kbase://model-hints` is still served, so `kbase.py`'s references to it (lines 321–333) stand | `git -C ../kbase show 916aaad:cmd/surface.go \| grep -n 'ModelHintsResource()'` → `167:` "…mcp.SheetResources(servedKB), mcp.ModelHintsResource(),"; `git -C ../kbase show 916aaad:internal/mcp/resources.go \| grep -n 'ModelHintsURI  ='` → `23:	ModelHintsURI  = "kbase://model-hints"` |

### Steering principles

- **The skill carries only what kbase's offered surface does not.** CONVENTIONS.md, "A skill's
  reference carries only what its tool's offered surface does not", states the rule and what the
  offered surface is. The skill carries what that surface does not, chiefly when to engage kbase.
  Where a stale item can be cut in favour of a pointer to the offered surface (`kbase://help/<name>`),
  the pointer is the preferred fix.
- **Only the cited stale text changes.** `building.md`, `maintaining.md` and `scoring.md` are not
  slimmed in this package. The same CONVENTIONS.md bullet makes a change of the minimum version the
  moment to re-read the references. WP1.2 does that re-read and **reports** any other text that is
  false against 0.9.1. It does not edit that text.
- **The contract documents do not enumerate another project's perishable names** (tools, resources,
  calls) unless strictly necessary. They keep adjagent's own facts.

### WP1.1 — mechanical (`python-coder`, `model: sonnet`)

**Brief:** §Rule for every dispatch, WP1 §Outcome, and this section.

**Outcome:** the minimum kbase version reads 0.9.1 everywhere it is stated. README.md names the
family tools. The two tests that pin skill text expect the new forms.

**Scope:** `adjagent/definitions/kbase.py` (`KBASE_MIN_VERSION` only), `README.md`, `SPEC.md`,
`tests/test_adjagent.py` (`test_the_kb_reading_reference_names_the_harness_mcp_tool`), and
`tests/test_write_op_contract_sources.py` (the module docstring and the `"closed set"` row of
`CONTRACT_TOKENS`).

**First, record the pre-package render footprint.** Run these before any edit:

1. `just render latest`, then `just render-diff`
2. `just render latest-opencode --harness=opencode --model-tier-map=all=inherit`, then `just render-diff reference-opencode latest-opencode`

| # | fact acted on (command → answer at HEAD `3af4390`) | edit |
|---|---|---|
| 6 | `grep -n 'KBASE_MIN_VERSION = ' adjagent/definitions/kbase.py` → `12:KBASE_MIN_VERSION = "0.9.0"` | `KBASE_MIN_VERSION = "0.9.1"` |
| 6a | `grep -n '0\.9\.0' SPEC.md README.md` → `SPEC.md:65:` "… Version 0.9.0 is the minimum kbase this product is written for," and `README.md:36:` "- kbase 0.9.0 or later, installed by you …" | Change `0.9.0` to `0.9.1` at both sites. |
| 7 | `grep -n -E 'Every query, write op\|mcp__kbase__stats' README.md` → `377:` "names no KB path. Every query, write op, \`refresh\`," and `379:` "own prefix — \`mcp__kbase__stats\` under Claude Code, \`kbase_stats\` under opencode. A settings file" | Replace the span from "Every query, write op," (line 377) through "\`kbase_stats\` under opencode." (line 379) with exactly: ``Its queries are operations of one tool, `query`, and its write ops of another, `write`; every other command is a tool of its own. Each is offered under the harness's own prefix — `mcp__kbase__query` under Claude Code and `kbase_query` under opencode, called with operation `stats`.`` Rewrap the paragraph; change nothing else in the list item. |
| 8 | `grep -n 'mcp__kbase__find' tests/test_adjagent.py` → `434:    [(CLAUDE, "mcp__kbase__find"), (MAGE, "mcp_kbase_find"), (OPENCODE, "kbase_find")],` | Change the three names to `"mcp__kbase__query"`, `"mcp_kbase_query"` and `"kbase_query"`. Line 440's assertion stays. |
| 3b | `grep -n -E 'write-op tool\|closed set' tests/test_write_op_contract_sources.py` → `4:` "brief at all: every metadata write is one write-op tool call whose schema is that op's closed set of" and `30:` `("closed set", "the op's schema is its closed set of value keys, which is what the seat supplies"),` | Docstring lines 4–5: replace "every metadata write is one write-op tool call whose schema is that op's closed set of value keys," with "every metadata write is one call of the `write` tool carrying that op's closed set of value keys, which kbase checks,". Line 30: the second string becomes `"each op's closed set of value keys, which kbase checks, is what the seat supplies"`. The token `"closed set"` stays. |

**Done-line (WP1.1):**

- `just test-changed` reports 3 failures, all of them
  `test_the_kb_reading_reference_names_the_harness_mcp_tool[…]`, and no other failure. These are
  expected, and WP1.2 clears them. Do not edit anything to clear them.
- `just sweep-python` runs, its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.

**Return:** the done-line results, and both pre-package `render-diff` outputs verbatim. WP1.2's brief
carries them.

### WP1.2 — expert (`python-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, all of WP1 except WP1.1's table, WP1.1's returned
`render-diff` outputs, and this section.

**Scope:**

- `adjagent/definitions/kbase.py`: the router body and the `references/reading.md` and
  `references/maintaining.md` bodies, at the spans below only
- `adjagent/clauses.py`: `kb_orientation`, the "Metadata is written by the tools" paragraph
- `ARCHITECTURE.md`: Subsystem Map, the "kb set + kbase" entry

| # | fact acted on (command → answer at HEAD `3af4390`) | edit |
|---|---|---|
| 1 | `grep -n -E 'query tools\|MCP_TOOL_PREFIX\}find' adjagent/definitions/kbase.py` → `142:` "…carries a \`clm-xxxxxx\` id; the query tools below", `190:` "…Use the \`kbase\` server's query tools, which the harness", `191:` "offers under the server's prefix — \`{clauses.MCP_TOOL_PREFIX}find\` — and the bullets below name each tool" | Rewrite the sentence on lines 190–192 to say: the queries are operations of the one tool `` `{clauses.MCP_TOOL_PREFIX}query` ``, each named by `operation`. The bullets may keep naming each query, now as operations. The rendered text must hold the tool name in backticks, because WP1.1's test asserts `` `mcp__kbase__query` ``. On line 142, "the query tools below" becomes the queries below. |
| 2 | `grep -n -E 'strength-below\|weak-points' adjagent/definitions/kbase.py` → `179:` "refutation's cap. \`strength-below\` and \`weak-points\` omit pending claims but list unjudged \`0.00\` ones", `214:` "- \`strength-below\` with a \`max-strength\` — shaky claims", `215:` "- \`weak-points\` — highest-leverage rework targets (shaky *and* load-bearing)" | Line 179: `strength` without `pending` omits pending claims but lists unjudged `0.00` ones. The rest of the sentence, on line 180, stands. Lines 214–215 cover four things. Shaky claims are `strength` with `max`. Highest-leverage rework targets are `strength` with `sort: dependents` and a `min-dependents`. `pending: true` lists unscored claims. Point at `kbase://help/strength` rather than restating the arguments. |
| 3a | `grep -n 'write-op tool' adjagent/definitions/kbase.py adjagent/clauses.py` → `kbase.py:489:` "claim marker, a premise bullet, an analysis-to-claim pair — each is written by one write-op tool that"; `clauses.py:453:` "…is composed by the \`kbase\` server's write-op tools from values a seat supplies, each tool's schema being that op's closed set of value keys. …" | `kbase.py:489`: every write op is an operation of the one `write` tool. `clauses.py:453`: replace the per-op tool schema clause with "each op's closed set of value keys, which kbase checks". The words "closed set" stay, because `tests/test_write_op_contract_sources.py` asserts them in `references/maintaining.md`, which takes this paragraph through `kb_orientation`. |
| 4 | `grep -n -E 'should not exist\|re-point' adjagent/definitions/kbase.py` → `601:` "- **A claim that should not exist** — a duplicate of one already in the graph, or one a correction", `606:` "bullets you drop were dependents' warrants: re-point each one that still holds onto the claim that", `607:` "replaces it, or the dependent is left resting on nothing. A re-pointed bullet…"; the bullet runs to line 608 | Rewrite lines 601–608. `drop-claim-node` alone deletes the claim and every edge naming it, and it is refused only while prose names the claim. Before the drop, read the dependents' `rests-on` edges with `deps`. After it, re-point each edge that still holds onto the replacing claim. Keep the fact that a re-pointed bullet enters at a `*pending*` bearing. The cycle advice at lines 618–619 is unchanged. |
| 5 | `grep -n -E 'toplevel\|documentclass' adjagent/definitions/kbase.py` → `50:` "Identify the volume root — the entry whose \`usage\` is \`toplevel\` in \`00README.json\` where the project", `51:` "has one, else the \`.tex\` file carrying \`\\\\documentclass\` — put it to the user, and route to" | Keep the step of identifying the volume root and putting it to the user. Replace the inline rule with a pointer to `kbase://help/build`. |
| 9 | `grep -n -E 'every query, write\|model-hints. resource\|leaving .wait.' ARCHITECTURE.md` → `524:` "…the set's route to it is MCP-only: every query, write", `527:` "that server's \`kbase://model-hints\` resource, read by uri. The router says so. When a request", `545:` "run's ledger and pid stand, leaving \`wait\`, \`status\` and \`cancel\` to follow — the same three the" | See item 9 below. |

**Item 9, ARCHITECTURE.md Subsystem Map, "kb set + kbase".**

Change the route sentence (lines 524–527) to say, in substance: the set's route to kbase is MCP-only,
through the harness's `kbase` MCP server, offered under the harness's `mcp_tool_prefix`, and what
the server offers is kbase's own surface.

Cut three things:

- the enumeration "every query, write op, `refresh`, `verify`, `build` and `score`"
- the `kbase://model-hints` sentence
- the `wait`/`status`/`cancel` listing on lines 544–546

Keep:

- the point that `score`'s call returns before its run ends
- "The router says so."
- the reference file list and the `kb-` runner target names

**Reference re-read.** Read `building.md`, `maintaining.md`, `scoring.md`, `scoring-system.md`,
`reading.md` and `installing.md`, as `kbase.py` renders them, against the facts in "What kbase 0.9.1
serves" and kbase's `kbase://help/<name>` text at commit `916aaad`. List every further span that names a
tool, operation, argument or resource 0.9.1 does not offer, with its `kbase.py` line. Edit none of
them.

**Done-line (WP1.2, and WP1's):**

- `just test-changed` passes.
- `just sweep-python` runs, its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.
- **Render and compare both slots.**
  - `just render latest`, then `just render-diff`
  - `just render latest-opencode --harness=opencode --model-tier-map=all=inherit`, then
    `just render-diff reference-opencode latest-opencode`

  For each pair the outputs list, `diff -u` its two files under `rendered/<slot>/` and compare the
  spans with the pre-package footprint WP1.1 returned. Beyond that footprint, only these change:
  - `skills/kbase/SKILL.md`: item 5 and the version
  - `skills/kbase/references/reading.md`: items 1 and 2
  - `skills/kbase/references/maintaining.md`: items 3a and 4, and the `clauses.py` paragraph
  - `skills/kbase/references/installing.md`: the version

  The opencode slot's `reading.md` shows `` `kbase_query` ``.

**Return:** the done-line results, and the reference re-read's list. An empty list is stated as
empty.

---

## WP2 — the guardrail keeps sessions out of `kb-root/.index/` on kb installs

### Outcome

On a kb install, both guardrails refuse a tool call that reads or writes `<root>/kb-root/.index/`.
That directory holds kbase's records (`nodes.yaml`, `edges.yaml`, `format.yaml`).

- The check runs on the shell tool and the file tools. It sits beside the existing mutation check in
  both implementations and is held to the same case table.
- On a base install the check is off, and the guardrail behaves as it does today.
- Each harness still ships one guardrail file, copied byte-verbatim. Nothing is rendered, nothing is
  added per install type, and there is no second hook or plugin.

### Settled design

- **The switch is runtime.** Each implementation turns the `.index/` check on only when
  `<harness-dir>/skills/kbase/SKILL.md` exists, and reads it on every call. Presence suffices; the
  banner is not read.
- **The harness directory comes from the script's own path.** It never comes from the root or the
  working directory, which `--subdir` would make wrong.
  - `guardrail.pl` uses `$0`, which is `<harness-dir>/hooks/guardrail.pl`.
  - `guardrail.ts` uses `import.meta.url`, which is `<harness-dir>/plugins/guardrail.ts`.
- **Resolution has two modes.**
  - The new check collapses `..` lexically against the call's working directory, else `<root>`, then
    follows symlinks wherever the path exists, so a link into `.index/` is caught.
  - The mutation check is unchanged in behaviour: lexical, shell-only, and all 61 current cases pass
    untouched.
- **Claude Code has one settings entry.** Its matcher is `Bash|Read|Write|Edit|NotebookEdit|Grep|Glob`
  on every claude install, and a re-install replaces an earlier `Bash`-only entry in place.
- **opencode has one plugin.** Its tool filter widens to `read`, `write`, `edit`, `patch`, `grep` and
  `glob`.
- **`patch` is covered.** Each path named on a `*** Add File:`, `*** Delete File:`,
  `*** Update File:` or `*** Move to:` line of `patchText` is judged as a file-tool path.
- **No `list` tool exists** in opencode v2.2.3. A directory listing is `read` on a directory, so it
  is covered by `read`.
- **The check does not chase indirection** — interpreters, variables, `eval`, globs that expand into
  `.index/`. This matches CONVENTIONS.md: the guardrail "is not a boundary against a command built to
  evade it".

### Requirements

- **Subject.** A path at or under `<root>/kb-root/.index/`. `<root>` is the project root each
  implementation already resolves:
  - `guardrail.pl`: `$CLAUDE_PROJECT_DIR`, else the input `cwd`
  - `guardrail.ts`: `ctx.location.directory`

  A `kb-root/` anywhere else, such as `<root>/sub/kb-root/`, is not the subject.
- **File tools: a path argument.** Refuse a call whose path argument resolves into the subject. The
  arguments are:
  - Claude: `file_path` (Read, Write, Edit), `notebook_path` (NotebookEdit), `path` (Grep, Glob)
  - opencode: `path` (read, write, edit, grep, glob), and `patchText`'s marker lines (patch)

  A relative path resolves against the input `cwd`, else `<root>` (Claude), or against `<root>`
  (opencode).
- **File tools: a search.** A search's root is its `path`, else the working directory. For a Glob,
  that root is extended by the pattern's leading literal segments: those before the first segment
  holding `*`, `?`, `[` or `{`. So `kb-root/**` with no `path` is rooted at `<root>/kb-root`.
  - **A search rooted in the subject** is refused with the path reason.
  - **A search rooted at or inside `<root>/kb-root/`, outside the subject,** is refused unless its
    file filter cannot match `nodes.yaml`, `edges.yaml` or `format.yaml`. The filter is a Grep's
    `glob` (opencode: `include`) or a Glob's `pattern`. "Cannot match" means the filter's last path
    segment, read as a glob over `*`, `?`, `[…]` and `{a,b}`, matches none of the three names.
  - **No filter counts as matching all.** A Grep with no `glob`/`include` has none, and neither does
    one filtered by Claude's `type` alone. Grep's own `pattern` is a content regex and never a filter.
  - **The `hidden` argument of opencode's `glob` is not read.**
  - **A search rooted above `kb-root/`** is allowed, as is one from the project root or the default
    working directory.
  - **A file-tool search refusal uses the recursive-search reason.**
- **Shell: a stated heuristic.**
  - Refuse a command any of whose words resolves into the subject.
  - Refuse a recursive search or walk rooted at or inside `<root>/kb-root/` that does not exclude
    `.index`: `grep -r`/`-R`, `rg`, `find`, `ls -R`, `tree`.
  - Allow existence checks on the subject: `test -e|-d|-f <path>`, `[ -e <path> ]`, `stat <path>`.
  - A recursive search rooted above `kb-root/` is allowed.
- **Refusal texts.** The message is `Blocked: <reason>`, with no further text. The mutation check's
  ". Use the Edit and Write tools …" tail does not apply. The `reason` values, exactly:
  - A path into the subject:
    ``kb-root/.index/ holds kbase's records: read them with kbase's `query` tool and change them with its `write` tool``
  - A recursive search: that sentence, then
    ``; exclude .index from this search (grep: --exclude-dir=.index; rg: -g '!**/.index/**'; find: -path '*/.index' -prune; Grep: a glob (opencode: include) no .index file matches; Glob: a pattern no .index file matches)``
- **Perl stays load-safe.** Any module the check needs (`Cwd`, for instance) is loaded with
  `require` inside the existing `eval`, never with `use`, so a load failure exits 1, not 2.

### Facts acted on

Commands run from the adjagent root. The opencode rows read the sibling opencode checkout at tag
`v2.2.3`, and `bash -c` is used so that the helper splits on whitespace.

| fact | command → answer |
|---|---|
| The matcher is `Bash` | `grep -n '"matcher"' adjagent/harnesses/claude.py` → `75:    return {"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}` |
| The claim reads the command, never the matcher, so an earlier `Bash`-only entry is already ours and is replaced whole; **`_guardrail_claim` needs no change** | `sed -n '78,92p' adjagent/harnesses/claude.py` → reads only `element.get("hooks")` and each hook's `command`, through `_GUARDRAIL_COMMAND.fullmatch`. `grep -n 'if spliced == text' adjagent/install.py` → `808:` |
| The hook runs the script by absolute path, so `$0` names it | `grep -n 'exec perl' adjagent/harnesses/claude.py` → `54:    f'{_GUARDRAIL_SCRIPT}"; if [ -f "$s" ] && [ -r "$s" ]; then exec perl "$s"; fi; '`, with `s="$CLAUDE_PROJECT_DIR/<harness>/hooks/guardrail.pl"` (`52:`) |
| The kb signal | `grep -n -E '^KBASE_SKILL_DIR\|^KBASE_ROUTER' adjagent/install.py` → `44:KBASE_SKILL_DIR = "skills/kbase"`, `46:KBASE_ROUTER = f"{KBASE_SKILL_DIR}/SKILL.md"` |
| The perl hook judges Bash only, and resolves lexically | `grep -n -E "tool_name\|filesystem is never read\|Blocked:" adjagent/harnesses/resources/claude/hooks/guardrail.pl` → `17:` "…the filesystem is never read.", `111:  if (($input->{tool_name} // '') eq 'Bash') {`, `123:` "Blocked: ${reason}. Use the Edit and Write tools …" |
| The opencode filter and refusal | `grep -n -E 'shellTools\|Blocked:' adjagent/harnesses/resources/opencode/plugins/guardrail.ts` → `10:const shellTools = new Set(["bash", "shell"])`, `97:` "if (!shellTools.has(…)) return", `102:` "Blocked: ${reason}. Use the edit and write tools …" |
| The case table and its fields | `grep -n '_CASE_FIELDS = ' tests/test_guardrail.py` → `33:_CASE_FIELDS = {"command", "reason", "files", "cwd"}`; `python3 -c "import json;print(len(json.load(open('tests/guardrail_cases.json'))))"` → `61` |
| Tests run the source-tree scripts, whose directories hold no `skills/` | `grep -n -E '^_PERL_HOOK\|^_TS_PLUGIN' tests/test_guardrail.py` → `27:_PERL_HOOK = _RESOURCES / "claude/hooks/guardrail.pl"`, `28:_TS_PLUGIN = _RESOURCES / "opencode/plugins/guardrail.ts"` |
| The reason strip needs the old tail | `grep -n 'rindex' tests/test_guardrail.py` → `41:    return message[len("Blocked: ") : message.rindex(". Use the ")]` |
| The TS runner hard-codes the shell tool | `grep -n 'tool: "bash"' tests/guardrail_ts_runner.ts` → `38:    before({ tool: "bash", input: cwd === root ? { command } : { command, workdir: cwd } })` |
| A guardrail test pins Bash-only scope by name | `grep -n 'def test_guardrail_pl_passes_a_tool_other_than_bash' tests/test_guardrail.py` → `153:`; its docstring reads "Only a Bash call is judged" |
| Contract text to change | `grep -n -E 'Bash commands\|entry for Bash\|lexically\|change together' SPEC.md ARCHITECTURE.md CONVENTIONS.md README.md` → `CONVENTIONS.md:99:`, `:100:` "…block exactly the same Bash commands…"; `README.md:138:` "…blocks Bash commands which change a file…", `:150:` "adds one \`PreToolUse\` entry for Bash…", `:409:` "The two guardrails change together…" (still true; unchanged); `ARCHITECTURE.md:169:` "resolves relative targets lexically…"; `SPEC.md:191:` "guardrails block the same Bash commands…", `:196:` "registers it as a \`PreToolUse\` entry for Bash…" |
| The claude render slot holds the hook, and its settings entry, only where perl passes the probe | ARCHITECTURE.md:402–404 "A slot holds the claude hook script only where \`perl\` passes the probe on that machine"; :181–183 "A failed probe … drops the script from the files copied, skips the settings merge" |
| Claude Code: a matcher of letters and `\|` is an exact list of tool names | `https://code.claude.com/docs/en/hooks`, matcher table: "Only letters, digits, \`_\`, \`-\`, spaces, \`,\`, and \`\|\` \| Exact string, or list of exact strings separated by \`\|\` or \`,\`…" |
| Claude Code tool inputs | `https://code.claude.com/docs/en/agent-sdk/typescript`: `type NotebookEditInput = { notebook_path: string; …}`, `type GrepInput = { pattern: string; path?: string; glob?: string; type?: string; …}`, `type GlobInput = { pattern: string; path?: string; }`, `type FileEditInput = { file_path: string; …}`. `https://code.claude.com/docs/en/hooks`: Read and Write take `file_path`, and "\`tool_input.file_path\` is always absolute". `https://code.claude.com/docs/en/tools-reference` lists `NotebookEdit` and no `MultiEdit` |
| opencode: every tool call, shell or not, passes `execute.before` with the tool's name and its input | `bash -c 'git -C ../opencode show v2.2.3:packages/core/src/tool.ts \| grep -n -E "const beforeExecute\|execute.before\|beforeExecute\(input.call.name"'` → `121:    const beforeExecute = (name: string, input: unknown, context: Tool.Context) =>`, `122:      hooks.trigger("tool", "execute.before", {`, `324:` "const event = yield* beforeExecute(input.call.name, input.call.input, context)" |
| opencode: the event's fields are `tool` and `input`, and a throw rejects the call | `git -C ../opencode show v2.2.3:packages/plugin/src/promise/tool.ts \| grep -n -E '"execute.before"\|^    tool: string\|^    input: unknown'` → `39:`, `40:    tool: string`, `45:    input: unknown`; `git -C ../opencode show v2.2.3:packages/plugin/src/promise/adapter.ts \| grep -n '"execute.before": (run)'` → `666:  "execute.before": (run) => Effect.tryPromise({ try: run, catch: toolError }),` |
| opencode tool names | `bash -c 'for t in read write edit patch grep glob shell; do git -C ../opencode show v2.2.3:packages/core/src/tool/plugin/$t.ts \| grep -n "export const name"; done'` → `"read"`, `"write"`, `"edit"`, `"patch"`, `"grep"`, `"glob"`, `"shell"` |
| opencode has no `list` tool | `git -C ../opencode ls-tree --name-only v2.2.3 packages/core/src/tool/plugin/ \| grep -c '/list\.ts$'` → `0`; `read.ts:18:` "path: … 'File or directory to read'" |
| opencode path arguments | `git -C ../opencode show v2.2.3:packages/core/src/tool/plugin/<t>.ts \| grep -n -E '^  (path\|include\|pattern): '` → `read.ts:18`, `write.ts:24`, `edit.ts:25` `path`; `grep.ts:18` `pattern`, `:23` `path` (optional), `:26` `include` ("Glob pattern to filter files"); `glob.ts:18` `pattern`, `:19` `path` (optional) |
| opencode resolves a relative path against the location directory | `git -C ../opencode show v2.2.3:packages/core/src/file-access.ts \| grep -n 'resolvePath(location.directory, input.path)'` → `96:` |
| opencode `patch` carries its paths on marker lines | `git -C ../opencode show v2.2.3:packages/core/src/tool/patch.txt \| grep -n -E '^\*\*\* (Add File\|Delete File\|Update File\|Move to):'` → `11:` "*** Add File: <path>", `12:` "*** Delete File: <path>", `13:` "*** Update File: <path>", `22:` "*** Move to: src/main.py" |
| opencode `grep` searches hidden directories, so it reaches `.index/`; `glob` skips them unless `hidden` is set | `git -C ../opencode show v2.2.3:packages/core/src/ripgrep.ts \| grep -n -E '"--hidden",\|--glob=!\*\*/\.\*'` → `178:` "...(input.hidden ? [] : ["--glob=!**/.*"]),", `226:            "--hidden",` |
| opencode loads a standalone plugin file by its own file URL, so `import.meta.url` is `<harness-dir>/plugins/guardrail.ts` | `git -C ../opencode show v2.2.3:packages/core/src/plugin/module.ts \| grep -n 'pathToFileURL(operation.target).href'` → `112:` |

### WP2.1 — mechanical (`python-coder`, `model: sonnet`)

**Brief:** §Rule for every dispatch, WP2 §Outcome, the fact rows "The matcher is `Bash`" and "The
claim reads the command…", and this section.

**Outcome:** every claude install registers the guardrail for Bash and the file tools, and an
earlier `Bash`-only entry is replaced in place.

**Scope:** `adjagent/harnesses/claude.py` (`_guardrail_entry`), `tests/test_adjagent_install.py`.

**First, record the pre-package render footprint.** Run these before any edit:

1. `just render latest`, then `just render-diff`
2. `just render latest-opencode --harness=opencode --model-tier-map=all=inherit`, then `just render-diff reference-opencode latest-opencode`

**Edits:**

1. `claude.py:75`: `"matcher": "Bash"` becomes `"matcher": "Bash|Read|Write|Edit|NotebookEdit|Grep|Glob"`.
   In `_guardrail_entry`'s docstring (line 66), "on every Bash call" becomes "on every Bash and
   file-tool call".
2. `tests/test_adjagent_install.py`: add one test, modelled on
   `test_a_reinstall_replaces_our_entry_in_place_and_a_second_changes_no_byte` (line 1441).
   - **Setup:** a settings file whose `PreToolUse` holds `{"matcher": "Bash", "hooks":
     _hook_entry(".claude")["hooks"]}`, followed by `json.loads(_SED_HOOK)`.
   - **Assert after one install:**
     - `PreToolUse == [_hook_entry(".claude"), json.loads(_SED_HOOK)]`
     - `_BY_HAND` is absent from the captured output

   `_guardrail_claim` is not edited.

**Done-line (WP2.1):**

- `just test-changed` passes.
- `just sweep-python` runs, its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.

**Return:** the done-line results, and both pre-package `render-diff` outputs verbatim. WP2.2's brief
carries them.

### WP2.2 — expert (`generalist-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, all of WP2 except WP2.1's section, WP2.1's returned
`render-diff` outputs, and this section.

**Scope:**

- `adjagent/harnesses/resources/claude/hooks/guardrail.pl`
- `adjagent/harnesses/resources/opencode/plugins/guardrail.ts`
- `tests/guardrail_cases.json`, `tests/test_guardrail.py`, `tests/guardrail_ts_runner.ts`
- SPEC.md: Deployed Surfaces, the harness-shipped-files paragraph (lines 178–200)
- ARCHITECTURE.md: Install Consumption Model (lines 150–177)
- CONVENTIONS.md: "The two guardrail implementations change together"
- README.md: "### Bash guardrail" (lines 136–156)

**Step 0.** Re-run every row of WP2's "Facts acted on". If an answer differs, stop and report the
row, and edit nothing.

**Implementation invariants:**

1. **Both sides of a comparison resolve the same way.** `<root>` takes the same symlink-following
   step as the target. On macOS a temp root under `/var` resolves to `/private/var`.
2. **The Claude-to-opencode mapping exists once**, in `tests/test_guardrail.py`. It maps tool names
   and argument names: `Read`→`read`, `Write`→`write`, `Edit`→`edit`, `Grep`→`grep`, `Glob`→`glob`;
   `file_path`→`path` and Grep's `glob`→`include`. `type` and `NotebookEdit` have no opencode
   counterpart. The TS runner receives already-mapped `{tool, input}` per run and holds no mapping.
3. **The matcher and the case table agree.** `tests/test_guardrail.py` asserts two things:
   - every tool named in `CLAUDE.guardrail.entry(".claude")["matcher"]` has a case in the table
   - every Claude tool a case names is in the matcher

**The case table.** It gains the cases below.

- **Shell, refused:**
  - `cat kb-root/.index/nodes.yaml`
  - `grep -r claim kb-root`
  - `rg title kb-root`
  - `find kb-root -name '*.yaml'`
  - `cd kb-root/.index && ls`
  - `cat .index/edges.yaml` with `cwd` `kb-root`
  - `cat kb-root/link`, where `link` is a symlink into `.index/`
- **Shell, allowed:**
  - `test -d kb-root/.index`
  - `test -e kb-root/.index/nodes.yaml`
  - `stat kb-root/.index`
  - `grep -r --exclude-dir=.index claim kb-root`
  - `rg -g '!**/.index/**' title kb-root`
  - `grep -r foo .` at the root
  - `cat kb-root/entry-point.md`
  - `cat sub/kb-root/.index/nodes.yaml`
- **File tools, refused:**
  - Read of `kb-root/.index/nodes.yaml`
  - Read of the directory `kb-root/.index`
  - Write of `kb-root/.index/format.yaml`
  - Edit of `kb-root/.index/edges.yaml`
  - NotebookEdit of `kb-root/.index/x.ipynb` (claude only)
  - Grep with `path: kb-root` and no `glob`
  - Grep with `path: kb-root` and `type` only
  - Glob `kb-root/**` with no `path`
  - patch whose `*** Update File:` names `kb-root/.index/nodes.yaml` (opencode only)
- **File tools, allowed:**
  - Read of `kb-root/a.md`
  - Grep with `path: kb-root` and `glob: "*.md"`
  - Grep with no `path` from the root
  - Glob `kb-root/**/*.md` with no `path`
  - patch whose `*** Update File:` names `kb-root/a.md` (opencode only)
- **A kb-off variant of every refused `.index/` case.** It is the same case with the signal absent,
  and its `reason` is null.

**Case form constraints:**

- A file-tool case carries `tool` (the Claude name, or an opencode-only name such as `patch`) and
  `input` (that tool's argument names). Claude sends `file_path` absolute, so it uses `@root@/…`.
- A case runs under every harness that has its tool.
- The signal is a file the case lists in `files`, as `@harness@/skills/kbase/SKILL.md`.
  `@harness@` is filled per implementation (`.claude` or `.opencode`), as `@scratch@` is.
- Each runner runs a copy of the script staged at `<case-root>/@harness@/hooks/guardrail.pl` or
  `<case-root>/@harness@/plugins/guardrail.ts`.
- A symlink is a new optional field, such as `links`, mapping a path to its target.
- `_CASE_FIELDS`, `_IDS` (which reads `command`) and `_reason` (which strips the old tail) widen to
  the new shapes.
- `test_guardrail_pl_passes_a_tool_other_than_bash` keeps its point, that the mutation check judges
  only Bash. Its docstring is corrected.

**Contract documents:**

- **SPEC.md, the harness-shipped-files paragraph.** State:
  - the `.index/` read check and the tools it covers
  - that it is active only where the harness directory holds the kbase skill's `SKILL.md`
  - that it follows symlinks, while the mutation check stays lexical
  - that the claude entry covers Bash and the file tools

  Line 191's "Bash commands" and line 196's "entry for Bash" change accordingly.
- **ARCHITECTURE.md, Install Consumption Model.** State:
  - the matcher
  - that `_guardrail_claim` recognises an entry by its command alone, so an earlier matcher is
    replaced in place
  - that every claude install runs the script on each file-tool call, and a base install finds the
    signal absent
  - how each script locates its harness directory
  - the two resolution modes

  Line 169's "resolves relative targets lexically" is scoped to the mutation check.
- **CONVENTIONS.md, "The two guardrail implementations change together".**
  - The purpose sentence (line 100) widens to the `.index/` read check and the file tools.
  - The sentence that the guardrail "is not a boundary against a command built to evade it" stays.
- **README.md, "### Bash guardrail".**
  - The heading, line 138 and line 150 follow the wider scope.
  - Add one paragraph on the `.index/` refusal and when it is active.
  - Line 409 is unchanged.

**Done-line (WP2.2, and WP2's):**

- `just test-changed` passes, `tests/test_guardrail.py` included, under `bun` and `perl`.
- `just sweep-python` runs, its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.
- **Render and compare both slots.**
  - `just render latest`, then `just render-diff`
  - `just render latest-opencode --harness=opencode --model-tier-map=all=inherit`, then
    `just render-diff reference-opencode latest-opencode`

  For each pair, `diff -u` its two files under `rendered/<slot>/` and compare the spans with the
  pre-package footprint WP2.1 returned. Beyond that footprint, only these change:
  - `hooks/guardrail.pl`, and the guardrail entry's matcher in the claude slot's settings file
  - `plugins/guardrail.ts` in the opencode slot

  If the render's install output reports the hook skipped, report that in place of the claude line.

**Return:** the done-line results, and the step 0 re-run's answers.

---

## WP3 — the kbase skill's provider setup stores the key through kbase

### Outcome

When a build launch is refused for a provider configuration gap, the kbase skill's setup offer
includes storing the provider's API key through kbase's own store, piped on stdin, with the session
never asking for the key. Nothing else in the skill states the key remedy: kbase's refused-key
failures carry it.

### Precondition

This table replaces "Preconditions for every package" for WP3.

| check | must answer |
|---|---|
| `git status --porcelain --untracked-files=no` | only ` M ACTIVE_PLAN.md`, ` M SPEC.md` and ` M adjagent/definitions/kbase.py` (the stale-span fixes WP3 lands with) |
| `just test` | passes |
| `../kbase/bin/kbase --version` | `0.9.1` |

### Facts acted on

Run from the adjagent root.

| fact | command → answer |
|---|---|
| The setup offer | `grep -n -E 'Then offer to set it up\|configure. with .model-map' adjagent/definitions/kbase.py` → `310:` "  Then offer to set it up: \`configure\` with \`create\` writes annotated templates for both files where", `312:` "  \`configure\` with \`model-map\` writes the choice." |
| The `check: provider` sentence before it stays | `sed -n '306,309p' adjagent/definitions/kbase.py` → "…A \`check: provider\` item is a configuration gap: call the \`show-config\` tool and relay its document rather than reading the file yourself to explain the refusal, so the user can fix the file the item's \`path\` names in the layer \`show-config\` reports." |
| kbase stores a key piped on stdin, by `auth add <provider>` | `../kbase/bin/kbase auth add --help \| grep -F '\| kbase auth add <provider>'` → "<command-that-prints-the-key> \| kbase auth add <provider>" |
| No adjagent source names the key file, the store's verb or a key variable | `git grep -n -E 'apiKeyFile\|auth add\|KBASE_API_KEY' -- ':!*.md'` → no output (exit 1) |
| The maintaining.md edge bullet runs from line 594 to line 601. Line 598 is the only line over 99 characters | `awk 'NR>=594&&NR<=601{print NR": "length}' adjagent/definitions/kbase.py` → `594: 91`, `595: 99`, `596: 96`, `597: 97`, `598: 106`, `599: 95`, `600: 98`, `601: 18` |
| The bullet's "its" is ambiguous | `sed -n '596,597p' adjagent/definitions/kbase.py` → "  name, or both where you name none — and \`drop-inbound-edges\` removes every other node's edge" and "  naming it: its \`supports\` edges out, and every \`references\`, \`lifts\`, \`refutes\` or experiment's". The "its" on line 597 can be read as the other node's (line 596) or as the claim's. kbase means the claim's (next row) |
| What `drop-inbound-edges` removes | `../kbase/bin/kbase drop-inbound-edges --help \| head -4` → "drop-inbound-edges removes every edge record by which another node names the claim id: a supports edge from id into another node, a references edge into id, and every lifts or refutes edge into id and every experiment's supports edge into it." (across four lines) |
| The module's wrap width | `awk 'NR>=305&&NR<=315{print length}' adjagent/definitions/kbase.py \| sort -n \| tail -1` → `101` |

### WP3.1 — expert (`python-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, WP3 in full.

**Scope:** `adjagent/definitions/kbase.py`, at the two spans below only.

**First, before any edit:** `just render pre-wp3`.

**Edits:**

1. **The setup offer, lines 310–312.** Replace it with exactly this text. Wrap it at most 101
   characters per line, two-space continuation indent included, as lines 305–315 run. Do not break
   the code span `` `<command-that-prints-the-key> | kbase auth add <provider>` `` across lines:

   > Then offer to set it up: `configure` with `create` writes annotated templates for both files
   > where none stands; once `providers.toml` names an endpoint, its key is stored from a shell,
   > `<command-that-prints-the-key> | kbase auth add <provider>`, which the user runs, or you run with
   > the key-printing command the user names; never ask for the key. Then `models` lists that
   > provider's ids and `configure` with `model-map` writes the choice.

2. **The maintaining.md edge bullet, lines 594–601.** Rewrap it at most 101 characters per line, as
   in edit 1. Make `drop-inbound-edges`' clause name the edges unambiguously: the `supports` edges
   out of the claim into other nodes, and every `references`, `lifts`, `refutes` or experiment's
   `supports` edge into it. Change no other wording in the bullet. Its drop-and-re-add procedure
   stays.

**Done-line:**

- `just test-changed` passes.
- `git grep -n -E 'apiKeyFile|auth add|KBASE_API_KEY' -- ':!*.md'` → exactly one hit: the edit-1
  line in `adjagent/definitions/kbase.py`.
- `just render latest`, then `just render-diff pre-wp3`. It names exactly two pairs:
  `skills/kbase/references/building.md` and `skills/kbase/references/maintaining.md`.
  - `diff -u rendered/pre-wp3/skills/kbase/references/building.md rendered/latest/skills/kbase/references/building.md`
    shows only edit 1.
  - `diff -u rendered/pre-wp3/skills/kbase/references/maintaining.md rendered/latest/skills/kbase/references/maintaining.md`
    shows only edit 2.

**Return:** the done-line results, and both edited spans quoted before and after.

---

## WP4 — the claude guardrail reads `$CLAUDE_PROJECT_DIR` as the project root

### Outcome

`guardrail.pl` reads a shell path word that opens with `$CLAUDE_PROJECT_DIR` or
`${CLAUDE_PROJECT_DIR}` as that path under the project directory. So a write into scratch spelled
that way is let through, and a write elsewhere is judged by today's rules, against the expanded path
— a `cp`/`mv` destination's `-d`/`-f` tests included. File-tool arguments are read literally.
opencode exports no project-directory variable, so `guardrail.ts` is unchanged.

### Invariants

1. **Shell path words only.** A *shell path word* is a word of a Bash command that the guardrail
   reads as a path. These are the words the shell-side callers of `path_of` pass it, at
   `guardrail.pl` lines 65 (`free`: redirect and `tee` targets), 114–115 (`cp`/`mv`), 189 and 195
   (`shell_index_reason`). The expansion never applies to a file-tool argument (`index_reason`'s
   calls at lines 206 and 217: `file_path`, `notebook_path`, Grep's and Glob's `path`, and Glob's
   `pattern`). Choose the site so this holds — a shell-side wrapper around `path_of`, for instance,
   which those five call sites use while lines 206 and 217 keep `path_of`.
2. **Exactly one variable, at one position.** The expansion applies only where a shell path word,
   after its surrounding quote is stripped, begins with `$CLAUDE_PROJECT_DIR` or
   `${CLAUDE_PROJECT_DIR}`, followed by `/` or the word's end. A longer name (`$CLAUDE_PROJECT_DIRX`),
   a suffix after the braces (`${CLAUDE_PROJECT_DIR}x`), a modifier (`${CLAUDE_PROJECT_DIR:-x}`) and a
   mid-word occurrence are all read literally.
3. **The value is `$ENV{CLAUDE_PROJECT_DIR}` alone,** read by the expanding code itself. It is never
   `$root` (line 231, `$ENV{CLAUDE_PROJECT_DIR} || $input->{cwd}`) and never `cwd`, and no new
   parameter threads it in. Where the variable is unset or empty, the word stays literal.
4. **The limit is a contract.** This is the only expansion either guardrail performs, and no other is
   added. Edit 3 states it once, in CONVENTIONS.md.
5. **Quote kind is not distinguished.** A single-quoted `'$CLAUDE_PROJECT_DIR/…'` expands like a
   double-quoted one. This is a known miss the change accepts: the form is not habitual, and
   telling the two apart would mean carrying quote state through `redirects()`.

### Precondition

Replaces the global precondition for WP4.

| check | must answer |
|---|---|
| `git status --porcelain --untracked-files=no` | only ` M ACTIVE_PLAN.md` |
| `just test` | passes |

### Facts acted on

Run from the adjagent root.

| fact | command → answer |
|---|---|
| The perl hook takes its root from the environment | `grep -n 'CLAUDE_PROJECT_DIR' adjagent/harnesses/resources/claude/hooks/guardrail.pl` → `231:    my $root = $ENV{CLAUDE_PROJECT_DIR} \|\| $input->{cwd};` |
| `path_of` strips one surrounding quote and resolves lexically | `sed -n '46,50p' adjagent/harnesses/resources/claude/hooks/guardrail.pl` → `sub path_of {`, `  my ($word, $cwd) = @_;`, `  (my $p = $word) =~ s/^["']\|["']\z//g;`, `  return resolve($p =~ m{^/} ? '' : $cwd, $p);` |
| `path_of`'s call sites: five shell-side, two file-tool | `grep -n 'path_of(' adjagent/harnesses/resources/claude/hooks/guardrail.pl` → `65:` "my $abs = path_of($word, $cwd);", `114:` "my $abs = path_of($dest, $cwd);", `115:` "…path_of($_, $cwd)…", `189:` "return $index_path if grep { under(real(path_of($_, $cwd)), $subject) } @ws;", `195:` "return $index_search if grep { under(real(path_of($_, $cwd)), $kb) }…", `206:` "my $at = sub { real(path_of($_[0] // '', $cwd)) };", `217:` "my $base = real(path_of(glob_root($in->{pattern} // ''), path_of($in->{path} // '', $cwd)));" |
| Lines 206 and 217 serve file tools only: the Bash branch returns before `$at` is used | `sed -n '207,209p' adjagent/harnesses/resources/claude/hooks/guardrail.pl` → "  if ($tool eq 'Bash') {", "    return shell_index_reason($in->{command} // '', $cwd, $kb, $subject);", "  }" |
| The test runner always sets `CLAUDE_PROJECT_DIR` for a case, so no case observes it unset | `sed -n '118,119p' tests/test_guardrail.py` → "    if project_dir is not None:", `        env["CLAUDE_PROJECT_DIR"] = str(project_dir)`; `grep -n 'def test_guardrail_pl_takes_the_input_cwd' tests/test_guardrail.py` → `247:` |
| The known-fields set, and the per-implementation case filters | `grep -n -E '^_CASE_FIELDS =\|^_PL_INDEXES =\|^_TS_INDEXES =' tests/test_guardrail.py` → `38:_CASE_FIELDS = {"command", "tool", "input", "reason", "files", "links", "cwd"}`, `68:_PL_INDEXES = [i for i, case in enumerate(_CASES) if _tool(case) in _OPENCODE_TOOLS]`, `69:_TS_INDEXES = [i for i, case in enumerate(_CASES) if _opencode_tool(_tool(case)) is not None]` |
| The kb signal, and the `.index/` path reason, as a case spells them | `grep -n -m1 'SKILL.md' tests/guardrail_cases.json` → `68:` `{"command": "cat kb-root/.index/nodes.yaml", "files": ["@harness@/skills/kbase/SKILL.md", "kb-root/.index/nodes.yaml"], "reason": "kb-root/.index/ holds kbase's records: read them with kbase's \`query\` tool and change them with its \`write\` tool"},` |
| A redirect's reason spells the target as written, quotes stripped | `grep -n 'my file' tests/guardrail_cases.json` → `21:` `{"command": "echo hi > \"my file.txt\"", "reason": "a redirect that writes my file.txt"},` |
| Sentences that become false | `grep -n -E 'block the same calls\|exactly the same calls\|A behaviour change edits both\|runs the table through each\|runs every case of\|one case table through both' SPEC.md CONVENTIONS.md ARCHITECTURE.md README.md` → `SPEC.md:191:` "guardrails block the same calls. …", `CONVENTIONS.md:100:` "…are meant to block exactly the same calls, and nothing at runtime compares", `CONVENTIONS.md:102:` "…A behaviour change edits both and \`tests/guardrail_cases.json\` in one change, and", `CONVENTIONS.md:103:` "…it runs the table through each, under \`bun\`", `ARCHITECTURE.md:437:` "held to one behaviour by \`tests/test_guardrail.py\`, which runs every case of", `README.md:417:` "guardrail parity test (\`tests/test_guardrail.py\`) runs one case table through both guardrails and" |
| A variable-spelled scratch write is refused today | `python3 -c 'import json,sys;print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]},"cwd":sys.argv[2]}))' 'echo x > "$CLAUDE_PROJECT_DIR/.claude-temp/a.txt"' "$PWD" \| CLAUDE_PROJECT_DIR="$PWD" perl adjagent/harnesses/resources/claude/hooks/guardrail.pl; echo "exit=$?"` → output contains `Blocked: a redirect that writes` and `exit=2` |
| opencode's shell exports no project-directory variable | `git -C ../opencode show v2.2.3:packages/core/src/tool/plugin/shell.ts \| grep -n 'invocation.env\.'` → `207:                    invocation.env.AGENT = "1"`, `208:                    invocation.env.OPENCODE = "1"`, `209:                    invocation.env.AI_AGENT \|\|= "opencode"`, `210:                    invocation.env.OPENCODE_SESSION_ID = context.sessionID`, and nothing else |
| A case carries no harness restriction today | `python3 -c "import json;print(sorted({k for x in json.load(open('tests/guardrail_cases.json')) for k in x}))"` → `['command', 'cwd', 'files', 'input', 'links', 'reason', 'tool']` |
| Contract text to change | `grep -n -E 'judged lexically\|resolves relative targets\|is not a boundary' SPEC.md ARCHITECTURE.md CONVENTIONS.md` → `SPEC.md:194:` "…relative target is judged lexically against the working directory of the call…", `ARCHITECTURE.md:174:` "…Its mutation check judges Bash calls only, resolves relative targets", `CONVENTIONS.md:105:` "…redirect forms agents habitually use and points them to the edit tools; it is not a boundary" |

### WP4.1 — expert (`generalist-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, WP4 in full.

**Scope:**

- `adjagent/harnesses/resources/claude/hooks/guardrail.pl`: the expansion, and the five shell-side
  call sites invariant 1 names. Lines 206 and 217, and line 231's `$root`, are unchanged.
- `tests/guardrail_cases.json`, `tests/test_guardrail.py`
- SPEC.md: the guardrail paragraph, lines 189–196
- ARCHITECTURE.md: the `guardrail.pl` paragraph around line 174, and the test paragraph at
  lines 436–441
- CONVENTIONS.md: the "two guardrail implementations change together" bullet, lines 99–107
- README.md: line 417's sentence

**First, record the render baseline.** Before any edit: `just render pre-wp4`.

**Edits:**

1. **`guardrail.pl`:** the expansion, holding invariants 1–3 and 5.
2. **The case table.**
   - **A new optional `harness` field,** `"claude"` or `"opencode"`, runs a case under that
     implementation only. `tests/test_guardrail.py` reads it where `_PL_INDEXES` and `_TS_INDEXES`
     are built (lines 68–69), adds it to `_CASE_FIELDS` (line 38), and names it in the module
     docstring.
   - **Reasons.** Every refused redirect's reason is `a redirect that writes <the target as written,
     quotes stripped>`, as line 21 spells it. A refused `.index/` case's reason is the path reason
     line 68 carries.
   - **New cases,** each with `"harness": "claude"`:
     - allowed: `echo x > "$CLAUDE_PROJECT_DIR/@scratch@/a.txt"`
     - allowed: `echo x > ${CLAUDE_PROJECT_DIR}/@scratch@/a.txt`
     - allowed: `echo x | tee "$CLAUDE_PROJECT_DIR/@scratch@/log"`
     - refused: `echo x > "$CLAUDE_PROJECT_DIR/out.txt"` → `a redirect that writes $CLAUDE_PROJECT_DIR/out.txt`
     - refused: `echo x > "$CLAUDE_PROJECT_DIRX/@scratch@/a.txt"` → `a redirect that writes $CLAUDE_PROJECT_DIRX/@scratch@/a.txt`
     - refused: `echo x > "${CLAUDE_PROJECT_DIR}x/@scratch@/a.txt"` → `a redirect that writes ${CLAUDE_PROJECT_DIR}x/@scratch@/a.txt`
     - refused: `echo x > "a/$CLAUDE_PROJECT_DIR/@scratch@/a.txt"` → `a redirect that writes a/$CLAUDE_PROJECT_DIR/@scratch@/a.txt`
     - refused: `echo x > "$HOME/@scratch@/a.txt"` → `a redirect that writes $HOME/@scratch@/a.txt`
     - refused on a kb install: `cat "$CLAUDE_PROJECT_DIR/kb-root/.index/nodes.yaml"`, with
       `"@harness@/skills/kbase/SKILL.md"` and `kb-root/.index/nodes.yaml` in `files` → the path
       reason
     - allowed on a kb install: `"tool": "Read"` with `file_path`
       `$CLAUDE_PROJECT_DIR/kb-root/.index/nodes.yaml`, and the same `files`. The argument is not
       expanded. Read literally, it is a relative path, resolving to `<cwd>/$CLAUDE_PROJECT_DIR/…`,
       outside the subject, so the hook lets it through: `reason` null. HEAD's hook answers the
       same: exit 0, no output.

     No existing case changes.
   - **A named test,** beside `test_guardrail_pl_takes_the_input_cwd_as_root_without_claude_project_dir`
     (line 247). With `CLAUDE_PROJECT_DIR` unset and the input `cwd` set to the root,
     `echo x > "$CLAUDE_PROJECT_DIR/<scratch>/a.txt"` is refused, with reason
     `a redirect that writes $CLAUDE_PROJECT_DIR/<scratch>/a.txt`.
3. **Contract documents.**
   - **SPEC.md, lines 189–196.**
     - State that the claude guardrail reads a shell path word opening with `$CLAUDE_PROJECT_DIR`
       as under the project directory, that file-tool arguments are read literally, and that no
       other variable is read.
     - Line 191's "Both guardrails block the same calls" becomes: they block the same calls but
       that one spelling, which only the claude guardrail reads.
   - **ARCHITECTURE.md.**
     - The `guardrail.pl` paragraph (around line 174) states the expansion's site, its rule and its
       value.
     - The test paragraph, lines 436–441: "runs every case … through `guardrail.pl` … and through
       `guardrail.ts`" becomes every case not restricted by its `harness` field, with that field
       named.
   - **CONVENTIONS.md, the guardrail bullet.** Add the sentence invariant 4 names.
     - Line 100's "are meant to block exactly the same calls" gains the `$CLAUDE_PROJECT_DIR`
       exception.
     - Line 102's "A behaviour change edits both" stays, but a change to that expansion edits
       `guardrail.pl` alone.
     - Line 103's "it runs the table through each" becomes each case not restricted by `harness`.
     - The "not a boundary" sentence stays.
   - **README.md:417.** "runs one case table through both guardrails" becomes one case table
     through both, each case under every guardrail its `harness` field allows.

**Done-line:**

- `just test-changed` passes, `tests/test_guardrail.py` included, under `bun` and `perl`.
- The third fact row, re-run: the hook prints nothing, and the last line is `exit=0`.
- `just render latest`, then `just render-diff pre-wp4`: exactly one pair,
  `hooks/guardrail.pl`.

**Return:** the done-line results, and the `guardrail.pl` diff.

---

## WP6 — the kbase skill follows kbase 0.10.0's offered surface

### Outcome

Every adjagent text a session reads about kbase is true against kbase 0.10.0's offered surface, and
carries only what that surface does not.

- **The offered surface** is the MCP surface and the maintained block kbase stamps into
  `kb-root/AGENTS.md` and `kb-root/CONVENTIONS.md` (row S28). The MCP surface is the server
  instructions, the tool and parameter descriptions, and the resource text.
- **Who reads the stamped documents.** The reading and maintaining references have the session read
  both documents (T5). The building and scoring references have it read neither, and restate
  nothing they say.
- **The convention follows.** WP6.3 extends the CONVENTIONS leaf "Skill references omit offered
  surface" to count the stamped blocks (E11).
- **The text in scope** is the `kbase` skill's router and references, the kb clauses, mage's kbase
  project rule, README.md's kb sections, and the SPEC and ARCHITECTURE leaves that describe the kb
  set.
- **The write-contract test module is gone.** It pinned kbase's write contract as skill text, and
  kbase's `write` help now carries that contract.

### Precondition

This table replaces "Preconditions for every package" for WP6. Run it before WP6.1.

| check | must answer |
|---|---|
| `git status --porcelain --untracked-files=no` | nothing, or only ` M ACTIVE_PLAN.md` |
| `just test` | passes |
| `kbase --version` | `0.10.0` |
| `grep -n 'KBASE_MIN_VERSION = ' adjagent/definitions/kbase.py` | `12:KBASE_MIN_VERSION = "0.10.0"` |
| `mkdir -p .claude-temp/wp6 && git rev-parse --short HEAD > .claude-temp/wp6/base && cat .claude-temp/wp6/base` | any commit whose `adjagent/`, `tests/`, `README.md` and `PROJECT_DOCS/` match `b33d582`'s: `git diff --stat b33d582 "$(cat .claude-temp/wp6/base)" -- adjagent tests README.md PROJECT_DOCS` prints nothing. This is **WP6's base** |

### Shell definitions for every fact row

Every fact row below runs from the adjagent root in one shell call that begins with these lines. A
row runs exactly as written after them:

```sh
B=$(cat .claude-temp/wp6/base)
S=.claude-temp/wp6/surface.jsonl
d=.claude-temp/wp6/kbfact
I='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"wp6","version":"0"}}}'
```

The T rows read WP6's base through `git show "$B":<path>` or `git grep … "$B"`. That way they
answer the same after WP6.1 has edited the working tree.

### Capturing the surface

WP6.1 and WP6.2 each run these three blocks from the adjagent root before their fact rows. WP6.3
needs none of them: its rows read only `$B` and the working tree. The blocks write only under
`.claude-temp/wp6/`, and the S rows read what they write.

**A — the MCP surface.** Writes 12 JSON-RPC replies, one per line:

```sh
mkdir -p .claude-temp/wp6
I='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"wp6","version":"0"}}}'
N='{"jsonrpc":"2.0","method":"notifications/initialized"}'
R() { printf '{"jsonrpc":"2.0","id":"%s","method":"resources/read","params":{"uri":"kbase://%s"}}' "$1" "$1"; }
printf '%s\n' "$I" "$N" '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' '{"jsonrpc":"2.0","id":3,"method":"resources/list"}' "$(R help/write)" "$(R help/query)" "$(R help/score)" "$(R help/build)" "$(R help/remove-node)" "$(R help/verify)" "$(R help/configure-providers)" "$(R help/find)" "$(R model-hints)" | kbase mcp > .claude-temp/wp6/surface.jsonl
wc -l < .claude-temp/wp6/surface.jsonl
```

The last line must print `12`.

**B — every command's help, for reading.** A `kbase://help/<name>` resource carries the same body
as `kbase <name> --help`, except that MCP spells an argument without dashes:

```sh
for c in $(kbase --help | awk '/^Commands:/{f=1;next} f&&NF{print $1}'); do echo "### $c"; kbase "$c" --help; done > .claude-temp/wp6/cli-help.txt 2>&1
```

**C — a scratch KB with one claim.** The `git init` and the commit happen in the scratch directory
only, never in either repository:

```sh
d=.claude-temp/wp6/kbfact; command rm -rf "$d"; mkdir -p "$d" && git -C "$d" init -q && git -C "$d" -c user.email=x@y -c user.name=x commit -q --allow-empty -m init && kbase --project-dir "$PWD/$d" init >/dev/null && mkdir -p "$d/kb-root/v1" && printf '# V1\n\nTwo evens sum to an even.\n' > .claude-temp/wp6/kbfact/kb-root/v1/index.md && printf 'entry:\n  - {operation: add-claim, title: Even sum, rationale: r, document: v1/index.md, line: 3, snippet: Two evens}\n' | kbase --project-dir "$PWD/$d" write | grep -E '^outcome|kb-summary'
```

It must print `outcome: "done"` and `    - "v1/kb-summary.md"`.

### What kbase 0.10.0 serves

The facts are pinned to the installed binary's own output. `../kbase` has no `v0.10.0` tag. Row S1
establishes that the binary was built from a tarball whose tree is identical to kbase commit
`c23f685`. The rows that read `../kbase` read that commit. `$S`, `$d` and `$I` are set by "Shell
definitions for every fact row".

| # | fact | command → answer |
|---|---|---|
| S1 | The installed binary was built from the local tap tarball, whose tree is kbase commit `c23f685` | `python3 -I -c "import json;print(json.load(open('/opt/homebrew/Cellar/kbase/0.10.0/INSTALL_RECEIPT.json'))['source']['path'])"` → `/Users/agent-user/projects/kbase/bin/tap/kbase.rb`; `grep -n '^  url' ../kbase/bin/tap/kbase.rb` → `5:  url "file:///Users/agent-user/projects/kbase/bin/tap/kbase-0.10.0.tar.gz"`; `t=.claude-temp/wp6/tree; command rm -rf $t; mkdir -p $t/tar $t/head && tar -xzf ../kbase/bin/tap/kbase-0.10.0.tar.gz -C $t/tar && git -C ../kbase archive c23f685 \| tar -x -C $t/head && diff -rq -x '._*' $t/tar/kbase-0.10.0 $t/head` → no output |
| S2 | The version is 0.10.0 | `kbase --version` → `0.10.0`; `git -C ../kbase show c23f685:internal/version/version.go \| grep -n 'const Current'` → `8:const Current = "0.10.0"` |
| S3 | The server offers 16 tools | `grep -o '"name":"[a-z-]*","description"' $S \| cut -d'"' -f4 \| tr '\n' ' '` → `build build-trail cancel query configure-models configure-providers export-latex init models probe score show-config status update-format verify write`, and nothing else |
| S4 | The query tool's operations | `grep -o '"enum":\["citations-of"[^]]*\]' $S` → `"enum":["citations-of","edges","find","show","stats","trace"]` |
| S5 | Every write is one batch through the `write` tool, and these are its ops | `grep -o 'The write ops: [^.]*\.' $S` → `The write ops: add-analysis, add-axiom, add-citation, add-claim, add-edge, add-experiment, add-work, edit-analysis, edit-axiom, edit-claim, edit-edge, edit-experiment, edit-work, move-node, remove-edge, remove-node, restore-demoted.` |
| S6 | Every command, op and query the skill names today that 0.10.0 lacks | `for c in refresh rewind-build deps strength gated-on referenced-by subtree configure set-rigor set-bearing insert-claim-entry insert-work-entry mark-claim-in-leaf add-rests-on resolve-demoted drop-claim-node drop-claim-edges drop-inbound-edges render-citation; do kbase $c 2>&1 \| grep -q 'unknown command' && printf '%s ' "$c"; done` → all 19 names, in that order |
| S7 | The runner snippets' other commands exist | `kbase --help \| grep -E '^  (init\|verify\|update-format\|stats\|score\|export-latex) ' \| awk '{print $1}' \| tr '\n' ' '` → `export-latex init score stats update-format verify` |
| S8 | `auth`, `wait` and `mcp` are CLI-only | `kbase mcp --help \| grep -n -E 'Three commands are served\|wait, since'` → `9:` "…Three commands are served", `10:` "by no tool: auth, since a key never travels through MCP; wait, since an MCP" |
| S9 | `build` and `score` return once the run has started, handing back a `wait` shell line; no tool waits | `grep -o -F 'Its result gives \"pid\", \"state-dir\" and \"wait\"' $S \| wc -l` → `4` (both tool descriptions and both help resources) |
| S10 | The server instructions carry four rules the skill restates today: `.index/`, rigor and bearing values only from the user, `commit` on every batch, and never ask for a key. They also defer to the skill | `grep -o -F 'never read or write anything under it' $S`, `grep -o -F 'a work'"'"'s rigor and a founds edge'"'"'s bearing stay pending until the user gives one' $S`, `grep -o -F 'Pass `commit` on every write batch' $S`, `grep -o -F 'never ask for a key or read a key file into the conversation' $S`, `grep -o -F 'The kbase skill carries the workflow.' $S` → each prints its pattern at least once |
| S11 | Under `--project-dir-required`, the instructions already tell the session to get the project path from the user | `printf '%s\n' "$I" \| kbase mcp --project-dir-required \| grep -o -F 'Get that path from the user, by asking or by proposing one for them to confirm.'` → that sentence |
| S12 | List queries return complete answers: there is no cap and no `truncated` | `grep -o -F 'find, edges, trace and citations-of return their complete answers' $S \| head -1` → that phrase |
| S13 | Resources: one help resource per tool and op, plus `query`, `write` and `model-hints` | `grep -o '"uri":"kbase://[^"]*"' $S \| sort -u \| wc -l` → `40`; `grep -c '"uri":"kbase://model-hints"' $S` → at least `1` |
| S14 | Starting over is removing `kb-root/` or running `build-trail`'s started-at command. `rewind-build` and the `check: inputs` refusal are gone | `kbase build --help \| grep -n -E 'is how to start over'` → `26:kb-root/ is how to start over: kbase does not inspect half-built state. \`kbase build-trail\` lists each` |
| S15 | `score` `resume` takes no run id. `rescore-manual` is a boolean. No pass reaches a work's rigor or a `founds` bearing | `grep -o -F 'continues the repository'"'"'s most recent score run' $S \| head -1`, `grep -o '"rescore-manual":{"type":"boolean"' $S`, `grep -o -F 'No pass reaches a work'"'"'s rigor' $S \| head -1` → each prints its pattern |
| S16 | `remove-node` removes every edge naming the node. It is refused while a citation of the node survives. Its result's `removed-edges` is what re-pointing reads | `kbase remove-node --help \| grep -n -E 'every edge naming it\|citation of it\|removed-edges'` → `5:`, `13:`, `21:` |
| S17 | `verify` refusals carry their remedies. An empty batch re-derives the summary pages. A bare id in prose is a fault | `grep -o -F 'remedy: an empty write batch, `write {\"entry\":[]}`' $S \| head -1`, `grep -o -F 'check: bare-id' $S \| head -1` → each prints its pattern |
| S18 | Provider setup is `configure-providers`, then `configure-models`. Its result's `next` gives the key step, so the skill need not | `grep -o -F 'next gives the steps' $S \| head -1`, `grep -o -F '<command-that-prints-the-key> \| kbase auth add <name>' $S \| head -1` → each prints its pattern |
| S19 | `find` covers every kind, and `label` reaches a work by its citation key | `kbase find --help \| grep -n -E 'across every kind\|label \(a work'` → `3:`, `5:` |
| S20 | A work's id is minted, not built from its key. A second add of a standing title is refused, and nothing is adopted | `kbase add-work --help \| grep -n 'wrk-<minted>'` → `3:`; `kbase add-claim --help \| grep -n 'nothing is'` → `9:` ("…nothing is", with "adopted." on line 10) |
| S21 | A batch is all or nothing, and ids minted in one batch take their edges in the next | `kbase write --help \| grep -n -E 'empty batch\|second, from the id\|all or nothing'` → `5:`, `13:`, `15:` |
| S22 | `update-format` rewrites only kbase's maintained block in `AGENTS.md`, `CONVENTIONS.md` and `README.md`. The `strengthen-by` field is dropped in conversion | `kbase update-format --help \| grep -n -E 'vvv-kbase\|unfenced\|strengthen-by'` → `15:`, `18:`, `42:` |
| S23 | Statement markers are `<!-- kbase-id: <id> -->` | `grep -o 'kbase-id: clm-[a-z0-9]*' $d/kb-root/v1/index.md` → one `kbase-id: clm-…` |
| S24 | The summary pages are `kb-summary.md`. A node in prose is referred to only by a citation. The stamped `AGENTS.md` names the `kbase` skill | block C prints `v1/kb-summary.md`; `grep -o -F 'In an authored file, a reference to a node is a structured field, a marker or a link, never an id' $d/kb-root/CONVENTIONS.md` and `grep -o -F 'Work it through the `kbase` skill' $d/kb-root/AGENTS.md` → each prints its pattern |
| S25 | `show` prints an unscored claim's `rigor` as `null` | `kbase --project-dir "$PWD/$d" show "$(kbase --project-dir "$PWD/$d" find \| grep -o 'clm-[a-z0-9]*' \| head -1)" \| grep -E '^ +(rigor\|build_status):'` → `    rigor: null`, `    build_status: "unsubstantiated"` |
| S26 | kbase's scoring-scheme documents left its repository root, and so did its MCP wiring guide | `git -C ../kbase ls-tree --name-only c23f685 \| grep -c -E 'SCORING_SCHEME\|INTEGRATING_KBASE'` → `0`; `git -C ../kbase show c23f685:PROJECT_DOCS/SPEC/scoring/index.md \| grep -n 'entry-point.md'` → `5:`, `6:`; `git -C ../kbase show c23f685:README.md \| grep -n '^### Using kbase from an agent harness (MCP)'` → `408:` |
| S27 | That `PROJECT_DOCS/` tree is not on kbase's `main` yet | `git -C ../kbase ls-tree -r --name-only origin/main \| grep -c '^PROJECT_DOCS/'` → `0` |
| S28 | What the stamped blocks state. `kb-root/AGENTS.md` (lines 3–23) carries: the `.index/` rule; rigor and bearing values only from the user; what the tree holds (a built leaf is a verbatim, mechanical rendering, and text a maintainer adds lives in its own place); read `CONVENTIONS.md` before any work beyond reading. `kb-root/CONVENTIONS.md` (lines 3–24) carries: authored versus derived (the derived side includes the `kb-summary.md` pages and the sheets); records and statement markers are written only by a write op; a node is referenced by a field, a marker or a link, never a loose id; no agent edits inside the maintained block, and text outside it is the KB's own; axioms go in `axioms.md` | after block C: `grep -n -E 'never read or write anything under it\|Rigor and bearing values are judgements\|^## What this tree holds\|verbatim, mechanical rendering' $d/kb-root/AGENTS.md \| cut -d: -f1 \| tr '\n' ' '` → `7 9 11 15`; `grep -n -E '^## Authored versus derived\|written only by a write op\|no agent edits inside it\|axioms go in' $d/kb-root/CONVENTIONS.md \| cut -d: -f1 \| tr '\n' ' '` → `6 12 21 23`; `grep -n -E 'vvv-kbase the block\|kbase-\^\^\^ -->' $d/kb-root/AGENTS.md $d/kb-root/CONVENTIONS.md \| cut -d: -f2 \| tr '\n' ' '` → `3 23 3 24`. Read both blocks in full before editing |
| S29 | Under `--project-dir-required`, every one of the 16 tool schemas requires `project-dir` | `printf '%s\n' "$I" '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \| kbase mcp --project-dir-required \| grep -o '"required":\[[^]]*"project-dir"[^]]*\]' \| wc -l` → `16` |
| S30 | `score` takes `dry-run` and `scoring-model` | `kbase score --help \| grep -n -E '^  --(dry-run\|scoring-model) ' \| cut -d: -f1 \| tr '\n' ' '` → `62 68` |
| S31 | `find` takes `path`, a leaf or a directory under `kb-root/` | `kbase find --help \| grep -n -E '^  --path ' \| cut -d: -f1` → `29` |
| S32 | The term "claim-rigor" appears nowhere in 0.10.0's surface or its stamped documents | after blocks A–C: `cat .claude-temp/wp6/cli-help.txt $S $d/kb-root/AGENTS.md $d/kb-root/CONVENTIONS.md \| grep -c -i 'claim-rigor'` → `0` |

### Where adjagent's text stands

Every row reads WP6's base, `$B`, so it answers the same whether or not an earlier dispatch has
edited the working tree. A line number below is a line of the file at `$B`. WP6.1 runs first, so
for it these are also the working tree's lines. WP6.2 locates its spans by heading and quoted text
instead.

`T1PAT` is the T1 pattern. Done-lines reuse it: set it in the same shell call, after the shell
definitions.

```sh
T1PAT='refresh|rewind-build|deps|gated-on|referenced-by|set-rigor|set-bearing|insert-(claim|analysis|experiment|work)-entry|mark-claim-in-leaf|add-rests-on|resolve-demoted|drop-claim-node|drop-claim-edges|drop-inbound-edges|render-citation|claim-rigor\.md|strengthen_by|strengthen-by|model-map|INTEGRATING_KBASE_VIA_MCP'
```

| # | fact | command → answer |
|---|---|---|
| T1 | Spans naming something S6 lists, or a retired name | `git grep -n -w -E "$T1PAT" "$B" -- adjagent/definitions/kbase.py adjagent/clauses.py adjagent/harnesses/mage.py README.md PROJECT_DOCS \| cut -d: -f2,3 \| tr '\n' ' '` → exactly `PROJECT_DOCS/SPEC/deployed-surfaces/base-and-kb-installs.md:41 PROJECT_DOCS/SPEC/deployed-surfaces/base-and-kb-installs.md:42 README.md:357 README.md:371 adjagent/clauses.py:447 adjagent/clauses.py:451 adjagent/definitions/kbase.py:176 adjagent/definitions/kbase.py:196 adjagent/definitions/kbase.py:199 adjagent/definitions/kbase.py:200 adjagent/definitions/kbase.py:202 adjagent/definitions/kbase.py:206 adjagent/definitions/kbase.py:209 adjagent/definitions/kbase.py:210 adjagent/definitions/kbase.py:211 adjagent/definitions/kbase.py:222 adjagent/definitions/kbase.py:226 adjagent/definitions/kbase.py:231 adjagent/definitions/kbase.py:314 adjagent/definitions/kbase.py:332 adjagent/definitions/kbase.py:351 adjagent/definitions/kbase.py:353 adjagent/definitions/kbase.py:423 adjagent/definitions/kbase.py:430 adjagent/definitions/kbase.py:432 adjagent/definitions/kbase.py:514 adjagent/definitions/kbase.py:518 adjagent/definitions/kbase.py:525 adjagent/definitions/kbase.py:551 adjagent/definitions/kbase.py:562 adjagent/definitions/kbase.py:563 adjagent/definitions/kbase.py:565 adjagent/definitions/kbase.py:571 adjagent/definitions/kbase.py:583 adjagent/definitions/kbase.py:584 adjagent/definitions/kbase.py:593 adjagent/definitions/kbase.py:596 adjagent/definitions/kbase.py:598 adjagent/definitions/kbase.py:601 adjagent/definitions/kbase.py:605 adjagent/definitions/kbase.py:608 adjagent/definitions/kbase.py:616 adjagent/definitions/kbase.py:618 adjagent/definitions/kbase.py:619 adjagent/definitions/kbase.py:620 adjagent/definitions/kbase.py:647 adjagent/definitions/kbase.py:649 adjagent/definitions/kbase.py:655 ` |
| T2 | Where the reference bodies start. The router body is lines 27–105 | `git show "$B":adjagent/definitions/kbase.py \| grep -n -E 'path="references/' \| cut -d: -f1 \| tr '\n' ' '` → `108 262 359 458 661 667 ` (reading, building, scoring, maintaining, scoring-system, installing) |
| T3 | The kb clause and its paragraphs | `git show "$B":adjagent/clauses.py \| grep -n -E '^def kb_orientation\|^KB_RUNNER_TARGETS\|^\*\*(Authored\|Per-project\|Metadata is\|The off-graph)\|claim-rigor\.md' \| cut -d: -f1 \| tr '\n' ' '` → `434 440 447 449 451 453 455 460 `. These are `KB_RUNNER_TARGETS`, `def kb_orientation`, the claim-graph bullet (naming `claim-rigor.md`), the endcap (which builds a work's id from its citation key, against S20), authored vs derived, metadata, per-project facts, and `def kb_orientation_docs` |
| T4 | Spans the surface now carries or contradicts | `git show "$B":adjagent/definitions/kbase.py \| grep -n -E 'committing is not yours\|refresh. — idempotent\|Two things it never scores\|Then offer to set it up\|Starting over\|A list result is capped' \| cut -d: -f1 \| tr '\n' ' '` → `218 310 353 417 616 634 `. They are: list capped (against S12), setup offer (S18), starting over (S14), two things never scored (S10, S15), refresh step (S6, S17), and the worktree hazard (its commit clause; see WP6.2 item 3) |
| T5 | Only the reading and maintaining references have the session read the stamped documents | `git show "$B":adjagent/definitions/kbase.py \| grep -n 'kb_orientation_docs' \| cut -d: -f1 \| tr '\n' ' '` → `111 472 ` (reading, maintaining) |
| T6 | Mage's project rule renders in the router, so in `skills/kbase/SKILL.md` only | `git show "$B":adjagent/definitions/kbase.py \| grep -n 'KBASE_PROJECT_RULE'` → `41:{clauses.KBASE_PROJECT_RULE}` |
| T7 | Mage's project rule restates S11 and S29 | `git show "$B":adjagent/harnesses/mage.py \| grep -n -E 'every kbase tool call\|run the probes above' \| cut -d: -f1 \| tr '\n' ' '` → `41 44 `. Lines 41–44 read "…every kbase tool call passes \`project-dir\` … and a call without it fails. Establish that path before anything else, asking the user where nothing in the session names it, and run the probes above with \`.\` read as that path…" |
| T8 | The test module pins kbase's write contract as skill text, and nothing else refers to it | `git show "$B":tests/test_write_op_contract_sources.py \| grep -n '^    ("' \| cut -d'"' -f2 \| tr '\n' ' '` → `entry per call closed set mints the id unchanged adopts wrote nothing offending lock identical three times contended failed `; `git grep -n test_write_op_contract_sources "$B" -- ':!ACTIVE_PLAN.md' \| wc -l` → `0` |
| T9 | The reading test pins the harness tool name | `git show "$B":tests/test_adjagent.py \| grep -n 'mcp__kbase__query' \| cut -d: -f1` → `439` |
| T10 | The scoring-system reference links files S26 shows gone | `git show "$B":adjagent/definitions/kbase.py \| grep -n -o -E 'blob/main/[A-Z_]+\.md' \| tr '\n' ' '` → `663:blob/main/STRENGTH_SCORING_SCHEME.md 664:blob/main/RIGOR_AND_BEARING_SCORING_SCHEME.md ` |
| T11 | WP3's key line is now kbase's (S18) | `git grep -n -E 'apiKeyFile\|auth add\|KBASE_API_KEY' "$B" -- ':!*.md' \| cut -d: -f2,3` → `adjagent/definitions/kbase.py:312`, and nothing else |
| T12 | `reading.md` uses "claim-rigor entry" (absent from 0.10.0, S32), and the "Assisting derivations" paragraph names `deps` | `git show "$B":adjagent/definitions/kbase.py \| grep -n -E 'claim-rigor entry\|^\*\*Assisting derivations\|\(.deps. on the claim\)' \| cut -d: -f1 \| tr '\n' ' '` → `137 141 221 222 ` |

### Steering principles

- **The skill carries only what kbase's offered surface does not.** The CONVENTIONS leaf "Skill
  references omit offered surface" states the rule. Apply this test to every line: would it have to
  change whenever kbase rewords its own surface? If yes, it goes, unless an agent cannot act
  without it. The preferred replacement is a pointer: `kbase://help/<name>`, or the tool's
  description. A reference names tools and resources by their MCP spelling, never by the CLI form.
- **The stamped blocks are offered surface.** WP6.3's edit E11 records this in the CONVENTIONS
  leaf.
  - Adjagent text does not restate what kbase's maintained block in `kb-root/AGENTS.md` or
    `kb-root/CONVENTIONS.md` says (S28). It keeps only what an agent cannot get from those blocks
    or from the MCP surface.
  - The reading and maintaining references have the session read both documents (T5, after WP6.1
    item 5), so for them the stamped text is surface already in hand.
  - The building and scoring references have the session read neither. They must restate nothing
    the stamped blocks say, and they need no read.
- **What stays is what adjagent alone knows:**
  - when the skill applies, and how it routes between its references
  - how to locate the KB
  - the harness tool prefix (`clauses.MCP_TOOL_PREFIX`)
  - running a `wait` line as a background shell command
  - install and version check, and the runner targets
  - the user's decisions: which model, which values, when kbase runs, who runs a reset, whether a
    write batch commits
  - the editorial and judgement guidance a session needs that kbase does not give: what to promote
    or park, which premises a derivation consumes, the volume-order heuristic, the hazards, one live
    writer
- **No interleaving.** Usage guidance for a kbase field, command or outcome belongs on kbase's
  surface. Where the skill needs kbase to say something it does not, the line goes, and the need is
  listed under "Requests to kbase" below. It is never rewritten into the skill.
- **The contract documents and README do not enumerate kbase's perishable names** — tools,
  operations, arguments, fields — unless strictly necessary. They keep adjagent's own facts.
- **Settled, not reopened:**
  - `KBASE_MIN_VERSION` stays `"0.10.0"`.
  - The runner snippets stand (S7).
  - The guardrail is unchanged.
  - `rendered/reference*` is retaken only at release close.

### Requests to kbase

None of these is written into the skill. The coordinator relays them to kbase.

1. **`write`, outcome `retry`:** say what a session does next — re-issue the identical batch, and how
   many times before reporting the KB as contended. The skill's bound ("re-issue the identical
   call, unchanged, up to three times", in `maintaining.md`) leaves with WP6.2.
2. **Serve the strength model and the band thresholds** as a resource. The model is
   `strength = min(max(derivation, every lift), every cap)`, with pending premises left out. The
   thresholds are the five bands `stats` names. Today they live only in kbase's
   `PROJECT_DOCS/SPEC/scoring/` (S26), so `reading.md` keeps its own statement of the model, and
   `scoring-system.md` links documents that are not served.
3. **`show` and the query help disagree on how an unscored value reads.** `show` prints
   `rigor: null` for an unscored claim (S25). `kbase://help/query` says such a value "reads
   *pending*".
4. **`kbase://model-hints`: say what drives a role's wall clock.** The decision role asks one
   question per candidate link, so the number of links, not the model alone, sets that walk's time.
   `building.md` carries this today ("The decision model answers one ask per candidate link"), and
   it leaves with WP6.2.
5. **The server instruction "Pass `commit` on every write batch" (S10) reads as mandatory.** Ask
   that it read as recommended, leaving whether a batch commits `kb-root/` to the user.

### WP6.1 — expert (`python-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, WP6 from "Outcome" through "Requests to kbase", and this
section.

**Scope:**

- `adjagent/definitions/kbase.py`: the router body and the `references/reading.md` body
- `adjagent/clauses.py`: `kb_orientation` and `kb_orientation_docs`
- `adjagent/harnesses/mage.py`: `_KBASE_PROJECT_RULE`
- `adjagent/harness.py:113`: the `kbase_project_rule` field's comment

**First, record the render baselines.** Before any edit, and after blocks A–C:

1. `just render pre-wp6`
2. `just render pre-wp6-opencode --harness=opencode --model-tier-map=all=inherit`
3. `just render pre-wp6-mage --harness=mage`

**Edits.** Read every span below against blocks A–C's output and the S rows. Each item states the
outcome. The wording is yours.

1. **Router.** "claim markers" (line 59) becomes "statement markers" (S23). Everything else in the
   router stands unless the surface contradicts it, and you report anything you change beyond
   this item.
2. **`reading.md`, the queries (lines 189–219).**
   - The queries are operations of the one tool `` `{clauses.MCP_TOOL_PREFIX}query` ``. Keep that
     tool name in backticks, because T9's test asserts it.
   - `kbase://help/query` says what the operations share, and `kbase://help/<operation>` gives each
     one's arguments.
   - What stays is routing a user's need to an operation (S4), each named once, with no argument
     restated beyond what the routing itself needs. The needs are:
     - a result named in words, resolved to an id
     - one node's record
     - one hop of edges
     - the chain bearing on a claim, or what a claim's strength reaches
     - shaky, high-leverage and unscored claims
     - who cites a node
   - Keep adjagent's user-experience rules: the user never has to know or guess an id; lead with
     the name and the strength; surface a citation of a node on request rather than following it.
   - Cut `deps`, `strength` as an operation, `gated-on`, `referenced-by`, `strengthen_by` (S6, S22),
     and the "capped … truncated" paragraph (S12).
3. **`reading.md`, claim rigor and strength (lines 135–187).**
   - The derivation model stays (request 2).
   - Cut whatever restates S10 or the query help, such as "pending is unscored, not weak" stated as
     a rule.
   - Rewrite the spans T1 lists for this range: `deps`, and "`strength` without `pending`".
   - Do not state the literal form a pending value prints in (S25).
   - The band table goes: `show` and `find` report the band by name (S25 shows `build_status`).
   - "claim-rigor entry" (lines 137 and 141, T12) names nothing in 0.10.0 (S32). It becomes the
     node's record, which `show` returns.
4. **`reading.md`, "Assisting derivations" and the works paragraph (lines 221–234).**
   - Line 222's "(`deps` on the claim)" becomes `trace` with `direction: in`, which walks the whole
     chain bearing on the claim and gives each edge's contribution (T12, S4).
   - Lines 226 and 231 name `deps` for a claim's own edges, and they become `edges` with the
     claim's `id`.
   - `find` reaches works by `label`, the citation key (S19), and a work's id is minted (S20). So
     "`find` does not reach works … build the id from the citing leaf's own citation key" becomes:
     find the work by the citing leaf's key.
5. **`kb_orientation` and `kb_orientation_docs`.** First read both stamped blocks in full:
   `.claude-temp/wp6/kbfact/kb-root/AGENTS.md` lines 3–23 and
   `.claude-temp/wp6/kbfact/kb-root/CONVENTIONS.md` lines 3–24 (S28).
   - **`kb_orientation_docs`** has the session read both `kb-root/AGENTS.md` and
     `kb-root/CONVENTIONS.md` once, at the point its `when=` names. Keep the `axioms.md` sentence.
   - **Cut from `kb_orientation` whatever the stamped blocks or the MCP surface state.** Three
     paragraphs go whole:
     - "Authored vs. derived" (CONVENTIONS, authored versus derived)
     - "Metadata is written by the tools" (CONVENTIONS: written only by a write op)
     - the seeding and maintenance half of "Per-project facts" (CONVENTIONS, the maintained
       documents)

     Cut the spans that restate the leaf as a verbatim rendering (AGENTS, what this tree holds),
     and anything S10's instructions carry.
   - **What remains is adjagent's own system model, made true against 0.10.0:**
     - the two graphs and the summary's routing role
     - the claim graph: a node's host, the scoring relations, and why `references` and `demoted`
       differ
     - the off-graph endcap
     - "this set edits neither orientation document"
     - the seat line

     Within it:
     - The register page `claim-rigor.md` becomes the summary pages, preferred to the file name
       (S24).
     - A work's id is minted, and its citation key is its `label` (S20).
     - A claim reaches a work by a `founds` edge from the work, not by a "`rests-on` bullet".
     - Derived values are re-derived by kbase after every write, not "rendered by `refresh`"
       (S21).
   - **The router's "KB metadata goes through kbase" section** keeps only what neither surface
     says: take no value from a marker, never grep or count markers, and a value comes from a
     query. The "no metadata byte typed by hand" clause is CONVENTIONS', so it goes.
6. **`_KBASE_PROJECT_RULE`** (T7). Cut what S11's instructions and S29's required `project-dir`
   already tell the session. Keep the rule `.` follows in the router's probes: the project path the session has
   established, not the directory it stands in. The rule stays non-empty, because
   `test_the_kbase_project_rule_paragraph_renders_under_mage_and_drops_under_claude` asserts it.
   `harness.py:113`'s comment then reads: how a kbase session locates its project where the server
   serves many.

Wrap new text as the surrounding text is wrapped: at most 101 characters per body line, with a
two-space continuation indent in bullets.

**Done-line (WP6.1):**

- `just test-changed` reports no failure outside `tests/test_write_op_contract_sources.py`. Any
  failure inside that module is expected: WP6.2 deletes it. Do not edit anything to clear it.
- **T1, limited to WP6.1's scope.** After `just render latest`, run this with `T1PAT` set:
  `grep -n -w -E "$T1PAT" rendered/latest/skills/kbase/SKILL.md rendered/latest/skills/kbase/references/reading.md adjagent/clauses.py adjagent/harnesses/mage.py`
  It must print nothing.
- `just sweep-python` runs, its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.

**Return:** the done-line results, the list of spans you cut with the S row that justified each,
and any further span false against 0.10.0 that lies outside your scope, with its line.

### WP6.2 — expert (`python-coder`, coordinator's model)

**Brief:** §Rule for every dispatch, WP6 from "Outcome" through "Requests to kbase", WP6.1's
return, and this section.

**Scope:**

- `adjagent/definitions/kbase.py`: the `building.md`, `scoring.md`, `maintaining.md` and
  `scoring-system.md` bodies
- `tests/test_write_op_contract_sources.py`: deleted

**Edits.** As in WP6.1, each item states the outcome, and the wording is yours.

- **Text no item below names stands.** Report any change you make beyond the items, with the S
  row that justified it.
- **Find each span by its heading or quoted text, never by line number.** WP6.1 has already moved
  `kbase.py`'s lines. Every quotation below is text at WP6's base, and
  `git show "$B":adjagent/definitions/kbase.py` shows it.

1. **`building.md`.**
   - **What the build takes.** Keep: only the volume roots the user names are inputs, and anything
     else the user typed is said not to be one. Cut the ordering rule and "absolute path": the help
     states how roots resolve and are ordered.
   - **The fast path.** Keep the offer, and the trade stated to the user: structure, not a complete
     KB, and that the fast run is not upgraded later. Cut the mechanics, which `kbase://help/build`
     states.
   - **Launch.** Keep:
     - Tell the user that every stage boundary is a commit.
     - Run the result's `wait` line as a background shell command in the same turn, as printed, and
       relay the outcome when it returns (S9).
     - Relay a refusal's items and remedies.
   - **Provider setup.** It becomes an offer to set the provider up through `configure-providers`,
     then `configure-models`, following each result's `next` (S18). Cut the key-store sentence and
     "never ask for the key", which S10 and S18 carry. T11's grep then has no hit.
   - **Choosing models.** Keep:
     - The choice is the user's.
     - Read `kbase://model-hints`.
     - Propose an id that `models` listed and that matches the capability.
     - Say what would move the choice.

     Cut the wall-clock explanation (request 4). Cut the fallback for model-hints not being offered:
     S13 shows it served. `model-map` becomes `configure-models` with a role's argument.
   - **Resuming and starting over.** A resume is `build` with `resume`. Starting over is
     `build-trail`'s started-at command, or removing `kb-root/` (S14). Relay the command and any
     `dirty` paths for the user to run. Cut `rewind-build` and the `check: inputs` refusal.
2. **`scoring.md`.**
   - Cut "What a pass does", "One quantity per ask", "Two things it never scores", "Values age" and
     "The ledger and resumption". `kbase://help/score` and S10 carry them, and the "pass … subtree"
     sentence is false: a pass is rigor, bearing or all.
   - Keep the model decision: `show-config` for the configured role, a `dry-run` first with its
     count given to the user, the trade, no run before the user picks, and `scoring-model` for an
     override (S30). Point at `kbase://model-hints` rather than paraphrasing its scoring row.
   - Keep the launch's `wait` line in the background, and `status` and `cancel` on the user's word.
   - Keep "Filling in `founds` bearings" as procedure only: name the edge by both ends with both
     titles, take the user's number, one edge at a time or a list, and say which are still open. The
     rule against proposing a value is S10's, so cut it. Values are written by `edit-edge`, and a
     work's rigor by `edit-work`. Edges are read with `edges`.
3. **`maintaining.md`.**
   - **What the stamped blocks say goes (S28).**
     - The paragraph opening "**A built leaf's body is the corpus's words; a leaf you author is
       your own.**" restates AGENTS' "What this tree holds". Keep only its adjagent half: migrating
       `session/` work means writing whole leaves, which are yours end to end.
     - The paragraph opening "**You write by hand**" keeps the hand-written list.
     - Cut any clause that restates CONVENTIONS' write-op rule.
   - **The write contract**, the paragraph opening "**You supply values; the call writes the
     bytes.**" and its bullets. It becomes a pointer: metadata is written through the
     `write` tool, `kbase://help/write` states the batch and its outcomes, and
     `kbase://help/<operation>` states each op. Cut "one entry per call", "adopts", the outcome
     ladder and the retry bound (S5, S20, S21, request 1).
   - **A batch's `commit`.** Add one statement, kept minimal: whether a batch commits `kb-root/` is
     the user's call, and passing `commit` is strongly encouraged because it makes the batch
     undoable as one unit. Say nothing of what `commit` does; `kbase://help/write` states it.
   - **The paragraph opening "**You do NOT score rigor.**"** Cut it: S10 carries the rule.
     `clauses.KB_RUNNER_TARGETS` stays.
   - **Job A.** `show` and `deps` become `show` and `edges`.
   - **Anatomy of a correct leaf.** Keep the up-link and the `> Related:` form. A node's statement
     marker is placed by its add op, so cut `mark-claim-in-leaf`. A node named in prose is a
     citation (S24, S17); point at `kbase://help/add-citation` rather than restating the forms.
   - **Claim-graph wiring.**
     - Keep the judgement: which premises a derivation actually consumes, as `supports` and
       `founds` edges; a `founds` edge only where the warrant leaves the corpus, never as a
       placeholder; the volume-order heuristic; and the `exp-` gate.
     - Cut every op mechanic the help states: inserts and minting, the work exception, acyclicity
       and Kahn's sort and file order, `demoted`, the edge-class drops.
     - "A claim that should not exist" becomes `remove-node`. Keep the judgement to re-point each
       dependent edge that still holds onto the replacing claim, and point at
       `kbase://help/remove-node` for how (S16).
   - **The regen → verify loop.** After a direct body edit, call `verify` and follow each refusal's
     remedy (S17). Done means `verify` returns done; otherwise report the failing check verbatim.
   - **Hazards.**
     - Worktree: the hazard reads "no branch switch, no \`git\` mutation, no stage, no commit —
       committing is not yours". Keep "no branch switch, no stage". "no \`git\` mutation" and
       "no commit — committing is not yours" both go: they contradict the `commit`
       encouragement. The `commit` statement above is the operative text.
     - Coverage gate: N comes from `find`, with `path` for a subtree (S31), or from `stats`. Count
       one `done` or `unchanged` entry outcome per item.
     - The other hazards stand.
   - **One live writer.** "every write-op call, `refresh`" becomes every `write` batch. The
     cascade is kbase's derivation after each write. "Run no write op and no `refresh`" becomes run
     no write batch.
4. **`scoring-system.md`.** The body becomes exactly:

   > The scoring system — rigor and bearing, and how strength is computed edge by edge — is
   > specified in kbase's
   > [scoring schemes](https://github.com/benn-herrera/kbase/blob/main/PROJECT_DOCS/SPEC/scoring/index.md).

   S27 shows the link resolves only once kbase 0.10.0 is on `main`. That is a release-order
   dependency for the coordinator, not this dispatch's concern.
5. **Delete `tests/test_write_op_contract_sources.py`** (T8). Every token it pins is kbase's
   contract, which the `write` help now carries. If your rewrite keeps a fact a session acts on
   mid-call that kbase's surface lacks, report it rather than keeping a token test for it.

**Done-line (WP6.2, and WP6.1's):**

- `just test-changed` passes.
- **T1, limited to the skill.** After the render below, run this with `T1PAT` set:
  `grep -n -w -E "$T1PAT" adjagent/definitions/kbase.py adjagent/clauses.py rendered/latest/skills/kbase/references/*.md`
  It must print nothing. README.md and PROJECT_DOCS are WP6.3's.
- `git grep -n -E 'apiKeyFile|auth add|KBASE_API_KEY' -- ':!*.md'` (T11, on the working tree)
  prints nothing.
- `grep -c 'kbase://help/' rendered/latest/skills/kbase/references/{reading,building,scoring,maintaining}.md`
  shows at least `1` for each file. Run it after the render below.
- `just sweep-python` runs, its candidate list is read, and every candidate pair touching a changed
  file is reported with a verdict: one idea, or not.
- **Render and compare all three slots** against WP6.1's baselines:
  - `just render latest`, then `just render-diff pre-wp6`
  - `just render latest-opencode --harness=opencode --model-tier-map=all=inherit`, then
    `just render-diff pre-wp6-opencode latest-opencode`
  - `just render latest-mage --harness=mage`, then `just render-diff pre-wp6-mage latest-mage`

  The pairs named are `skills/kbase/SKILL.md` and `skills/kbase/references/` `reading.md`,
  `building.md`, `scoring.md`, `maintaining.md` and `scoring-system.md`, and nothing else.
  `installing.md` does not change. The project rule renders only in `SKILL.md` (T6), so the mage
  slot's `SKILL.md` diff includes WP6.1's project-rule change, and the claude and opencode slots'
  diffs do not.

**Return:** the done-line results, the `render-diff` outputs verbatim, and the list of spans cut
with the S row that justified each.

### WP6.3 — mechanical (`tech-writer`, `model: sonnet`)

**Brief:**

- §Rule for every dispatch
- WP6 §Outcome
- WP6's "Shell definitions for every fact row", and the `T1PAT` definition with row T1
- WP6.2's returned list of `render-diff` pairs for the `pre-wp6` slot
- this section

The render slot `pre-wp6`, which WP6.1 rendered, is already under `rendered/`. Blocks A–C are not
needed. The files below are ones WP6.1 and WP6.2 do not edit, so their line numbers at WP6's base
are their working-tree lines.

**Scope:** `README.md`, `PROJECT_DOCS/SPEC/deployed-surfaces/base-and-kb-installs.md`,
`PROJECT_DOCS/ARCHITECTURE/subsystem-map.md`, `PROJECT_DOCS/ARCHITECTURE/composition-model/holes.md`
and `PROJECT_DOCS/CONVENTIONS/adding-definitions/skill-references-omit-offered-surface.md`.

Each edit replaces the quoted span with the given text. Rewrap only the paragraph or list item
edited, at the width of the lines around it, and change nothing else.

| # | fact acted on (command → answer at HEAD `b33d582`) | edit |
|---|---|---|
| E1 | `sed -n '37,42p' PROJECT_DOCS/SPEC/deployed-surfaces/base-and-kb-installs.md` → from "Its call answers once the run's ledger and pid stand," to "through \`set-rigor\`" / "and \`set-bearing\`." | Replace from "Its call answers" through "and \`set-bearing\`." with: "Its call answers once the run has started, not when the walk ends. A run enumerates the KB's scoring set itself, so an interrupted run is resumed rather than repeated. It never supplies two scores — a work's rigor and a \`founds\` edge's bearing, both because the work lies outside the corpus; the user authors those." |
| E2 | `sed -n '18,21p' PROJECT_DOCS/ARCHITECTURE/subsystem-map.md` → "\`clauses.kb_orientation\`, carrying the system model (two graphs, the leaf/summary contract," … "which modifies; \`build.md\` and \`scoring.md\` carry what their own job needs." | "carrying the system model (two graphs, the leaf/summary contract, authored-vs-derived metadata, the cast) with" becomes "carrying the KB system model with"; "\`build.md\`" becomes "\`building.md\`". |
| E3 | `sed -n '43,49p' PROJECT_DOCS/ARCHITECTURE/subsystem-map.md` → "Scoring is the one whose call outlives it: …" through "…and the ledger and" / "resumption." | Replace lines 43–49 with: "Scoring is the one whose call outlives it: \`score\` starts the run detached and answers once the run has started, before its run ends. The loop is kbase's own, and \`references/scoring.md\` carries what kbase's own text does not." Keep the two-space list indent. |
| E4 | `sed -n '7,8p' PROJECT_DOCS/ARCHITECTURE/composition-model/holes.md` → "…\`kbase_project_rule\` (how a kbase call names its project where" / "the server serves many)…" | "(how a kbase call names its project where the server serves many)" becomes "(how a kbase session locates its project where the server serves many)". |
| E5 | `sed -n '327p' README.md` → "metadata spine. The set is one skill, \`kbase\`, with four references, project-portable: per-project" | "with four references," becomes "with the references its router routes to,". |
| E6 | `sed -n '350,352p' README.md` → "…drives kbase's \`build\` tool: reports the refusal, or the" / "launch that entered a stage — its \`state-dir\`, \`pid\`, \`resume\` and \`wait\` lines, \`wait\` run in" / "the background to hear the build end; then \`status\` on request, \`cancel\` on your word" | From "reports the refusal" through "to hear the build end" becomes: "relays the launch or its refusal, and runs the \`wait\` line a launch returns in the background to hear the build end". The text after it ("; then \`status\` on request, \`cancel\` on your word") stays. |
| E7 | `sed -n '357p' README.md` → "the refresh→verify loop, for a correction or a migration a session lands by hand" | "the refresh→verify loop" becomes "the \`verify\` loop". |
| E8 | `sed -n '370,371p' README.md` → "kbase's own documentation is its repository, [benn-herrera/kbase](https://github.com/benn-herrera/kbase);" / "\`INTEGRATING_KBASE_VIA_MCP.md\` there is the wiring guide. The same install:" | The code span `` `INTEGRATING_KBASE_VIA_MCP.md` there is the wiring guide. `` is replaced by the plain text inside this code span, its double quotes included: `` its README's section "Using kbase from an agent harness (MCP)" is the wiring guide. `` |
| E9 | `sed -n '377,380p' README.md` → "names no KB path. Its queries are operations of one tool, \`query\`, and its write ops of another," … "\`stats\`. A settings file carrying JSONC comments, …" | From "Its queries are operations" through "called with operation \`stats\`." becomes: "Each of its tools is offered under the harness's own prefix — kbase's \`query\` tool is \`mcp__kbase__query\` under Claude Code and \`kbase_query\` under opencode." |
| E10 | `sed -n '389,391p' README.md` → "The route is MCP-only for every verb, scoring among them: the \`score\` tool starts its run detached" / "and answers once the run's ledger and pid stand, and the run is followed with \`status\`, \`wait\` and" / "\`cancel\`. When you ask …" | From "the \`score\` tool starts" through "\`wait\` and \`cancel\`." becomes: "the \`score\` tool starts its run detached and answers once it has started; the session follows the run with \`status\` and \`cancel\`, and runs the \`wait\` command line the answer carries in the background." |
| E11 | `grep -n 'stays in the reference' PROJECT_DOCS/CONVENTIONS/adding-definitions/skill-references-omit-offered-surface.md` → `10:` "only the tool's README carries is not offered to a session, and stays in the reference.", the last line | After the second sentence ("…once it reads it — the listing carries a resource's uri, name and mimeType only — so a reference that restates one is a second source for text its consumer already reads, and the two drift the moment either moves."), insert: "kbase's surface also includes the maintained block kbase stamps into \`kb-root/AGENTS.md\` and \`kb-root/CONVENTIONS.md\`, for a reference that has the session read those documents." Rewrap the paragraph; change nothing else. |

**Done-line (WP6.3, and WP6's):**

- `just test-changed` passes, the docs surface (`just check-links`) included.
- **Full T1, on the working tree.** With `T1PAT` set, this must print nothing:
  `git grep -n -w -E "$T1PAT" -- adjagent/definitions/kbase.py adjagent/clauses.py adjagent/harnesses/mage.py README.md PROJECT_DOCS`
- `just render latest`, then `just render-diff pre-wp6`. It must name the same pairs WP6.2
  returned for that slot, and no other: WP6.3 changes no render.

**Return:** the done-line results, and each edited span quoted before and after.

### Landing and review

- **Landing.** One commit carries WP6.1, WP6.2 and WP6.3, and this plan's WP6 Status rows set to
  landed.
- **Review.** WP6 has no review of its own. The release's single "Post-sprint review" below runs
  once WP6 has landed.
- **No reference retake.** WP6 does not run `just retake-reference`. It runs at release close, as
  the last step of the post-sprint review.

---

## Post-sprint review

There is one post-sprint review for the whole release. Run it once all packages have landed,
WP1–WP4 and WP6. It reviews the changes, not the plan.

1. **Review.** Dispatch four reviewers, each with THESIS.md, SPEC.md, ARCHITECTURE.md and
   CONVENTIONS.md as pre-task reading. **None receives this plan.**
   - `architect`
   - `python-coder`, for the Python: the generator and the tests
   - `generalist-coder`, for `guardrail.pl`, `guardrail.ts`, `tests/guardrail_ts_runner.ts`, the
     `justfile`, `python.just` and `devtools/scripts/`
   - `tech-writer`

   **Each reviews `git diff d092cd2`** against those standards and for suitability to purpose:
   - the kbase skill driving kbase 0.10.0 through its offered surface (the MCP surface and kbase's
     stamped blocks), carrying only what that surface lacks
   - the guardrail keeping sessions out of `kb-root/.index/` on kb installs, with both
     implementations held to one case table, and the claude guardrail's `$CLAUDE_PROJECT_DIR`
     reading
   - the contract documents as the `PROJECT_DOCS/` tree, with the root files as pointers, and the
     link and tree check that `just test` runs

   **Each review includes the tests the diff touches:**
   - `tests/test_adjagent.py`
   - `tests/test_adjagent_install.py`
   - `tests/test_guardrail.py`
   - `tests/guardrail_cases.json`
   - `tests/guardrail_ts_runner.ts`
   - the deletions of `tests/test_kbase_retired_forms.py` and
     `tests/test_write_op_contract_sources.py`

   **The `tech-writer` reviews what the diff ships as documentation:** SPEC.md, ARCHITECTURE.md,
   CONVENTIONS.md and README.md. It checks them for accuracy against the code, and for whether a
   reader without the work thread can act on them.
2. **Burndown.** The architect merges the four reports into one burndown list and writes it to
   `ACTIVE_PLAN_REVIEW_BURNDOWN.md` at the repository root.
3. **Burndown review and revision.** The `prompt-engineer` reviews `ACTIVE_PLAN_REVIEW_BURNDOWN.md` for
   usability, and the architect revises it on those findings. Only then is any burndown item
   dispatched.
4. **Close.** Close every item. The burndown is done when, on the result, two things hold:
   - The done-lines of WP1.2, WP2.2, WP3.1, WP4.1 and WP6.3 hold together, with `just test` in
     place of `just test-changed`. Any done-line that compares against a slot no longer present is
     excepted.
   - `just test-changed d092cd2` passes.

   Then, at release close, run `just retake-reference`. This is the only point at which it runs.
