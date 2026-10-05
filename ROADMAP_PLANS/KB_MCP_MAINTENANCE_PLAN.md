# KB_MCP_MAINTENANCE_PLAN.md — the KB's formal tool surface, over the CLI and MCP

**Status: design, not started.** The owner's settled direction is incorporated as given and not
reargued here; what this plan adds is the operation catalogue, the module skeleton, the
registration design, the protocol subset and its tests, the places the two-stage assumption lives,
the contract changes, and the rows. Open questions are at the end and are few on purpose.

## What this is for

After conversion the KB is canonical and LaTeX is derived (`kb_tools/SPEC.md`, What a KB Is).
Maintenance is people and agents working inside the KB — exploring, deriving, synthesizing, adding
and pruning nodes and hierarchies, and stitching the claim graph as they go. Today that work reaches
the KB through `kb_util` write ops driven by a dispatched `kb-maintainer`, and reading reaches it
through `kb_cmd` driven by a `kb-docent` loaded into the session. This plan gives both sides one
formal surface: the `kb_util` / `kb_cmd` CLI as the portable baseline, and a stdlib stdio MCP server
exposing the same operations to any harness that speaks MCP.

The usage pattern — convert, settle in, explore, draft, integrate, repeat — is an example. Nothing
below assumes or enforces that order or any part of it.

## Invariants

Each invariant names what it prevents.

1. **One implementation per operation.** Every MCP tool body is one call into a function the CLI
   already runs: a `kb_cmd` query, a member of `kb_write.ops.OPS` / `READ_OPS`, or a member of the
   two new claimgraph registries (`navigate.OPS`, `region.OPS`). The server module parses no JSONL,
   composes no metadata byte, and holds no KB vocabulary. The tool table is the **union of those
   registries**, never a list typed in the server, and a test asserts the tool names equal the
   non-build subcommands of `kb_util` plus `kb_cmd`'s. *Prevents:* a second implementation that
   drifts from the CLI; a tool with no CLI counterpart on a harness without MCP.
2. **The CLI is the baseline.** A capability lands as a `kb_util` or `kb_cmd` subcommand first and
   the MCP binds it second, in the same change. *Prevents:* MCP-only behaviour that pi-style
   harnesses cannot reach.
