# ACTIVE_PLAN — adjagent

## Status

| package | dispatch | rating | seat | state |
|---|---|---|---|---|
| WP1 | WP1.1 | mechanical | `python-coder`, `model: sonnet` | waiting on the kbase `v0.9.1` precondition |
| WP1 | WP1.2 | expert | `python-coder`, coordinator's model | runs after WP1.1 |
| WP2 | WP2.1 | mechanical | `python-coder`, `model: sonnet` | landed |
| WP2 | WP2.2 | expert | `generalist-coder`, coordinator's model | landed |

- **Landing unit.** WP1.1 and WP1.2 land as one commit, and WP2.1 and WP2.2 as another. No commit
  lands between the two dispatches of a package.
- **Order.** WP1 and WP2 depend on nothing in each other, and either can land first. They never run
  at the same time, because both edit README.md, SPEC.md and ARCHITECTURE.md.

## Preconditions for every package

Re-run each of these before a package's first dispatch. If any answer differs, stop and report it,
and dispatch nothing.

| check | must answer |
|---|---|
| `git status --porcelain --untracked-files=no` | nothing, or only ` M ACTIVE_PLAN.md` |
| `just test` | passes |

## Rule for every dispatch

Before editing, re-run every fact row the dispatch's brief carries. If any command's answer differs
from the plan's, stop and report that row, and edit nothing.

---

## WP1 — the kbase skill follows kbase 0.9.1's MCP surface

### Outcome

The `kbase` skill, its neighbours in `adjagent/clauses.py`, the tests that pin its text, README.md,
SPEC.md and ARCHITECTURE.md describe kbase 0.9.1's MCP surface and nothing older. A session driving
kbase through the skill calls tools that exist, and names operations and arguments that exist.

### Precondition — kbase 0.9.1 is tagged and installed

The kbase repository is not WP1's to edit. Commands run from the adjagent root, against the sibling
kbase checkout.

| check | must answer | answers today |
|---|---|---|
| `git -C ../kbase show v0.9.1:internal/version/version.go \| grep -n 'const Current'` | `8:const Current = "0.9.1"` (any line number) | fails: tag `v0.9.1` does not exist; HEAD `ab582ae` reads `8:const Current = "0.9.0"` |
| `kbase --version` | `0.9.1` | `0.9.0` |
| every row of "What kbase 0.9.1 serves", re-run at `v0.9.1` (substitute `v0.9.1` for `HEAD`) | the answer recorded there | — |

### What kbase 0.9.1 serves

Each command reads the kbase repository at a commit. Its answers below were read at HEAD `ab582ae`,
and the precondition re-runs them at `v0.9.1`.

