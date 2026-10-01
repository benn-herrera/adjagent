# Marker expansion: one expander, sources as pure lookups

## Goal

Today `gen_defs/markers.py:render` takes each data source as its own parameter (chunks, scope, overlays, dynamic, harness), threads them through every recursive call, and holds source-specific rules inside itself (the "no harness file is loaded here" branch, the value/overlay namespace split). `gen_defs/agents_file.py` runs a second substitution pass for user content outside it. Adding a source means editing the renderer.

After this change, one expander owns the marker grammar, the substitution loop and the depth cap. Each source is a pure lookup, routed by namespace through a table the caller builds. Adding a source means writing the source, adding its prefix to `NAMESPACES`, and putting it in the routing table of each render that offers it. The expander function does not change.

Rendering is byte-identical before and after (Acceptance, below).

## Settled design (not reopened here)

1. **One expander.** It scans text, asks the routed source for each marker, splices the answer in, rescans, and repeats until a pass makes no substitution. It stops with the existing `marker expansion exceeded maximum depth (cycle?)` InputError when the depth cap is exceeded. Marker syntax is parsed in `gen_defs/markers.py` and nowhere else.
2. **Sources are pure lookups.** A source takes a name (and, for a chunk, the call's arguments) and returns a value or raises. A source never scans text and never expands. It holds no reference to the expander or to any router: no callback, no global. Missing-key behaviour belongs to the source:
   - a `fam` anchor that no loaded family fills returns `""`;
   - a missing `dyn` key or `hrn` key raises;
   - an unknown chunk raises;
   - an unbound `arg` raises.
3. **Routing table, keyed by namespace:**

   | Key | Source | Prefix in templates |
   |---|---|---|
   | `chk` (default route) | `shared-chunks.toml` | bare marker |
   | `arg` | the chunk call's bound arguments | `arg.` |
   | `dyn` | invocation and computed values | `dyn.` |
   | `fam` | `family/<name>.toml` overlays | `fam.` |
   | `hrn` | `harness/<name>.toml` | `hrn.` |

   Template prefixes do not change.
4. **`arg` is lexical.** Inside a chunk body, `@!arg.x!@` means that chunk call's `x`.
5. **Everything authored expands.** That includes `hrn` values and computed `dyn` values. Operator-supplied text is returned marked *verbatim*: the agents file's two user-content values and the install-dir argument. Verbatim text is final, and the expander never rescans it.
6. **Per-source rules keep their behaviour.** This covers chunk arguments, variants, defaults and `wrap=`; the residual-marker check; anchor collection; tier tokens; and `hrn` being available only to the agents-file render. A rule that belongs to one source moves into that source.

## Decisions made in this plan

- **`chk` is not a prefix.** `@!chk.x!@` is refused by the existing "names no source" error, because `chk` is not in `NAMESPACES`. `chk` is only the routing key for a bare marker. A second spelling of a chunk marker would be a second grammar for nothing (CONVENTIONS.md: "a namespace earns its place by deciding where a value comes from").
- **Three value kinds.** A source returns one of:
  - `str`: authored text. It is spliced in and rescanned in the enclosing span. Used for `arg`, `dyn`, `fam` and `hrn`.
  - `Verbatim(text)`: operator text. It is spliced in as a final segment. It is never rescanned, never residual-checked, and acts as a hard boundary: no scan reads across it.
  - `Span(body, args, finish)`: a chunk call. Only the chunk source returns it.
- **How `arg` scope works.** The expander expands a `Span` as its own nested expansion, with `arg` bound to `Span.args`. All other routes are inherited from the caller. When the nested expansion has nothing left to substitute, the expander applies `finish` (the `wrap=` width, or none) and splices the result in. The top-level span binds `arg` to the arguments the caller passes: the output's fence parameters for a surface template, and `{}` for the agents file. The routing table a caller builds therefore carries `chk`/`dyn`/`fam`/`hrn`. The expander supplies `arg`, and `ArgSource` (a mapping lookup that raises on a miss) lives beside it in `markers.py`.
- **Depth.** The depth cap counts nesting, the same as today's recursion. A span entered at depth *d* runs pass *k* at depth *d+k*. A `Span` found during a pass at depth *p* is entered at *p+1*. The error is raised when a marker is *found* at a depth above `MAX_EXPANSION_DEPTH` (10). One threshold moves: today, text with no markers that is reached at depth 11 also raises. Any input that renders today renders the same way under the new rule.
- **The residual check ignores verbatim text.** `assert_no_residual_markers` takes the expansion result. It reports a `@!`/`!@` only when both characters lie outside every verbatim span.
- **`wrap=` over verbatim text is refused** (InputError). Wrapping would merge verbatim text back into authored text and lose its finality. No real input does this (no template uses `wrap=`, Evidence E6).
- **The placeholder swap in `agents_file.py` is removed.** User content becomes two `Verbatim` `dyn` values. The guarantees it gave are kept, each by a different mechanism:
  - *never expanded*: verbatim segments are never rescanned;
  - *never residual-checked*: the check skips verbatim spans;
  - *never searched*: no placeholder exists any more, and scans stop at verbatim boundaries;
  - *never silently dropped*: the structure check reads the expansion's verbatim spans. It requires exactly one span from `dyn.existing-user-content-before-rendered-minus-h1`, starting above the begin marker line, and exactly one from `dyn.existing-user-content-after-rendered`, starting below the end marker line. This is today's rule, applied to spans instead of placeholder strings.

  To support this, the expander records every verbatim span, including zero-length ones, with its offset and the marker that produced it. An empty user-content value is still counted.
- **`_resolve` path expansion does not bind the user-content parameters.** A `_resolve` entry that names one raises "unknown invocation parameter". Today it would render a placeholder into a path.
- **The agents-file render routes `fam` to an empty family source.** This keeps today's result, where a `fam` anchor there renders `""`. Surface renders do not route `hrn`. Reaching an `hrn` marker in a surface render raises the expander's generic error: "a registered namespace this render does not route", naming the namespace and listing what is routed.
- **Behaviour changes on inputs no real render contains, disclosed here:**
  - Operator-supplied values are returned `Verbatim`, never expanded: the `--model-pin-map` and `--model-tier-map` values, the install-dir argument, the agents-file scope name (all three cases — `Global`, `Project`, and DIR's own name), and the two user-content values. A delimiter in any of them passes through as literal text rather than being expanded or refused by the residual check: text that could not reasonably carry markers is never interpreted.
  - An install DIR whose path contains `@!` or `!@` is now accepted. Today its `_resolve` path is refused by the residual check.

  Byte identity is unaffected: E7 shows no shipped value carries a delimiter.
- **Where things live** (one module per concern, ARCHITECTURE.md Repo Layout):

  | Module | Holds |
  |---|---|
  | `markers.py` | grammar, the expander, value kinds, `ArgSource`, a generic strict `TableSource` (used by `dyn` and `hrn`), anchor scan, residual guard |
  | new `chunks.py` | chunk table, variants/defaults/`wrap=`, the chunk source |
  | `model_tuning.py` | the family source; `OverlayMap`/`OverlaySource` move here from `markers.py` |
  | `rendering.py` | `routing_table(chunks, dynamic, overlays)`, the one builder for a surface render's routes |
  | `agents_file.py` | the `hrn` source. Its routes are `routing_table(chunks, dynamic, {})` plus `hrn` |

## Invariants (what coders must hold)

| # | Invariant | Failure it prevents |
|---|---|---|
| I1 | `markers.expand` names no namespace except through the routing table and the `arg` binding. No `HARNESS_`/`FAMILY_`/`DYNAMIC_NAMESPACE` appears in its body. | Source-specific branches growing back into the expander |
| I2 | `expand` is referenced only in `markers.py`, `rendering.py` and `agents_file.py`. Checked mechanically (new test T8). | A source calling back into the expander, e.g. a chunk source expanding its own body |
| I3 | A chunk body is expanded as its own span with `arg` bound to that call's arguments before it is spliced in. A `fam` value inside it is rescanned in that same span. | Chunk bodies reading the parent's arguments |
| I4 | A `Verbatim` segment is never rescanned, never residual-checked, never crossed by a scan, and never dropped. It is recorded even when empty. | User content being expanded, refused, or silently lost |
| I5 | Depth counts nesting, not total substitutions. | Long but shallow templates hitting the cap |
| I6 | `MARKER`, `ARG` and `IDENTIFIER` stay single-spelled in `markers.py`. `anchors_in`/`collect_anchors` use the same parse and take the namespace to collect as a parameter. `OVERLAY_NAMESPACES` and `VALUE_NAMESPACES` are deleted. | A second marker parser; overlay knowledge staying in the grammar module |
| I7 | `TierBinding`, `all_renders`, `render_template`, `render_output`, and the public functions of `agents_file` keep their signatures. | Churn across around 40 test call sites that do not test expansion |

Not specified, and left to the coder: the internal segment representation; whether sources are classes or closures; the field names of the expansion result (it must give `.text` and the verbatim spans with offset and marker); error wording beyond the regexes the tests match.

## Evidence (re-runnable; Grep over the repo root unless a path is given)

| # | Query | Answer |
|---|---|---|
| E1 | `\brender\(\|import.*\brender\b` in `gen_defs/` | `agents_file.py:140` import, `:329`; `rendering.py:10` import, `:67`, `:68`; `markers.py` itself |
| E2 | `markers\.render` in `tests/` | `test_gen_defs.py` 180, 189, 194, 205, 212, 214, 218, 222, 228, 606, 607, 614, 623, 624, 686, 691, 698, 699, 705, 710, 717, 751, 753; `test_agents_file_render.py` 189, 194, 201 |
| E3 | `load_chunks` in `gen_defs/`, `tests/` | `cli.py:65`, `:295`; `agents_file.py:140`, `:318`; `model_tuning.py:211` (docstring); `test_gen_defs.py` 95, 573, 1836, 1843, 2151, 2504; `test_traversal_sweep.py:103` |
| E4 | `OverlaySource\|OverlayMap` in `gen_defs/` | `markers.py` 91, 94 (definitions); imports at `rendering.py:10`, `generation.py:52`, `installation.py:124`, `model_tuning.py:175` |
| E5 | `OVERLAY_NAMESPACES\|VALUE_NAMESPACES` | `markers.py` 68, 75, 76, 78, 162, 267, 276; `model_tuning.py:69`; `templates/family/README.md:43`; `ARCHITECTURE.md:65`; `test_gen_defs.py:172`; `test_agents_file_render.py:199` |
| E6 | `wrap="` in `templates/` | no matches. `wrap=` is exercised only by unit tests, so T6 is added |
| E7 | `@!\|!@` in `templates/harness/*.toml` | no matches. `DEFAULT_PIN_MAP` values (`model_tuning.py:204`) carry none either |
| E8 | `="[^"]*@!` in `templates/` | `cpp-coder.md.tmpl:60` and `c-coder.md.tmpl:62` (`enable="@!full-warning-set!@"`). An argument value carrying a marker is exercised by the default render |
| E9 | `PLACEHOLDER` in `tests/` | `test_agents_file_install.py` 175–176 |
| E10 | `@!\|!@\|MARKER\b` in `gen_defs/` excluding `markers.py` | docstrings and error f-strings only. No other module parses markers |

## Rows

Run the rows in order. R1–R6 leave the suite red until R7, and R8 is the gate. One coder, one change. **Do not commit before R8.** The agents file renders the short HEAD sha, and `**dirty**` while `templates/` has changes, so a commit or a `templates/` edit before R8 shows up as a false diff.

| Row | Files owned | Work | Done when |
|---|---|---|---|
| R0 | none (runner only) | On the unmodified tree, run `just test`, then `just render before-default`, `just render before-gemma --family=gemma-4`, `just render before-opencode --harness=opencode`. | `just test` reports 3026 passed / 48 skipped, and the three slots exist |
| R1 | `gen_defs/markers.py` | Add `CHUNK_ROUTE = "chk"` (not in `NAMESPACES`), the value kinds `Verbatim` and `Span`, `ArgSource`, `TableSource(table, namespace, noun)`, and `expand(text, routes, *, args) -> Expansion`, per Decisions and I1–I6. Make `assert_no_residual_markers` take an `Expansion` and skip verbatim spans. Parameterize `anchors_in`/`collect_anchors` by namespace. `DynamicMap` values widen to `str \| Verbatim`. Delete `render`, `OVERLAY_NAMESPACES`, `VALUE_NAMESPACES` and the harness branch. Move the chunk table to R2 and the overlay aliases to R3. Rewrite the module docstring for routing, value kinds and lexical `arg`. | Grep `HARNESS_NAMESPACE\|FAMILY_NAMESPACE\|DYNAMIC_NAMESPACE` in `markers.py` matches only constant definitions and `NAMESPACES` |
| R2 | new `gen_defs/chunks.py` | Move `load_chunks`, `chunk_body` and `wrap` here unchanged. Add the chunk source: `(name, args)` returns `Span(body, defaults ∪ args minus variant/wrap, finish=wrap-to-width or None)`. Unknown chunk and variant errors keep today's text. The module docstring takes the chunk-call grammar paragraph from `markers.py`. | `chunks.py` imports no `expand` |
| R3 | `gen_defs/model_tuning.py` | Receive `OverlayMap`/`OverlaySource` from `markers.py`. Add the family source over a resolved `OverlayMap`: an unfilled anchor returns `""`. Update the docstring: line 69's `OVERLAY_NAMESPACES` reference, and lines 10–12 and 231's "threaded through every expansion", which becomes "reaches every span through the routing table". | Grep `OVERLAY_NAMESPACES` in `gen_defs/` returns nothing |
| R4 | `gen_defs/rendering.py` | Add `routing_table(chunks, dynamic, overlays)`. `render_output`'s two passes call `expand(body, routing_table(binding.chunks, binding.probe\|real, resolve(tier)), args=params).text`. `render_template` passes the `Expansion` to the residual check. | Signatures in I7 are unchanged |
| R5 | `gen_defs/agents_file.py` | Build base routes once: `routing_table(chunks, dynamic, {})` plus `hrn` → `TableSource(values, "hrn", "harness key")`. The install dir becomes `Verbatim`. `_resolve` expands under base routes. Each body render adds the two user-content values as `Verbatim`. Delete both `*_PLACEHOLDER` constants and the swap. `_assert_agents_file_structure` checks verbatim spans per Decisions. Update the module docstring's "User content is never rendered…" paragraph (lines 87–92). | Grep `PLACEHOLDER` in `gen_defs/` returns nothing |
| R6 | `gen_defs/cli.py`, `generation.py`, `installation.py` | Repoint imports: `load_chunks` comes from `chunks`, and `OverlaySource` from `model_tuning` (E3, E4). No behaviour change. | Grep `from .markers import .*(load_chunks\|OverlaySource)` in `gen_defs/` returns nothing. The import itself is proven by R7's `just test` |
| R7 | `tests/test_gen_defs.py`, `tests/test_agents_file_render.py`, `tests/test_agents_file_install.py`, `tests/test_traversal_sweep.py`, `tests/test_gen_defs_structure.py` | Rewrite the signature-pinned tests (below) in place, with no change to their count. Repoint the `load_chunks` sites (E3). Add T1–T9. | `just test` reports 3035 passed / 48 skipped. Every baseline test id still exists and passes |
| R8 | none (runner only) | Before any commit and before R9: `git status --porcelain -- templates` is empty. Run `just render after-default`, `just render after-gemma --family=gemma-4`, `just render after-opencode --harness=opencode`, then `just render-diff before-default after-default`, `just render-diff before-gemma after-gemma`, `just render-diff before-opencode after-opencode`. Run `just sweep-python` and read its candidate list. | All three `render-diff` runs print nothing. Sweep candidates have been read and adjudicated |
| R9 | `ARCHITECTURE.md`, `CONVENTIONS.md`, `templates/family/README.md` | **ARCHITECTURE.md:** in Repo Layout, the `markers.py` line becomes "marker grammar, the expander, value kinds, residual guard", and a `chunks.py` line is added. In Template System: line 59, "`render` dispatches" becomes "the expander routes on the prefix through a per-render routing table". Line 65 drops `OVERLAY_NAMESPACES`; an unfilled anchor is the family source's rule. Line 66, "threaded through every expansion" becomes "routed to every span". Line 67: user content and DIR are verbatim values, spliced in and never rescanned or residual-checked, replacing "substituted after the render and the residual check"; `hrn`/`dyn` values are authored and expand. **CONVENTIONS.md:16:** add `chunks.py` to the mechanism docstring list. **`templates/family/README.md`** lines 9 and 43: point at `model_tuning.py` for the family source. SPEC.md needs no change: its Harness Agents File guarantee ("returned verbatim") still holds. | `just test` still reports 3035 passed / 48 skipped. Commit with R1–R8 |

### Tests that pin the old signature: rewritten in place, count unchanged

Each call becomes `markers.expand(text, rendering.routing_table(chunks, dynamic, overlays), args=scope).text`, plus `hrn` where needed. A module-local helper is fine.

- `test_gen_defs.py`, class TestMarkerNamespace:
  - `test_registered_namespaces_are_the_whole_vocabulary`: the `OVERLAY_NAMESPACES` assertion is dropped;
  - `test_unknown_namespace_is_an_error_naming_the_registered_ones`;
  - `test_a_malformed_namespaced_marker_is_not_a_marker_at_all`;
  - `test_a_known_namespace_with_an_unfilled_key_stays_silent`;
  - `test_the_namespace_routes_and_the_name_never_does`;
  - `test_a_bare_marker_never_falls_back_to_an_argument`;
  - `test_an_unbound_argument_names_itself`;
  - `test_an_unknown_invocation_parameter_names_what_there_is`;
  - `test_a_namespaced_marker_takes_no_arguments`.
- `test_gen_defs.py`, class TestTierDiscovery:
  - `test_the_tier_tokens_expand_from_the_pin_map_alone`;
  - `test_a_tier_token_expands_inside_a_chunk_body`;
  - `test_the_tier_tokens_are_not_in_the_chunk_table_at_all`.
- `test_gen_defs.py`, class TestRenderOverlay:
  - `test_unfilled_anchor_expands_to_nothing`;
  - `test_filled_anchor_renders_the_family_text_verbatim`;
  - `test_base_text_never_modified_around_anchor`;
  - `test_overlay_text_is_marker_expanded`;
  - `test_typo_in_overlay_text_fails_loudly`;
  - `test_overlay_is_no_longer_a_reserved_marker_name`;
  - `test_anchor_inside_chunk_body_resolves`.
- `test_agents_file_render.py`:
  - `test_a_harness_marker_inside_a_chunk_resolves`;
  - `test_a_harness_marker_with_no_harness_table_is_an_error`: now matches the generic "does not route" message;
  - `test_a_harness_namespace_is_not_an_overlay`: the `OVERLAY_NAMESPACES` line is dropped.
- `test_agents_file_install.py`:
  - `test_user_text_is_never_rendered_or_searched` (I7): it can no longer reference the deleted placeholder constants. The tricky span keeps `@!dyn.tier-low!@`, a lone `!@`, and adds a complete `@!` … `!@` chunk marker.

### Tests added (9)

| # | Name | Scope |
|---|---|---|
| T1 | `TestExpander.test_a_chunk_body_reads_its_own_call_arguments` | Lexical `arg`: the parent binds `x=outer`, the chunk call binds `x=inner`. Both the chunk body and a `fam` value inside it read `inner` |
| T2 | `TestExpander.test_an_authored_value_is_expanded` | A `dyn` value and an `hrn` value that carry `@!c!@` expand |
| T3 | `TestExpander.test_a_verbatim_value_is_final_and_unchecked` | `Verbatim("@!c!@ !@")` comes out literally, passes the residual check, and is reported with offset and marker. A zero-length one is still reported |
| T4 | `TestExpander.test_a_cycle_hits_the_depth_cap` | A self-including chunk, and a `dyn` value naming itself, each raise "cycle?" |
| T5 | `TestExpander.test_chk_is_not_a_prefix` | `@!chk.x!@` raises "names no source" |
| T6 | `TestExpander.test_wrap_wraps_the_expanded_chunk_body` | `wrap=` is applied after the body's own expansion (E6) |
| T7 | `TestExpander.test_wrap_refuses_verbatim_text` | Refusal per Decisions |
| T8 | `test_gen_defs_structure.py::test_only_the_renders_reference_the_expander` | I2, read from the AST like its neighbours |
| T9 | `test_agents_file_install.py::test_a_template_failing_the_structure_check_is_refused[after-twice]` | New parametrize id: an after-content marker placed twice is refused, with nothing written |

## Acceptance

- R8: the three `render-diff` comparisons print nothing.
- R7/R9: `just test` reports 3035 passed / 48 skipped, and no baseline test id is lost.
- Grep `def render\b` in `gen_defs/markers.py` returns nothing.
- Grep `PLACEHOLDER` in `gen_defs/` returns nothing.
- Adding a source means writing the source, adding a prefix to `NAMESPACES`, and adding a routing-table entry in each render that offers it. `markers.expand` is unchanged.

## Probes: run before approval (execution-only assumptions)

| # | Command | Settles |
|---|---|---|
| P1 | On the unmodified tree: `just render probe-a && just render probe-b && just render-diff probe-a probe-b`, then the same with `--harness=opencode` on both | That two renders of identical code differ in nothing: no slot path, timestamp or ordering leaks. R8's "no output" depends on it |
| P2 | `just test` on the unmodified tree | The 3026 / 48 baseline |
| P3 | `git status --porcelain -- templates` | It is empty now, so R0's agents file renders the clean sha that R8 must reproduce |

## Landed after this plan

- **Harness-aware surface render.** `generate`/`install --harness NAME` (default `claude`) load the harness file into the binding, and `rendering.routing_table` routes `hrn` for the agent and command surfaces; `just render --harness=NAME` forwards the flag to its install.
- **Harness provenance.** The banner's `!TUNING!` line closes with `harness=<name>`, `Tuning` carries the harness (`is_default` requires `claude`), and the run report prints it; a banner without the field still parses.
- **Claude-specific literals to `hrn` markers.** `.claude/`, `.claude-temp` and `CLAUDE.md` in `templates/shared-chunks.toml`, `templates/agents/` and `templates/commands/` are spelled `@!hrn.project-harness-dir!@/`, `@!hrn.project-temp-dir!@` and `@!hrn.agents-file!@`; SPEC.md Deployed Surfaces states paths against the installing harness's project directory.
