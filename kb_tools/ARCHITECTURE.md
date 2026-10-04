# ARCHITECTURE – kb_tools

How the toolchain and the agent set that drives it satisfy SPEC.md: the module layout, the CLI's op
set, the build pipeline's stage table and ledger, and the query surface. Cites SPEC's requirements
rather than restating them.

Before deciding whether a stage belongs in this table at all, or whether a question about this
pipeline's shape is even worth answering, read THESIS.md — that judgment is settled there, not here.

## Module Inventory

Single-source modules (the anti-drift discipline — one definition, many consumers):

| Module | Role |
|---|---|
| `install_location.py` | Which harness this copy is installed under (SPEC.md, Runner Targets): `current()` walks up from the package's own `__file__` — unresolved, so a symlinked `agents/` is located at the link — to the nearest `.claude` or `.opencode` ancestor and returns an `InstallLocation` (`harness_dir`, `project_root`, `agents_dir` — the PYTHONPATH entry — `agents_relpath`, `scratch_dir`), raising `InstallLocationError` where there is none. Called at the point of use, never at import, so a module imported from the source tree fails only where it spells a harness path. Every harness-named path reaches the code through it, via `kb_util`'s `harness_dirname` / `scratch_dirname` / `invocation` / `driver_invocation` / `install_line`; it reads nothing about the repository being worked on. The test suite runs from the source tree, so `tests/conftest.py` stands up `<tmp>/.claude/agents/kb_tools` (a link to the package) and points `current` at it before collection; a subprocess given `current().agents_dir` as its PYTHONPATH then locates itself through the link for real. |
| `kb_util.py` | Repo/KB path construction (the consuming repo's root is discovered by walking up from the cwd to `.git` with `kb-root/` beside it — never from `__file__`, which points wherever this toolchain happens to have been installed rather than at the repo being worked on; the KB directory name is single-sourced here, not hardwired across tools; harness-named paths spelled relative to that root come from `install_location`) **and** maintenance-command hints (`just`/`make` `kb-refresh`/`kb-verify`, detected from the root's runner file) for remediation output + tests. Also the build front-end CLI, one subcommand per op — `preflight` / `graph-init` / `install-targets` / `uninstall-targets` / `show-status` / `show-stage-status` / `start-build` / `advance-step` / `show-run-lock` / `validate-build` / `insert-claim-entry` / `insert-support-entry` / `insert-experiment-entry` / `insert-work-entry` / `set-work-strength` / `set-applicability` / `set-rigor` / `set-rationale` / `add-depends-on` / `set-frontmatter` / `mark-claim-in-leaf` / `set-on-point-fraction` / `render-citation`; see Runner Targets and the Build Ledger, below, and The Write API (`kb_write/`), below. One CLI by ruling: the validator, the reading verbs, every member of `kb_write.ops.OPS` and the one read-only metadata op in `READ_OPS` are members of this op set, not second entry points. Each subcommand declares its own options, so a companion belonging to one op cannot be spelled on another. `show-run-lock` reports the driver's run lock — live, stale or absent, with the holder named — for callers outside `kb_driver/`; the judgement is `runlog.lock_state`'s and the op restates none of it, writes nothing, clears nothing, and answers on stdout rather than through its exit status. (`survey-sources`, `validate-skeleton` and `render-manifest` fronted the deleted LaTeX-reading survey and are gone with it — kb_survey, Retained, above.) |
| `kb_pipeline.py` | The build pipeline's state machine: the ordered stage table (the single source of the stage vocabulary), the git-commit-trail ledger, and the checklist render. Driven through `kb_util`'s ledger ops (`show-status` / `show-stage-status` / `start-build` / `advance-step`). Also the readers and writers of the claim graph's build records — the node-pass record, and the classification and unmarked records through one pair-keyed letter-record codec — because `kb_claimgraph` imports this module and not the reverse. |
| `kb_schema.py` | The build-band ladder, the `clm`/`exp`/`sup` id grammar (`[a-z0-9]{6}` body), the collision-checked id minter, and the one id grammar that is **not** minted — `work-` plus a citation key, derived by `work_id` from the key rather than drawn, which is why `work` sits outside `ID_KINDS` (every consumer of that tuple is asking about minting). Also the **node-kind vocabulary**, `NODE_KINDS` — every value a `node_type` takes, which answers the other question: what exists, rather than what gets minted. A census, a breakdown, a union or an ordering iterates it; a site that *branches* per kind keeps naming kinds and wraps its table in `kind_table`, which refuses one that is not total over the vocabulary at the moment it is defined. `FRAMEWORK_KINDS` is the bedrock subset and `node_kind_plural` the one statement of a kind's report label. The definition of each vocabulary, not a copy of one. Also the **equation node's title grammar** (`equation_title` / `equation_label`, `` Equation (`label`) — heading ``) — the join key that makes a `clm-` entry an equation node to any reader, since neither its id nor its register entry otherwise distinguishes it from any other claim: `kb_claimgraph` composes it at mint time and `verify_kb_metadata` reads it back to classify a canonical entry as one, and neither package may import the other for it, the same discipline `kb_index_lib`'s KB-walk sits apart from both to keep. |
| `kb_links.py` | Low-level Markdown link-scanning primitives (code-span neutralization, inline-link regex, file crawl, skip-dir rules, the document-template skip) shared by the link checker and the query CLI's reverse-find. Also the toolchain's one link rewrite, `rebase_inline_links`, for inline text copied into a document in another directory. Primitives only; classification/gating stays in the checker. `blank_fenced_lines` is the toolchain's one fence scanner, and it reads a fence the way SPEC.md point 9 spells one: any indentation, **any depth of blockquote marker**, a close on the same character at least as long, carrying nothing after it but emphasis markers. Each condition is a measured failure, and the last two are the same document twice — a display-maths fence inside a labelled blockquote (point 12) that no column-anchored scanner opens, so `[T_{P,Q}g](z)` is read as an inline link to a file named `z`, and that same fence's close written `` ```* `` because the emphasised theorem statement around it terminates on the delimiter's own line. A fence opened inside a blockquote closes with the blockquote — fenced content takes no lazy continuation, so an unprefixed line is outside both — which is what bounds an unclosed quoted fence to its block instead of blanking the file to its end and reporting the silence as a clean scan. `strip_code` additionally blanks **inline** maths (`INLINE_MATH_RE`, public because `kb_claimgraph/shortlist.py` reads maths spans with it), which the gfm writer spells `` $`…`$ `` and hard-wraps mid-span, so a continuation line's `\bigl[…\bigr](\xi)` is not read as a link to a file named `\xi`; the `$` required at both ends is what makes a multi-line blank safe where a bare code span is not — an odd backtick in prose cannot open one and take real broken links with it. |
| `pandoc.py` | The one module that knows how LaTeX is read: `to_ast` / `to_markdown` / `from_ast` / `version`, and nothing else in the package names the `pandoc` binary or builds an argv for it. It owns one three-way decision: `--citeproc` and one `--bibliography` per file where any bibliography stands, and `CITATION_KEYS_ONLY_FLAG` where none does — one condition, three flags, so a caller cannot set two and land back in silent deletion. `bibliographies` is a **set of files and not a choice among them**: pandoc takes the flag repeatedly and merges what it is given, and citeproc renders only the entries a source cites, so an uncited extra is inert. The order is the caller's and is preserved, a key two files define resolving to the first. Filters precede `--citeproc` in the argv and pandoc applies them in order, which is what lets the filter mark a citation before citeproc resolves it (measured against pandoc 3.11, not read off the manual). The single enumerated exception to SPEC.md's stdlib-only invariant, and a different kind of one than the vendored parser it replaced — a system binary this module assumes present rather than a copy the repository ships (SPEC.md, Corpus Invariants). `PandocMissingError` is what a caller gets instead of a bare `FileNotFoundError`. `PandocBibliographyError` is the second named failure and the only one a caller may continue past — a `--bibliography` the reader could not parse, discriminated on pandoc's own exit code (25, against an unparseable source's 64) rather than on message text, so widening the recovery to a real failure takes an exit code and not a reworded string; the code says *a* file failed and not which, so pandoc's own complaint is the only thing naming it. `PandocIncludeError` is the third, and the one failure raised at **exit 0**: an `\input` target the reader could not load takes its file's content out of the parse entirely, so it reaches neither side of either partition check and a silent run produces a paper without its body (SPEC.md point 8, the known hole). It is matched on pandoc's own sentence because no exit code and no artifact records it — the stderr line is the only evidence there is — and `_UNLOADABLE_INCLUDE_RE` is narrowed to that sentence plus a source position of its own shape, the position's filename optional because this module's sources arrive on stdin and pandoc names no file for one. It carries every unloaded target with the line that named it. See The Document Graph (`kb_docgraph/`), below. |

Pipeline scripts:

| Script | Role |
|---|---|
| `kb_index_lib.py` | Core library: leaf/register parsing + the shared `compute_solidity` / subtree-aggregate / leaf-reference computations. Also **the** KB document walk (`kb_files` / `document_texts`), here because `kb_pipeline` and `kb_claimgraph` each need it and may not import each other (What the Stage Table Declares, below). Both refresh and verify call these so the two can never dual-compute and drift. Also `scan_authored_ids(kb_root) -> {id: IdRecord(kind, register_path, hosting_leaf)}` — the authored-id inventory, read from registers and leaf frontmatter and **never** from `.index/`, so it is correct on a KB whose derived index is empty or stale — and `anchor_section(text, anchor)`, the code-stripped body of the section an anchor names, which the citation gate and the citation composer both read a cited document through. |
| `refresh_kb_metadata.py` | The refresh target — regenerates derived metadata (solidity write-backs, subtree aggregates, leaf-reference footers), the `.index/*.jsonl`, and then the claim-graph sheet from the index it just wrote (The Claim-Graph Sheet, below). Idempotent: same canonical state → byte-identical output, and always a full rebuild rather than an incremental one — the freshness gate is this same rebuild run in dry-run and diffed against disk, so an incremental path would leave verify rebuilding by a route refresh does not take (future intent: see ROADMAP.md). |
| `verify_kb_metadata.py` | Claim-graph integrity gate — frontmatter coverage, id uniqueness, orphan/referential integrity, bidirectional coverage, acyclicity, and freshness (runs the build in dry-run, diffs against on-disk; any diff = stale = hard fail). **Tier-2 marker coverage exempts an equation node from both the count and the demand** (`check_tier2_coverage`'s `equation_ids` argument, `equation_node_ids` reading `kb_schema.equation_label` against each register title): a maths fence's `\label` line is already the node's position, the way the same title already carries its identity, and no block-level marker may be written into a fence without touching the mathematics point 9 guarantees verbatim — so a leaf hosting one block claim and four equations still demands a marker for the one claim only, exactly as it did before the equations were minted. The exemption takes the `work-` node's own shape in `check_uncited_entries`, dropped from marker coverage entirely rather than merely excused from failing it. **Bidirectional coverage still reaches an equation node** — it is listed in its hosting leaf's `claims:` like any other entry; only the marker relation excludes it. The claim-graph sheet joins that freshness gate on the same terms: `check_claim_graph_fresh` re-composes the sheet the on-disk `.index/` renders and byte-compares it, absent and hand-edited being one drift. |
| `verify_md_links.py` | Repo-wide dead-link gate — **every** `.md` file must have zero dead links, a document template (`*.tmpl.md`) excepted: its links resolve where a build stamps it, and the stamped file is gated there. |
| `verify_citations.py` | Citation-grammar gate over authored files (grammar in SPEC.md, Citation Grammar): channel exclusivity, referent existence, excerpt match + length bound, durable targets, and edge-backed foreign-domain references. Leaf bodies exempt; `.index/` out of scope. |
| `kb_cmd/` | Read-side query package over `.index/` (`index.py` loads JSONL into dataclasses and exposes question-shaped lookups; `cli.py` is the shell wrapper). See Query Surface, below. |
| `kb_graph/` | The claim-graph SVG renderer, in four staged modules: `model.py` assembles the node table, the drawn edge set — deduped, narrowed to the premise relations with a group whose surviving `relation` is `references` dropped whole, then **transitively reduced** over the premise relation (SPEC.md, The Claim-Graph Sheet) — the defects decidable without geometry and each node's domain attribution, reading `.index/` only through `kb_cmd.index`'s dataclasses and taking `depends-on.jsonl` as its sole edge source. **The reduction is greedy and reads the edges still standing rather than a snapshot**, which is what makes it defined on a graph that is not a DAG: a ring has a route from each member back to itself, and a snapshot-based reduction elides every edge of one and strands its claims, while testing against what is left leaves the last stroke holding the ring. Its unit is the premise *pair* and not the stroke — two strokes can state one premise, and they are one relationship for a reader as they are one constraint for the layering — and its direction is the premise direction (`model.premise_pair`, the single statement of which end of a record is the premise, read by the reduction and by `layout._premise_pairs` alike), never the record's: a `supports` record and a `depends` record spell a chain in record order that is no chain at all in premise order. Reachability is invariant across every elision, which is why `isolated` and `components` may be measured over the reduced set at all. **It happens here rather than at the drawing because a placeholder column is planted by `layout._occupants` from `graph.edges`**: an edge elided downstream of that would still take its columns and still set the sheet's width, so the only place the reduction pays is upstream of geometry; `layout.py` places geometry — layering, in-layer ordering, coordinate assignment, edge routing, and hop detection with hop-side selection — in exact integer arithmetic. **A node of degree zero over the corpus's drawn graph is not layered at all**: layering has nothing to ask of a node with no premises and no dependents, so every one of them landed on layer 0. Such a node leaves the hierarchy and is drawn in a grid block below everything the hierarchy occupies and flush with its left edge, `style.ORPHAN_ROW` to a row, in the same ascending-id key a layer's occupants start from — and degree is the corpus's, never the drawn sheet's, or a node whose one edge leaves a selected domain would be an orphan on that sheet and a premise on the full one. Since the drawn set is the premise set, **a claim only `references` reach is one of them**, and the block's height is the measure of how much of the KB the argument does not attach — a diagnostic on a mechanically-built corpus rather than an accident of it. An edge spanning N layers routes as a chain of N−1 dummies, one per intervening layer, each taking a real column of its own layer on the in-layer ordering key, and draws as one path of N runs; `PlacedEdge` carries `points` with `start`, `end` and `segments` as derived properties, and crossing detection runs pairwise over segments rather than whole edges, since two chains can cross more than once. The `viewBox` unions every drawn box with every stroke vertex, because a chain can bend to the right of the widest box in its own layer. **Which layer a claim stands on is not its depth from bedrock**: layer assignment is an adopted phase of the algorithm, by the network simplex — the premise relations' total layer span minimised, which is the placeholder count, so a premise nothing holds down rises to meet the claim that needs it instead of being drawn on bedrock under a chain of placeholders. In-layer order is no longer id-ascending alone: crossing reduction is an adopted phase of the algorithm, an iterated sweep over the dummy-bearing layers. **A column index is no longer a coordinate either**: coordinate assignment is an adopted phase too, by the priority method — each occupant pulled toward the barycentre of its neighbours in the adjacent layer, a dummy outranking every real node so a long edge's chain straightens, and no occupant passing its neighbours in the order the sweep chose or closing the gutter between two boxes. **Those three phases hand their result to an *arrangement*, which is the only thing that decides where an occupant stands** (SPEC.md, The Claim-Graph Sheet): `layout.PLACEMENTS` holds them, `layout.DEFAULT_PLACEMENT` is the one that ships and `layout.PLACEMENT_ENV` — `KB_GRAPH_PLACEMENT`, accepting `linear`, `ring-rectangle` and `ring-ellipse` — overrides it. That variable is a **development control and nothing a consumer touches**: no runner target passes it, no op takes a flag for it, and an unrecognised value raises rather than falling back, a sheet silently drawn by an arrangement nobody asked for being indistinguishable from one that was and reading, at the freshness gate, as a change to the graph. The concentric arrangement is what ships, and its ring index *is* the layer counting inward from bedrock, so the conclusions are the centre — measured rather than assumed, bedrock-centred costing area on every corpus and leaving a 448×362 empty half-side on the arXiv one. Its two **forms** differ in the candidate positions they offer and in nothing else — `rectangle`, whose candidates are one column pitch apart along the horizontal sides and one layer pitch apart along the vertical ones and therefore clear by construction, and `ellipse`, walked in integers by `math.isqrt` on `svg._fixed_length`'s precedent since libm is not byte-reproducible across hosts — because the separation rule is a property of two placed rectangles and never of any ring, and so lives in `layout._place_ring` with the forms stating positions alone. A ring that cannot seat its occupants clear of each other and of the ring within it **grows**, which is how a form pays for needing room deterministically and what the ellipse's diagonal sector spends; a ring that exhausts `RING_GROWTH` draws crowded rather than refusing, on the same rule as every other cap in the module. `style.RING_STEP` is how many pitches one ring stands outside the one within it, and it exists as a constant because at one pitch the rings sit exactly as far apart as two side-by-side boxes and the nested rectangles tile a lattice with no boundary in it. Two consequences reach the rest of the sheet: a ring has no up, so a stroke anchors at the box centres rather than at a top and a bottom edge — the emitter drawing the boxes opaque and last is what still makes a stroke leave from under its own box edge — and the orphan block's floor is read off the placed occupants (`layout._orphan_origin`) rather than off the baseline, a disc having nothing below it until the occupants say where. On the layered arrangement both resolve to exactly what they always were. Every phase's method, parameters, round cap and convergence condition are recorded in this module's own docstring rather than here; a hop's bulge is not, being the emitter's, which orders the arc's two endpoints by screen x so the bridge reads the same way on an edge the graph drew right to left. **Nor is the curve those points are joined by**: layout decides where a chain's vertices sit and `svg.py` decides only how they are connected, by centripetal Catmull-Rom (α = ½) written as one cubic Bezier per run, with both control points of every run clamped to the bounding box of that chain's own vertices — which is what makes a stroke leaving the `viewBox` impossible rather than unobserved, the `viewBox` already unioning those vertices. The parametrisation, the variants measured against it and what each cost are recorded on `svg._control_points`; and so is where the hop glyph goes: `layout._hops` still finds crossings between the straight chords, and `svg.draw_hop_over` places the glyph on the drawn cubic at the parameter the crossing sits at along its own chord — exact rational evaluation, with no curve–curve intersection to root-find. Geometry stays a pure function of the graph's own records, independent of the order they were loaded in. No stroke reaches layout that states no premise, so the layering has no class to exempt and no stroke needs a channel of its own to say it is not a dependency. `style.py` holds every presentation constant and gates nothing; `svg.py` is the only module composing markup, built as an element tree and serialized by it. Nothing in the package refuses: a defective graph is the picture's subject, so a cycle, a ghost id or a `relation` conflict comes back as data for the drawing and the report lines, and no property of the graph — not a cycle, not zero edges, not zero nodes — is a precondition. `ops.py` is the op: `render` writes one sheet and returns its exit code, report and path; `compose` stops a step short at the markup, which is what lets `verify` ask what the index would render without writing anything. Fronted by `kb_util`'s `render-claim-graph` subcommand, and called by `refresh` and `verify` (The Claim-Graph Sheet, below). |
| `kb_write/` | The metadata write API: the ops every authored metadata byte reaches a KB file through — values in, canonical bytes out, each write proven by readback before it lands. Contract in SPEC.md, The Write API's Contract; module roles below. |
| `kb_docgraph/` | LaTeX volumes in, the KB's navigable Markdown tree out — one pandoc parse per volume root, zipped against that parse's own whole-volume rendering, split into documents, written and gated. The current front end for everything SPEC.md's Topography graph guarantees. See The Document Graph (`kb_docgraph/`), below. |
| `kb_claimgraph/` | The KB's navigable Markdown tree in, the claim-graph metadata spine authored into it — the conformance gate, the claim-site inventory, claim identification, dependency attribution, assembly, the write passes and the refresh/verify gate, over five invocations: the declared graph mechanically, the node pass over every leaf's prose, the referenced equations, the unmarked references asked over a mechanical shortlist, then the dependency edges additively over the node set those three fixed. Reads the tree as its **sole input** and writes every metadata byte through `kb_write`. See The Claim Graph (`kb_claimgraph/`), below. |
| `kb_survey/` | Three stdlib-only modules retained from the toolchain's pre-pandoc LaTeX reader: the manifest schema, a second (unused-by-`kb_docgraph`) skeleton derivation, and the tree validator `kb_docgraph` itself calls. Nothing here reads LaTeX any more. See kb_survey, Retained, below. |
| `kb_driver/` | The build sequencer — walks a step table itself rather than briefing an agent to walk it. It sequences a KB build end to end: the head, where the two front ends below produce the tree and the claim graph over it, and the tail, where that product is validated and documented. Contract in SPEC.md, The Driver's Contract; module roles below. |
| `inference/` | One model call, for any tool here that wants one: `liaison_tools.call_chat`, one tool-less chat-completions request made directly to the server named by `liaison_tools`' own environment — the format `post-openai.py` reads and a `reaper-*.env` file holds: `API_BASE_URL`, the API root with `/v1` already in it, to whose `/chat/completions` the request goes; `MODEL`, the model; `API_KEY_FILE`, the key file, read and validated by `openai_chat.read_api_key`, the reader `post-openai.py` uses, and never logged; and `ALLOW_HTTP`, exactly `1` accepting plaintext http to a non-loopback host as it does there. `TEMPERATURE` is not read. **`check_environment` is the one validation of that environment**, public so a caller can refuse before it spends anything, and `call_chat` runs it on every call: an unset `API_BASE_URL`, `MODEL` or `API_KEY_FILE`, a key file that is missing or not one whitespace-free key, and a URL that is not https, http to a loopback host, or http with `ALLOW_HTTP=1` each raise `ValueError` naming the variable, before any request and echoing neither the URL nor the key. An empty system prompt or prompt is refused the same way. The request goes through the shipped `liaison_tools` package's `openai_chat`, imported at the call so `kb_tools` still imports where that package is absent, and carries the call's system prompt, `chat_template_kwargs.enable_thinking: false`, temperature 0 — passed explicitly, whatever `TEMPERATURE` the environment sets or `liaison_tools` defaults to — and no tools, and asks for the usage chunk. **How a call ended is `Outcome`**: a stream reaching `[DONE]` is `OK`, an empty reply or one cut at the token limit included, the cut logged; one short of it is `TRANSPORT_FAILURE`. `timeout_seconds` bounds each socket read and nothing bounds the call as a whole. **The capture's producer owns its reader.** A capture is every SSE payload verbatim and, per attempt, a closing `liaison-request` line carrying the request's measured time and outcome; no key or base URL is written or logged. `read_capture` gives the attempts that streamed `reasoning_content` or `reasoning`, counted over every attempt, and the rest — the measured time, `usage.prompt_tokens`, `completion_tokens` and `prompt_tokens_details.cached_tokens` — off the last closed attempt, each `None` where the server sent none. **Policy is the caller's**: retry, a re-ask, where a bound's value comes from. It knows no KB vocabulary. Stdlib only, and it configures no logging handler: a run attaches its own to `inference.LOGGER_NAME` (`runlog.configure`). |
| `installed/` | Artifacts written **into** a consuming KB, never rendered here: `AGENTS.tmpl.md` and `CONVENTIONS.tmpl.md`, stamped into `<kb-root>/` by `kb_pipeline.stamp_readiness_docs`, `phase-3a`'s pre-commit hook, each only if absent, beside a `CLAUDE.md` the stamp writes from `kb_index_lib.AGENTS_REDIRECT` rather than from a template. `AGENTS.tmpl.md`'s `{scope-pin}` slot is filled there from the build's recorded charter (SPEC.md, Project Scoping), and `CONVENTIONS.tmpl.md`'s `{agents-dir}` from `install_location` and `{node-kinds}` from `kb_schema.NODE_KINDS`. A `kb-root/CLAUDE.md` that is not the redirect stops the stamp, refresh and verify alike through one predicate, `kb_index_lib.unmigrated_agents_file`. Neither template is the source of the file of the same name beside this table. |
| `tests/` | Unit tests over synthetic fixtures (the project's test target). |

### The Write API (`kb_write/`)

`kb_write/` is where SPEC.md's write-API contract (values in, canonical bytes out — see The Write
API's Contract) is composed. Consumers reach it through one `kb_util` subcommand per member of
`ops.OPS`, and its read-only op through one more (see the CLI table above).

| Module | Role |
|---|---|
| `render.py` | The single composer of metadata bytes: register entries (claim, support and external work), the kb-frontmatter block, id and Tier-2 markers, structured bullets, prose collapse, derived-field placeholders, and the citation form. Values in, text out — total, pure, path-free, and holding no validation. |
| `values.py` | The values-file grammar (TOML) and the closed per-op key vocabulary: parse, domain-check, and refuse with a message naming the field and the line. It answers "is this a well-formed value?" and nothing else — it resolves no id and opens no file under `kb-root/`. Every numeric bound it enforces is inherited from the contract that already states it; this package authors none of its own. |
| `store.py` | The read-modify-write path over authored Markdown: path containment inside `kb-root/`, the register census, locate/splice, the temp beside the target, the readback proof on the temp, the concurrency check, and the atomic replace. Returns written / refused / retry as data; the exit codes are `ops`'. |
| `ops.py` | Op semantics: the validation ladder in order, mint fusion, the report lines, and the outcome-to-exit-code mapping — one function per op, plus the two registries a surface binds: `OPS`, the ops that write, and `READ_OPS`, the ops that read to verify and print. Surface-independent by construction (no `argparse`, no `sys.argv`, no `sys.exit`), so what an op means does not change when its surface does. One non-op name is public: `excerpt_lines`, the matching `mark-claim-in-leaf` resolves a locator by, exported so a caller composing one can ask the op's own question before spending a write. A caller that re-implemented it would be the checker that re-derives what the emitter derived, and a pre-check disagreeing with the op it pre-checks is worse than none. |

### The Document Graph (`kb_docgraph/`)

LaTeX volumes in, the KB's navigable Markdown tree out — run from its own command line
(`python3 -m kb_tools.kb_docgraph --source <root> [--source ...] [--bibliography <path> ...] --kb-root <dir>`),
and by `kb_driver` at the `document-graph` stage, which composes that same line from the run's own
sources (The Driver, below). It is the front end for everything SPEC.md's Topography graph
guarantees, and produces no claim-graph artifact of any kind — no `.index/`, no frontmatter, no id
or claim-quality marker.

Four stages, each mechanical, plus the checks that make the mechanical claims enforceable rather
than aspirational:

| Module | Role |
|---|---|
| `convert.py` | Stage 1: one volume root, a source pre-pass (`strip_environment_declarations`, over `\newenvironment` — it must run *before* pandoc parses, because pandoc expands a declared environment during parsing and by the time any filter runs the author's name for it is gone), a second source reading (`theorem_display_names`, over `\newtheorem` — the preamble is consumed, so the internal-name→display-name mapping reaches the filter only if the caller reads it off the source; a babel translation macro resolves to its stem, and any other display name carrying a backslash is dropped rather than put on a label line), then two pandoc calls under one shared Lua filter and the same mapping — `to_ast` for the index, `to_markdown` (`-s`, so the metadata channel survives) for the content. Both get the mapping because check A compares the AST's own text against the rendering's, and a label word on one side only reads as a drop. The scan is the volume root's own text, so a preamble reached by `\input` yields no mapping and every block falls back to its internal name. The working directory is set to the volume's own on every call, because pandoc resolves `\input` against the invoking process's directory rather than the source file's. **One pandoc failure is recoverable here and the rest are stops**: a `--bibliography` the reader cannot parse is the input SPEC.md point 10 says a corpus may not have, so both conversions are re-run with none — both, because stage 2 zips them and check A compares one's text against the other's — and the files travel out on `Volume.unreadable_bibliographies` for `build.py` to report. The retry drops the **whole** set rather than a guess at the offender, pandoc's exit code naming none of them. The catch is on `pandoc.PandocBibliographyError` and never on the base type, so an unparseable source still stops. `pandoc.PandocIncludeError` is caught too and is not a recovery: it is re-raised as itself carrying the volume root, because the source travels to pandoc on stdin and its complaint names a line with no file, so a run over several roots would otherwise report the loss against none of them. **Neither source pre-pass refuses, and the standing rule is why**: both read author markup held to no fixed standard, so a form the scan cannot read is an ordinary input rather than an exception — nothing mechanical is provably wrong and the unit that cannot be read can be named. `strip_environment_declarations` is brace-balanced and comment-aware, a `%` ending a line inside a declaration as it does anywhere else: LyX writes `\newenvironment{elabeling}[2][]%` and puts the body groups on the lines beneath, which a whitespace-only scan stops at and calls malformed. A declaration it still cannot read is left where it was written and travels out on `Volume.unreadable_declarations` for `build.py` to report on its own `declaration-read` line — a `FACT` naming the line of the volume root each one opens on, and stated in a zero form too, because a tree whose blocks lost their names reads exactly like a corpus that distinguished no block — and the scan carries on from the end of that keyword. What that costs is the environment's own blocks: pandoc expands them as the author defined them, so their content reaches the tree and neither partition check goes false, but they arrive as ordinary content rather than as labelled blockquotes carrying a name (SPEC.md point 12). |
| `outline.py` | Stage 2: the AST's `Header` sequence zipped against the rendering's own headings — asserted aligned, in count, level and text, before either is used — builds the tree. Level and label come from the AST (a heading's `\label` has nowhere to land in gfm); text comes from the rendering, never re-rendered from an AST slice. Frontmatter is parsed and classified here too (`CONTENT_KEYS`/`APPARATUS_KEYS`): `abstract` and `title` are content, `address`/`author`/`date`/`bibliography` are apparatus and dropped. The list enumerates and SPEC.md point 13's criterion classifies: `address` is `amsart`'s author affiliation and the only one of that class's byline macros pandoc 3.11 lifts into `meta` at all, so the rest are absent because nothing emits them rather than because the criterion is unsure of them. `split_bibliography` lifts citeproc's reference list out of the rendering *before* the split at headings and `_references_document` makes it `<volume>/references.md`, the volume index's last child (SPEC.md point 10); the marker is the Div's own `id="refs"` plus its `csl-bib-body` class, the labels it declares move to it with its content, and the words stay on both sides of check B because this is a relocation, not an elision. `_lift_own_prose` is the sibling relocation: a section's own prose ahead of its first subsection becomes a first child leaf titled by `OWN_PROSE_TITLE`, splitting the section's labels the same way — see The Derived Skeleton, below, for both. |
| `judge.py` | The heuristic seam: `judge(tree) -> Verdict` accepts every input today; `recut(tree, verdict) -> Tree` is reached only from the reject branch and raises if invoked. See The Derived Skeleton's judgment seam, below. |
| `partition.py` | The build's own checks: the two checks below (The Partition Checks), the maths-survival count, the anchor-landing check, and the image-asset report. |
| `walk.py` | Reads pandoc's JSON AST. Word-granular — every word a `Str`, every gap a `Space` — so everything here walks rather than phrase-matches: the `Header` sequence, every cross-reference-bearing identifier (a `Div`/`Figure`/`Span` id, an equation's in-source `\label`), `meta` walked *recursively by node type* rather than enumerated by container (`author` is a `MetaList`; a walk that handles only `MetaBlocks`/`MetaInlines` skips it without a word), and every `Math` element's LaTeX. **A `Header` inside a `BlockQuote` is not in that sequence** (SPEC.md point 12): the filter has already reshaped an author-distinguished block into one, and an author's `\paragraph{Step 1.}` inside a proof is a step of that proof. `text.headings` leaves the same heading quoted where it sits, so the two sequences stage 2 zips are one rule read on two representations rather than two rules that agreed until a proof carried a heading. Only the heading reads differently inside a quote — a `Span` id still reaches `anchored_labels` from there, which is exactly where point 12 puts `<span id="thm:bif">` — and the heading's own label maps to the enclosing section, so a `\ref` to it lands on the document the block reached. `math_texts` takes the content metadata keys from its caller and walks no others: `blocks` in full plus `outline.CONTENT_KEYS`, which is where point 9 meets point 13 (an abstract's maths is counted, a byline's `^{1}` affiliation marker is not, having no document to reach). The classification stays in `outline.py`; a second reading of it here is a second thing to move when point 13's list moves. |
| `text.py` | Turns AST text and rendered Markdown into comparable token streams (`plain_tokens` / `markdown_tokens`, fence-aware, undoing what the gfm writer did to a rendering — tags, escapes, wrapped autolinks, character references, and a whole `<math>` element dropped the way a `` $`…`$ `` span is, the AST spelling that element once where the tag pass alone would leave both its glyphs and its annotation behind as text, and an inline code span **padded rather than dropped** — `walk`'s runs break at a `Code` and hold none of its content, while the writer spells the span flush against its neighbour, so restoring the boundary keeps the words on this side too, which matters because check B compares this stream against itself and a dropped span would hide a splitter that lost one) and finds headings in rendered text (`headings`, wrapped continuation lines folded back in) — the one normalization the splitter and the partition checks share. Its three fence scans read one delimiter rule (`_delimiter`): any indentation, because point 9's fence opens at a list item's content column; a close on the opening marker alone, because an author's `~~~` spacing is equation content; and `fenced_blocks` giving the item's columns back, because point 9's verbatim LaTeX does not carry them. **The writer has a second spelling of verbatim and `markdown_tokens` reads that too**: an attribute-less `CodeBlock` — every `\begin{verbatim}` — is written indented rather than fenced, and is measured against its *container's* content column, because pandoc writes `1.  ` and an enumerate item's second paragraph otherwise sits at the same four columns a top-level code block does. Read as code, its cross-reference runs would break; read as prose, its `_` is deleted as an emphasis mark and every identifier carrying one is reported lost. |
| `build.py` | Stage 3: writes the tree and its copied image assets, runs both partition checks plus the maths/anchor/asset checks, `kb_survey.validate.validate_build` (below) and the repo-wide dead-link gate, and returns a `Report` whose `failed` property is the whole verdict. A failure stops; there is no fix loop, because every check compares one mechanical product against another and a red gate is a defect in this package or its input, never something a seat repairs. |
| `authored_blocks.lua` | The one Lua filter both pandoc calls run under. Wraps every `Cite` in `<span class="citation" data-cites="…">` — pandoc's own markup for one — leaving the `Cite` inside so citeproc still resolves it and still emits the `refs` Div the references leaf is cut from; where `pandoc.CITATION_KEYS_ONLY_FLAG` says no citeproc will run, the span carries the keys as its own visible text instead. That flag is read in a first `Meta` pass and **removed**, because it is an invocation argument the tool passed itself rather than the document's metadata, and `outline.py` classifies every metadata key it finds against a closed list. Also reshapes an author-declared Div into a labelled blockquote, carrying the identifier forward on a `Span` so a `\label` survives to the label-to-node map — and, downstream of that map, as the definition end of SPEC.md's cross-reference join (Corpus Invariants), which is what a reference resolves against; drops the `titlepage` Div outright. **Identifying such a Div is structural and naming it is not.** Pandoc classes an unrecognised environment with the declaration's *internal* name, so `\newtheorem{claimbox}{Result}` yields a Div classed `claimbox`, and a filter keyed on a list of declarations would find neither an environment nobody declared nor amsthm's `proof`; but that class is an arbitrary handle, and point 12's label line carries the *display* name. The mapping arrives on `pandoc.THEOREM_NAMES_FLAG` — read in the same first `Meta` pass, JSON-decoded, and removed for the same reason — because pandoc consumes the preamble and no `\newtheorem` reaches a filter in any form; a class the mapping does not answer falls back to itself. **Lifts a display equation out of the `Emph` around it**, the words either side keeping their emphasis and an emphasised group left holding no word emitted unwrapped. A `\newtheorem` environment's statement is italic, so the reader returns the whole statement — display equations included — as one `Emph`, and where an equation opens it the gfm writer puts that `Emph`'s delimiter against the fence's own backticks: `*``` math`, which opens no fence for any reader, leaves the closing delimiter to open one, and reads every heading after it as fenced. SPEC.md point 9 says display maths reaches a document as a fenced block holding the LaTeX verbatim, so the emphasis is what gives way. `Emph` is where this has been measured; another inline wrapper carrying display maths would reach stage 2's alignment check rather than pass quietly. |
| `__main__.py` | The CLI: `--source` (repeatable, each a volume root — never a file reached by `\input`), `--bibliography` (repeatable, none legal — the reader merges what it is given and renders only cited entries, so the caller passes the set it has rather than choosing), `--kb-root`. Prints the report's lines; exits 1 on any `FAIL`. |

#### The Derived Skeleton (`outline.py`, `judge.py`)

`outline.build_tree` places every heading at exactly one KB path, ranked per SPEC.md's
"normalisation is ranking, not subtraction": a volume's tree levels are the *rank* of each heading
level among the levels that volume actually uses, so `{1,4}` becomes tree levels `{1,2}` rather than
a tree carrying two empty interior levels. `entry-point.md` lists every volume; each volume owns a
directory named from its own title (or its filename stem, where it declares none); a heading with
descendants is `<slug>/index.md`, one without is `<slug>.md`; a volume's own lead-in material, and
every section's own prose ahead of its first subsection, becomes a first child leaf of that node
under a supplied `Overview` heading (`outline.OWN_PROSE_TITLE`), so an index node's own extent is
relocated rather than dropped and no index carries source of its own — the index keeps its own
heading, so every index reads the same whether or not its section wrote a lead-in. A node with
nothing below its heading has nothing to lift and gets no leaf, the answer `_references_document`
already gives an empty bibliography. `OWN_PROSE_TITLE` is accounted in `_supplied_titles` once per
leaf `_lift_own_prose` emits: a supplied title is listed exactly as many times as a segment carries
it, which is what keeps the lift a relocation rather than a word the split invented — check B's word
totals move by one word per leaf emitted, on both sides at once, and the check gates on the two
differences being empty rather than on the totals matching. The lift also splits a section's labels:
a heading's own identifier (`outline.header_labels`) stays with the heading and so with the index,
while a label the lead-in prose declares on its own account — a Div or Span id, an equation's
in-source `\label` — follows the prose to the leaf; in a built tree, `#preliminaries` stays on
`preliminaries/index.md` while `thm:mainrect`, declared in the Introduction's lead-in, resolves to
`introduction/overview.md`. Path segments are slugged from titles, collisions resolved by sibling
ordinal, and the slugger reserves `kb_index_lib`'s `EXCLUDE_NAMES` / `EXCLUDE_DIRS` and the `index`
stem, so a derived path can never be one leaf discovery would not see. `DepthError` stops the build
when the realized tree depth disagrees with the volume's own count of distinct heading levels — a
fault in the derivation, never a finding about the corpus.

**The judgment seam.** `judge(tree) -> Verdict` is where "is this decomposition good enough, or does
it need help?" will be asked — a volume that is one undivided wall of text, a leaf far larger than
its siblings, a hierarchy one level deep. It is stubbed: every volume is accepted today.
`recut(tree, verdict) -> Tree` is reached from the reject branch and from nowhere else, and raises
if it is ever invoked — there is no inference call, no prompt, and no data format for a response;
populating those is unbuilt work. Judging a decomposition undesirable is never done by truncating
it: the tree carries the author's hierarchy at whatever depth they wrote it.

#### The Partition Checks (`partition.py`)

**Two checks, because there are two things that can lose content.** Check A
(`check_ast_against_markdown`) compares the AST's blocks and `meta`'s content-bearing entries
against the whole-volume rendering, matching by contiguous word run rather than set membership — an
abstract restates the body's own vocabulary, so token overlap would score a dropped abstract as
present. It catches what *pandoc* drops. Check B (`check_markdown_against_tree`) compares that
rendering against the tree, Markdown on both sides, a near-total partition; it catches what *this
package's splitter* drops. The elision either check exempts is a closed list —
`outline.APPARATUS_KEYS` plus the `titlepage` Div the filter drops, and nothing else, a literal a
diff can show rather than a judgment call. Neither check sees what pandoc drops *before* parsing —
`tikzpicture` is the confirmed instance, absent from the AST entirely at exit 0 with no warning — so
a build is not self-certifying against a reader-level drop the AST itself never recorded. **A
reader-level drop the reader does announce is stopped where it is announced, never checked for
here**: an include pandoc could not load is `pandoc.PandocIncludeError` at exit 0, raised off the
stderr line that is the only record such a file leaves anywhere. Both checks would pass over it,
because the content is missing from both sides of both comparisons.

**Maths, citations and figures**, in the order SPEC.md states them: every `Math` element reaches a
document by literal containment (`check_math`), read in each of the three forms the writer carries
it in — an inline code span, a fence, and a caption's MathML annotation, the last unescaped first
because it is XML text and its LaTeX arrives written in character references. The source side of
that count is `blocks` plus `outline.CONTENT_KEYS`, never the whole of `meta`: point 13 elides the
byline before any document exists, so its `^{1}` affiliation markers have none to reach and asking
point 9's question over them reports the elision as a drop; citations *survive* because the Lua
filter wraps every `Cite` in pandoc's own citation markup before citeproc sees it, and *resolve*
where an explicit `--bibliography` is passed. The two used to be one thing: without `--citeproc`
every `\citet{}` reached the gfm writer as a `RawInline` it had nowhere to put and the citation was
silently gone, so a bib-less corpus built a tree with no citations in it and exited clean. Now a
bibliography is optional (SPEC.md point
10) and its absence costs resolution and the references leaf, not the citation. **A bibliography
    that cannot be read costs the same and is reported** — `build`'s own `bibliography-read` line, a
    `FACT` naming every file the volume was offered, because the degraded tree carries the same
    citation markup as a resolved one and a silent fallback would read as citations that resolved;
    figures are tabled (`ROADMAP.md`, the inline-drawn-figures item) — an external image that is on
    disk is copied and embedded as a self-linking image, one that is not is reported
    (`check_assets`) rather than a build stop, and an inline-drawn figure (`tikzpicture`) is not yet
    recoverable at all, pandoc having dropped it before the AST exists for any rule to select.

### The Claim Graph (`kb_claimgraph/`)

The tree in, the claim-graph metadata spine authored into it — invoked as a subprocess by
`kb_driver` at the five stages that follow the spine seed, one per invocation (The Driver, above),
never directly by an operator:
`PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_claimgraph [--pass 1|2] [--scope block-hosted|full|equations|unmarked]` is the argv `kb_pipeline`'s
stage table composes for that subprocess (`ClaimgraphInvocation.flags`), not a command line a
build's operator types. It takes no root override: the repository is walked up to from the working
directory, the way every other tool here resolves one.

**Five invocations, and they are separate because inference is the part that needs repeating.**
`--pass 1 --scope block-hosted` — the default — authors the *declared* graph, what the author marked
explicitly, and is mechanical end to end; it mints no equation, and writes the node-pass record
fresh and the classification and unmarked records empty, so none is ever read from an earlier
build. `--pass 1 --scope full` is **the node pass** (`claims-discovered`): one letter ask per asked
paragraph of each leaf's readable prose, minting a claim node per paragraph that states a result and
recording a verdict for every paragraph it asks about. `--pass 1 --scope equations` mints the
referenced equations the references that still count name, mechanically.
`--pass 2 --scope unmarked` (`references-found`) asks, of each pair a mechanical shortlist
proposes, whether the source claim's text points at the target with no cross-reference, and
records the answers; it writes nothing under `kb-root/`. `--pass 2` classifies every edge
candidate over the node set those three fixed. Each extends its predecessor's output
additively rather than rebuilding it, so a failed or improved inference costs none of the mechanical
work and can be re-run against a different model without rebuilding the tree. **The node set is
fixed when `equations-minted` ends**: the three minting stages declare `Stage.mints_nodes` and form
one contiguous run, and no later stage changes `kb_index_lib.scan_authored_ids` — asserted in
`test_kb_pipeline.py` and `test_kb_claimgraph_nodepass.py`, not at run time, nothing on a reachable
path producing the violation.

**The node pass is the one home for claimhood in prose.** Its scope is every leaf, whether or not it
hosts blocks — THESIS gap 1 is any claim constructed in prose — and what it reads of each is the
**readable prose**: every line outside the leaf's headings and its claim-bearing, `proof` and
`definition` blocks (`prose.excluded_lines`; a heading names a section and states nothing).
`label.render` shows those blocks unlabelled and lets each break the paragraph it interrupts, which
makes it the one paragraph rule: it decides the unit a verdict covers, a yes-claim's span, stage D's
drop, and a paragraph's identity in the record — the 0-based line it begins on. A paragraph of
readable prose holding a reference that resolves to a document is **obligated**. **The paragraph is
the unit of the ask** (`identify.asked_paragraphs`): every obligated paragraph is asked, whatever
its words, and every other readable paragraph is asked where it holds a sentence that could open a
claim (`identify._opens_a_claim`: at least `MIN_OPENING_WORDS` canonical words, not inside a maths
fence), which leaves markup-only paragraphs and two-word labels unasked. Each is one letter ask
(`ask.py`, `letters.py`) — *states a result* or *does not* — and the leaf is the group whose render
every one of its asks shares. A leaf with no paragraph to ask — one whose only readable text is its
heading — is recorded as having nothing to read and gets no ask.

**A yes mints one claim, and its span is its whole paragraph**, marked on the paragraph's first
line. **Its title is derived, never generated** (`identify._title`): the paragraph's first sentence
that could open a claim (its first sentence where none could), its citation and cross-reference
markup reduced to what the page shows (`inventory.page_text`, the reduction block titles take),
collapsed to one line, cut at the last word boundary within `identify.TITLE_MAX_CHARS` with `…`
where cut, and suffixed with a space and `(¶<k>)` — `k` its 1-based position among the leaf's
readable paragraphs — where the leaf already carries that title. So it is the author's bytes, unique
in its leaf, and the same on every run, which is what `write.land_leaf` resumes by and `graph.read`
joins a register entry back to its site by. **Every title, prose, block or equation, reaches its
register through `assemble.register_title`**, which rebases each relative link target in it
(`kb_links.rebase_inline_links`) from the leaf's directory to the register's; a leaf below its
domain root otherwise lands a link that resolves only from the leaf. Both writes and `graph.read`'s join
to a block key on that form.

**Every asked paragraph ends with exactly one recorded verdict**: claim, not a claim, or
**defaulted** with its cause — `no-letter` where the ask and its one re-ask came back with no
offered letter, `unplaceable` where a yes's paragraph has no slice that appears exactly once under
`ops.excerpt_lines`, the op's own matching. A default costs that paragraph and never the stage: it
is named on the report's `stage-C-defaulted` line, and `prose.standing` reads it as unjudged, so its
references keep the rules for prose no reading reached rather than being dropped, and still count
toward equation minting. Only a call that never completes (`ask.AskError`) stops the stage. Whether
a paragraph *is* a claim is never checked; **the stage's exit check** is that every obligated
paragraph carries a recorded verdict, recomputed over the tree the run just wrote.

**The node-pass record is the pass's build state, and it never enters `kb-root/`** (SPEC.md, The
Driver's Contract). `kb_pipeline.NODE_PASS_RELPATH` — `kb-build-node-pass.json` at the repo root —
is stdlib JSON written deterministically through `kb_survey.manifest.write_text_atomic`; its reader
and writer are `kb_pipeline`'s, because `kb_pipeline` may not import this package. Per leaf it holds
the read state (`unread`, `planned`, `landed`), the outcome (`minted`; `no-claim`, read and minting
nothing, the leaf keeping the frontmatter it carries; `nothing-to-read`), the planned claims by
title and locator, and a verdict for every asked paragraph by its line — `claim`, `not-a-claim`, or
`defaulted` with a cause from `kb_pipeline.DefaultCause` (`no-letter`, `unplaceable`). It holds no
reason: a blockless leaf minting nothing keeps the `no-claim:` the declared pass wrote, and
`land_leaf` writes it no frontmatter change. The declared pass writes it fresh, every declaring leaf
unread; the node pass writes a leaf's whole outcome as `planned` **before** any KB write for it,
lands the leaf in one per-leaf act (`write.land_leaf`), and marks it `landed`. So a resume never
asks about a leaf the record holds: it skips a landed one and completes a planned one from the
record, idempotently — a planned claim whose title the leaf's register already carries under an id
this leaf hosts, or under one no document hosts, takes that id rather than a second. A yes-verdict's
claim is found through the Tier-2 marker on its paragraph, which is KB fact, so the record does not
repeat it. It is **kept at the build's end**: it is the build's only statement of which references
produced no edge and why, which leaves no reading reached under `--no-inference`, and which
paragraphs defaulted; nothing reads it after `depends-attributed`, `refresh` and the verifiers never
walk the repo root, and its own `about` field says it joins to the tree at this build's own commits.
A paragraph is identified by line with no content digest, because nothing on a reachable path edits
a leaf body mid-build: the only in-build change is a marker appended to an existing line, and the
render strips markers before it segments.

**The discovered graph is a lower bound by construction, in both directions.** A result the author
stated in a way discovery's ask does not recognise is invisible, and a dependency the author never
cross-referenced is visible only where the unmarked-reference shortlist proposes its pair and the
ask over that pair answers yes; a pair ranked below the shortlist's `K` is asked about by nobody.
No run can claim completeness for either the nodes or the edges it authors; that is a property of
the input and of the method, not a defect to be closed.

**Discovery's checks are weak by construction, and the asymmetry is deliberate.** What is checkable
is *location*: the bytes a claim points at are the tool's own slice of its document — its whole
paragraph — so verbatimness is obviated rather than checked, and what remains is that the slice
appears exactly once. Paragraphs share no line, so one claim's marker never moves another's slice.
Nothing bounds fabrication of claimhood. The paragraph ask therefore biases toward recording,
because a wrong claim is a register entry anchored at a span a reader can compare against the
document and a missed claim is invisible to every gate, count and roll-up in the build. That
visibility is a person's, not a gate's.

**Each invocation has its own re-entrancy guard, and they ask different questions.** Pass 1's is
over the tree: point 14's cleanliness check refuses any of the artifacts it writes, because a second
run would mint a second set of ids. The node pass's is the record's read state, per leaf, and it
writes per leaf rather than per batch, so a stopped run costs at most one leaf's asks. The equations
stage skips an equation already minted and lands each leaf through the same idempotent
`write.land_leaf`. Pass 2 mints nothing.

**The tree is its sole input** — no `.tex`, no AST, no bibliography — which is what makes SPEC.md's
Document-Tree Contract the replaceable seam it is stated to be. **`graph-init` runs before it**
(Initialising the Claim-Graph Spine, below): the derived-index directory and the runner include line
are that verb's writes, and a run finding either absent exits **3** naming it rather than seeding
half a spine itself.

| Module | Role |
|---|---|
| `tree.py` | The readings every stage shares: the document set with its down-link and up-link relations, the blockquote-prefix strip a scan over an author-distinguished block runs first, and the two readings of what `kb_write` inserts, both read off `kb_write.render` rather than re-typed: `METADATA_OPENERS`, what each artifact opens with, and `strip_markers`, which takes an appended marker back off a line of authored content. Also the `kind:` derivation — three values off path shape alone: `entry-point.md` by name, a document with children an `index`, one without a `leaf`. `LIST_SEPARATOR` is what a page writes between the items of one printed list (*Lemmas 2 and 3*, *Sections 4, 5, and 7*), shared by the two readings that walk such a list — the word before an anchor (`inventory.py`) and a claim named by hand (`hand_named.py`) — so they agree on where a list ends. |
| `conform.py` | **Stage A**, the conformance gate over the Document-Tree Contract. Writes nothing and stops on the first failed assertion naming the point. Ordered by dependency rather than by the contract's numbering: point 7 first, because every relation below it is derived from links and a dead link is a phantom child; point 14 last, because a fresh tree passes everything above it. Point 14's cleanliness check is pass 1's **double-run guard**. Its one unchecked clause is point 14's `.index/` ban, which describes what `kb_docgraph` leaves behind and not what `graph-init` legitimately creates between the two stages. `pass_two_gate` is the later invocations' entry condition: the same structural checks, and in place of the cleanliness check a partition of the leaves by `determination` — hosting claims, carrying a no-claim reason, or declaring neither — for the run's census line and nothing else. No reason is compared by identity and no `Determination` admits or closes a leaf: which leaves the node pass reads is the record's. |
| `inventory.py` | **Stage B**, the claim-site inventory: labelled blockquotes with their name, identifier, title-and-locator span off the display line, and extent (point 12); display-maths fences and the `\label` tokens in them (point 9), the fence scan itself being `math_fence_extents` over any unquoted lines; rewritten cross-references with their resolved target, the author's own label off the anchor's third attribute, and which block they sit inside where they sit inside one (point 7) — the label because an `eqref` resolves to its document with an empty fragment, point 9 leaving an equation's `\label` inside the maths fence rather than as an addressable id, so it is the only thing naming which equation; and the citations the tree renders recognisably (point 10). **An anchor also carries the word the page shows before it** (`Anchor.preceding_word`), as spelled — the last run of non-space characters past whitespace and any opening bracket — and an anchor continuing a printed list (*Sections 4 and 5*) carries the word the list opened with, reading `tree.LIST_SEPARATOR`. It is the author's own word only for a `\ref`: a cleveref command generates its noun at typesetting and the reader renders the number alone, so a `\cref` carries whatever the author wrote ahead of it, never the kind of what it names. **A citation reports which of point 10's three states it ended in, and the discriminator is the span rather than the build.** `Citation.state` is a `CitationState` — `resolved`, `unanswered`, `key-only` — read off the span's own two halves: `data-cites` holds the keys and the span's text holds what became of them, so a span whose text is exactly `(key1; key2)` was offered no bibliography, and where citeproc ran a key marked `**key?**` is one it could not answer while its neighbours in the same group resolved. That makes the state **per key**, which a multi-work `\citep` needs and a build-wide condition cannot give; "the tree renders no reference list" is *not* the test for "no bibliography was offered", since a bibliography answering none of the cited keys emits none either and that is the other state. The reference list's entries are `Work` records rather than citations — the list is the volume's and carries each work once — which is what stops a one-work corpus being reported as two. `build.py`'s `stage-B-citations` line carries one count per state (`inline-resolved` / `inline-unanswered` / `inline-key-only`, every state present so an unreached one reads zero) plus `reference-list` for the works. **The two tables hold display names, which is what point 12's label line carries.** A `\newtheorem` internal handle is arbitrary — aliased (`Cor`, `Lem`, `Pro`), starred (`lem*`) and written in other languages (`Teo`, `oss`) — so the tables key on the display name instead; `claimbox` is classified as the `Result` it declares itself to be, and needs no entry of its own. Where no display name was declared the label carries the internal one (amsthm's `proof`) and the tables carry that word too. Matching folds case, the label carrying the author's own capitalisation. The tables are still closed, and a name outside them is **recorded rather than refused**: the block is admitted as not-claim-bearing — `Block.claim_bearing` reads `CLAIM_BEARING` alone, so an unclassified name is outside it by construction — and the name is counted into `Census.unclassified`, which `build.py` reports on its own `stage-B-unclassified` line. What the closed table guards against is silence, not omission: nothing classifies an unknown name as claim-bearing, so no claim enters the graph on a guess, and a named counted omission is the census line a reader greps where a halted build reports one bit. `NOT_CLAIM_BEARING` is not obviated, and it is branched on at the target end for every member but `proof`: `NOT_A_CLAIM_TARGET` is derived as `NOT_CLAIM_BEARING` less `proof` rather than listed, so a name added to `NOT_CLAIM_BEARING` later reaches the target-end refusal in the same act rather than a second one somebody has to remember. `proof` alone is subtracted, not for costing more or less than the rest, but because it is the one member with a better answer available than a refusal — an anchor naming a proof block can resolve to the claims that proof establishes, which `inventory.Proof` already binds. `NOT_A_CLAIM_TARGET` is read by `attribute._target_end`, which ends a reference there rather than falling through to whatever claim the target document hosts (the `attribute.py` row). The set's role in the census is unaffected by any of this: subtracting all of `NOT_CLAIM_BEARING` is still what separates a name somebody classified as not stating a result from a name nobody has classified, and only the second is reported. This is what keeps the stage usable on a corpus it has not seen: an unclassified name is typically a one-off like `Setup`, `Axiom`, `Fact` or `Hypothesis`, and names of that kind skew away from results, so defaulting one to not-claim-bearing is both safe and usually right. A blockquote with no label line is ordinary quoted prose, not an unclassified block. A Tier-2 marker an earlier pass appended sits on the end of a quoted line, so it neither ends a blockquote nor joins the content read off it, which is what lets pass 2 re-scan a tree pass 1 has written markers into. **A block's title and its locator are one span of its display line, and point 12's optional argument is not required to supply it.** Where the author wrote one the span is `**Theorem 2** (The governance bifurcation).` and the title is the argument; where they wrote none — the norm outside corpora written with tooling that prompts for a title — the span is the environment's printed word and its number, `**Lemma 3**.`, and the title is that with its emphasis markers off. Nothing composes a title from the block's content: a bare *Lemma 3* is a poorer heading in `ask.py`'s enumeration than an author's sentence, and it is the one the page carries. **A span that runs inside another block's display line grows through its own content until it does not**, because `\newtheorem*` renders every block of an unnumbered environment under the same word and a locator matching two blocks binds a claim to the wrong site silently; growth is decided against the document's other display lines rather than against the spans already handed out, so both of two alike blocks grow and neither depends on which comes first. The title grows with the span, a register entry being bound back to its site by title in `graph.read`. **The span is one span read for two purposes, and only the locator is bytes**: `Block.display` is matched against the document and nothing normalises it, while `Block.title` is read by a person — a register heading, an entry in `ask.py`'s enumeration — so `page_text` takes point 10's citation markup and point 7's cross-reference anchors off it and keeps what each renders — the same reduction a prose claim's derived title takes (the `identify.py` row). An author titling a block `[\citet{gibbons2020}]` titled it with a `<span class="citation" data-cites="…">`, which is the reader's markup rather than the author's words; the substitution runs through `CITATION_SPAN_RE`, the same reading of that markup the citation inventory is built on, and the anchor's through `tree.ANCHOR_RENDERING_RE`. **Two shapes stay unreadable, and each costs its own block rather than the build**: a display line not opening with the printed name in bold at all — an environment declared in a class file rather than the volume root, so the reader prints no name and no number and the content begins with the author's sentence — and one running inside another block's to its last word, where no span names one block rather than the other. Such a block carries no title and no locator, `Block.claim_bearing` is false for it on that second condition as well as on the name, it enters the graph as no claim, and it is counted into `Census.unreadable` — reported per document on `build.py`'s own `stage-B-unreadable` line, which is what keeps the absence from being silent. This is the same trade the unclassified name takes one sentence above: a halt is right where two mechanical artifacts disagree or where a loss would reach no check at all, and here neither holds — one authored block is unreadable, and stopping charges every other document of the tree for it. **A sixth reading says which claim each proof establishes** (`Inventory.proofs`), and it is a reading rather than a consumer's derivation because two passes direct a reference by it — stage D a `\ref`, the off-graph endcap a `\cite` — and a binding derived twice could disagree about the corpus with no third artifact to settle it. It binds *blocks* to blocks, so it is usable before the first id is minted, which is what lets the endcap run in the declared pass; it runs after the per-document loop because a proof may name its subject in another document and therefore needs every document's blocks first. The two arms and everything the binding misses are in the `attribute.py` row, which is where the ruling that a proof establishes the claim it belongs to is argued. |
| `label.py` | The sentence-labelled render each of the node pass's paragraph asks shows its leaf in — and the one paragraph rule the node pass and stage D share — and the map from a label back to the document. One sentence per line with the wraps collapsed, the paragraph breaks kept, each line opening with `S<n>` — and **no label for the up-link or the frontmatter block**, which is what retires the navigation exclusion rather than checking it: what the render does not offer, a locator cannot name. A paragraph here is exactly a run of lines a slice can span, because `ops.excerpt_lines` joins each body line's collapsed text with single spaces and a blank line puts two into its haystack. A display-maths fence is not special — the render's blank-line rule draws no exception for it, so a fence sits inside whatever paragraph its surrounding text forms and a span crossing one is findable; the render only leaves its lines unsegmented. `Span.excerpt` is the tool's own slice, and `Span.locator` the label range a paragraph ask names its paragraph by. **An excluded region** — the node pass's headings and its claim-bearing, proof and definition blocks — is shown as it stands with no label, and each excluded line ends the paragraph it interrupts. `Render.paragraphs` and `paragraph_at` are the lookup from a line to its paragraph, named by the line it begins on; this module knows nothing of anchors, verdicts or the record. |
| `identify.py` | **Stage C.** `block_claims` is C-mech, wholly mechanical: title, locator and host are all read off one display line, titled or not (the `inventory.py` row). `check_block_coverage` is the comparison that says every block is named exactly once. **C-inf is the node pass's reading of one leaf, and it asks nothing itself**: `reading_of` builds the leaf's `Reading` — its on-disk text, its marker-stripped body, its fences, blocks, excluded lines and obligated paragraphs, and the render over them; `asked_paragraphs` names the paragraphs the pass asks about (The Claim Graph, above), each an `Asked` carrying its span, its label range and its position; and `judge` turns one answer per asked paragraph — states a result, does not, or no offered letter — into the leaf's `Identification`: a `kb_pipeline.ParagraphVerdict` for every asked paragraph and a `ProseClaim` for every yes that places. A yes is its whole paragraph, titled by `_title` (The Claim Graph, above) against the titles the leaf's blocks and its earlier yeses already carry, and placed by `_placed`: the paragraph's slice must appear exactly once under `ops.excerpt_lines` — the matching `mark-claim-in-leaf` will itself run, over the same bytes, rather than a second implementation of it — and a yes whose slice does not is recorded `defaulted` with cause `unplaceable`. Paragraphs share no line, so placing one claim's marker never moves another's slice, and each is placed alone. **Verbatimness is obviated rather than checked**: the bytes are the tool's own slice. `_opens_a_claim` is the one statement of what a claim may open on — at least `MIN_OPENING_WORDS` words under `ops.canonical_form`, the matcher's own fold, and not inside a maths fence — and it decides both which unobligated paragraphs are asked and which sentence titles a claim. |
| `prose.py` | The node pass's reading of a leaf, in phase 1 and phase 2 alike: the **readable region** (`excluded_lines`: every line but the leaf's headings — `label.heading_lines`, the render's own heading rule — and its claim-bearing, proof and definition blocks), the leaf rendered over its marker-stripped body with that region excluded (`readable`), the **obligated paragraphs** — those holding a reference that resolves to a document (`obligated`) — and `standing(anchor)`, which joins the record's verdicts to the render: *outside* for a reference in an excluded block, where the block and proof rules apply; *claim* and *not-a-claim* where a recorded verdict covers its paragraph; *unjudged* everywhere else — a paragraph whose verdict is `defaulted`, one never asked, and every leaf still unread. `claim_of` is the join to the Tier-2 marker a yes-verdict's claim carries on its paragraph. It imports neither `attribute`, `graph`, `identify` nor `discover`, and asks no model. |
| `graph.py` | The authored claim graph read back off the tree: each document's `claims:` joined to its domain register's entries, and each claim bound to its site — by block title where a block carries it, and otherwise by `marker_locator`, the line that claim's own Tier-2 marker sits on. That second arm is a prose claim's only route back to a span. Nothing is re-derived; the only thing computed is the join. |
| `attribute.py` | **Stage D's narrowing: every edge candidate, classed and drafted; it selects nothing.** `narrow` returns one `Candidate` per ordered pair `(source, target)`, whatever harvested it (`Harvest`: a reference anchor, a hand-written name, or an unmarked-reference yes), carrying the relations it may be `offered`, its `draft`, and its own `passages` — the paragraph of each anchor or mention that produced it (`_reference_line`, over a `(document, line)`). **An unmarked-reference yes is a further candidate** (`narrow`'s `unmarked=`, the pairs `unmarked.found` reads off the record): classed as an undirected provenance of its pair — claim to claim, or equation target where the target is a minted equation node — drafted *mention*, its passage the source claim's own body as `hand_named.bodies` yields it, collapsed to one line, because the yes was about that claim's text. A source no body reaches gets no passage, as `classify.statements` shows it by its title. `Harvest` is read by the report's counts alone; the class, the letters offered and the draft come from the pair. **The source end of a reference in readable prose goes through `prose.standing` first**: prose judged not a claim gives it no source and so no pair and no `references` edge, a paragraph judged a claim gives it that paragraph's claim alone, and prose nobody judged falls to the rules that follow. Each end of an anchor is attributed to a claim where a rule settles it: the **source** end through the claim-bearing block it sits inside, through the claim the *proof* it sits inside establishes, or — the prose fallback, settling nothing about direction — every claim the document hosts, there being no narrower rule to try; the **target** end through the fragment naming a block's own source label (`BY_IDENTIFIER`); through a fragment naming a block `inventory.NOT_A_CLAIM_TARGET` classifies, which ends the reference with no pair at all rather than falling through to a claim the author did not point at; through the label-to-fence join reaching whichever claim holds the labelled equation — a claim-bearing block's, a proof's subject, or the equation's own minted node — or through a document hosting exactly one claim (`BY_SOLE_CLAIM`), there being no other. **Ordering decides the target end's route, not the reference's own type**: the identifier route is tried first, the `NOT_A_CLAIM_TARGET` refusal next, and the equation join is its fallback, so a `\\cref` naming a theorem wins on the identifier route and never reaches either the refusal or the equation join, while a `\\ref` naming a block `NOT_A_CLAIM_TARGET` classifies gets no target at all. **This last route is a refusal, not a narrowing**: `_target_end` returns `((), None)` because every route behind the fragment would answer with a claim the author did not point at, on the same ground two existing rules already stand on — `_equation_claims` returning `()` rather than falling back to the target's sole claim, and a proof whose opening run resolves to no claim binding to nothing rather than to the block above it. The refusal reaches classified names alone — `Hypothesis`, `Setup` and other unclassified names fall through as before — and among classified names it reaches every member of `NOT_CLAIM_BEARING` but `proof`: `NOT_A_CLAIM_TARGET` is derived as `NOT_CLAIM_BEARING` less `proof` rather than listed, so a name added to `NOT_CLAIM_BEARING` later is refused here in the same act rather than a second one somebody has to remember. `proof` alone is subtracted — not for costing more or less than the rest, but because an anchor naming a proof block has a better answer available than a refusal, in the claims that proof establishes (`inventory.Proof` already binds them). Where both ends are settled **and the source end was settled by proof containment**, the pair is drafted *supported by* — a proof establishes what it belongs to, so containment supplies the direction a bare cross-reference does not carry; every other candidate is drafted *mention*, and every candidate is classified either way (`classify.py`). `_fragment_claim` is this package's whole reading of SPEC.md's cross-reference join (Corpus Invariants), asked at the join's definition end: the fragment against the identifier the target block declares, never against how an author spells a label. **An equation node is reachable through the label-to-fence join alone.** It is excluded from `graph.AuthoredGraph.hosted_by`, so neither the source end's prose fallback nor the target end's sole-claim fallback may offer one — counting it as an ordinary hosted claim would resolve a prose reference onto a document that only stopped being sole-claim once an equation was minted into it, and would let a bare cross-reference land on a formula nobody pointed at. **Three narrowings were reconsidered and reversed, and the reasoning they replaced is kept in `attribute.py`'s docstring rather than deleted.** They dropped every `eqref`, every reference whose fragment named a section, and any direction a proof's containment would have supplied, each on the ground that a wrong edge is worse than a missing one. What inverted that is what an edge is on this path — a draft a later inference pass corrects, against a claim recorded as resting on nothing, which is a wrong answer nobody is prompted to revisit — while the line that does not move is being provably wrong inside a mechanical constraint, which the two checks below hold. One argument survives unanswered and is paid: a section reference into a **multi-claim** document offers every claim that document hosts, so the enumeration is k×m in exactly the place discovery multiplies m; that case stays ambiguous and stays the ask's — except where the page names it a section. **The word before an anchor filters what a fallback opened and never what containment settles** (`names_no_premise`). Where the target end fell to a fallback route — sole-claim or every claim a multi-claim document hosts — and the anchor's `preceding_word` names a kind no premise relation can hold, the pairs it would open are no candidate and are counted on `Attribution.word_dropped` instead, less any a further anchor or a hand-written name reaches: the author pointed at a section, a figure or a remark, and the fallback's claims are a stand-in for it. The vocabulary has two halves. `STRUCTURAL_KINDS` is a fixed list — sectioning units, floats, footnotes and their abbreviations — because no display name carries them: no `\newtheorem` declares a section and the reader prints none of their numbers on a label line. The other half is `inventory.NOT_A_CLAIM_TARGET`, the classified display names the fragment refusal above already spends, read here off the word for an anchor whose fragment names no block; claim-bearing names need no entry, since the filter only removes. A fragment or label that named the claim outranks the word — the identifier and equation routes are untouched — and a pair containment settled stays drafted *supported by* whatever word precedes it, which is what keeps every drafted `depends` edge where it was. Measured through `kb-testing/tools/measure-claim-naming.py` over 54 kb-roots (the 50-paper arXiv corpus and three ModernCorp fixtures), the filter removed 497 of 2238 candidate pairs and 37 of 556 questions with the `depends` count unchanged in every root; *section* accounts for most of it, and 25 anchors whose word names no premise reached the equation route and kept their pairs. **A claim named by hand is a further candidate** (`hand_named.harvest`, the `hand_named.py` row), merged with whatever a reference reached on the same pair: one candidate, passages unioned, offered relations intersected. **A pair from a claim to one of its own equations is no candidate, whatever harvested it** (`equation_sites.own_equations`, counted on `Attribution.own_equations`): the claim states that equation, so a prose claim cross-referencing an equation inside its own paragraph is neither a dependency in either direction nor a reference. **A proof binds to its claim two ways**, in order: the anchors of the italic run its content opens with, which is where the reader renders `\begin{proof}[Proof of Theorem \ref{…}]` and which binds across documents; otherwise the block *immediately* above it, where that block states a claim. **That binding is stage B's** (`Inventory.proofs`, the `inventory.py` row) because it is about blocks and lines and is knowable before any id exists; what `_proofs` adds here is the one step that needs minted ids — mapping each subject block to the claim it carries, through the same `_claim_of` join `graph.read` made, so a subject block no register entry carries drops out and the proof binds to nothing. Reaching past a block that states none is what inverts an edge — a result stated in ordinary prose sat between two proofs, and reaching past both bound the second to the lemma above them and closed a cycle with the first — so the binding stops at the block above and every case it misses stays an open pair rather than a directed edge. A further narrowing was considered and refused, and is unchanged: shared containment in a directory contributes no candidate on its own, because filing is a placement decision and not a dependency relation. **The class is a fact about the pair, read once here, and it does not travel past the narrowing**: `_class_of` reads a provenance as *proof-directed* where `_source_end` reported containment settled the source end, as *equation target* where the target is a minted equation node (`target.equation`, never an `eqref` that resolved *through* an equation to a block's or a proof's claim), and as *claim to claim* otherwise. `OFFERED` maps each class to its relations, and only claim to claim is offered *in support of*: an edge originating at a sink is provably wrong, and a proof of `s` citing `t` while `t` rests on `s` is circular unless it is a mention. Two provenances of one pair intersect what they offer, and every subset holds *supported by* and *mention*, so the intersection never empties and the draft is always offered. **A ring among the drafts costs its own directions and nothing else**: every pair containment settled that lies on a cycle of the settled set (`cycle_edges`: an edge is on a cycle exactly when its target reaches its source, a property of the edge set and not of its order, so two runs over one corpus demote the same pairs with no tie-break key to agree on) is drafted *mention* and reported on `Attribution.demoted`. A ring is not evidence that the corpus reasons circularly — proofs citing one another for symmetry, and one argument carried across several statements, both read as direction-bearing to containment — and it is evidence about nothing but its own members. A minimum feedback set was refused: it leaves the ring's other members asserted as dependencies on a discrimination nothing in the corpus supports, and on a 2-cycle it is a coin flip reported as a finding. **`written` is the one map from a candidate and a relation to its record**: *supported by* is a `depends` edge source → target, *in support of* a `depends` edge target → source, *mention* a `references` record source → target; a dependency carries no `references` record beside it. `Attribution.edges` and `.references` are what the drafts write, and a build with no reader writes exactly them. |
| `letters.py` | The letter asks' decisions, whichever kind is asked. **The stage owns every decision; the reader owns only the call.** `LetterReader` is the seam — `LetterQuestion(kind, group, item, prompt, offered)` in, `Reply(text, confidence, stats)` out, `ask.AskError` where the call never completed — so every check runs against a fixed reader. `decide`: the argmax over the *offered* letters where the reply carries a per-label `confidence`, the first offered winning a tie; otherwise the strict parse — after stripping whitespace, exactly one character, and an offered one. `ask_group` runs one group: its first item alone, so the server prefills and caches the shared prefix once, then the rest with `KB_READER_CONCURRENCY` asks in flight (`reader_concurrency`, read at the point of use, 4 when unset, refused by name when not a whole number of at least 1). An item whose reply carries no offered letter is re-asked once, through its `LetterItem.compose` given what came back, and otherwise ends `defaulted` with no letter, for its stage to give the item its stated default. An `AskError` propagates once the calls in flight return, and the group records nothing. Results are kept in item order whatever order the calls finish in, so concurrency changes nothing a stage writes. The `GroupRecord` it returns — and, given a `record_dir`, the JSON file `group_record_path` names — holds the group's shared prefix once, cut at a line boundary, and per item its offered letters, letter, outcome (`answered` / `re-asked` / `defaulted`) and confidence, with each call's prompt tail, reply, wall time and the reader's `CallStats`. `AskTotals` sums a stage's records for its report in the zero form: outcomes, thinking blocks, output tokens, wall and API seconds, and the cache share over every call but each group's first. |
| `ask.py` | The claim graph's asks and the reader that puts them. **The letter asks** are composed here and run by `letters.py`. `paragraph_asks` asks one leaf's paragraphs (`ParagraphGroup`: the leaf's path and its `label.render` body; `ParagraphItem`: a paragraph's label range and labelled lines), `classify_asks` one source claim's edge candidates (`ClassifyGroup`: the source and its statement; `ClassifyItem`: the target, its statement, its own passages and its offered letters), numbering the group's passages once — sorted, deduplicated, `P1`… — so each question names its own by number, and `unmarked_asks` one source claim's shortlisted pairs (`UnmarkedGroup`: the source's leaf path and `label.render` body, the source and its statement; `UnmarkedItem`: the target and its statement), each offered both letters. Each returns `letters.LetterItem`s whose `compose` turns the previous reply, or `None`, into the prompt. **One letter→meaning table per kind**, `ParagraphLetter`, `ClassifyLetter` and `UnmarkedLetter`: a candidate offered fewer meanings is offered fewer letters, never relabelled ones, and the letters reach `paragraph.tmpl.md`, `classify.tmpl.md` and `unmarked.tmpl.md` only as the composer constants `LETTER_SLOTS`. Every per-item slot (`ITEM_SLOTS`) sits in a template's last section, after every group slot, so a group's asks share every byte before the question; `tests/test_kb_claimgraph_ask.py` holds that and the shared prefix for every kind. A re-ask chooses `letter-correction` for `@!correction!@`, after the question, carrying the reply cut to `RETURNED_MAX_CHARS`; `@!classify-options!@` takes the closing question naming the letters a candidate admits (`CLASSIFY_OPTIONS`, keyed by the offered set). **`ask_without_tools` is the one `LetterReader`**: one `inference.call_chat` on the environment's `MODEL`, the `reader-system` fragment (`prompt-templates/fragments/reader-system.tmpl.md`, a composer-resolved fragment no template names) rendered whole as the system prompt, no agent definition read, and no tool to call — a model able to read neighbouring leaves or the sources would judge on evidence the ask excludes, and on whatever it chose to look at. Its `captures` directory is bound with `functools.partial` by the stage that holds it; with none the capture is spooled and discarded. It returns no `confidence`, and reads its own capture through `inference.read_capture` into `letters.CallStats`: one thinking block per attempt that streamed reasoning, and the measured time, output tokens, cache reads and prompt tokens off the last attempt. **What ends a call is read off that stream, never off the reply's words.** A call short of `[DONE]` is re-issued identically up to `TRANSPORT_ATTEMPTS`, and so is one whose usage reports no token read and none written — an inference server aborting a request answers that way, its error message as the reply text, where a call that ran reports the prompt it read; either, exhausted, raises `AskError`, the one thing that stops a stage. The text is the last attempt's alone, every attempt appending to one capture. An environment `call_chat` refuses is a `ValueError`, and `__main__` checks it with `inference.check_environment` before an inference-spending stage starts, exiting 2 with the refusal, which names the variable. Each ask's captured stream lands under the run's scratch workspace — `__main__.ASKS_SUBDIR`, beside the write passes' values files in the consuming repository, because this package resolves everything against that root and is invocable with no driver run directory in existence. |
| `assemble.py` | **Stage E.** No new fact enters: the register batches, the frontmatter records, the marker records and the endcap's works and edges, with claims named by position in the entry list because ids do not exist until the first write pass mints them. A work needs no such indirection, its id being derived from its key. The declared pass arranges block claims only; a leaf with none takes `BLOCKLESS_REASON`, a plain reason saying it carries no author-marked claim block and nothing more, compared by identity nowhere. `equation_entries` arranges the referenced equations for the `equations-minted` stage. |
| `equation.py` | Which referenced equations are claim nodes: `unheld` takes the references that count — every one, less those in prose the node pass judged not a claim, which is the caller's to decide — and returns each equation one of them names and no claim-bearing block and no proof holds. |
| `endcap.py` | The off-graph endcap's join, in stage E's service: which external works this corpus's claims cite, and which claims rest on them. Reads nothing new — `Citation.line` compared against a run of lines a claim owns, all of it already stage B's — and asks nobody anything. **A claim owns two such runs**: its own block, and the body of the proof establishing it (`Inventory.proofs`, which this module consumes rather than re-deriving). The second is where the warrants are: a claim's own display line, when it names a source at all, is almost entirely the theorem environment's *optional argument* — an author attributing the whole statement rather than a step — while a proof's body is where an author cites the results a step actually leans on. Containment is asked of the proof's lines while the pairing is recorded under the subject's site, because the head arm binds across documents. A claim citing one work in both its statement and its proof rests on it once. The node's identity is the citation key, so a work three volumes cite is one node; it is tied to the bibliography and not to the per-volume `references.md` leaves, which are citers of it. Where the bibliography answered the key, the reference list's own rendered text titles the node; where none did, the key does, and the rationale says which. Neither of the two scores is defaulted, heuristic or inferred (SPEC.md, Claim-Graph Nodes and Edges). |
| `write.py` | **Stage F**, the passes of SPEC.md's write-API contract, in the order the ops' preconditions force. The endcap's two passes sit inside that order: the works are inserted before any edge can name one, and their `rests-on` edges go through the same `add-depends-on` batch stage D's do — one op, two things it lands over a build's three invocations, told apart by the report name. The values file is the one thing composed here, and it is put through `tomllib` against what the composer declared it must parse back as before any op sees it; prose travels in `'''` literal blocks. A `7` stops the run, an `8` is re-issued identically. Mint order is proved against the register through the production parser rather than trusted. `write_edges` is pass 3, `add-depends-on`, one batch — the declared pass's off-graph edges and pass 2's attribution alike, the dependency edges and the `references` edges of one source travelling in the same values entry so a refusal cannot land half of one claim's edges. `land_leaf` is every writer after the declared pass's, and it is **one leaf per call**, the leaf's final state in one act: the insert, taking an id already landed rather than a second one; the `set-frontmatter` carrying the leaf's existing `claims:` forward with the new ids after them, and every attribute it does not own as it stands, written only where the leaf gains a claim; and markers over the final claim set, a prose claim's however few the leaf declares — a block-hosted claim's locator is recoverable from the tree forever and a prose claim's is not — and a block claim's where the leaf's claims other than equations now number two or more. |
| `gate.py` | **Stage G**, the runner's `kb-refresh` then `kb-verify`, by target name. Green or stop, on the return code alone — there is no fix loop and no seat to run one. |
| `build.py` | Pass 1's pipeline, mechanical end to end. |
| `discover.py` | The node pass's pipeline. Scope is the record: per leaf not yet landed — leaves in sorted order — the leaf's paragraph asks where it is unread, as one `letters.ask_group` whose group is the leaf and whose shared context is its render (`ask.paragraph_asks`), each item's letter read through `ask.ParagraphLetter` and handed to `identify.judge`; its whole outcome into the record as `planned`; `land_leaf`, which writes no frontmatter change for a leaf minting nothing; and the leaf marked `landed` — so a planned leaf is completed from the record without an ask, and a stop costs at most one leaf's asks. The reader is `ask.ask_without_tools` bound to the consuming repository by `__main__`, and each leaf's ask record lands under `__main__.ASKS_SUBDIR`. Two report lines carry the asks in the zero form: `stage-C-asks` — `letters.AskTotals` over this run's groups (answered, re-asked, defaulted, thinking blocks, output tokens, seconds per call, the warm-call cache share) — and `stage-C-defaulted`, the defaulted paragraphs by cause and by leaf and line. Its own exit condition is **every leaf landed and every obligated paragraph carrying a recorded verdict**, recomputed over the tree the run just wrote, before the same stage G; `stage-C-identify` carries the prose claims minted. |
| `equations.py` | The `equations-minted` stage's pipeline, mechanical: the counting references read through `prose.standing`, `equation.unheld` over them, each equation not yet minted arranged by `assemble.equation_entries` and landed per leaf through `land_leaf`, and the exit condition that the equation nodes the tree now holds are exactly the counting set, before the same stage G. |
| `hand_named.py` | **Claims named by hand**, the mechanical half of THESIS gap 2: a printed name and number with no `\ref` — *follows directly from Lemma 4.6* — offered as an edge candidate. The names are the corpus's own (`claim_names`: the display names its claim-bearing blocks carry), compiled with their plurals into a `Vocabulary`; the number is `NUMBER`, any dotted depth or a single capital, a lowercase sub-item suffix matched and dropped, and a printed list yields one mention per item (`tree.LIST_SEPARATOR`). A mention is a candidate only where it joins (`printed_claims`): a claim-bearing block whose display line prints that name and number, or a claim with no block whose title is that label and nothing more; where the label joins claims in several volumes the mention's own is preferred. Scanned only within node bodies — a claim block's extent and the paragraph a prose claim's marker sits in (`prose.marks`), never a proof or unjudged prose — with an anchor, a citation span and a mention its next words hand to a citation (*Theorem 3 of* `\cite{…}`) skipped, and a block's own display label blanked, since corpora print two blocks under one number often enough that reading it would join each to its twin. The join reads the number the reader printed, which a paper numbering within sections may not share: the reader's own counter can render the author's *Proposition 1.3* as *Proposition 17*, and that mention joins nothing. `bodies` is that scan's unit — each block or prose claim's text, raw — and also what a classify ask shows as a claim's statement. A candidate it yields is merged, classified and recorded like every other (`attribute.narrow`, `classify.py`). |
| `equation_sites.py` | **Where an equation node is stated.** `fences` maps each equation node to its fence — the first in the node's document carrying its label — and `own_equations` is every `(claim, equation node)` pair whose fence lies inside the claim's own body (`hand_named.bodies`): the claim states that equation rather than pointing at it. The one statement of both relations: `classify.statements` shows an equation node by `fences`, `unmarked.plan` leaves a source's own equations out of its pool, and `attribute.narrow` drops them as candidates. |
| `depends.py` | Pass 2's pipeline: the node-pass record, the entry condition, the inventory, the authored graph, stage D's narrowing over the record's verdicts and the unmarked record's yeses (`unmarked.found`, read and never recomputed, and none where no unmarked record stands), classification, `write_edges`, and the same stage G. It takes a `letters.LetterReader` or `None`, and where the classify groups' ask records land. Its report carries, each in its zero form: candidates by harvest and by letters offered, and the pairs dropped as a claim's own equation (`stage-D-candidates`), drafts by relation and the routes containment directed by (`stage-D-drafts`), `stage-D-word-filtered`, the containment-ring drafts by name (`stage-D-containment-ring`), classifications by relation and by outcome (`stage-D-classified`), every defaulted candidate by name (`stage-D-defaulted`), the asks' `letters.AskTotals` — thinking blocks, output tokens, seconds per call, warm-call cache share (`stage-D-asks`) — and the write verdict naming every classified edge a cycle demoted (`stage-D-classify`). |
| `classify.py` | **Classification**: every candidate *supported by*, *in support of* or *mention* (THESIS gap 3). One letter ask per candidate (`ask.classify_asks` through `letters.ask_group`), grouped by source in ascending id, offered the letters of its `offered` relations and no others (`LETTER_RELATION`, the one map from a classify letter to a relation). A reply naming no offered letter is re-asked once and then takes the candidate's draft; only a reader's `AskError` stops the stage. **Each group lands in the classification record (`kb_pipeline.CLASSIFICATION_RELPATH`) as it completes**, and a resumed run asks only what the record does not hold — a *drafted* entry, written where no reader was, is not held against a run with one. The declared pass writes the record empty, as it writes the node-pass record fresh, so a record an earlier build left is never this build's resume point. With no reader every candidate takes its draft. `records` maps each classified candidate through `attribute.written` and then demotes every `depends` edge on a cycle of the classified set to a `references` record (`cycle_edges`), with no re-ask, so what remains is acyclic by construction and the post-write gate is the one acyclicity check. `statements` is what an ask shows as a claim's statement: its block's or prose paragraph's text (`hand_named.bodies`), or its equation fence (`equation_sites.fences`). |
| `shortlist.py` | **The unmarked-reference shortlist, mechanical**, and `unmarked.py`'s draft. `rank` orders, per source, every other node of the statements it is handed — less every pair whose unordered form is already an edge candidate (`attribute.narrow`'s `Candidate.pair`) — by cosine of TF-IDF vectors (sublinear tf, smoothed IDF over the target statements), ties to the lower target id; `top_k` takes the first `K`. A statement's terms (`tokens`) are its words through `kb_write.ops.canonical_form` plus the maths symbols of its inline spans (`kb_links.INLINE_MATH_RE`) and display fences (`inventory.math_fence_extents`). Stdlib only, and reads nothing it is not handed. `kb-testing/tools/measure-unmarked-shortlist.py` ranks its wm/statement variant through `rank` and reports the stage's own `unmarked.plan` at `K`, so the curve it measures is this ranking. |
| `unmarked.py` | **The `references-found` stage's pipeline** (THESIS gap 2): the node-pass and unmarked records, the entry condition (`conform.pass_two_gate`), the inventory, the authored graph, `classify.statements`, and `attribute.narrow` for the pairs already candidates; then `plan` — per source claim, every node but a minted equation, its `shortlist.K` best targets over the whole node set, less every existing-candidate pair and every equation node whose fence lies inside the source's own body (`equation_sites.own_equations`; the claim states that equation rather than pointing at it), no locality bound entering the pool — a pure function of the statements and those excluded pairs. The plan lands in the record before the first ask; each source, in ascending id, is one `letters.ask_group` (`ask.unmarked_asks`) over the planned targets the record does not hold, and its letters land as it completes, so a stop costs at most the group in flight and a resume asks only what the record lacks. **The unmarked record**, `kb_pipeline.UNMARKED_RELPATH` (`kb-build-unmarked.json` at the repo root, on the node-pass record's placement and for its reasons), holds the planned shortlist — `null` until a plan stands — and per asked pair the classification record's entry shape through the same pair-keyed codec: letters offered, the letter or null, the outcome. The declared pass writes it empty; under `--no-inference` the stage's row is dropped and it stays so. An answer is a fact about the text, so a pair answered under an earlier plan is kept, and `found` — the pairs answered `UnmarkedLetter.POINTS` — reads the whole record. Only `A` yields; `B` and a default are recorded and yield nothing. It writes nothing under `kb-root/`, so no stage G follows; its exit is the ledger's coverage, every planned pair carrying an outcome. Report lines, each in its zero form: `stage-U-shortlist` (sources, `K`, pairs planned, pairs excluded as existing candidates and as a source's own equation, pairs held and asked), `stage-U-asks` (`letters.AskTotals`), `stage-U-yeses` (by `locality`: same document, same directory, same paper, cross paper) and `stage-U-defaulted`, every defaulted pair by name. |
| `report.py` | The uniform `[claimgraph] STATUS name detail` line, the `Report` every pipeline produces, and the stop that becomes a line. No answer format raises a stop: an unreadable reply to a letter ask is a recorded outcome (`letters.py`). |

**No number is authored anywhere.** Every register entry's rigor is `kb_schema.PENDING_LITERAL`, as
is every external work's `strength` and every `rests-on` edge's applicability — and those two are
pending permanently as far as any build is concerned, nothing deriving them and no stage pointed at
them; `solidity`, the bullet annotations, the roll-ups and the leaf-reference footers are all
`refresh`'s (SPEC.md, Derived Metadata, Defined). Those two pendings now carry a consequence a
build's reader sees: a `rests-on` edge gates, so a claim citing outside work has a pending
`solidity` until both are supplied, and the scoring pass owes one `strength` per work plus one
applicability per pairing before any such claim carries a number again (SPEC.md, Claim-Graph Nodes
and Edges).

**Three properties of this pass need an integration target over a real corpus, and none exists yet —
they are unproven.** Such a target builds a document tree from a multi-volume corpus, stands up a
throwaway installed consumer repository, seeds it with `graph-init` and runs pass 1, the endcap
included, over a corpus carrying at least one citation inside a claim block. What it must establish:
that `kb-refresh` and `kb-verify` exit 0 over the result, that every line gained is a frontmatter
line and every line rewritten is the same line with a Tier-2 marker appended, and that a second
pass-1 run refuses at the conformance gate naming point 14 with `kb-root/` byte-identical. **Neither
inferential invocation belongs in that target**, because a run of either spends inference and the
target must be green without a model reachable. They are exercised instead by
`kb_tools/tests/test_kb_claimgraph_cinf.py` and `kb_tools/tests/test_kb_claimgraph_pass2.py`, each
of which stands up the same shape of consumer and drives every stage against a fixed `letters.LetterReader`.
Neither asserts anything about two runs agreeing: what a fixed seam establishes is that the
mechanism holds answers fixed, never that a model would give the same ones twice.

### kb_survey, Retained

Three stdlib-only modules survive from the toolchain's pre-pandoc LaTeX reader — `manifest.py`,
`skeleton.py`, `validate.py` — unchanged by this cut. Everything that read LaTeX through the
vendored parser (`_pylatexenc.py`, `expand.py`, `compose.py`, `strip.py`, `harvest.py`, `leaf.py`)
is deleted, with the survey ops that fronted them (`survey-sources`, `render-manifest`) and the
golden fixtures that pinned their output.

| Module | Role |
|---|---|
| `manifest.py` | The schema — record types, the closed `FlagCode` enum, the `mf:` id prefix, reader and writer, atomic write, `volume_slug`. Unchanged; nothing currently *writes* one (below). |
| `skeleton.py` | `derive(manifest)`: manifest in, KB tree out, by the same ranking rule `kb_docgraph.outline` now applies independently and without it. `partition_defects` is its audit; `sections_needing_recut` is a judgment seam of its own, parallel to — and, with `p1.judge` gone, currently uncalled beside — `kb_docgraph.judge` above. |
| `validate.py` | `validate_build(paths, kb_root)`: the checks over a built tree, manifest-agnostic in its own function signature. `paths` is the path list the caller independently holds, or `None` where it holds none — `kb_docgraph.build` supplies the documents it just wrote, which is what makes the tree-diff check a real comparison there, and `kb_util validate-build`, handed a tree and nothing that says what should have been built, passes `None` and the check reports itself inapplicable rather than passing. A tree compared against a walk of itself cannot fail, and a `PASS` line for it would claim a coverage the run does not have. |

**Nothing in the current toolchain produces the manifest `skeleton.derive` still expects, and
nothing calls for one.** `kb_docgraph` writes a tree directly and emits no
`kb_survey.manifest.Manifest`-shaped file; nothing adapts its output into one, and no live call site
asks for one — the driver's domain partition is walked off the built tree instead (The Driver,
below).

Both modules are kept because they are stdlib-only, import no parser, and — the acceptance surface a
future in-house replacement for `kb_docgraph` would still have to satisfy, not because either sits
on a live path from source to KB today.

### The Driver (`kb_driver/`)

`kb_driver/` sequences the stages, makes each model call, checks what came back, and records the
ledger, per SPEC.md's driver contract. Every brief it composes is forbidden from naming a stage id
or the record verb — enforced by a lint over the templates. Its step table holds ten stages, in two
halves:

- **The head**, where the build produces what it will then be judged on — `document-graph` (the
  tree, from the run's own `--source` list), `spine-seed` (`graph-init` over that tree),
  `claims-declared`, `claims-discovered`, `equations-minted`, `references-found` and
  `depends-attributed` (the five `kb_claimgraph` invocations, in that order).
- **The tail**, over the product — `phase-3a` (validation gate) and `overview-drafted` (the overview
  document written) — after `start`, which opens the build.

**A retired stage id stays in the ledgers that recorded it, and reads as no stage.** Built KBs carry
a `phase-5` boundary, the document audit that once followed `overview-drafted`.
`kb_pipeline.recorded_stages` keeps only ids `kb_pipeline.STAGES` holds, so such a ledger reads
complete with every current stage recorded, and its checklist and count name the current stages
alone. The id is therefore never reused: a new stage spelled `phase-5` would read as already
recorded in every one of those ledgers.

**Where a stage boundary falls is decided by what must not be repeated, and the step table is where
that is checked.** A stage is as small as the most expensive thing in it (SPEC.md, The Driver's
Contract), so every row with `steps.Step.spends_inference` stands immediately in front of its
stage's ledger row and nothing failable stands between the two — which is why `overview-drafted`'s
draft is the last row before its boundary. The property is asserted over
`steps.STEPS` in `test_kb_driver_steps.py` rather than re-argued at each insertion, and a stage that
grew a second such row fails there. Its consequence for a resume is the discard rule: position comes
from the ledger alone, so an artifact no boundary accounts for is re-earned rather than adopted,
which costs one row's work and never more.

**Every head row is a tool row.** Each invokes a module and reads an exit code, so none briefs a
seat, none writes a brief, and the only barrier the head raises is `spine-seed.runner-choice` — a
repository carrying neither runner file cannot be told where the include line goes, and no other row
can answer that either. A red front end is not a finding any seat addresses: every check either tool
makes compares one mechanical product against another, so a red one is a defect in the tool or in
its input, and the run stops.

**The head's order is forced at every step, and the stage boundaries are part of the mechanism.**
The seed refuses a `kb-root/` with no tree in it; the declared pass refuses a `kb-root/` with no
spine; the node pass reads the leaves the declared pass recorded unread; the equations stage mints
from the references the node pass's verdicts leave counting; the unmarked-reference asks run over
the node set those three fixed; stage D classifies edges over it. `equations-minted` is a stage of
its own rather than a tail on `discover.build` because a tail would stop that row declaring its
inference, and the ledger would no longer name the row a build spending none drops. The seed is a
stage of its own rather than a row of `start` because its preflight refuses a dirty worktree, and
the tree the stage before it has just written is exactly that — the `document-graph` boundary
commit is what clears it.

**No row is conditional, and a launch is the only thing a guard has to recognise.** There is one
kind of build and one kind of continuation (SPEC.md, The Driver's Contract): an invocation that
finds `start` unrecorded is opening a build, and one that finds it recorded is resuming, re-derived
from the ledger every time (`Runner._recorded`) and configured nowhere — `config.RunSection` carries
no mode field, and `[run] build_mode` is refused at load as an unrecognized key, the general rule
every key `config.load` does not read falls under — in `[timeouts]`, `[retry]` and `[log]` as in
`[run]`, and over the file's sections themselves, each recognized set being its own reads
(`config._refuse_unknown_keys`) rather than a vocabulary written down twice. `[barriers]` is the one
section checked otherwise, having a registry of admissible pairs to check against. What keeps
`dg.build` from re-deriving the tree over the documents a spine is stamped into is therefore the
ledger — a recorded stage is not re-walked — plus one guard for the case the ledger cannot speak to:
a `kb-root/` this build did not write. `pre.kb-root` is that guard, the last row of `start` before
the first write, reading `kb_util.kb_root_state`: `absent` and `spine-only` proceed (`.index/` is
derived space with no authored byte to lose), `populated` is exit 14 naming the state and the tree.
It sits in `start` rather than beside `dg.build` because that is what makes it a *launch* guard: a
resume skips the whole stage, so a build interrupted between `dg.build` and its record re-derives
its own half-written tree rather than being refused entry to it.

**`--no-inference` drops rows and bounds nothing.** `steps.Step.spends_inference` is the derived
union of the two routes a row can cost a model call by — a `system` prompt this driver makes a call
under, or `spends_own_inference`, a model called inside a tool it invokes — and `steps.applies`
refuses every such row under the flag. Every other row runs for real, every stage is walked, and
every stage is recorded, so the product is a real KB built without those rows rather than a walk
that stopped. **Derived from the rows, never from a stage id**: a stage that gains or loses an
inference-spending row moves the answer without an edit, and a constant naming `claims-declared`
would read identically today and be silently wrong on the first insertion after it.

**The second route is a seam this driver does not own, and it is why the flag reaches past the rows
it drops.** `claims-discovered`, `references-found` and `depends-attributed` all spend inference
inside `kb_claimgraph`'s own `letters.LetterReader` seam (`ask.ask_without_tools`), not through the
driver's transport — so the flag has two mechanisms rather than one. `discover.build` and
`unmarked.build` are inference whole and declare `spends_own_inference`, so those rows are dropped,
the unmarked record staying as the declared pass wrote it, empty. `depends.attribute` is not: stage
D's narrowing drafts every edge candidate whether or not a model is reachable, and only classifying
them needs one, so dropping the row would discard the drafts along with the asks. It declares nothing
and `run._claim_graph` passes the **tool's** own `--no-inference` through instead, and every
candidate takes its draft. All three stages therefore honour the flag; two of them do it by not
running.

**What the build says about it is a boundary commit's body.** `run._stage_note` supplies
`advance-step`'s `--note` for a stage that lost rows and the empty string for every other, naming
the rows off `steps.inference_rows` rather than counting them. It is the only possible statement:
the KB itself cannot distinguish a document a step never read from one it read and found nothing in,
so a reader counting documents learns nothing — which is why the node pass's record also lists every
leaf no reading reached as `unread`, and a build spending no inference yields today's graph: every
paragraph unjudged, every reference counting. The mode flag is rendered back into
`config.invocation`, against the one bound that is not — a resume line dropping `--no-inference`
would spend the calls the build was told to do without.

**The record states the build and excuses nothing by itself.** `run._record_stage` passes
`--no-inference` through `ledger.record_stage` to `kb_util advance-step` on **every** stage record,
not only the ones that lost rows, because which coverage units that excuses is `kb_pipeline`'s
classification and not this layer's to anticipate (The Build Pipeline's Coverage Checks, below).

| Module | Role |
|---|---|
| `steps.py` | The ordered step table — the only place that says what happens next. Rows carry the call unit, the fragment that is a calling row's system prompt, template, declared artifacts, parses, and barriers. Stage order is imported from `kb_pipeline`, never restated. |
| `run.py` | The sequencer: stage iteration, resume, and exit selection. **It carries no resumption state.** `run.RUNNER_ATTRIBUTES` is the closed set of attributes a `Runner` may hold and states the criterion that admits one — the stage boundary: a resume re-enters at one, so a value a row writes is read stale by a later invocation exactly where its reader runs in a different stage, and an attribute is admissible only where the invocation fixes it, where every reader runs in the writer's own stage (`_seq`), or where the walk re-derives it before any row reads it (`_recorded`, from the ledger). Closure is checked at construction and at every stage transition; which ground a name stands on is stated in the registry, because no check can read it. Anything else is re-derived at the point of use — `seed.graph-init` asks `kb_util.detected_runner` whether this repository carries a runner file, rather than taking `pre.preflight`'s answer two stages back, which a resume skipping `start` left at its constructor default and which is why `spine-seed.runner-choice` could not fire on a resume at all. A `--decide` answer no barrier asked for is reported rather than dropped, by `run._report_unconsumed` through `runlog.notify` — stderr and `run.log`, the values in the message text, `notify` being the stderr counterpart of `relay` so a notice about the invocation stays off the stream a session pastes from. Position comes from the ledger and from nothing else, and no call is counted anywhere: a stage's rows are a fixed sequence, so its entry saying the stage is behind the build says every one of them ran. A file an earlier process left under the scratch layout is therefore never read as evidence that a call already happened — it is work no boundary accounts for, and the row that really runs overwrites it. The one thing a boundary commit says beyond that is what the build did *without* (`run._stage_note`), which its own product cannot state. |
| `call.py` | This driver's **policy** over one call — retry, the one re-ask, contract validation, an environment the transport refuses (exit 14, never retried), and the persistence route. The transport is `inference.call_chat`, injected as `Caller.transport` so a suite stands a scripted reply in its place: one tool-less request per attempt, the row's `system` fragment rendered whole as its system prompt and the composed brief as its prompt, each socket read bounded by `[timeouts] silence_seconds` and nothing bounding the call as a whole (Module Inventory, above). It names no agent and builds no argv. The driver-persists route writes through `kb_survey.manifest.write_text_atomic` — a temp beside the target and a rename, the toolchain's one such writer rather than a second copy of it — because every reader of a declared artifact asks presence and non-emptiness and nothing else, so a file left half-written under its final name reads as work that finished. |
| `prompt_templates.py` + `prompt-templates/*.tmpl.md` | Prompt composition: strict slot fill in both directions, shared fragments injected by the composer, and the template lint (the enforcement mechanism SPEC.md's driver contract names). A slot is `@!slot-name!@` — the marker grammar `gen_defs` renders the agent definitions with, delimiters and name class alike, so one syntax serves both model-facing surfaces and a brace in a body is only a brace. The name is strict kebab (`prompt_templates.SLOT_NAME`), which is what lets a write op's slot be the op token verbatim: `@!insert-claim-entry!@` expands to an invocation ending in the string it is spelled with. **A namespace routes the slot, and the name never does**: `@!dyn.<name>!@` is filled from the caller's per-call data and from nowhere else, `@!<name>!@` from the composer's own sources — the constants pool, a fragment, a caller-selected alternative, the calling row — and from nowhere else. `prompt_templates.DYNAMIC_PREFIX` sits outside the name class rather than widening it, so a namespace is never mistaken for a name; the composer keys every mapping by the spelling, which is why the two cannot shadow one another and why each direction's failure names the mistake — a `dyn.` slot the caller supplied no value for, or a composer slot it supplied one for — instead of leaving an unfilled slot and an unused value to be read together. The templates are edited by agents holding no repository context, and a hole indistinguishable from prose invites the helpful edit that inlines the literal it stands for, which is the divergence the slot exists to prevent. Bodies are the prompt engineer's. **The directory layout is the declaration**: `prompt-templates/` holds exactly what something dispatches and `prompt-templates/fragments/` exactly what something splices into one, so a reader tells the two apart by where a file sits rather than by decoding its name. Every file under `fragments/` is registered in exactly one of two vocabularies — `FRAGMENT_SLOTS`, which the composer resolves because a template named the slot, and `ALTERNATIVE_SLOTS`, which registers per slot the choices a caller may name — and the correspondence is checked in both directions. An alternative resolves the way a fragment does, one level deep with its own slots lifted into the required set and nesting refused; what a caller hands in is the chosen name, or `None` where the slot registers the empty fill, never the chosen body's prose. `template_paths` walks the whole tree, fragments included, because the lint and the model-facing sweeps are questions about prose and a fragment's prose reaches a model as a template's does; nothing is made dispatchable by appearing there, a row naming only its own `template`. The templates are the shelf; a *composed* brief lands under the run directory's own `briefs/`, and the claim-graph asks' composed prompts under that build's workspace. |
| `barriers.py` / `baton.py` | The typed barrier registry (`barriers.REGISTRY` — one entry per `(stage, kind)` pair, each with its admissible answers) and the relay card every terminating invocation prints. An answer-substituting exit code arrives either from a raised barrier or from a stage that failed mechanically, and only the first has a question or an answer; `BatonContext.pair` is what tells them apart at render time, and the second gets a card that asks nothing and offers no `--decide` resume. Which way a given code arrives follows from which registered spec carries it, and is asserted in neither module: today no spec carries `EXIT_GATE_RED`, so every red gate takes the second card, and a registry that gains a red-gate spec gets the question card back with no edit. A registered barrier ends the run only by going unanswered — every admissible answer continues, which is why no spec enumerates stopping answers. The stage-record refusal is on the other side of the same distinction: `kb_pipeline` exit 6 says a stage's own declared output was absent at record time, which no brief and no seat is party to, so it carries `baton.EXIT_COVERAGE` and a card that resumes once that output stands rather than `EXIT_CONTRACT`'s, whose subject is a dispatched call that could not produce its declared shape. Whichever card is rendered, the failing op's own report lines ride its detail (`ledger._failure_detail`) — a card naming only the return code is one an operator can only act on by re-running the stage by hand. |
| `ledger.py` | Subprocess adapter over the sanctioned `kb_util` ops — the ledger verbs and the build front ends — and the `kb-refresh` / `kb-verify` targets, plus the one place a tool exit becomes a driver exit. **Every op it adapts is one a step-table row invokes.** An adapter with no calling row states a second time a contract `kb_util` already holds and stays operator-reachable for, and it states it against a rc vocabulary nothing exercises; a row that needs one composes it then, from the op's own rc ladder. |
| `config.py` / `runlog.py` / `checklist.py` | The run overlay (TOML), the run directory and its logs, and the one parse of `show-status`'s checklist block — `kb_pipeline` writes that block and the driver reads the render back across the subprocess adapter, so the format travels as text and is parsed in one place. |

**CLI surface** — one mode, `run`, from the consuming repo's root. The run is the shell-resident
driver process a person starts in a terminal and it is the only session there is (SPEC.md, Project
Scoping), so the driver has no mode for observing a run from outside it:

```sh
# Run the build from wherever the ledger says it is.
PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_driver run \
    --source <path> [--source <path> ...] \
    [--config <path.toml>] \
    [--decide <stage>.<kind>=<answer>[:<note>]] ... \
    [--run-dir <dir>] [--no-inference] [--through <stage>]
```

**A launch composes nothing.** The one `[run]` field with no default — `sources` — is a flag, so a
build starts from a command line and no authored file; every other field of `config.DriverConfig`
has a default. Four of them — the barrier answers, the run directory, the mode flag `no_inference`,
and the walk bound `through` — carry a flag as well; the rest
are reachable only through `--config`, which stays supported for a run that needs one.
`[run] bibliography` is one of those: the document graph takes bibliographies and the launch line
carries only sources, so where the key names none `run.bibliographies_beside` passes **every**
`.bib` sitting in the directories the sources sit in, sorted — the reader merges them and renders
only cited entries, so several is an ordinary corpus and none is too, and the key exists for a run
that wants the set narrowed to one file rather than for an ambiguity to be resolved. Where both are
given the flag wins for the field it names, which is the precedence `--decide` already has over the
config's `[barriers.*]` tables — one rule for both doors — and a repeated `--source` replaces the
configured list rather than extending it. A flag's value is validated by the key's own config check,
so both doors refuse in the same words at load (exit 13). Every relay card's resume line is rendered
from what the run was actually given (`config.invocation`), so a flags-only run is handed its own
flags back rather than a `--config` it never used.

**The bound is the exception the resume line makes, and deliberately.** `--through` bounds one
invocation rather than specifying the build, so `config.invocation` does not render it: a card that
handed it back would name a run that stops in the same place forever, and resuming past a bound is
what resuming is for. It takes a stage id or the stage's own display name — `phase-3a` and
`validation gate` name one stage — resolved to an id at load by `kb_pipeline.resolve_stage`, so
nothing downstream deals in two spellings and an unknown name is refused (exit 13) carrying the
whole vocabulary in walk order. Reaching it is exit 18 (`baton.EXIT_BOUNDED`), whose card resumes
without the bound. It composes with the mode flag and neither implies the other; the refusal that
once paired `--through` with `--no-inference` is gone with the bound that made some stages
unreachable.

**The server is the environment's, and it is checked before the walk.** No config key names a server
or a model: every call is `inference.call_chat`, which reads both from the environment the run was
launched from. `run.Runner._require_server` runs `inference.check_environment` once per invocation,
after the recorded stages are read and before the first stage is walked, wherever a stage left to
walk holds a row that calls a model (`steps.Step.calls_a_model` — the rows `--no-inference` drops,
plus `depends.attribute`, which declares `spends_inference_in_part` because it keeps running under
the flag). It is not a `start` row, because a resume skips `start`; it is skipped under
`--no-inference` and when no such row is left. A refusal is exit 14 naming the variable — the
refusal is `check_environment`'s own — so a missing variable stops a run before hours of mechanical
stages rather than at the first call after them.

`--decide` is repeatable, takes precedence over the config's `[barriers.*]` tables for its pair, and
is consumed once per process; an answer whose barrier was never raised is reported rather than
silently dropped. `--run-dir` overrides `[log] run_dir` and should point **outside** the consuming
repo, because a restage wipes the scratch directory and the run directory is the evidence. It is
settled at load like every other flag, so `config.log.run_dir` is the effective parent and
`config.invocation` renders it back wherever it is not the default — so the resume line a card
offers names the directory this run's evidence is in, rather than the default parent the next
invocation would otherwise file under.

**A run's report is written on every exit, the ones nobody planned included.** `run.write_report`
puts `cadence.jsonl` and `exit.json` in the run directory on the way out of every ending — a
barrier, a red gate, a boundary check, a terminating signal (`runlog.terminating_signals`), an
exception no handler names — because an ending nobody planned is the one least likely to have said
anything legible on the way out, and the endings whose own card calls that directory the bug report
were the ones leaving none in it. A signal exits `128 + n`, the shell's convention rather than a
rung of the ladder: nothing in the build decided that ending, so the fallback card is the true one
for it and a borrowed code would state a verdict no stage reached.

**The charter is optional.** `pre.charter` resolves once whether one stands at `[run] charter_file`,
and that one answer reaches every consumer: the `start` record names a charter only where there is
one. It reaches the build through `start-build --charter` and through no brief slot at all — the
briefs that quoted it went with the front end that had them. A build with no charter is an ordinary
build whose scope is the sources it was given.

**No call is handed a path to open.** A call is offered no tool, so everything it judges is in its
prompt; a call row's slots carry text, never a location for a model to resolve. `ov.docs`' one slot,
`@!dyn.excerpts!@`, is filled by `kb_readme.compose_excerpts`, which reads exactly the documents
SPEC.md's overview paragraph lists and nothing else: the entry point, each document it lists, and
that document's child linked as `kb_docgraph.outline.OWN_PROSE_TITLE`. A body loses its metadata
block (`kb_index_lib.strip_frontmatter`) and its up-link, and each link is reduced to its text
through `kb_links.LINK_RE`; every other construct stands. A boundary line names each document by
title. `kb_readme.EXCERPT_DOCUMENT_CHARS` and `EXCERPTS_TOTAL_CHARS` cap one body and the whole; a
cut falls on a paragraph boundary and comes back as an `ExcerptCut`, which `run._meta_docs` logs as
a warning by title. `kb_readme` reads the tree itself rather than through `kb_claimgraph.tree`,
whose reader would serve, because `kb_claimgraph` imports `kb_driver` and `kb_driver` imports
`kb_readme`.

**The passage is checked for structure, and re-asked through a fragment.** `call._accept` refuses a
driver-persisted reply holding a heading, a list item, a table row, a code fence, a Markdown link or
a `.md` path — each would corrupt the document the reply is substituted into — and the refusal
carries those lines verbatim. The re-ask composes the same template with the row's
`steps.Step.correction` chosen: `passage-correction` filled with the `overview-correction` fragment,
whose `@!dyn.rejected-lines!@` slot receives the lines. An empty reply has no line to quote, so its
re-ask is the unchanged brief. Sentence count and the absence of counts stay in the prompt alone:
"Part 4" and "three mechanisms" are corpus facts, and no check can tell them from a KB figure.

One path-bearing value is stated, relative, with its base stated where it is read: the document path
in `kb_claimgraph.ask`'s two asks (`@!dyn.document!@`, and the `stated in` clause of a claim line)
is kb-root-relative and names the document whose body is inlined in the same prompt: it is a
citation, not a path to open, and those asks show one document deliberately.

**The driver runs the tree's production and authors none of it.** The tree is `kb_docgraph`'s whole
product, computed from the sources the run was launched with; what the driver contributes is the
invocation, the exit-code reading and the boundary commit. No seat is dispatched, no invariants
list, navigation spec or acceptance criteria is written by anybody, and no row proposes a
decomposition — SPEC.md's "the build derives the tree and grades none of it" describes this shape
exactly, with the judgement seam living inside `kb_docgraph.judge` rather than in a row here (The
Derived Skeleton, above).

**Nothing in the tail repairs a gate.** `phase-3a` runs `kb-refresh` then `kb-verify` and either
records or stops (`run._p3a_gate`): each of the three verifiers compares one mechanically-produced
artifact against another, so a red one is a defect in a tool or in what was authored, and a model
sent to rewrite the KB over it would be repairing mechanical output a mechanism checks. The
verifier's whole report reaches the run log at INFO; the card names the target that failed and
carries the lines of its report that name the failure. Nor does any stage review the document a
model wrote: `overview-drafted` records once the passage is assembled, and no call asks a model
whether work is good enough (CONVENTIONS.md, "a `kb_claimgraph` stage never exits on a model's
opinion").

**The driver runs the claim graph's production and grades none of it.** Minting a
`clm-`/`exp-`/`sup-` id, writing a `depends` edge and placing a Tier-2 marker are `kb_claimgraph`'s,
across the five stages that invoke it; every value any of them writes is the unscored literal, which
is the state SPEC.md's "the build authors the claim graph and grades none of it" requires and the
state `kb-claim-scorer` later reads. No row renders a leaf's prose: leaf bodies are computed from
their own extents by `kb_docgraph`, and no stage asks a seat to read a source extent or to
transcribe one.

**No row of the table mints, so nothing guards a row that does.** The self-graded-work guard the
driver used to carry (`run._check_minted_grades`, riding a `steps.Step.writes_register` declaration)
guarded rows whose *seat* authored register entries, and the minting rows it was written for
(`phase-2.5`, `phase-2.6`) went with the rest of the front end. What mints now is `kb_claimgraph`,
mechanically and undispatched: it writes the unscored literal by construction, and
`depends-attributed`'s verify coverage is what holds it there. SPEC.md's "the build authors the
claim graph and grades none of it" is satisfied by that, not by a driver-side scan of what a seat
wrote.

An invocation can enter from two states, and `kb_tools/tests/test_kb_driver_head.py` drives both
against a real repository and a real ledger. The launch runs against a consumer holding its LaTeX
sources and no `kb-root/` at all — made the way the launch line specifies one — and `--no-inference`
carries it to a closed-out build, every row that would cost a model call dropped and every stage a
build owes still recorded. **The resume entry — a consumer whose tree is already built and whose
head stages are already recorded — is the same file's second walk of one consumer**: the first
invocation is bounded at `depends-attributed`, and the second, which exercises the tail's one call,
says nothing about resuming, so what says it is continuing a build rather
than opening one is the ledger's own recorded stages, read back out of `show-status`'s render. It
spends its inference into a model injected at `call.Caller`'s transport, which the driver's own
surface offers no flag for and must not: a consumer's installed copy carries no fake model.

### The Derived Index (`<kb-root>/.index/`)

`refresh` materializes a fixed set of JSONL files, one record per line, each sorted by a per-file
key so a new node or edge is a single inserted `git diff` line. The record shapes and field orders
are `kb_index_lib`'s emitters — their own definition, with no prose second view — and the freshness
contract is `verify_kb_metadata`'s dry-run diff. This section is the map.

| File | Builder | Sort key | Holds |
|---|---|---|---|
| `claims.jsonl` | `build_claims_records` | `(node_type, id)` | every graph node, type-tagged by `node_type` over the node-kind vocabulary, `kb_schema.NODE_KINDS` |
| `depends-on.jsonl` | `build_depends_on_records` | `(source, target, context)`, a null context sorting as `""` | every edge of all four classes (SPEC.md, Claim-Graph Nodes and Edges); all eight keys on every record, only the class's own ones non-null |
| `strengthen-by.jsonl` | `build_strengthen_by_records` | `(claim_id, item_idx)` | a claim's open-work bullets, verbatim plus the ids they mention — no edge, traversed by nothing |
| `cites.jsonl` | `build_cites_records` | `(claim_id, leaf_path)` | the leaf→claim hosting edges |
| `supported-by.jsonl` | `build_supported_by_records` | `(claim_id, sup_id)` | the reverse view of the `supports` edges, carrying each one's realized lift — a convenience index, never consulted for solidity |
| `subtree-aggregates.jsonl` | `build_subtree_aggregate_records` | `node_path` | per index / entry-point roll-ups, from the same `compute_subtree_aggregates` the frontmatter refresh and the verify check read |

`depends-on.jsonl` is the whole edge substrate: `supported-by.jsonl` is a reverse view of records
already in it, `cites.jsonl` and `strengthen-by.jsonl` carry no `DependsOnEdge` at all, and
`kb_graph` takes `depends-on.jsonl` as its only edge source. Solidity is not computed from this tree
— refresh and verify both call `compute_solidity_full` against the parsed authored state, upstream
of every file here. Per-edge integrity is checked in `verify_kb_metadata` line by line and
relation-aware — for each the admissible source and target node types, the `target_kind` match, and
which of `strength` / `fraction` must be null and which must carry a value in range. A `rests-on`
edge's row of that check is claim → work, `strength` null, `fraction` in [0, 1] or the pending
literal. A `supports` edge is additionally checked at its two authored ends: `FanOutRecord` pairs
the register's staged fraction against the hosting leaf's declared one, and a disagreement is not
refresh-fixable, both ends being authored. No such pairing exists for any other class.

### The Claim-Graph Sheet (`<kb-root>/claim-graph.svg`)

One derived artifact more, and derived from the table above rather than from the authored layer:
`kb_graph` reads `.index/` and draws it. It is kept fresh the way `.index/` itself is — **`refresh`
mints it, `verify` checks it** — and that is one write site and one check site rather than a hook on
every invocation that moves the graph, because `refresh` is what rewrites the index the sheet is a
view of.

`refresh` renders it as its last phase, after the index is on disk, through `kb_graph.ops.render`.
`verify` composes the sheet the on-disk index would render, through `kb_graph.ops.compose`, and
byte-compares; a mismatch and an absent sheet are one refresh-fixable failure, beside the index
freshness failure it reads like. The check is skipped on two conditions, neither of them about the
graph: an index already reported missing or malformed has no sheet to render against, and an
`--index-dir` pointing away from the KB's own is a run asking about a synthetic index rather than
about this KB's sheet.

**The render's only precondition is that the index loads.** No property of the graph is one — a
cycle, a ghost id, zero edges, one node, zero nodes: each draws and exits 0. The failure that rules
out is dependency-order — *no picture until something else has been done* — and it is why the render
sits inside `refresh` rather than after the `kb-refresh`-then-`kb-verify` gate a claim-graph pass
ends on: a build that halts at that gate is the one a reader most needs a current picture of.

`verify` stays read-only across this: `compose` returns bytes, and the directory it composes against
is the KB root because that is where the sheet is read from and what every node hyperlink in it
resolves relative to.

**What the sheet elides, the census counts.** The `FACT edges` line reports the strokes drawn and,
beside them, how many premises a drawn route already carried (`ops._census`) — the count SPEC.md,
The Claim-Graph Sheet puts in place of a picture that cannot show them without drawing the strokes
it just left out. It is the corpus's figure rather than the selected view's, as the
disconnected-component count already is.

The comparison rests on determinism (SPEC.md, Corpus Invariants) — same graph, byte-identical sheet
— which the gate makes load-bearing. Perceptual locality is *not* part of it: a small graph change
may rearrange the sheet freely.

## The Agent Set

The toolchain is the mechanism; the agents are the workflow (the rule that editing must go through
them is SPEC.md, Agent-Mediated Editing). Roles, by lifecycle stage:

**Create** — `kb_docgraph` (The Document Graph (`kb_docgraph/`), above) turns a canonical corpus
into the KB's tree, and `kb_claimgraph` (The Claim Graph (`kb_claimgraph/`), above) authors the
claim-graph spine over it: two mechanical CLIs, not agents, with no seat dispatched at any point in
either. `kb_driver` runs both — as the seven stages of the build's head — and then sequences the
validation and meta-documentation tail over what they produced: ten stages, `start` through
`overview-drafted` (SPEC.md, The Driver's Contract; The Driver, above). The orchestrator is a
program, not a seat: it walks a static step table, makes each calling row's model call itself, and
stops at a barrier rather than asking. `/kb-build` prints the command line that starts it and does
nothing else. **No stage remediates a gate's findings**: `phase-3a` runs the verifiers and either
records or stops, because what each of them faults is mechanically-produced content a mechanism
already checks. **The build dispatches no agent.** Its one model call of its own is the passage
`README.md` is assembled around, at `overview-drafted`: a tool-less request under the
`overview-system` fragment. `tech-writer` and `tech-writer-reviewer` stay in the agent set for the
protocols that use them, and the build names neither.

Nothing in the build reviews KB content. Adversarial review of leaf fidelity and of navigability was
a hedge against agent-authored leaves; the head is mechanical end to end, so its output is checked
by the verifiers rather than read by a seat.

No current seat reads the source corpus directly or reports the notation/concepts/anomalies a walk
over its markup would not — `kb-latex-specialist`, the source specialist this toolchain used to
ship, is deleted along with the survey pipeline it served (kb_survey, Retained, above).

**Use** — `kb-docent` (read-only) guides navigation through the topography graph, manages session
state, and executes topic switches. Loaded via the `/kb-start` and `/kb-next` commands; it is the
sanctioned way to browse the KB.

**Maintain** — `kb-maintainer` is the write side: add/edit leaves, wire leaf frontmatter and
claim-graph ids/edges, migrate finished work into canonical leaves, and run the refresh→verify loop
to green. Parallel-safe by file ownership.

**Score the graph** — `kb-claim-scorer` supplies the inputs the tooling cannot derive: hand-authored
`confidence` / `quality` (local rigor), a `supports` edge's on-point fraction, and the off-graph
endcap's two — an external work's `strength` and a `rests-on` pairing's applicability, which reach
the KB through `set-work-strength` and `set-applicability`. Supplying that pair is what clears a
citing claim's `solidity` from `*pending*`: a positive applicability puts the work's `strength` into
the claim's dependency `min`, a zero one takes the pairing out of it, and either left unscored keeps
the claim — and everything downstream of it — pending. It reads a leaf and takes its dependencies as
given; everything downstream (`solidity`, bands, aggregates) is then mechanical. **This is not a
build stage** and never was one this seat ran inside: a build used to mint and attribute at
`*pending*` and stop there (SPEC.md, The Driver's Contract), leaving scoring to enter separately
through the maintenance path's write ops — `set-rigor` and `set-on-point-fraction` — which is still
how this seat's output lands. What has changed is upstream of it: no *driver* stage mints or
attributes anything for it to score (The Driver, above). `kb_claimgraph` does, mechanically and
undispatched, for the claims an author marked — every one of them at `*pending*`, which is exactly
the state this seat reads.

**Extend the toolchain** — `python-coder` for changes to `kb_tools/` itself (stdlib-only per
SPEC.md's Corpus Invariants, but for the one external `pandoc` dependency).

## Query Surface

`kb_cmd/index.py` loads the JSONL once per process into plain dataclasses and exposes
forward/inverse dependency, open-work, citation, subtree, filter, and lookup queries. It is a normal
package — `from kb_tools import kb_cmd` (or `from kb_tools.kb_cmd import load`) for programmatic
access, or run the CLI as `python -m kb_tools.kb_cmd`:

```sh
PYTHONPATH=<repo> python3 -m kb_tools.kb_cmd <cmd>
# deps <id> [-i] | gated-on <id> | cited-by <id> | solidity-below <n>
# weak-points | subtree <path> | show <id> | stats     (--json for jq)
```

**The load drops nothing.** Every `node_type` discriminator in `kb_schema.NODE_KINDS` has its own
dataclass, but for the `invariant`/`axiom` pair, which share `FrameworkNode` — so a support's
`quality`/`solidity`, an experiment's `status` and an external work's `strength` survive the load,
and none is given the framework pair's bedrock semantics. The builder table is proven total over the
vocabulary at import (`kb_schema.kind_table`), and a discriminator outside it is refused naming the
unknown value and the known set, never typed as framework. A support's `build_band` is **not** on
its record (the emitter writes `quality` and `solidity` only): the query side derives it through
`kb_index_lib.derive_build_band`, the same mapping the build side bands a claim with. A
`DependsOnEdge` carries the record's `relation`, `strength` and `fraction`, so a `supports` edge is
distinguishable from a `depends` edge and a pending fraction arrives as `kb_schema.PENDING_LITERAL`
— compare against that constant, never a typed-out string.

**`stats` is a census.** It carries one node count per kind in `kb_schema.NODE_KINDS`, in that
vocabulary's own order and keyed by `kb_schema.node_kind_plural`, and they partition `claims.jsonl`:
every record is counted in exactly one bucket, and the buckets sum to the file's record count. A
bucket is present whether or not the KB populates it, and a kind added to the vocabulary reaches
this census — and the `[index]` breakdown `kb-verify` prints — by that alone. The census used to
name its buckets by hand: the total counted the external works and no breakdown ever named them.

At KB scales in the low hundreds of nodes, the query surface reloads the full index on every query
rather than maintaining a cache.

## Runner Targets and the Build Ledger

A consuming project's runner gains the KB targets by **include, not copy into the runner file**:
exactly one installed line pulls in a fragment that ships with this toolchain, at its installed
location under `<harness-dir>/agents/` —
`-include <harness-dir>/agents/kb_tools/runner-snippets/kb.mk` in a Makefile, or `import? '<harness-dir>/agents/kb_tools/runner-snippets/kb.just'` in a justfile (`import?`
requires just ≥ 1.33), formatted by `kb_util.install_line` from the installer's own location. The
non-fatal include forms are deliberate: a project whose `<harness-dir>/agents/` has not been
installed (or has been removed) degrades to missing KB targets, never a broken runner. Each fragment
finds the PYTHONPATH it hands its recipes from its own location rather than from the consumer's root
— just's `source_directory()`, make's `$(lastword $(MAKEFILE_LIST))` read before anything else is
included — two levels up being the directory holding `kb_tools`, so neither names a harness. The
line is managed mechanically by the installer, run from the consumer root:

```sh
PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_util install-targets
PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_util uninstall-targets
```

(An existing justfile wins over a Makefile; `--runner just|make` forces the choice, and on install
creates the runner file when it doesn't exist. `--runner` is declared on `graph-init`,
`install-targets` and `uninstall-targets` and on no other op, so naming it elsewhere is a usage
error rather than a silently ignored flag. The op that seeds parts company with the two that only
install here: given a repo carrying neither runner file and no `--runner`, a seed creates the
default runner's file — `kb_util.DEFAULT_RUNNER`, a Makefile today — while `install-targets`
refuses.)

### Initialising the Claim-Graph Spine (`graph-init`)

The whole claim-graph metadata seed is one mechanical command, run from anywhere inside the
consuming repo:

```sh
PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_util graph-init [--runner just|make]
```

**The document tree is the precondition, not the obstacle.** `kb_docgraph` (The Document Graph,
above) writes the tree first and this verb initialises claim-graph metadata over it, so a `kb-root/`
with no tree in it is what has nothing to attach to. `kb_util.document_tree_present` is the test —
`entry-point.md` at the KB root with at least one volume directory beside it, the shape that front
end writes — and it is a precondition check rather than the conformance gate, which reads the whole
of SPEC.md's Document-Tree Contract and belongs to the claim-graph builder. Its absence prints an
advisement naming `kb_docgraph`'s own command line and exits **3** (`kb_util.EXIT_NO_DOCUMENT_TREE`)
having written nothing: the environment is sound, so this is neither a preflight failure nor a
repair anyone performs here, and its own code is what routes a caller to the front end instead.

It is self-guarding: it opens by running the preflight suite (below) — same code, same report lines,
printed as part of its own output — and any `FAIL` stops it with nothing seeded (exit 2). Ordering
the two verbs in prose is therefore unnecessary; an agent that skips `preflight` entirely still
cannot mis-seed.

Seeding creates `kb-root/.index/` and installs the runner include line, then runs refresh and
`kb-verify`'s three verifiers through the modules those targets wrap — the targets do not exist
until the include line is in. The verifiers run through `kb_util.run_kb_verify`, the one in-process
statement of `kb-verify`'s composition, which `phase-3a`'s verify-gates check calls too. Every step
no-ops when its work is already done, so re-running is safe and a fully-initialised spine reports
itself as such; the exit code is 1 if refresh or verify fails. Which runner file the include line
lands in is decided by the probe order stated above.

**The fused `kb-verify` gate excludes one check, named and scoped to this verb alone.** SPEC.md's
Document-Tree Contract point 14 has `kb_docgraph` produce no frontmatter block, so
`verify_kb_metadata`'s frontmatter-presence check would fail by construction on the tree this seed
runs over, before any claim-graph stage has stamped one — an assertion about phase 2's output, asked
before phase 2 runs. `graph_init_kb` calls `run_kb_verify` with `skip_frontmatter_presence`, which
hands `verify_kb_metadata` `--skip-frontmatter-presence`, an explicit, single-named flag bound to
that one check; every other metadata check stays live, because each is keyed on a classified
document (`kind: leaf`) and nothing classifies as one on a tree with no frontmatter at all, so each
passes vacuously rather than needing its own exclusion. Every other caller of `verify_kb_metadata` —
the runner's `kb-verify` target, `phase-3a`'s gate — keeps frontmatter-presence as a real check; the
exclusion narrows what this one fused pass claims, from "this KB is complete" to "this spine is
correctly installed over the tree that is there," and is not a weakening of the check itself.

The seed is not undoable and needs none: it stands alone, its work stays wherever it got to, and
re-running it is a no-op over what already landed. The boundary commit that follows it is what makes
it durable — the seed's own writes are uncommitted until the `spine-seed` record sweeps them up
(Driving the Build Ledger, below).

**The seed writes no format contract, and a KB holds no copy of one.** The write API renders every
metadata byte, so there is nothing a per-build contract copy could say that a seat is free to act
on. A project's own scope is pinned in `<kb-root>/AGENTS.md` instead — the file carrying the rest of
the KB's per-project orientation; who writes it and when is in SPEC.md, Project Scoping. Nothing
gates on a file's mere presence.

Because preflight gates on a clean worktree, a seed's own output must be committed before
`graph-init` is run again in the same repo.

The repo root is always derived from the working directory — no tool here takes a root override; run
from inside the target repo.

### Checking the Environment (`preflight`)

The mechanical form of a build's environment checks, one report line per item in a uniform
`[preflight] STATUS name detail` format:

```sh
PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_util preflight
```

`PASS`/`FAIL` items gate (exit 0 iff none failed), and every `FAIL` names its restoring action: the
resolved git root, both docent commands under `<harness-dir>/commands/`, the scratch directory's
gitignore coverage, and a clean worktree. `FACT` items never gate: the kb-root tri-state (`absent` |
`spine-only` | `populated`, named once as `kb_util.KB_ROOT_STATES`) — reported plainly and acted on
nowhere here, the one place it decides anything being the driver's `pre.kb-root` launch guard (The
Driver, above) — the detected runner file, and whether `<scratch>/kb-build/` exists. `<harness-dir>`
and `<scratch>` are the installed location's (`install_location`): `.claude` and `.claude-temp`
under Claude Code.

Creating the scratch directory when it is missing is the only side effect and is not a check; the
worktree is read before that mkdir, so preflight can never fail on its own writes. It never edits
gitignore rules and never commits — those remedies are named, not performed. **A non-empty scratch
directory is not evidence of a prior build**: a consumer may have filled it with unrelated scratch
and never run one. Only `kb-root/`, `kb-build:`-prefixed commits, and `<scratch>/kb-build/` indicate
build state.

### The Build's Opening Gate

**One route into a build, and it is `start-build`.** A build opens by recording the `start` boundary
(Driving the Build Ledger, below) and by nothing else: no op stands in front of that one, and there
is no second door to keep in step with it. That matters because a route stated twice is a route that
drifts — `kb_driver` walks this one, row for row (`pre.*` → `start.record` → `dg.*` → `seed.*`, The
Driver, above), and a door it never walked would be the one nothing exercised. The spine seed is not
part of opening a build either: it is `spine-seed`'s, through `graph-init`, two stages later and
over the tree `document-graph` has by then written.

**What the build is told about its scope reaches it as a charter path.** `start-build`'s `--charter`
names a charter that already stands on disk, and `kb_pipeline.CHARTER_RELPATH` is where the build
keeps one (tracked, at the repo root, outside both the scratch tree a restage wipes and the
`kb-root/` refresh and the verifiers walk). `kb_pipeline.NODE_PASS_RELPATH`, the node pass's record,
sits beside it for the same reasons and is committed at the boundaries of the two stages that write
it (The Claim Graph, above).

**A charter is not required to open a build, and the absence is recorded rather than merely
permitted.** SPEC.md (The Driver's Contract) makes the charter optional — a build given none runs on
the sources it was given — so `start-build` takes `--charter` optionally and refuses nothing when it
is left off. What it does not do is record silently: the `start` boundary's body names the charter
where one stands and states `kb_pipeline.NO_CHARTER_BODY` where none does. An empty body would be
indistinguishable from a caller that dropped the argument, and the boundary commit is the only
durable place the two can be told apart — so a charter written somewhere the build never looked is
found by reading the ledger instead of being inferred from silence.

### Driving the Build Ledger (`show-status` / `start-build` / `advance-step` / `show-stage-status`)

The build pipeline's state machine — four top-level ops, each carrying only the options it takes;
the first and last read, the two in the middle record. Three of the four are `kb_driver`'s own:
`ledger.py` drives `show-status`, `start-build` and `advance-step` as its subprocess adapter (Module
Inventory, above). `show-stage-status` answers no row in the driver at all — it is a diagnostic read
for whoever is inspecting the ledger from outside a run, since no coordinator process consumes it
(SPEC.md, The Driver's Contract):

```sh
PYTHONPATH=<harness-dir>/agents python3 -m kb_tools.kb_util \
    show-status
    start-build       [--charter <repo-relative-path>]
    advance-step      --stage <stage-id> [--note <text>]
    show-stage-status [--stage <stage-id>]
```

`--charter` is `start-build`'s alone, and is optional: a build carrying no charter records without
one, and the boundary commit's body — whose whole content here is what the build was told about its
charter — then carries `kb_pipeline.NO_CHARTER_BODY` rather than standing empty (The Build's Opening
Gate, above, for why the absence is stated). The coverage unit tells the three conditions apart: a
*read* holds no record argument and reports the unit missing for that reason (below), a record
naming no charter is a vacuous unit rather than a failed one, and a record naming a path is checked
on disk. `--stage` is declared on the two ops that take a stage — required by `advance-step`,
optional on the coverage read below — and on no other, so a record command missing its argument is a
usage error rather than a run that proceeds on a default.

**The stage table lives in `kb_pipeline.STAGES` and only there** — ids and display names. No agent
definition enumerates stages; they are read out of the render.

Every render is one block, in this order:

```
[kb-build] status: <state> (<n> of <stages> stages recorded)
[kb-build] note: ...                     (only when kb-root/ is unseeded)
[x] start             build started
[*] phase-3a          validation gate
[ ] overview-drafted  overview drafted
[stage-status] MISSING <unit> (<source>) — <detail>   (refusals only)
```

The three `[x]`/`[*]`/`[ ]` lines above are the **checklist block**, shown truncated: the real
render carries one line per `kb_pipeline.STAGES` entry. It is contiguous and is the only thing
matching `^\[([x* ])\] (\S+)` — `[x]` recorded, `[*]` in progress (the first unrecorded stage,
once the build has started), `[ ]` undone. Every other line carries a word in its brackets, so a
parser lifts the checklist without knowing the rest.

**What a stage is *for* is its `display`, and that is the whole of what the table says about
purpose.** It reaches a reader in three places and nowhere else: the checklist line above,
`show-stage-status`' `FACT` line, and the boundary commit's own subject — so a build stopped at
`phase-3a` names the stage and says it is the validation gate, from one string, whichever of the
three the reader is looking at.

**There is no action card, and the reader one addressed does not exist.** Each stage used to carry a
tuple of procedural obligations rendered under the checklist — the command to run, the coverage read
to ask, the record to make. Every one of them instructed a reader to run a command the driver runs
itself, and SPEC.md (The Driver's Contract) abolished that reader: there is no coordinator seat, and
no artifact this toolchain produces admits a second controller. What is left is the state: where the
build stands, and — on a refusal — which units are not covered.

**Baton lines** name the next command: `preflight` and `graph-init` on their standalone runs alone —
neither prints one where the call it sits inside has already run that same suite or that same seed.
The ledger ops need none: the checklist says where the build stands, and the driver walks on.

**The ledger is the git commit trail** — there is no pipeline metadata file (SPEC.md, The Driver's
Contract: resumption's state lives in the working tree). A boundary is a commit whose subject is
`kb-build: <stage-id> | <display name>`, with an optional body paragraph (the charter path on
`start`, the `--note` text elsewhere); `show-status` reads them back with `git log --grep`.
Recording sweeps with `git add -A` (gitignore keeps scratch out) and falls back to `--allow-empty`
when no tracked file changed — the boundary is the point, not the diff. Each stage's sweep is also
what leaves the worktree clean for the next stage's tool, which the head depends on: `graph-init`'s
preflight refuses a dirty worktree, and the tree the stage before it wrote is exactly that until the
boundary commit lands.

Recording is **stage-addressed and declarative**. Re-recording a recorded stage is exit 0 with a
banner above the checklist and no commit; an out-of-order stage is refused (exit 4) with the
checklist, correcting a caller's wrong world-model rather than obeying it. `start-build` on an
already-started build refuses with exit 5.

Exit 6 is a failed **postcondition**. Every stage carries one, and they check that the stage's
observable artifacts *exist* — the charter file (`start`), `README.md` (`overview-drafted`).
`CONVENTIONS.md` is not among them: `phase-3a`'s readiness stamp writes it, so a boundary check for
it after that stage is satisfied by work the meta-documentation stage did not do, and a contract no
run can fail distinguishes nothing. `phase-3a` is the exception in depth: its postcondition runs all
three verify gates rather than looking for a file.

**Existence is not quality.** No postcondition reads a file's contents or judges them; that is the
verify gates' job. A refusal names each unsatisfied unit and where it was looked for, under the
checklist that says where the build actually stands — the same `MISSING` lines `show-stage-status`
prints.

#### What the Stage Table Declares

**One question — does this pass run, and what must be true for it to — used to be answered in four
places that could not see each other.** `kb_pipeline` is the only module both sides can share (it
imports stdlib, `kb_util` and `kb_index_lib`, and `kb_driver` imports it throughout), so the stage
table there declares all of it and both consumers read the declaration:

| Declared on `Stage` | Read by |
|---|---|
| the stage id | everything; the vocabulary was already single-sourced |
| `work_is_inference` | `_excused`, for which coverage units a build spending none has nothing left to assert |
| `claimgraph_invocation` | `kb_driver.run._claim_graph` composes the flags from it; `kb_claimgraph.__main__` resolves the same flags back to a stage |
| `mints_nodes` | `test_kb_pipeline.py`, which holds the minting stages to one contiguous run ending at `equations-minted` |
| `precondition_of(stage)` | the stage whose own work must already stand — the stage before it, so the order is stated once |
| the coverage split (`CoverageUnit.asserts_own_work`) | `_excused`, below |

**`steps.stages_without_own_inference` is gone, and its guarantee is not.** That function derived
the old walk bound at runtime, and its docstring ended "Do not 'simplify' it back" — the failure it
names is binding, its mechanism was not. The durable requirement is that *an inference-spending row
inserted anywhere must not silently escape*, and what carries it now is: one runtime source
(`Stage.work_is_inference`, which `_excused` reads and nothing re-derives), plus a test that
performs the derivation itself over `steps.STEPS` and compares to the declaration **in both
directions** (`test_kb_driver_steps.py`). A test that only asked whether the declaration is
self-consistent would pass on a table that had stopped describing the rows, and would look identical
in review.

**The claim-graph invocation table is the one that existed nowhere.**
`--pass 1 --scope block-hosted`, `--pass 1 --scope full`, `--pass 1 --scope equations`,
`--pass 2 --scope unmarked` and `--pass 2` are `claims-declared`, `claims-discovered`,
`equations-minted`, `references-found` and `depends-attributed`;
`ClaimgraphInvocation` is that pairing, composed by `.flags` and resolved by `claimgraph_stage`. The
driver holds no pass number of its own and the tool branches on a stage id rather than on a number,
so a build cannot invoke a pass the tool would run as a different stage. The flags themselves are
unchanged — see ROADMAP.md for what the surface would become.

**`kb_pipeline` imports nothing from `kb_claimgraph`, and that is now structural.** Its coverage
checks read nothing of that package: the document walk is `kb_index_lib`'s (`document_texts` /
`kb_files`, the one walk the verifiers, the claim-graph builder and the coverage checks all share),
and `claims-discovered`'s and `references-found`'s coverage read the node-pass and unmarked records
through this module's own readers.
`test_kb_pipeline.py` asserts the absent import directly.

#### The Build Pipeline's Coverage Checks

**Every coverage unit is one of two kinds, and it says which.** `CoverageUnit.asserts_own_work` has
no default, so a check cannot forget to classify what it is asking. A unit asserting *this stage did
its work* has nothing to assert of a build that dropped the work and reports as vacuous; a unit
asserting *the state handed across this boundary is valid for what comes next* is never excused,
because whatever path reached the boundary the next stage is entitled to its contract.

**The classification is the unit's rather than the stage's, and `_check_verify_gates` is why.** That
one check is `equations-minted`'s, `depends-attributed`'s and `phase-3a`'s postcondition alike, and
`depends-attributed` is a stage whose work a no-inference build drops — so a per-stage answer would
excuse a validity gate at the head's own exit. Declared on the unit, one check carries one answer to
every boundary it guards.

**Excusing takes two conditions and both are the tool's.** `kb_pipeline._excused` turns a unit
vacuous only where `CheckContext.no_inference` holds *and* `Stage.work_is_inference` does. The
second is what keeps a build that spent no model call from excusing the stages whose work was never
a model call: it derived its tree and seeded its spine for real, and those units stand.
`kb_util advance-step --no-inference` is the whole of what a caller supplies — one statement about
the build, naming no unit and waiving no check — so a record cannot reach into the classification.

The consequence the owner confirmed: `kb-refresh`/`kb-verify` runs at every boundary that declares a
validity unit, `equations-minted`'s and `depends-attributed`'s included, over a KB that stage may
have left unchanged. Refresh is idempotent absent claim-value changes and verify is cheap, so asking
twice costs nothing beside a validity gate silently skipped.

`show-status` is read-only, exits 0 in all three world-states, and names which holds (`not started`
/ `in progress` / `complete`). A present-but-incomplete ledger is what says an invocation is
continuing a build rather than opening one — the driver's whole reading of the distinction. It
anchors on the git root alone, because the ledger lives in the commit trail rather than in the KB: a
build being opened renders its all-undone checklist at confirmation time, *before* anything has
created `kb-root/`, and the render carries a note saying the spine is unseeded. **The two writing
ops anchor there too**, for the same reason: a build's opening stages are recorded before anything
has created `kb-root/`, the tree being the `document-graph` stage's own product.

**`show-stage-status` asks what remains inside a stage** instead of reconstructing it. It prints a
`FACT` line naming the stage and how many units it declares, then one `COVERED` or `MISSING` line
per unit carrying the path that unit is satisfied from — the section-to-path pairing no other verb
renders, which is where an operator debugging a stalled build reads the artifact path a check is
missing, rather than reconstructing it from the stage table by hand. The `MISSING` lines are the
same lines an `advance-step` refusal renders for the units it names: one computation, two callers.
It writes nothing, records nothing, renders no checklist (this render is as long as the corpus has
units, where `show-status`' is the fixed-length one), and exits **0** in every stage state —
recorded, in flight, or not yet reached. A stage whose declaring artifact cannot be read is not a
fourth state: it is one unsatisfied unit carrying that fact as its `detail`, rendered by the same
`MISSING` line as any other missing unit. Its only nonzero code is 2, for an unresolvable git root;
refusing is `advance-step`'s job. Without `--stage` it reports the stage in flight, through the
`current_stage()` decision behind the checklist's `[*]` marker; on a complete build it says every
stage is recorded rather than falling back to the last one. One stage's unit is argument-derived —
`start`'s charter — and a read reports it as missing because the argument rides the record, never as
a claim about the tree.

### Consumer-Side Targets

Defined by the included fragment (stdlib-only, run under the system `python3` — no venv):

- `kb-verify` — the green gate: `verify_md_links.py`, `verify_kb_metadata.py`, then
  `verify_citations.py`.
- `kb-refresh` — regenerate derived metadata + `.index/` from authored sources, then the claim-graph
  sheet from that index.
- `kb-stats` — claim-graph dashboard via the query CLI.

A register that loses an entry, or binds a marker to the wrong heading, fails `verify` — the same
binding the write API refuses an edit into.