3. **Refusals are intrinsic only, and the list is closed**: a dangling link the op would write, an
   edge to a missing node, a duplicate id, a register entry without its node, a `depends` cycle. An
   orphan claim, an unscored claim, a leaf with `no-claim:`, a draft with no edges — all valid. A
   tool never refuses on sequence ("mint before wire"), on location ("promote only from
   `topics/`"), or on completeness. *Prevents:* tools that encode the example workflow as a rule.
4. **A refusal explains, and a cycle refusal names the path it would close** — `t → … → s → t`.
   *Prevents:* a `7` the agent can only act on by guessing.
5. **Every operation is one call and complete on its own.** A mutating tool leaves the derived
   layer fresh: it runs the same refresh the runner's `kb-refresh` target runs
   (`refresh_kb_metadata.main`, in-process) and reports the derived delta — the nodes whose
   `solidity` or `build_band` moved — read by loading `kb_cmd.index` before and after. A write that
   comes back `8` (contended) is re-issued identically up to three times by the tool, not the agent.
   *Prevents:* an obligation ("remember to refresh", "retry three times") left to a model's
   tirelessness.
6. **No git in maintenance tooling.** Git writes exist only in the build ledger
   (`kb_tools/kb_pipeline.py`, `add -A` and `commit` at lines 1334–1345); git reads only in
   `kb_util.preflight_report` (lines 684, 709) and the ledger readers (`kb_pipeline.py:1227`,
   `1247`). A monopoly test on the pattern of `kb_tools/tests/test_binary_monopoly.py` holds that
   set fixed. Tools may *print* a suggestion to commit. *Prevents:* a "helpful" commit inside a
   promote or move.
7. **No model call in the tool surface, and no prompt in code.** Region checks return the build's
   own rendered asks — `kb_driver/prompt-templates/paragraph.tmpl.md` and `unmarked.tmpl.md`
   through `prompt_templates.render` with `ask.LETTER_SLOTS` — plus the letter→meaning table; the
   session's model judges. `kb_mcp.py` and `kb_claimgraph/region.py` import nothing from
   `kb_tools/inference/`. *Prevents:* a second inference configuration; a question text that
   diverges from the build's; a hidden second reader.
8. **stdout of the server carries JSON-RPC frames and nothing else.** The server takes the real
   stdout handle at start and redirects `sys.stdout` to a buffer around every tool body; the buffer
   is the tool's result text. Logging goes to stderr (and an optional file) through stdlib `logging`
   at a runtime-set level. *Prevents:* a verifier's `print` corrupting the stream — every verifier
   and `refresh` print to stdout today.
9. **Stdlib only; no MCP SDK.** The official SDK pulls pydantic and an HTTP stack
   (`kb_tools/SPEC.md`, Corpus Invariants, admits one exception and it is `pandoc`). The protocol
   version is one constant, `kb_mcp.PROTOCOL_VERSION`. *Prevents:* a dependency the install cannot
   deliver and a second enumerated exception nobody designed.
10. **Harness-agnostic server, harness-aware registration.** The server never reads its install
    location except through `install_location` for the hints the ops already print, and never
    reads a harness config file. Registration lives in `gen_defs`, reads three new keys of
    `templates/harness/<name>.toml`, and owns exactly one `kb` entry in the harness's project MCP
    config, merging. *Prevents:* a tracked tool knowing which harness started it; a user's other
    servers clobbered.
11. **The write vocabulary stays single-sourced.** A write tool's `inputSchema` is derived from
    `kb_write.values.OP_FIELDS` by one checker→schema table; the JSON arguments pass through the
    same per-op checks the TOML values file does. No prose copy of a vocabulary appears in the
    server, this plan included (`kb_tools/CONVENTIONS.md`, "Keep no prose copy of an op's key
    vocabulary"). *Prevents:* a schema that accepts a key the op refuses, or the reverse.
12. **Drafting location is the user's.** Nothing in a gate, an op or a definition requires a draft
    to start outside the tree, and nothing requires it to start inside. A tree document is valid
    from its first write because `place-document` writes its up-link, its parent's child link and
    a frontmatter block in the same act. *Prevents:* a two-stage workflow re-entering as a rule.
13. **Boundary checks at the frame.** Each incoming frame is checked for `jsonrpc == "2.0"`, an
    `id` of string/number/null, a string `method`, and — on `tools/call` — a known tool and
    arguments that are a JSON object carrying the schema's required keys with the right JSON
    types; the KB is located per call by `kb_util.find_repo_root()` from the process cwd and a
    miss is an `isError` result naming the probe, never a crash. Cheap, always on. *Prevents:* a
    traceback where the model needed a sentence.

Standing invariants not adopted, with the reason: switchable metrics (nothing here is
performance-critical; per-call wall time at DEBUG suffices), a new build target (the existing
`just test kb_tools` / `just test gen_defs` surfaces cover the new tests; `TEST_SURFACE_MAP` already
routes `kb_tools/` and `gen_defs/`).

## Operation catalogue

Tool names are the CLI subcommand names, so the two surfaces share one vocabulary; under Claude
Code they appear as `mcp__kb__<name>`. Every tool returns `content: [{type: "text", text}]`; a read
returns the same JSON `kb_cmd --json` prints, a write returns the op's `[kb-write]` report lines
followed by the derived delta. Refusals are `isError: true` with the report lines as text, every
failure line carrying the op's existing `restore:` clause.

The owner's verbs map onto ops as follows: **mint** = the four `insert-*` ops; **wire** =
`add-depends-on`, `remove-edge`, and the `supports` / `strengthens` declarations `set-frontmatter`
carries; **score** = `set-rigor`, `set-on-point-fraction`, `set-work-strength`, `set-applicability`;
**place / move / prune / promote** are the four topography ops below; **region checks** are the
three `region-*` ops.

### Phase 1 — read and navigate

| Tool | Wraps | Inputs (sketch) | Returns |
|---|---|---|---|
| `stats` | `Index.stats`, `band_distribution`, `weak_points`, `solidity_below` (as `kb_cmd stats --json`) | `{}` | the census, bands, leverage and weakest lists |
| `find` | `Index.find` | `{query: string}` | `[{id, title, solidity, build_band}]` |
| `show` | `Index.node` | `{id: string}` | the node record, any kind in `kb_schema.NODE_KINDS` |
| `deps` | `Index.depends_on_edges` / `dependents_of` | `{id: string, inverse?: boolean}` | forward edge records, or dependent ids |
| `gated-on` | `Index.gated_on` | `{id: string}` | claim ids whose strengthen-by names `id` |
| `cited-by` | `Index.cited_by` | `{id: string}` | the hosting edges |
| `referenced-by` | `Index.referenced_by` | `{id: string}` | leaves whose links reach the claim's home leaf (live scan) |
| `solidity-below` | `Index.solidity_below` | `{threshold: number}` | claims under the threshold |
| `weak-points` | `Index.weak_points` | `{max_solidity?: number, min_dependents?: integer}` | shaky and load-bearing claims |
| `subtree` | `Index.subtree_claims` | `{path: string}` | claim ids under a node path |
| `tree` | `navigate.tree` (new; over `kb_claimgraph.tree.read`) | `{path?: string, depth?: integer}` | the topography under `path`: each document's path, kind, title, children |
| `document` | `navigate.document` (new) | `{path: string}` | kind, title, parent, children, frontmatter fields, hosted ids (`Index.claims_in_leaf`), the absolute path for the harness's own read tool; no body text |
| `verify` | `kb_util.run_kb_verify` with output captured | `{}` | the three verifiers' report lines and codes |

No read refuses anything but an unknown id or path, in the words `kb_cmd` already uses
(`error: unknown node id: <id>`). Neither graph is touched.

### Phase 2 — stitching

Existing write ops, bound as-is. Schema: derived from `values.OP_FIELDS[<op>]`; effect and
refusals: as `kb_tools/SPEC.md`, The Write API's Contract, states them today. Each is one entry per
call; the CLI's values file stays the batch channel.

| Tool | Effect on the claim graph | Effect on the topography |
|---|---|---|
| `insert-claim-entry`, `insert-support-entry`, `insert-experiment-entry`, `insert-work-entry` | mints the node (a work's id is derived) and its register entry at `*pending*`; prints the id | none — hosting is `set-frontmatter`'s |
| `add-depends-on` | adds `depends` / `rests-on` / `references` edges; **gains the cycle refusal** (below) | none |
| `set-frontmatter` | hosts ids in a leaf; declares `supports` / `strengthens` ends | writes the block; `kind` is the caller's |
| `mark-claim-in-leaf` | places a Tier-2 marker | none |
| `set-rigor`, `set-on-point-fraction`, `set-work-strength`, `set-applicability` | the scores; the cascade is the refresh every write runs, reported as the derived delta | none |
| `set-rationale` | prose on an entry | none |
| `render-citation` | none (read) | none; prints the citation form |

**The cycle refusal (`add-depends-on`).** Today the op resolves targets and dedupes
(`kb_tools/kb_write/ops.py:2263–2326`, `_depends_targets` at 512–539) and a cycle is caught only
afterwards by `verify_kb_metadata.check_solidity_cycle` (lines 1160–1173), which reports
`SolidityCycleError.cycle_members` — the unreachable set, not a path (`kb_index_lib.py:2776–2788`).
`attribute.cycle_edges` (`kb_claimgraph/attribute.py:772`) names edges on cycles, not a path. The
gap is a path finder: `kb_index_lib.dependency_path(entries, start, end)` beside
`compute_solidity`, walking the authored `depends` graph (claim and support entries, `rests-on`
excluded since a work emits no edge). The op calls it for each new `depends-on` target and refuses
with: `REFUSED <id> depends-on <t> would close a cycle: <t> → … → <id> → <t>; restore: drop the
edge, or record it under references`. A cycle forced in by hand-editing the register stays
`kb-verify`'s business; no further guard.

New write ops, in `kb_write.ops.OPS` with their vocabularies in `values.OP_FIELDS`:

- **`remove-edge`** — `{id, target, class: "depends-on" | "references"}`. Removes one bullet from
  the entry's named list. Refuses: the entry does not hold that edge (names what it holds).
  Topography: none. `supports` / `strengthens` ends are removed by restating the hosting leaf's
  block through `set-frontmatter`, which already exists for that.
- **`retire-node`** — `{id}`. Removes a register entry; for a `clm-`, also its Tier-2 marker and
  its membership in the hosting leaf's `claims:`, every other frontmatter attribute carried forward
  (the carry-forward reader is `ops._existing_frontmatter`, lines 2392–2442); for an `exp-` /
  `sup-`, the leaf's declaration block likewise. Refuses: any entry's `depends-on`, `references`,
  `supports` or `strengthens` names the node (lists the edges; `remove-edge` first); the id does not
  resolve. Topography: none. An orphan this leaves behind — a leaf now hosting nothing — is valid
  and reported, not refused.
- **`place-document`** — `{destination, title, kind: "leaf" | "index", body, no_claim?: string}`.
  Creates a tree document from supplied text: the up-link to the parent (`<dir>/index.md`, or
  `entry-point.md` for a volume directory), the frontmatter block (`kind`, and for a leaf
  `no-claim: <no_claim>`; claims are hosted later by `set-frontmatter`), and the child link in the
  parent index, appended last. A `kind: index` destination `<dir>/index.md` creates the directory
  and links it from its own parent. Refuses: destination exists; parent index missing; a link in
  `body` that resolves to nothing (dangling, named); destination under an excluded directory
  (`kb_index_lib.EXCLUDE_DIRS`) or outside `kb-root/` (`store.resolve_target`). Claim graph: none.
- **`promote-document`** — `{source, destination, title, kind, no_claim?}`. `place-document` with
  the body read from `source`, a `.md` under an excluded directory (`session/`, `topics/`); the
  source is deleted after the placed copy is proven. Same refusals, plus: `source` not under an
  excluded directory, or absent. The two share one placement function; the op differs only in
  where the body comes from and in consuming the source.
- **`move-document`** — `{source, destination}`. Renames a tree document: rewrites its up-link,
  moves its child link from the old parent index to the new one (appended last), rebases its body's
  relative links (`kb_links.rebase_inline_links`, `kb_links.py:255`), and rewrites the leaf link in
  every register entry the document hosts (`store.PATH_DERIVED_FIELDS`, `store.py:396`). For an
  index, the whole directory moves and every descendant's links are rebased. Refuses: source not in
  the tree; destination exists; new parent index missing; a link elsewhere in the tree that
  resolves to the old path (named — the caller edits the citing documents first, or the op gains a
  `rewrite_citers` flag later; not in this plan). Derived fields (`Leaf references:` footers,
  `subtree-claims`, `.index/`) are the refresh's.
- **`prune-document`** — `{path}`. Deletes a tree document and its child link in the parent index.
  Refuses: it hosts any node (names the ids; `retire-node` first or `set-frontmatter` to re-host
  elsewhere); it is an index with children; another document links to it (named). Claim graph:
  none, by construction of the refusals.

Maintenance:

- **`refresh`** — wraps `refresh_kb_metadata.main`, output captured. `{}`. Exposed for after a hand
  edit; every write tool runs it already.

### Phase 2 — region checks

All three are mechanical, read the tree the way the build does (`kb_claimgraph.tree.read`,
`inventory.scan`, `graph.read`), make no model call, and never mint. `scope` is a kb-root-relative
path: a directory (prefix) or one document; absent means the whole KB. Each surfaces a
`GraphReadError` (a `claims:` id no register mints) as its error text rather than refusing to run.

- **`region-unminted`** — `{scope?: string}`. For each leaf in scope: the paragraphs the node pass
  would ask about (`identify.reading_of` → `identify.asked_paragraphs`, which already applies
  `MIN_OPENING_WORDS` and the obligated-paragraph rule), less paragraphs already carrying a claim
  marker (`prose.marks`) and less lines inside claim-bearing blocks (already excluded by the
  render). Returns, per leaf, the group prefix of the rendered `paragraph.tmpl.md` ask **once** and
  per paragraph the item tail — the same split `letters.GroupRecord` records a build's asks with —
  with `ParagraphLetter`'s meanings, the paragraph's locator (what `mark-claim-in-leaf` takes), and,
  where `kb_pipeline.read_node_pass` finds a record, the build's recorded verdict for that paragraph
  as information. Claim graph and topography: untouched.
- **`region-unmarked`** — `{scope?: string, k?: integer}`. `unmarked.plan` over the authored
  graph (`classify.statements`, `attribute.narrow(tree, graph, inventory)` with no record,
  `equation_sites.own_equations`), with `candidate_pairs` widened by every edge the registers
  already carry (`depends-on` and `references`, read off `kb_index_lib`'s entries) so an authored
  pair is never re-proposed; sources filtered to scope; `k` defaults to `shortlist.K`. Returns per
  pair the rendered `unmarked.tmpl.md` ask (prefix once per source, tails per target) with
  `UnmarkedLetter`'s meanings, and the two ids `add-depends-on` takes. Untouched graphs.
- **`region-status`** — `{scope?: string}`. Information, never errors: claims with no edge in either
  direction over `Index.all_depends_on_edges` (a new `Index.degree_zero()`; `kb_graph.model`'s
  `isolated` is the incumbent and is not used because it is defined over the transitively reduced
  premise set inside the renderer), entries at `*pending*` (rigor, applicability, strength), leaves
  carrying `no-claim:`, documents without frontmatter, and — if `kb-build-node-pass.json` stands —
  leaves the build left `unread`.

## Module skeleton

```
kb_tools/
  kb_mcp.py                      the stdio server: framing, dispatch, tool table = union of the
                                 registries, inputSchema from values.input_schema and each
                                 registry row's declared schema; stdout redirection around tool
                                 bodies; logging to stderr/file. Imports kb_util, kb_cmd.queries,
                                 kb_write.ops, kb_write.values, kb_claimgraph.navigate,
                                 kb_claimgraph.region, refresh_kb_metadata. Never: inference,
                                 kb_pipeline's writers, kb_driver.
  kb_util.py                     gains the `mcp` subcommand (starts kb_mcp.serve on stdin/stdout)
                                 and the navigation/region subcommands, bound by local import as
                                 the write ops are (`_handle_write_op`, kb_util.py:1203).
  kb_cmd/queries.py              NEW: the query table `QUERIES` — name → (callable over Index,
                                 inputSchema, serializer) — lifted out of cli._dispatch, which
                                 then reads it. The serializers are today's `_dep_to_dict` etc.
  kb_write/values.py             `check_entries(data, *, op)` over a parsed mapping, used by
                                 parse_values and by the server; `input_schema(op)` from one
                                 checker→schema table beside the checkers.
  kb_write/ops.py                `_execute` takes ParsedValues; the file read moves to the CLI
                                 adapter. New ops: remove-edge, retire-node, place-document,
                                 promote-document, move-document, prune-document.
  kb_write/render.py             the up-link line and the index child-link bullet, composed here
                                 and read by kb_docgraph.outline.render (which spells both today,
                                 outline.py:680) — retired there only after the render is proven
                                 byte-identical on the docgraph fixtures.
  kb_index_lib.py                `dependency_path(entries, start, end)`; EXCLUDE_DIRS gains
                                 `topics`.
  kb_cmd/index.py                `Index.degree_zero()`.
  kb_claimgraph/navigate.py      NEW: `tree`, `document` over tree.read; its `OPS` registry.
  kb_claimgraph/region.py        NEW: the three region checks; its `OPS` registry. Imports
                                 identify, prose, unmarked, shortlist, classify, attribute,
                                 equation_sites, ask (for the composers), kb_pipeline (readers
                                 only). Never: inference, letters.ask_group, write.
gen_defs/
  mcp_registration.py            NEW: read the harness's three keys, load the project MCP config
                                 if present (JSON object or refuse), set the one `kb` entry,
                                 write back only when the result differs. Called by installation.
  installation.py                calls mcp_registration after the copy and render, when ROOT's
                                 name is the harness's project-harness-dir; reports otherwise.
templates/harness/<name>.toml    three new keys (below).
```

Dependency direction: `kb_mcp` → registries → libraries. `kb_claimgraph.region` and `navigate` sit
inside `kb_claimgraph` because `tree.py`, `inventory.py`, `identify.py` and `unmarked.py` are what
they read; `kb_cmd` stays `.index/`-only. `kb_util` reaches both by local import, as it reaches
`kb_write.ops` today, because `kb_claimgraph` imports `kb_util`. `kb_docgraph.outline` importing
`kb_write.render` is a new cross-package edge; the coder confirms no cycle (neither `kb_write` nor
anything it imports reaches `kb_docgraph` today — `kb_write` imports `kb_util`, `kb_index_lib`,
`kb_schema`, `kb_links`).

What does **not** belong: no tool registry in `kb_mcp.py`; no argparse in any registry module; no
harness name in `kb_mcp.py`; no JSON-RPC in anything but `kb_mcp.py`; no `print` in a registry
function's success path that is not its declared output (the server captures it either way).

## Registration

Per harness, three new keys in `templates/harness/<name>.toml`, read by `gen_defs` the way
`agents_file.load_harness` reads the existing four:

- `mcp-config-file` — the project-root file: `.mcp.json` (claude), `opencode.json` (opencode).
- `mcp-config-section` — the top-level key holding servers: `mcpServers` (claude), `mcp` (opencode).
- `mcp-server-entry` — the `kb` entry as JSON text, spelling the harness's own agents directory:
  claude `{"command": "python3", "args": ["-m", "kb_tools.kb_util", "mcp"], "env": {"PYTHONPATH":
  ".claude/agents"}}`; opencode `{"type": "local", "command": ["python3", "-m",
  "kb_tools.kb_util", "mcp"], "environment": {"PYTHONPATH": ".opencode/agents"}, "enabled": true}`.
  The `PYTHONPATH` is relative because both harnesses start a project MCP server with the project
  root as its working directory — a fact the live check confirms, and the reason the entry carries
  no absolute path into a tracked file. The spelling is the harness's and is confirmed against its
  current release in the live check; a key the harness renames is a template edit, not a code one.

`gen_defs.mcp_registration.register(project_root, harness)`: load `<project_root>/<mcp-config-file>`
if present (must parse as a JSON object, else refuse naming the file and writing nothing — this is
how an `opencode.json` carrying comments is handled); set `[section]["kb"]` to the entry; if the
result equals what is on disk, write nothing; else write `json.dumps(obj, indent=2) + "\n"`. Every
other key is carried as loaded; formatting is not preserved, content is. One rolling backup beside
the file on a changing write, as `agents_file` keeps (`BACKUP_PREFIX`). Symlinks refused in place of
the file, as there. The install report names the file written, or `unchanged`, or `skipped: ROOT
<x> is not <harness>'s project directory` (a `rendered/` slot or an empty `--subdir=`).

Where it runs: inside `install`, after the copy and render and independent of the prune, guarded by
`ROOT.name == project-harness-dir`, so `just install <project>` leaves a consumer registered and a
re-install is a no-op. The `.mcp.json` lands at the project root — outside ROOT — which is new for
`install` and is the first open question below.

## Protocol subset

Newline-delimited JSON-RPC 2.0 over stdio: one object per line, UTF-8, no embedded newline
(`json.dumps` default). The server is single-threaded and answers in order. EOF on stdin ends it
with exit 0.

- `initialize` → `{protocolVersion, capabilities: {tools: {listChanged: false}}, serverInfo:
  {name: "kb", version: kb_tools.__version__}}`. If the client's `protocolVersion` equals
  `PROTOCOL_VERSION` it is echoed; otherwise the server answers with `PROTOCOL_VERSION` and the
  client decides. The constant's value is whatever both harnesses negotiate in the live check — the
  current MCP revision when this lands — and is pinned there, not here.
- `notifications/initialized`, and every `notifications/*` → no response, logged at DEBUG.
- `ping` → `{}`.
- `tools/list` → every tool with `name`, `description`, `inputSchema` (`type: object`, properties,
  required); no cursor.
- `tools/call` → `{content: [{type: "text", text}], isError}`. A refusal or a caught exception
  inside a tool body is `isError: true` with the text the model needs; protocol faults are JSON-RPC
  errors: `-32700` parse (id null), `-32600` not a request object or a batch array, `-32601` unknown
  method, `-32602` unknown tool or arguments failing the frame check (invariant 13), `-32603` an
  exception escaping the dispatcher itself (logged with traceback).
- No server-to-client requests; no `roots`, `sampling`, `resources`, `prompts`. `structuredContent`
  not emitted.

### Test plan

Spec-shaped fixtures, `kb_tools/tests/fixtures/mcp/*.jsonl`: one transcript per case, alternating
request lines and the expected response line (or a marker for "no response"). Run by
`kb_tools/tests/test_kb_mcp.py` through `kb_mcp.serve(read, write)` on in-memory streams, over the
fixture consumer `tests/_claimgraph_consumer.install_claimgraph_consumer` so `tools/call` has a KB
to answer about. Cases: initialize with the pinned version; initialize with another version;
`notifications/initialized` produces no line; `ping`; `tools/list` names equal the registry union;
every `inputSchema` is an object schema; `tools/call stats`; `tools/call find`; `tools/call` unknown
tool is `-32602`; a non-JSON line is `-32700` with `id: null`; a batch array is `-32600`; an
unknown method is `-32601`; a tool whose body prints (`verify`) leaves exactly one frame on the
stream. Phase 2 adds: `insert-claim-entry` over the fixture returns the id and `run_kb_verify` is
green afterwards; `add-depends-on` closing a cycle returns `isError` naming the path; a staged
contention (`store` returns retry once) is absorbed; `region-unminted` over the fixture lists
exactly `identify.asked_paragraphs` minus the marked ones. One process-boundary test spawns
`python3 -m kb_tools.kb_util mcp` with `install_location.current().agents_dir` on PYTHONPATH
(`kb_tools/tests/conftest.py` stands that layout up) and runs the initialize/list/ping transcript
through real pipes.

One-time live check per harness, run by the operator in an interactive session (it needs the
harness): `just install <scratch-consumer>` into a directory under the project's own scratch,
confirm the harness lists `kb` as connected, call `stats` and `tree`, read the negotiated
`protocolVersion` off the harness's MCP log, and confirm the server's cwd was the project root (the
relative `PYTHONPATH` worked). Evidence — the version string, the harness release, the `tools/list`
the harness showed — goes in the landing commit message, where it is dated; `PROTOCOL_VERSION` and
the harness TOML entries are what it fixes. Repeat on a harness release that moves MCP, the way
root `ROADMAP.md` item 2 treats a definition-format release.

## Where the two-stage assumption lives, and what changes

The assumption: a docent reads and writes only `session/`; a maintainer is dispatched to migrate
finished work from `session/` into canonical leaves. Where it is built in, with the change:

| Where | Today | Change |
|---|---|---|
| `templates/agents/kb-docent.tmpl.md` lines 3, 11, 62–83, 100–101, 228–239 | description and role clause "read side"; "Query it through the index — don't grep" names the `kb_cmd` CLI; "You do not modify KB content"; "you do not re-score" | the session persona for all KB work: reads, and stitches on offer or on direction through the tools (CLI where no MCP); "What You Are Not" keeps: no rewriting a built leaf's body, no inventing content, no placement nobody asked for; drops the read-only clause and the no-scoring clause (the session may score, or dispatch the scorer) |
| `templates/agents/kb-maintainer.tmpl.md` lines 3, 22–28, 49–61 | "migrate finished work from `session/`"; Job B's PARK / promote boundary; "never open a new subtopic to hold work you are landing" | the dispatched batch worker for landing work from anywhere — a draft in the tree, `topics/`, `session/`, or a brief; the editorial boundary becomes advice to surface, not a rule; a new subtopic is opened when the assignment names it; keeps the regen→verify loop, hazards, and file-ownership parallelism |
| `templates/agents/kb-claim-scorer.tmpl.md` | returns judgments, writes nothing | unchanged; the landing op is now also the session's `set-rigor` |
| `templates/shared-chunks.toml` `kb-orientation` (478–496) | role clause "read side / write side"; "Authored is not typed… the op surface is the CLI's own" | role clauses per seat as above; the op surface is the CLI and, where the harness has it, the `kb` MCP server exposing the same ops |
| `templates/shared-chunks.toml` `kb-metadata-write` (537–542) | values travel in a file; re-run an `8` up to three times yourself | the CLI form stays as written; through a tool the values are the call's arguments and the retry is the tool's |
| `kb_tools/installed/AGENTS.tmpl.md` lines 5–14 | "To change anything in it — dispatch `kb-maintainer`"; "Do not edit files here directly" | change it through the tools, in the session or by dispatch; the direct-edit prohibition stays, scoped to metadata and derived files |
| `kb_tools/installed/CONVENTIONS.tmpl.md` lines 22–37, 68–71 | docent "writes only under `session/`"; "Create files only at targets an assignment names" | the tool surface and where drafts may live (anywhere; `topics/` and `session/` are outside the walk); assigned-targets stays for dispatched seats |
| `kb_tools/SPEC.md` Leaf Bodies Are Derived (49–57), Agent-Mediated Editing (733–738), The Write API's Contract (752–756) | "migrating `session/` work"; editing goes **through the agent set**; "Every write op takes `--values <file>`" | a hand-authored leaf wherever drafted; editing goes through the tool surface, which the agents carry; the CLI takes `--values`, the MCP takes the same values as arguments |
| `kb_tools/ARCHITECTURE.md` The Agent Set (708–731), Query Surface (735–768), `kb_util` row (17) | Use / Maintain / Score by seat | roles as above; the registries; the new subcommands |
| `kb_tools/kb_index_lib.py:107` `EXCLUDE_DIRS` | `{"session", ".index", "tools"}` | add `topics` — the drafting home beside `session/`, which stays the docent's continuity residue with its own fixed formats (`kb-docent.tmpl.md` 133–201) |
| `kb_tools/verify_kb_metadata.py` `collect_files` (206–216), `check_frontmatter_presence` (337–343), `check_tier1_coverage` (346–370) | every non-excluded `.md` needs a frontmatter block; a leaf declares `claims` / `no-claim` / `exp-id` | **no change**: `place-document` satisfies both from the first write, so in-tree WIP is valid by construction |
| `kb_tools/verify_md_links.py:110–117` | every crawled `.md` gates | **no change**: a dead link is intrinsic; a draft that wants a forward reference writes prose until the target exists. The queued warn tier at `verify_kb_metadata.py:89–97` is not adopted |
| `kb_tools/kb_links.py` `SKIP_DIRS` | unread here | the coder establishes whether `session/` is crawled (`grep -n SKIP_DIRS kb_tools/kb_links.py`) and treats `topics/` the same way, in the same change |

Documents and definitions that *do not* carry the assumption and need no change for it: the
`/kb-start` and `/kb-next` commands (they locate and load; `templates/commands/kb-start.tmpl.md`),
`/kb-build`, `kb-session-locate`, `kb-uplink`, `kb-solidity`.

## Contract-document changes

Routed per the house rule: behaviour → SPEC first, mechanism → ARCHITECTURE and code, traps →
CONVENTIONS.

- **`kb_tools/SPEC.md`** — new section *The Tool Surface*: the CLI is the baseline; an MCP server
  exposes the same operations over stdio JSON-RPC; the closed refusal list (invariant 3) and what
  it does not refuse (orphans, pending, drafts anywhere); every mutating operation leaves the
  derived layer fresh and reports what moved; no operation touches git; region checks propose and
  never mint, make no model call, and return the build's own questions. *The Write API's Contract*:
  the `--values` sentence scoped to the CLI; the new ops with their refusals; `add-depends-on`
  refuses a `depends` cycle naming the path. *Leaf Bodies Are Derived* and *Agent-Mediated
  Editing* as the table above states. *Runner Targets*: `mcp` as a sanctioned entry.
- **`kb_tools/ARCHITECTURE.md`** — Module Inventory rows for `kb_mcp.py`, `kb_cmd/queries.py`,
  `kb_claimgraph/navigate.py`, `region.py`; the `kb_util` row's op list; *Query Surface* reads the
  registry; *The Agent Set* roles; a *The MCP Server* subsection with the protocol subset and the
  stdout rule; *The Claim Graph* row for `region.py` saying what it reuses.
- **`kb_tools/CONVENTIONS.md`** — four traps: `kb_mcp`'s stdout carries frames only, capture around
  every body; a tool refuses only the intrinsic list — a workflow refusal is a defect; git stays
  inside the ledger and preflight, held by the monopoly test; the tool table is the registries'
  union — never list a tool by hand. And the fixture rule: protocol tests are transcript fixtures
  under `tests/fixtures/mcp/`, not asserted strings in code.
- **Root `SPEC.md`** — Deployed Surfaces: an install registers the shipped KB toolchain's MCP server
  in the selected harness's project MCP config, at the project root, owning exactly one `kb` entry,
  merging, refusing a file it cannot parse, reporting what it wrote; the registration is skipped
  with a notice where ROOT is not the harness's project directory. The harness file's key set.
- **Root `ARCHITECTURE.md`** — Repo Layout: `gen_defs/mcp_registration.py`; Install Consumption
  Model: registration as the fourth part; Template System: the three harness keys are read by
  `gen_defs`, not rendered through `hrn.` (no template spells them).
- **`kb_tools/installed/AGENTS.tmpl.md`, `CONVENTIONS.tmpl.md`** — as the table above; these ship
  into every new KB. Already-built KBs keep their stamped copies (`kb_pipeline.stamp_readiness_docs`
  is only-if-absent, `kb_pipeline.py:914–947`): a risk, below.
- **Root `ROADMAP.md`** — one item pointing at this plan while it is parked; deleted when it lands.
  `kb_tools/ROADMAP.md`: none.
- **Root `README.md`** — if it lists what an install writes, the registration line; the coder
  checks.

## Rows

Done-whens are observable; tests named are the ones the row adds. Every coder row includes the
contract-document edits its change invalidates. Prompt-engineer rows produce model-facing text and
are reviewed per the house rule before first use.

### Phase 1 — read, navigate, register

| # | Owner | Files | Done when |
|---|---|---|---|
| 1.1 | python-coder | `kb_tools/kb_cmd/queries.py` (new), `kb_cmd/cli.py`, `kb_cmd/index.py` | `QUERIES` holds every `kb_cmd` subcommand with its schema and serializer; `cli._dispatch` is a lookup in it; existing `kb_cmd` tests pass unchanged; `Index.degree_zero()` exists with a test |
| 1.2 | python-coder | `kb_tools/kb_claimgraph/navigate.py` (new), `kb_util.py`, `kb_tools/ARCHITECTURE.md` | `kb_util tree` and `kb_util document` print the JSON described above over the fixture consumer; `document` on an index lists its children in index order; the `kb_util` import of `navigate` is local |
| 1.3 | python-coder | `kb_tools/kb_mcp.py` (new), `kb_util.py` (`mcp` subcommand), `kb_tools/tests/test_kb_mcp.py`, `kb_tools/tests/fixtures/mcp/*.jsonl`, `kb_tools/tests/test_git_monopoly.py` (new), `kb_tools/SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md` | every Phase 1 fixture passes; the tool-name test holds; the process-boundary test passes; an import-structure test asserts `kb_mcp` imports nothing from `kb_tools/inference/`; the git monopoly test passes over today's tree; `KB_MCP_LOG_LEVEL` / `KB_MCP_LOG_FILE` are honoured; the incumbent check on `kb_driver.runlog` is reported (use it if `configure` can target stderr and a file with no run directory; otherwise configure stdlib `logging` in `kb_mcp` and say so) |
| 1.4 | python-coder | `gen_defs/mcp_registration.py` (new), `gen_defs/installation.py`, `gen_defs/agents_file.py` (shared harness-file reader only if it moves), `templates/harness/claude.toml`, `opencode.toml`, `tests/test_gen_defs.py`, root `SPEC.md`, `ARCHITECTURE.md` | `TestInstallEndToEnd` gains: install into `<tmp>/.claude` writes `<tmp>/.mcp.json` with one `kb` entry; a pre-existing foreign server survives; a second install writes nothing; an unparseable file is refused with nothing written and the report names it; `--subdir=` empty and a `rendered/` slot report `skipped`; the opencode harness writes `opencode.json` under `mcp` |
| 1.5 | prompt-engineer | `templates/agents/kb-docent.tmpl.md` (62–83 only), `templates/shared-chunks.toml` `kb-orientation` (the "Authored is not typed" paragraph) | the docent's query section names the tools with the CLI as fallback and says nothing yet about writing; render under `--family=gemma-4` and `claude` both read correctly; `just sweep-prose` shows no new candidate |
| 1.6 | operator | — | the live check above, both harnesses; `PROTOCOL_VERSION` and the two `mcp-server-entry` values confirmed or corrected in the same commit, with the evidence in its message |

### Phase 2 — stitching and region checks

| # | Owner | Files | Done when |
|---|---|---|---|
| 2.1 | python-coder | `kb_tools/kb_write/values.py`, `ops.py`, `kb_util.py` (`_handle_write_op`), `kb_tools/tests/test_kb_write_*.py` | `values.check_entries` is what `parse_values` calls after `tomllib`; `ops._execute` takes `ParsedValues`; `values.input_schema(op)` exists for every `OP_FIELDS` row and a test asserts its `required` equals the row's required fields and every property has a type; every existing write test passes byte-identical |
| 2.2 | python-coder | `kb_tools/kb_index_lib.py`, `kb_write/ops.py`, `kb_tools/SPEC.md` | `dependency_path` has unit tests over a synthetic cycle and a DAG; an `add-depends-on` values file closing a cycle exits 7 with the path in the report; `verify_kb_metadata.check_solidity_cycle` is untouched |
| 2.3 | python-coder | `kb_tools/kb_write/render.py`, `kb_docgraph/outline.py`, `kb_tools/tests/test_kb_write_render.py`, `test_kb_docgraph_*.py` | `render.render_uplink` and `render.render_child_link` exist; `outline.render` composes both through them and the docgraph fixtures render byte-identical before the old spelling is deleted (retire-after-replacement: the deletion lands in this row only after that comparison is green); no import cycle (`python3 -c "import kb_tools.kb_docgraph.outline, kb_tools.kb_write.render"` from the test suite) |
| 2.4 | python-coder | `kb_tools/kb_write/ops.py`, `values.py`, `store.py` (file create/delete/rename inside the atomic batch), `kb_util.py`, `kb_tools/tests/test_kb_write_ops.py`, `kb_tools/SPEC.md`, `ARCHITECTURE.md` | the six new ops are `OPS` members with `OP_FIELDS` rows and `kb_util` subcommands; each refusal in the catalogue has a test; after each op over the fixture consumer `run_kb_verify` is green with refresh run; `promote-document`'s source is gone only after the placed copy is proven; `move-document` of a claim-hosting leaf leaves its register link resolving |
| 2.5 | python-coder | `kb_tools/kb_claimgraph/region.py` (new), `kb_util.py`, `kb_tools/tests/test_kb_claimgraph_region.py`, `kb_tools/ARCHITECTURE.md` | over the fixture consumer, `region-unminted` lists exactly `identify.asked_paragraphs` minus marked paragraphs, each with a rendered ask whose prefix+tail equals `paragraph_asks(...)[i].compose(None)`; `region-unmarked` equals `unmarked.plan` minus authored edges, filtered by scope; `region-status` counts agree with `kb_cmd stats` where they overlap; the import-structure test asserts no `inference` or `letters.ask_group` import |
| 2.6 | python-coder | `kb_tools/kb_mcp.py`, `kb_tools/tests/test_kb_mcp.py`, fixtures | the Phase 2 fixtures pass: write tools refresh and report the derived delta; an `8` is absorbed; a cycle attempt is `isError` naming the path; `refresh` and the three region tools are listed |
| 2.7 | python-coder | `kb_tools/kb_index_lib.py` (`EXCLUDE_DIRS`), `kb_links.py` if `SKIP_DIRS` lists `session`, `kb_tools/SPEC.md` | `topics/` is outside the document walk and treated as `session/` is by the link crawl; a draft under `kb-root/topics/` leaves `kb-verify` green; `promote-document` accepts a source there |
| 2.8 | prompt-engineer | `templates/agents/kb-docent.tmpl.md`, `kb-maintainer.tmpl.md`, `templates/shared-chunks.toml` (`kb-orientation` role clauses, `kb-metadata-write`), `kb_tools/installed/AGENTS.tmpl.md`, `CONVENTIONS.tmpl.md` | the table above is reflected; neither definition states or implies a required order; the docent offers and accepts stitching actions and names orphan and pending as valid states; the maintainer's Job B lands work from anywhere; `tests/test_gen_defs.py` and `just sweep-prose` clean; both families render |
| 2.9 | python-coder | `kb_tools/tests/test_kb_mcp.py`, `kb_tools/tests/test_kb_util.py` | the tool-name test is extended to the Phase 2 set; a test asserts no `kb_util` build op (`preflight`, `graph-init`, `start-build`, `advance-step`, `show-*`, `validate-build`, `render-claim-graph`, `install-targets`, `uninstall-targets`) is a tool |

### Acceptance, the review loop's exit

- Every tool has a CLI counterpart and the two give the same answer on the fixture consumer.
- A fresh consumer after `just install` lists `kb` connected in both harnesses with no hand edit.
- Minting with no edges, scoring an orphan, and placing a draft leaf hosting nothing each leave
  `kb-verify` green.
- A `depends` cycle is refused at the write naming its path; nothing else about edge order or
  volume order is refused.
- No module under `kb_tools/` outside `kb_pipeline.py` and `kb_util.preflight_report` invokes git.
- `kb_mcp.py` and `kb_claimgraph/region.py` import nothing from `kb_tools/inference/`.
- The server survives a tool that prints: one frame per request on the fixture transcripts.

## Risks

- **Tool-list cost.** About 36 tools at ~200–400 tokens each is ~10K tokens of definitions in
  every session. Descriptions are kept to one sentence and schemas to the vocabulary; if it binds,
  the remedy is fewer read tools (`gated-on`, `cited-by`, `subtree` are the first to fold), not
  terser refusals.
- **Protocol version moves with harness releases.** Pinned constant plus the live check, repeated
  on a release that changes MCP; a harness refusing the pin is loud (no tools), not quiet.
- **Harness trust prompts.** Claude Code asks the user to approve a project `.mcp.json` the first
  time; opencode's behaviour is confirmed in the live check. Neither is this tool's to suppress.
- **A config the install cannot parse** (comments in `opencode.json`) is refused, and the user adds
  the entry by hand from the report; the server still works, unregistered until then.
- **Relative `PYTHONPATH`** relies on the harness starting the server from the project root. If a
  harness does not, the live check shows an import failure and the entry switches to an absolute
  path for that harness — a tracked-file portability cost, named here so it is a decision.
- **Full refresh per write.** Affordable at today's scale (`kb_tools/ROADMAP.md`, item
  "Full-vs-incremental refresh", revisits when rebuild time binds). The derived-delta read loads the
  index twice; also cheap.
- **Region-check output size.** A leaf's ask embeds the whole labelled body; the prefix-once split
  bounds it to one body per leaf or per source. A whole-KB `region-unmarked` is still large; the
  default scope in the agent text is a directory.
- **Already-built KBs keep the old conduct text** in their stamped `AGENTS.md` / `CONVENTIONS.md`.
  Remedy is the user's: delete and let the next `phase-3a` re-stamp, or edit. A `restamp` op is
  deliberately not in this plan.
- **`move-document` leaves citers to the caller.** Refusing when another document links to the old
  path is the honest minimum; a `rewrite_citers` flag is a follow-up if the refusal proves frequent.
- **Parallel writers.** The MCP server and a dispatched maintainer may write the same register;
  `kb_write.store`'s lock and the `8` retry already cover it, and the tool absorbs the retry.
- **Cross-package edge** `kb_docgraph.outline` → `kb_write.render`: a real import cycle would show
  in row 2.3's check; the fallback is to leave the build's spelling where it is and accept two
  composers with a test asserting they agree.

## Open questions for the owner

1. **Where registration runs.** This plan puts it inside `install`, guarded, because the server is
   inert unregistered and the write owns one key idempotently; the cost is a file `install` writes
   outside ROOT, which root `SPEC.md` (Deployed Surfaces) does not admit today. The alternative is
   an explicit verb on the `install-agents-file` model — one more step after every clone.
2. **The `kb-maintainer` seat.** With the session holding the full tool surface, the maintainer's
   remaining job is dispatched batch landing with file-ownership parallelism. Keep it for that (the
   plan assumes so), or retire it and let the session dispatch generic coders with the tools.