| fact | command → answer |
|---|---|
| Queries and `render-citation` are operations of one `query` tool, and write ops of one `write` tool | `git -C ../kbase show HEAD:cmd/surface.go \| grep -n -E 'queryFamily = \|writeFamily = '` → `28:	queryFamily = "query"`, `29:	writeFamily = "write"` |
| A family tool takes `operation` and `arguments`; an argument is a flag's name without dashes | `git -C ../kbase show HEAD:internal/mcp/mcp.go \| grep -n -E 'operationProperty = \|argumentsProperty = \|a flag by its name'` → `283:	operationProperty = "operation"`, `284:	argumentsProperty = "arguments"`, `307:` "…a positional by its Usage name, a flag by its name " + "without dashes; …" |
| Help is served per family and per operation | `git -C ../kbase show HEAD:SPEC.md \| grep -n -E 'kbase://help/query\|kbase://help/<operation>'` → `2136:` names `kbase://help/query` or `kbase://help/write`, and `2137:` `kbase://help/<operation>` |
| `strength`'s arguments are `min`, `max` (strictly below), `min-dependents`, `sort` (`strength` or `dependents`) and `pending` | `git -C ../kbase show HEAD:cmd/strength.go \| grep -n 'Var('` → lines 44–48: `"min"`, `"max"` ("only claims with strength strictly below this"), `"min-dependents"`, `"sort"` ("the order: strength or dependents"), `"pending"` |
| `drop-claim-node` deletes the record, the marker, and every edge and `demoted` record naming the claim, in one call. It is refused while a line under `kb-root/` outside the register pages, or a prose field of another record, mentions the id | `git -C ../kbase show HEAD:cmd/drop-claim-node.go \| grep -n -E 'demoted record\|refused while'` → `9:` "marker in every leaf carrying one, every demoted record naming it, and every", `10:` "edge record naming it, in one call. The op is refused while a line under" |
| The volume-root rule is `build`'s help, served as `kbase://help/build` | `git -C ../kbase show HEAD:cmd/build.go \| grep -n -E 'toplevel\|documentclass'` → `195:` "…00README.json's toplevel entry names,", `196:` "else the sole file containing \documentclass. …" |
| `kbase://model-hints` is still served, so `kbase.py`'s references to it (lines 321–333) stand | `git -C ../kbase show HEAD:cmd/surface.go \| grep -n 'ModelHintsResource()'` → `162:` "…mcp.SheetResources(servedKB), mcp.ModelHintsResource(),"; `git -C ../kbase show HEAD:internal/mcp/resources.go \| grep -n 'ModelHintsURI  ='` → `23:	ModelHintsURI  = "kbase://model-hints"` |

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

| # | fact acted on (command → answer at HEAD `d092cd2`) | edit |
|---|---|---|
| 6 | `grep -n 'KBASE_MIN_VERSION = ' adjagent/definitions/kbase.py` → `12:KBASE_MIN_VERSION = "0.9.0"` | `KBASE_MIN_VERSION = "0.9.1"` |
| 6a | `grep -n '0\.9\.0' SPEC.md README.md` → `SPEC.md:65:` "… Version 0.9.0 is the minimum kbase this product is written for," and `README.md:36:` "- kbase 0.9.0 or later, installed by you …" | Change `0.9.0` to `0.9.1` at both sites. |
| 7 | `grep -n -E 'Every query, write op\|mcp__kbase__stats' README.md` → `368:` "names no KB path. Every query, write op, \`refresh\`," and `370:` "own prefix — \`mcp__kbase__stats\` under Claude Code, \`kbase_stats\` under opencode. A settings file" | Replace the span from "Every query, write op," (line 368) through "\`kbase_stats\` under opencode." (line 370) with exactly: ``Its queries are operations of one tool, `query`, and its write ops of another, `write`; every other command is a tool of its own. Each is offered under the harness's own prefix — `mcp__kbase__query` under Claude Code and `kbase_query` under opencode, called with operation `stats`.`` Rewrap the paragraph; change nothing else in the list item. |
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

| # | fact acted on (command → answer at HEAD `d092cd2`) | edit |
|---|---|---|
| 1 | `grep -n -E 'query tools\|MCP_TOOL_PREFIX\}find' adjagent/definitions/kbase.py` → `142:` "…carries a \`clm-xxxxxx\` id; the query tools below", `190:` "…Use the \`kbase\` server's query tools, which the harness", `191:` "offers under the server's prefix — \`{clauses.MCP_TOOL_PREFIX}find\` — and the bullets below name each tool" | Rewrite the sentence on lines 190–192 to say: the queries are operations of the one tool `` `{clauses.MCP_TOOL_PREFIX}query` ``, each named by `operation`. The bullets may keep naming each query, now as operations. The rendered text must hold the tool name in backticks, because WP1.1's test asserts `` `mcp__kbase__query` ``. On line 142, "the query tools below" becomes the queries below. |
| 2 | `grep -n -E 'strength-below\|weak-points' adjagent/definitions/kbase.py` → `179:` "refutation's cap. \`strength-below\` and \`weak-points\` omit pending claims but list unjudged \`0.00\` ones", `214:` "- \`strength-below\` with a \`max-strength\` — shaky claims", `215:` "- \`weak-points\` — highest-leverage rework targets (shaky *and* load-bearing)" | Line 179: `strength` without `pending` omits pending claims but lists unjudged `0.00` ones. The rest of the sentence, on line 180, stands. Lines 214–215 cover four things. Shaky claims are `strength` with `max`. Highest-leverage rework targets are `strength` with `sort: dependents` and a `min-dependents`. `pending: true` lists unscored claims. Point at `kbase://help/strength` rather than restating the arguments. |
| 3a | `grep -n 'write-op tool' adjagent/definitions/kbase.py adjagent/clauses.py` → `kbase.py:489:` "claim marker, a premise bullet, an analysis-to-claim pair — each is written by one write-op tool that"; `clauses.py:453:` "…is composed by the \`kbase\` server's write-op tools from values a seat supplies, each tool's schema being that op's closed set of value keys. …" | `kbase.py:489`: every write op is an operation of the one `write` tool. `clauses.py:453`: replace the per-op tool schema clause with "each op's closed set of value keys, which kbase checks". The words "closed set" stay, because `tests/test_write_op_contract_sources.py` asserts them in `references/maintaining.md`, which takes this paragraph through `kb_orientation`. |
| 4 | `grep -n -E 'should not exist\|re-point' adjagent/definitions/kbase.py` → `601:` "- **A claim that should not exist** — a duplicate of one already in the graph, or one a correction", `606:` "bullets you drop were dependents' warrants: re-point each one that still holds onto the claim that"; the bullet runs to line 608 | Rewrite lines 601–608. `drop-claim-node` alone deletes the claim and every edge naming it, and it is refused only while prose names the claim. Before the drop, read the dependents' `rests-on` edges with `deps`. After it, re-point each edge that still holds onto the replacing claim. Keep the fact that a re-pointed bullet enters at a `*pending*` bearing. The cycle advice at lines 618–619 is unchanged. |
| 5 | `grep -n -E 'toplevel\|documentclass' adjagent/definitions/kbase.py` → `50:` "Identify the volume root — the entry whose \`usage\` is \`toplevel\` in \`00README.json\` where the project", `51:` "has one, else the \`.tex\` file carrying \`\\\\documentclass\` — put it to the user, and route to" | Keep the step of identifying the volume root and putting it to the user. Replace the inline rule with a pointer to `kbase://help/build`. |
| 9 | `grep -n -E 'every query, write\|model-hints. resource\|leaving .wait.' ARCHITECTURE.md` → `504:` "…the set's route to it is MCP-only: every query, write", `507:` "that server's \`kbase://model-hints\` resource, read by uri. The router says so. When a request", `525:` "run's ledger and pid stand, leaving \`wait\`, \`status\` and \`cancel\` to follow — the same three the" | See item 9 below. |

**Item 9, ARCHITECTURE.md Subsystem Map, "kb set + kbase".**

Change the route sentence (lines 504–507) to say, in substance: the set's route to kbase is MCP-only,
through the harness's `kbase` MCP server, offered under the harness's `mcp_tool_prefix`, and what
the server offers is kbase's own surface.

Cut three things:

- the enumeration "every query, write op, `refresh`, `verify`, `build` and `score`"
- the `kbase://model-hints` sentence
- the `wait`/`status`/`cancel` listing on lines 524–526

Keep:

- the point that `score`'s call returns before its run ends
- "The router says so."
- the reference file list and the `kb-` runner target names

**Reference re-read.** Read `building.md`, `maintaining.md`, `scoring.md`, `scoring-system.md`,
`reading.md` and `installing.md`, as `kbase.py` renders them, against the facts in "What kbase 0.9.1
serves" and kbase's `kbase://help/<name>` text at `v0.9.1`. List every further span that names a
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

## Post-sprint review

Run once both packages have landed. It reviews the changes, not the plan.

1. **Review.** Dispatch four reviewers, each with THESIS.md, SPEC.md, ARCHITECTURE.md and
   CONVENTIONS.md as pre-task reading. **None receives this plan.**
   - `architect`
   - `python-coder`, for the Python: the generator and the tests
   - `generalist-coder`, for `guardrail.pl`, `guardrail.ts` and `tests/guardrail_ts_runner.ts`
   - `tech-writer`

   **Each reviews `git diff d092cd2`** against those standards and for suitability to purpose:
   - the kbase skill driving kbase 0.9.1 through its offered surface
   - the guardrail keeping sessions out of `kb-root/.index/` on kb installs, with both
     implementations held to one case table

   **Each review includes the tests the diff touches:**
   - `tests/test_adjagent.py`
   - `tests/test_write_op_contract_sources.py`
   - `tests/test_adjagent_install.py`
   - `tests/test_guardrail.py`
   - `tests/guardrail_cases.json`
   - `tests/guardrail_ts_runner.ts`

   **The `tech-writer` reviews what the diff ships as documentation:** SPEC.md, ARCHITECTURE.md,
   CONVENTIONS.md and README.md. It checks them for accuracy against the code, and for whether a
   reader without the work thread can act on them.
2. **Burndown.** The architect merges the four reports into one burndown list and writes it to
   `ACTIVE_PLAN_REVIEW_BURNDOWN.md` at the repository root.
3. **Burndown review and revision.** The `prompt-engineer` reviews `ACTIVE_PLAN_REVIEW_BURNDOWN.md` for
   usability, and the architect revises it on those findings. Only then is any burndown item
   dispatched.
4. **Close.** Close every item. The burndown is done when, on the result, two things hold:
   - WP1.2's and WP2.2's done-lines hold together, with `just test` in place of `just test-changed`
   - `just test-changed d092cd2` passes

   Then run `just retake-reference`. This is the only point at which it runs.
