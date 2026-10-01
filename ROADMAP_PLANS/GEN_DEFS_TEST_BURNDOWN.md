# gen_defs test suite burndown

Scope: the generator's test modules — `tests/test_gen_defs.py`,
`tests/test_agents_file_render.py`, `tests/test_agents_file_install.py`,
`tests/test_gen_defs_structure.py` and `tests/test_traversal_sweep.py` — plus
three source fixes in `gen_defs/`. Every row below is either a contract
clause gaining a test that can fail, or a test that cannot fail, restates
data, or breaks on a correct change being removed or rewritten.

Baseline at `cb5f316`, collected items:

| Scope | Collected |
|---|---|
| `just test` (all three surfaces) | 3119 |
| `just test gen_defs` | 468 |
| the five modules above | 391 (287 / 37 / 56 / 3 / 8) |

Expected after every row: **3085 / 434 / 357** (`test_gen_defs.py` 258,
`test_agents_file_render.py` 32, `test_agents_file_install.py` 56, the other
two unchanged). Probe PR3 can move all three by +1.

Each row's count delta is in collected items. `test_gen_defs.py` is
`unittest` style, so a "parametrized" case there means `subTest` and counts as
one item. The two agents-file modules use `pytest.mark.parametrize`, where each
case counts separately.

## How a row is done

Every row:

- `just test` is green.
- The collected count moved by exactly the row's stated delta.
- `just format-python` has been run on the touched files.
- A helper, constant or fixture whose last caller the row removed is deleted in
  the same row (CONVENTIONS.md, "Obviated code is deleted, not parked").

A row that adds a test, or rewrites one that could not fail, also passes a
**mutation check**:

1. Apply the named mutation from the catalogue below to a separate git
   worktree. Never apply it to the shared working tree.
2. Run the new test there. It must fail.
3. Remove the worktree.

A test that does not fail on its mutation is not done. Report it with the
mutation's actual result.

A row that rewrites a test which broke on a correct change also passes a
**legitimate-change check**: apply the named L-change in a worktree, and the
rewritten test must pass.

### Mutation catalogue

Each entry replaces one exact string in one file. Where the old string occurs
more than once, the entry says which occurrence.

| ID | File | Old | New | Recorded result before this plan |
|---|---|---|---|---|
| m1 | `gen_defs/product.py` | `return sorted(found, key=lambda pair: pair[0])` | `return found` | no test failed |
| m2 | `gen_defs/model_tuning.py` | `return {tier: tiers[tier] for tier in TIERS}` | `return dict(tiers)` | no test failed |
| m3 | `gen_defs/product.py` | `INSTALL_EXCLUDED_DIRS = frozenset({"tests", "__pycache__", ".pytest_cache"})` | `INSTALL_EXCLUDED_DIRS = frozenset({"tests", ".pytest_cache"})` | only `TestInstallExclusions::test_exclusion_predicate_is_depth_independent` failed; `test_plain_install_carries_no_test_suites_or_caches` passed while `__pycache__` installed |
| m4 | `gen_defs/cli.py` | `ok = install(binding, smap, root=args.root, overlays=overlays, tuning=tuning,` | `ok = install(binding, smap, root=args.root, tuning=tuning,` | no test failed |
| m5 | `gen_defs/cli.py` | `allow_abbrev=False` (every occurrence) | `allow_abbrev=True` | only the `--model` subtest of `TestTuningCLI::test_the_retired_flags_are_unknown_flags` failed, through argparse's *ambiguous option* error |
| m6 | `gen_defs/model_tuning.py` | `return ",".join(f"{tier}={mapping[tier]}" for tier in TIERS)` | `... for tier in sorted(TIERS))` | 4 tests failed (see W10) |
| m7 | `gen_defs/banners.py` | `member = "none" if seat is None else tuning.tier_map[seat]` | `... tuning.pin_map[seat]` | only `TestSelectedGeneration::test_the_banner_records_the_member_the_run_tuned_against` failed; `TestTunedBanner::test_the_member_is_recorded_so_the_tier_never_has_to_be_inverted` passed |
| m8 | `gen_defs/cli.py` | `        validate_family_anchors(\n` | `        (lambda *_: None)(\n` | no test failed |
| P2 | `gen_defs/installation.py` | `HASH_COMMENT_SUFFIXES = frozenset({".py", ".sh", ".toml", ".mk", ".just"})` | the same set plus `".tmpl"` | no test failed |
| P3 | `gen_defs/generation.py` | both `target.write_text(rendered, encoding="utf-8")` lines in the overwrite branches (after `# so a backup of it would be landfill.` and after `backup = back_up(target)`) | prefix each with `target.unlink()` | no test failed |
| P4 | `gen_defs/generation.py` | `{max(used) + 1 if used else 0:02d}` | `{0:02d}` | no test failed |
| P5 | `gen_defs/cli.py` | `sys.exit(0 if ok else 1)` | `sys.exit(0)` | no test failed |
| P6 | `gen_defs/rendering.py` | `raise InputError(f"{rel(path)}: agent template must open with YAML frontmatter")` | `rest = "---\n" + text` | no test failed |
| P9 | `gen_defs/chunks.py` | `bound = {**chunk.get("defaults", {}), **call}` | `bound = {**call, **chunk.get("defaults", {})}` | no test failed; `templates/shared-chunks.toml` has 19 chunks with `defaults` |
| P11 | none: the current `gen_defs/chunks.py` is the defect | — | — | `load_chunks` accepted a chunk carrying both `text` and `variants`; a bare call errored `requires variant=`, and the `text` body was unreachable |
| c1 | `gen_defs/chunks.py` | `bound = {**chunk.get("defaults", {}), **call}` | `bound = {**call}` | not run |
| c2 | `gen_defs/chunks.py` | `    return variants[variant]` | `    return next(iter(variants.values()))` | not run |
| c3 | `gen_defs/chunks.py` | `raise InputError(f"chunk '{name}' requires variant= (one of {sorted(variants)})")` | `return next(iter(variants.values()))` | not run |
| c4 | `gen_defs/chunks.py` | `    if variant not in variants:` | `    if False:` | not run |
| c5 | `gen_defs/chunks.py` | `        if "variant" in args:` | `        if False:` | not run |
| g1 | `gen_defs/generation.py` | `        if body_untouched(actual):` | `        if body_untouched(actual) or "!BODY-SHA256!" not in actual:` | not run |
| r1 | `gen_defs/rendering.py` | `            rest = "---\n" + text` (the `elif surface == COMMAND_SURFACE:` branch) | `            rest = text` | not run |
| r2 | `gen_defs/rendering.py` | `stamp = banner(path, body_hash=` | `stamp = banner(path.with_name("go-coder.md.tmpl"), body_hash=` | not run |
| t1 | `templates/agents/mad/participant-contract.md.tmpl` | the opening `---\n---\n` | `---\nname: participant-contract\n---\n` | not run |
| t2 | `templates/shared-chunks.toml` | the first `@!hrn.project-harness-dir!@` | `.claude` | not run |
| a1 | `gen_defs/agents_file.py` | `**tier_binding(chunks, pin_map=DEFAULT_PIN_MAP).real,` | `**tier_binding(chunks, pin_map={tier: DEFAULT_PIN_MAP["medium"] for tier in DEFAULT_PIN_MAP}).real,` | not run |
| i1 | `gen_defs/installation.py` | `    target.write_bytes(source.read_bytes() if content is None else content.encode("utf-8"))` | the same line, then `    if content is not None and source.suffix == ".py":\n        source.write_bytes(content.encode("utf-8"))` | not run |

### Legitimate-change catalogue

Each entry is a correct change. No test may fail because of it.

| ID | Change | Recorded result before this plan |
|---|---|---|
| L1 | add `templates/agents/zig-coder.md.tmpl`, a copy of `go-coder.md.tmpl` with `go-coder` → `zig-coder` | `TestFloorRung::test_the_census_of_pinned_and_unpinned_templates_is_the_recorded_one` and `TestSelectionCLI::test_agent_glob_alone_excludes_the_commands_surface` failed |
| L2 | in `templates/shared-chunks.toml`, `A project AGENTS.md stays lean` → `Keep a project AGENTS.md lean` | both cases of `test_surface_definitions_name_agents_md_for_project_files_and_the_native_file_for_global` failed |
| L3 | in `templates/family/gemma-4.toml`, `low = "gemma-4-12B-it"` → `low = "gemma-4-12B-it-qat"` | `TestShippedFamilyFiles::test_gemma_members_carry_the_it_spellings` failed, and 53 subtests of `TestStockRung::test_every_banner_records_the_family_the_tier_map_and_a_stock_render` |
| L4 | L1, with the zig-coder pin site declaring `@!dyn.tier-lowest!@` | not run |

## Deletions (15 rows, 22 tests, −22)

Every test listed here is a tautology, a duplicate, a restatement of data, or
a guard on a path no verb reaches. The "covered by" column names what still
protects the clause.

### `tests/test_gen_defs.py`

| Row | Tests | Why | Covered by | Δ |
|---|---|---|---|---|
| D1 | `TestTierStates::test_a_member_missing_only_some_anchors_is_still_not_stock` | `assertNotIn("sonnet", [self.ENTRIES["fam.other"].get("models", {})])` tests a string against a one-dict list, so it is always true. The second assertion repeats a line of `test_a_mapped_member_with_tables_is_not_stock` | `test_a_mapped_member_with_tables_is_not_stock` | −1 |
| D2 | `TestTunedBanner::test_maps_serialize_in_tier_order_never_sorted` | fails together with `TestMapMerge::test_map_spec_serializes_in_tier_order_never_sorted` under m6: same function, same input | `TestMapMerge::test_map_spec_serializes_in_tier_order_never_sorted` | −1 |
| D3 | `TestShippedFamilyFiles::test_gemma_members_carry_the_it_spellings`, `::test_both_shipped_families_declare_a_total_tier_map`, `::test_both_shipped_families_are_stock_at_every_tier` | The first restates `gemma-4.toml` `[tiers]` and fails under L3. The second cannot be reached in a failing state, because `load_tiers` raises unless `set(tiers) == set(TIERS)`. The third breaks on the first member override authored in a shipped family, which is ordinary work | `TestFamilyLoading`; `TestTierStates` | −3 |
| D4 | `TestFloorRung::test_the_census_of_pinned_and_unpinned_templates_is_the_recorded_one` | asserts `(39, 13)` and fails under L1. A lost pin site is already an inequality in `TestDeclaredPinsAgainstRenderedPins` | `TestDeclaredPinsAgainstRenderedPins` | −1 |
| D5 | `TestSelectionMatching::test_split_globs_splits_on_the_separator` | asserts that `str.split("\|")` splits | `test_alternation_selects_the_union` | −1 |
| D6 | `TestGenerateRoundTrip::test_scratch_template_anchor_is_collectable`, `::test_a_family_filling_nothing_leaves_the_base_render`, `::test_hand_edited_target_backs_up_out_of_repo_too` | The first duplicates `TestAnchorCollection::test_collect_anchors_spans_templates_and_chunk_bodies`. The second passes no `overlays`, so it measures a parameter default rather than a family. The third repeats `TestWriteSafetyBackupBranches::test_hand_edited_target_is_backed_up_before_overwrite`; its in-repo/out-of-repo split no longer exists (SPEC.md, Deployed Surfaces: "no render is kept here") | `TestAnchorCollection`; `TestMixedTierRender::test_a_family_with_no_entries_renders_byte_identically_to_anchor_free`; `TestWriteSafetyBackupBranches` | −3 |
| D7 | `TestTierDiscovery::test_a_literal_pin_declares_no_tier`, `TestFrontmatterPin::test_real_set_pins_come_from_params_and_from_literals` | Both treat a literal pin as legal. ARCHITECTURE.md, Model tuning: a literal pin "fails the render: `assert_tiered` refuses it" | `TestLiteralPinGuard`; `TestDeclaredPinsAgainstRenderedPins` | −2 |
| D8 | `TestMixedTierRender::test_no_rendered_output_carries_the_sentinel`, `TestInstallEndToEnd::test_no_installed_file_carries_the_tier_sentinel` | the 3rd and 4th tier-sentinel checks, on the same `render_template` path | `test_pass_b_is_unconditional…` plus the M1 real-set sweep | −2 |
| D9 | `TestInstallEndToEnd::test_default_install_into_a_fresh_root_reports_integrity_ok` | Installs twice, so it duplicates the M5 re-install test. `assertNotIn("MISTUNED")` cannot fail: `MISTUNED` appears in `gen_defs/` only in a comment | M5 | −1 |
| D10 | `TestShippedPackageMapping::test_install_root_guard_covers_a_relocated_package_source` | same call and branch as `TestInstallSourceGuard::test_root_that_is_a_package_source_is_refused` | M6 refuse table | −1 |
| D11 | `TestSelectionCLI::test_the_flat_flag_surface_is_gone_rather_than_aliased` | argparse refuses any unknown flag, and the test still passed under m5 | W4 | −1 |
| D12 | `TestMarkerNamespace::test_registered_namespaces_are_the_whole_vocabulary` | `assertEqual(markers.NAMESPACES, ("arg","dyn","fam","hrn"))` restates the constant. Removing a namespace already fails `test_the_namespace_routes_and_the_name_never_does`; adding one is ordinary work | routing tests | −1 |
| D14 | `TestShippedPackageMapping::test_surface_filter_drops_the_agent_side_packages`, `TestInstallEndToEnd::test_the_removal_is_bounded_to_the_rows_the_surface_map_covers` | guard a branch no verb reaches (SF3). With the filter removed, exactly these two failed and nothing else | — | −2, **lands inside SF3** |
| D15 | `TestInstallPassContract::test_the_same_install_without_the_resolver_installs_the_wrong_bytes` | tests the hazard of an optional parameter that SF2 removes | N8, plus the signature itself after SF2 | −1, **lands inside SF2** |

### `tests/test_agents_file_render.py`

| Row | Tests | Why | Covered by | Δ |
|---|---|---|---|---|
| D13 | `test_render_agents_file_is_not_a_public_verb` | argparse `invalid choice` applies to every unknown verb | — | −1 |

## Merges (14 rows, −23)

### `tests/test_gen_defs.py`

| Row | Tests | Into | Δ |
|---|---|---|---|
| M1 | `TestBodyHashBanner::test_rendered_definitions_carry_a_true_hash` + `::test_no_shipped_render_carries_the_tier_sentinel` (two real-set renders for one sweep) | One real-set sweep that asserts the true hash and the absent sentinel. It also asserts that `banners.banner_claim(text)` names the template that produced each output. That last assertion covers SPEC.md, Generated-Definition Integrity: "Every banner claiming a definition is generated names a template that exists and declares that definition." Mutation check: r2. | −1 |
| M2 | `TestGenerateRoundTrip::test_bannerless_target_refused_out_of_repo_too` | Move it into `TestWriteSafetyBackupBranches` as that table's "no generated banner → refused" row, renamed to say so. It is the suite's only refusal test for generate | 0 |
| M3 | `TestGenerateRoundTrip::test_tuned_generate_fills_one_nb_and_claims_the_triple` + `::test_the_written_file_is_the_render_and_names_the_family_behind_it` | One test: two families, two renders, each banner names its own family | −1 |
| M4 | `TestRefactorBlastRadius` (3 tests over one fixture) | One test: `moved == {alpha, beta}`, the corrected wording is in both, gamma is byte-identical | −2 |
| M5 | `TestInstallEndToEnd::test_clean_install_is_one_summary_line`, `::test_clean_reinstall_stays_one_line_and_names_no_unbannered_file`, `::test_a_fresh_install_replaces_nothing_and_says_nothing`, `::test_a_clean_reinstall_says_nothing_about_pruning`, `::test_plain_install_renders_the_definitions_and_leaves_no_backups` (five tests asserting a one-line report) | Two tests. **Fresh install**: one summary line, no "rendered" clause, `!GENERATED!` present, no `*.bak`, nothing named as replaced. **Clean re-install**: one line, names the replaced package destinations (SPEC.md, Write Safety: "An install names every package destination it replaced"), no prune block, no unbannered file named | −3 |
| M6 | `TestInstallSourceGuard`: accept cases `test_the_clone_in_dot_claude_deployment_layout_passes`, `test_a_root_above_the_repository_is_allowed`, `test_a_root_named_like_a_deployed_surface_is_an_ordinary_consumer`, `test_the_justfile_install_shape_still_passes`; refuse cases `test_root_that_is_the_repository_root_is_refused`, `test_root_that_is_a_package_source_is_refused`, `test_root_inside_a_package_source_is_refused`, `test_a_root_reaching_the_source_through_a_symlink_is_refused` | One accept test and one refuse test, each a `subTest` table. `test_install_into_the_repo_root_refuses_before_writing_anything` stays separate (see PR3) | −6 |
| M7 | `TestShippedPackageMapping::test_both_source_layouts_install_the_same_keys`, `::test_both_source_layouts_install_to_the_same_targets`, `::test_a_relocated_package_still_reads_its_source_from_the_new_place`, `::test_pairs_are_ordered_by_destination_not_by_source_placement` | One test over the top-level source layout only. The nested `agents/kb_tools` layout cannot exist: SPEC.md says `agents/` is "not a directory in this repository". The planted `SHIPPED_PACKAGES` lists its rows in *reverse* destination order, and the test asserts keys, targets, the source each pair reads from, and keys sorted by destination. Mutation check: m1. The class docstring is rewritten to match | −3 |
| M10 | `TestQuietPass::test_the_exception_still_propagates` | Fold its `assertRaises` into `test_a_raising_pass_releases_its_report_too` | −1 |
| M12 | `TestNestedTemplateMirroring::test_template_targets_mirror_subpaths` | Delete it. It asserts `discovery.template_targets` directly, while `test_nested_template_renders_to_mirrored_path` checks the nested output on disk and `test_top_level_template_unaffected` checks the flat one | −1 |
| M13 | `TestRenderOverlay::test_overlay_is_no_longer_a_reserved_marker_name` | Move its `overlay` assertion into `TestTierDiscovery::test_the_tier_tokens_are_not_in_the_chunk_table_at_all` and rename that test for the one clause both assert. ARCHITECTURE.md, Template System: "Nothing is reserved: `[chunks.overlay]` and `[chunks.tier-low]` are ordinary chunks" | −1 |
| M14 | `TestExpander::test_chk_is_not_a_prefix` | Add `@!chk.x!@` to the marker table of `TestMarkerNamespace::test_unknown_namespace_is_an_error_naming_the_registered_ones`. It takes the same "names no source" branch | −1 |

### `tests/test_agents_file_install.py`

| Row | Tests | Into | Δ |
|---|---|---|---|
| M8 | `test_a_malformed_second_output_leaves_the_first_unwritten` + `test_a_redirected_target_is_planned_with_every_other_output` | One test parametrized on whether `AGENTS.md` is a redirect (two cases). SPEC.md, Harness Agents File: "refused, and nothing is written" | 0 |

### `tests/test_agents_file_render.py`

| Row | Tests | Into | Δ |
|---|---|---|---|
| M9 | `test_a_harness_marker_inside_a_chunk_resolves` | Delete it; `TestExpander::test_an_authored_value_is_expanded` already covers the `hrn` route | −1 |
| M11 | `test_the_behavior_change_destinations_name_the_global_native_file_and_the_project_agents_md` (2 cases) | Add `"~/.claude/CLAUDE.md" in text` to `test_claude_renders_agents_md_and_the_claude_md_redirect_into_a_project_dir`. The opencode half is already in `test_opencode_renders_agents_md_into_dir`. Then delete it | −2 |

## Rewrites (17 rows, −1)

### `tests/test_gen_defs.py`

| Row | Test | Rewrite to assert | Check | Δ |
|---|---|---|---|---|
| W1 | `TestFamilyLoading::test_tiers_table_is_returned_in_canonical_order` | Write the `[tiers]` table in reverse canonical order, then assert `list(tiers) == list(TIERS)`. The current input is already canonical, so m2 cannot fail the current test | mutation m2 | 0 |
| W2 | `TestInstallEndToEnd::test_plain_install_carries_no_test_suites_or_caches` | Its `stray` list is computed with `product.excluded_from_install`, the predicate under test. Instead, plant a scratch package source holding `__pycache__/x.pyc`, `.pytest_cache/x`, `.DS_Store`, `x.md.00.bak`, `tests/test_x.py` and `ROADMAP.md` beside one shipped file. Install with `source_root=` that scratch tree, and assert by literal path that none of the six lands and the shipped file does. SPEC.md, Deployed Surfaces: "test suites and their fixtures, caches, `.DS_Store`, generator safety copies, and this repository's own project documentation" do not travel | mutation m3 | 0 |
| W3 | `TestTunedBanner::test_the_member_is_recorded_so_the_tier_never_has_to_be_inverted` | With floor pins and the default tier map, `tier_map[seat] == pin_map[seat]` at `low` and `lowest`, so m7 cannot fail the current test. Rewrite: a scratch tree with two templates at `tier-low` and `tier-lowest`, pin map `all=haiku`, and a tier map that names a different member at each of the two tiers, neither equal to `haiku`. Generate, then assert the two banners carry different `seat=` values and each `member=` equals `tier_map[seat]`. ARCHITECTURE.md, Model tuning: seat and member are recorded "because the default pin map is not injective" | mutation m7 | 0 |
| W4 | `TestTuningCLI::test_the_retired_flags_are_unknown_flags` | Add `TestSelectionCLI::test_flag_abbreviation_is_off`: `generate OUT --fam claude` and `install OUT --fam claude` each exit 2 and write nothing. `install-agents-file` declares no `--` flag, so it has no case. Verify the test under m5, **then** delete the old test | mutation m5 (fails both verb cases) | 0 |
| W5 | `TestInstallEndToEnd::test_verbose_lists_every_file_and_names_the_unbannered_ones` + `TestInstalledBanner::test_comment_less_suffix_takes_no_banner` | The expected unbannered list is computed with `installation.bannerable`, the predicate under test. Instead, assert by name that `agents/kb_tools/installed/AGENTS.md.tmpl` installs byte-identical to `kb_tools/installed/AGENTS.md.tmpl` and is named on the `unbannered` line, and add `.tmpl` to the not-bannerable unit cases. SPEC.md, Deployed Surfaces: "the shipped `.tmpl` templates are that case" (installed unstamped) | mutation P2 (both tests) | 0 |
| W6 | `TestInstallEndToEnd::test_installed_copies_are_bannered_and_sources_are_not` | The before/after hash walks `rglob("*.md")`, which misses every `.py` source. Hash every file's raw bytes. Rewrite the comment claiming package documentation "no longer installs": SPEC.md says a package that grows a `README.md` ships it. SPEC.md, Deployed Surfaces: a shipped package is "never carrying a `!GENERATED!` banner in this repository" and its installed copy is stamped | mutation i1 | 0 |
| W7 | `TestInstalledBanner::test_html_banner_wraps_agents_material_without_frontmatter` | Use a package `README.md` fixture. The comment's reason becomes ARCHITECTURE.md, Banner and Backup Mechanism: frontmatter there "would present a package document as a definition". The current comment cites the Guest-Extraction Contract instead | green | 0 |
| W8 | `TestSelectionCLI::test_agent_glob_alone_excludes_the_commands_surface` | Drop the hard-coded list of seven coders. Assert the result is non-empty, every name matches `agents/*-coder*.md`, and `commands/` is absent. ARCHITECTURE.md, Definition selection: "Either flag implies the surface(s) the run covers" | L1 passes | 0 |
| W9 | `TestFloorRung::test_the_merge_reached_every_tier_a_definition_sits_at` | Replace the literal `{"highest","high","medium","low"}` with the set of tiers that `_DECLARED_PIN_SITE` finds across `templates/` | L4 passes | 0 |
| W10 | `TestStockRung::test_every_banner_records_the_family_the_tier_map_and_a_stock_render` | Derive the expected tier map with `model_tuning.map_spec(model_tuning.load_family(<gemma-4 path>).tiers)` instead of a string literal | L3 passes; m6 still fails it | 0 |
| W11 | `TestInstallPassContract::test_byte_perfect_install_of_a_tiered_output_is_clean` + `::test_the_same_install_without_the_triple_mislabels_every_banner` | Drop `assertNotIn("DRIFT")`, a string no `gen_defs` file contains. Rename the second test for what it asserts: the install banner records seat and member. Strip the "integrity pass", "MISTUNED", "C3" and "next check" wording from the class docstring and comments | green | 0 |
| W12 | `TestTunedBanner::test_the_generated_line_carries_only_the_template_and_the_chunks` | Drop `assertNotIn("with model family")`, which is retired wording. Keep the prefix assertion. ARCHITECTURE.md, Banner and Backup Mechanism, quotes the prefix: `# !GENERATED! from templates/agents/<name>.md.tmpl and templates/shared-chunks.toml` | green | 0 |
| W13 | message pins: `TestTuningCLI::test_the_divergence_notice_is_a_notice_and_gates_nothing`, `::test_the_tuned_notice_names_the_override_bearing_tiers_and_no_others`, `::test_the_run_echoes_its_triple_and_neither_notice_fires`, `TestMapMerge::test_unknown_tier_names_the_five_and_all`, `TestFamilyResolution::test_a_model_name_is_refused_and_the_families_are_listed` | Assert the names each message must carry (tiers, members, flag, families, harness), not the whole sentence. For "and no others", parse the tier list out of the notice line. ARCHITECTURE.md, Model tuning: "A run states its effective family/tier-map/pin-map triple and harness, and reports two non-gating notices" | green | 0 |
| W17 | module docstring and the `_shipped_renders` docstring | Module docstring: the claim "in-place update, inode and mode preserved" becomes true with N3, so verify it then. `_shipped_renders`: drop "check" from "The route generate, check and install all take", because there is no `check` verb (ARCHITECTURE.md, Verification) | green | 0 |

### `tests/test_agents_file_render.py`

| Row | Test | Rewrite to assert | Check | Δ |
|---|---|---|---|---|
| W14 | `test_surface_definitions_name_agents_md_for_project_files_and_the_native_file_for_global` (2 cases) | Replace the three pinned sentences with one test over the full render. Under `--harness opencode`, no body line below the banner block matches `\.claude/\|~/\.claude\|CLAUDE\.md\|\.claude-temp`, with no allowlist. The same pattern must hit at least once under `--harness claude`, as an anti-vacuity control. SPEC.md, Deployed Surfaces: "Every path written inside a definition body … is written against the installing harness's project directory" | L2 passes; mutation t2 fails it | −1 |
| W15 | `test_the_tier_token_renders_the_default_medium_pin` | Use a planted template (`template=`) that spells all five tier tokens, and assert each renders `DEFAULT_PIN_MAP[t]`. ARCHITECTURE.md, Template System, `hrn.` bullet: the agents-file render binds "the five tier tokens, which it pins from the default pin map" | mutation a1 | 0 |

### `tests/test_agents_file_install.py`

| Row | Test | Rewrite to assert | Check | Δ |
|---|---|---|---|---|
| W16 | `test_a_file_without_markers_is_kept_whole_above_the_block`, `test_a_global_install_writes_the_native_file_and_no_redirect`, `test_a_project_install_writes_agents_md_and_creates_the_claude_md_redirect`, `test_an_existing_native_redirect_is_left_alone` (2 cases), `test_a_redirect_installs_into_its_target_and_is_never_written` (3 cases), `test_reinstalling_through_a_redirect_changes_nothing` | Drop every exact-stdout equality and substring check where the test's own filesystem or mtime assertions already prove the behaviour. SPEC.md fixes no report wording | green | 0 |

## New tests (12 rows, +12): one per uncovered contract clause

All twelve go in `tests/test_gen_defs.py`. Each must fail under every mutation
in its Mutation column.

| Row | Clause (file, section: quoted line) | Test | Class | Mutation | Δ |
|---|---|---|---|---|---|
| N1 | ARCHITECTURE.md, Verification: "`1` the run completed and the answer is no (a `REFUSED` target)" | `generate OUT --agent-glob go-coder`, where `OUT/agents/go-coder.md` exists without a banner: exit 1, and the file is byte-unchanged | `TestSelectionCLI` | P5 | +1 |
| N2 | ARCHITECTURE.md, Banner and Backup Mechanism: "`NN` is per-target, zero-padded from `00`, allocated as the highest existing serial plus one, and never reused" | Two hand edits, each followed by a generate, give `.00.bak` then `.01.bak`. With `.00.bak` and `.02.bak` present, the next backup is `.03.bak` | `TestWriteSafetyBackupBranches` | P4 | +1 |
| N3 | ARCHITECTURE.md, Banner and Backup Mechanism: "a copy, not a rename, so the live file keeps its inode, owner, and mode regardless of who regenerates it" | `st_ino` and `st_mode` of the target are unchanged across both overwrite rows (hash-matching in place, and hand-edited with backup) | `TestWriteSafetyBackupBranches` | P3 | +1 |
| N4 | SPEC.md, Guest-Extraction Contract: "a definition that would not extract fails at generation"; CONVENTIONS.md: "an agents template must open with one" | A scratch agents template with no frontmatter: `generate` raises `InputError` naming the template, and nothing is written under the output root | `TestGenerateRoundTrip` | P6 | +1 |
| N5 | ARCHITECTURE.md, Template System: "`@!name key="value"!@` — bind a value … falls back to `[chunks.name.defaults]` when the marker omits it" | One chunk with a default for `k`. A call that binds `k` renders the call's value; a call that omits `k` renders the default | `TestExpander` | P9, c1 | +1 |
| N6 | ARCHITECTURE.md, Template System: "`@!name variant="x"!@` — expand a specific variant of a multi-variant chunk"; Chunks: "either a `text` body or a set of named `variants`" | A two-variant chunk: `variant="second"` renders the second. A bare call, an unknown variant, and `variant=` on a `text` chunk each raise `InputError` | `TestExpander` | c2, c3, c4, c5 | +1 |
| N7 | ARCHITECTURE.md, Template System, Chunks: "A chunk has either a `text` body or a set of named `variants` — never both" | `load_chunks` over a planted table whose chunk carries both raises `InputError` naming the chunk. Lands with SF1: red before the fix, green after | `TestExpander` | P11 (current code) | +1 |
| N8 | SPEC.md, Generation System: "An install that requests a tuning other than the default … renders the generated definitions under it" | In `TestTuningCLI`'s scratch repo, after planting one file per `SHIPPED_PACKAGES` source row: `install OUT --family probe` exits 0, `agents/applied-mathematician.md` contains `probe opus text`, and its `!TUNING!` claim equals the one `generate --family probe` writes | `TestTuningCLI` | m4 | +1 |
| N9 | `templates/family/README.md`: "naming an anchor nothing authors is a hard error, so a renamed or deleted anchor cannot leave a family file silently filling nothing" | In `TestTuningCLI`'s scratch repo, plant `stray.toml` (the probe tiers plus `[family.no-such-anchor] text = "x"`): `generate OUT --family stray` exits 2 and writes nothing | `TestTuningCLI` | m8 (PR2) | +1 |
| N10 | SPEC.md, Write Safety table: "generated banner, body hash absent or mismatched, render differs \| prior content copied aside as a numbered backup, then overwritten" | A target carrying a banner with no `!BODY-SHA256!` line, whose render differs: after generate, `.00.bak` holds the prior content and the target holds the render | `TestWriteSafetyBackupBranches` | g1 | +1 |
| N11 | SPEC.md, Deployed Surfaces: the banner never sits "out of the first body line a frontmatter-less command is described by"; ARCHITECTURE.md, Banner and Backup Mechanism: a command "is given a minimal frontmatter block holding only the banner" | Over the real set: for every command template that opens with neither `---` nor `+++`, the rendered file's first line after its closing `---` is the template's first line, rendered. Reuse the M1 render | M1's class | r1 | +1 |
| N12 | SPEC.md, Deployed Surfaces: what sits under `agents/mad/` "additionally carries a frontmatter block empty of dispatch keys" | Over the real set: no `agents/mad/**` frontmatter holds a `name:`, `description:` or `model:` key. Reuse the M1 render | M1's class | t1 | +1 |

## Source fixes (4 rows)

| Row | Files | Change | Rationale | Done-when | Δ |
|---|---|---|---|---|---|
| SF1 | `gen_defs/chunks.py`; N7 in `tests/test_gen_defs.py` | `load_chunks` raises `InputError` for a chunk carrying both `text` and `variants` | ARCHITECTURE.md, Chunks: "never both". Today the loader accepts such a chunk, and the `text` body is silently unreachable (P11). No chunk in `templates/shared-chunks.toml` carries both today, so the shipped file still loads | N7 fails before the change and passes after; `just test` green | 0 (N7 counted above) |
| SF2 | `gen_defs/generation.py`, `gen_defs/installation.py`, `gen_defs/rendering.py`, and every call site in `gen_defs/` and `tests/` | `overlays` becomes keyword-only with no default on `generate`, `install`, `render_template` and `all_renders`. `all_renders` currently takes it positionally, so its callers move to `overlays=`. A caller with no family passes `overlays=None` explicitly. Delete D15 in the same row | A default of `None` means that leaving the argument out ships definitions without their member overrides, and nothing notices. Under m4, `cli.main` dropped the argument on the install route and every test passed. `all_renders` already refuses the same omission for `tuning`; its docstring: "`tuning` is required rather than defaulted: every render runs under a triple, so a None one has no reading". Once the omission is a `TypeError` at the call, D15 guards nothing | `just test` green, which proves every call site was updated, since a missed one raises `TypeError` | 0 (D15's −1 is counted under Deletions) |
| SF3 | `gen_defs/product.py`; D14 in `tests/test_gen_defs.py` | Drop the `if surface in smap:` filter in `package_destinations`, and the docstring sentences in `package_destinations` and `package_pairs` that describe it (including "`--surfaces commands` installs no agent-side package"). Delete D14 in the same row | `install` declares no `--surfaces`, and `cli.main` hard-codes both surfaces for install (ARCHITECTURE.md, Install Consumption Model: each verb "declares only the flags it can act on"). The branch is unreachable, and with it removed exactly D14's two tests failed. CONVENTIONS.md: "Obviated code is deleted, not parked" | `just test` green | 0 (D14's −2 is counted under Deletions) |
| SF4 | `gen_defs/rendering.py` | In `output_tier`'s docstring, a literal pin is no longer "legal", and "or of a pin site not yet tokenized" goes. `output_tier` returns None for a literal pin, and `assert_tiered` refuses it | ARCHITECTURE.md, Model tuning: a literal pin "fails the render: `assert_tiered` refuses it" | green | 0 |

## Ordering

- **N8 before SF2.** SF2 deletes D15, and N8 is what then guards the install
  route's tuning wiring.
- **W4 is one row in two steps.** The new abbreviation test lands and passes
  its m5 check before the old test is deleted.
- **N7 before SF1's code change.** Red first, then green.
- **M7 before SF3.** Both edit `TestShippedPackageMapping`.
- **M1 before N11 and N12.** Both reuse M1's real-set render.
- **N3 before W17.** W17 verifies the docstring claim N3 makes true.
- **D8 and D9 before or with M5.** All three edit `TestInstallEndToEnd`'s report tests.
- **File ownership.** Every row touching `tests/test_gen_defs.py` (every D, M,
  W, N and SF row except D13, M8, M9, M11 and W14–W16) has one owner and runs
  serially. Rows in `tests/test_agents_file_render.py` (D13, M9, M11, W14,
  W15) and in `tests/test_agents_file_install.py` (M8, W16) can each run in
  parallel with that owner. SF2 also edits `gen_defs/` call sites. No other
  row edits `gen_defs/generation.py`, `gen_defs/installation.py` or
  `gen_defs/rendering.py` while SF2 is open, apart from SF4's docstring,
  which goes after SF2.
- **Recommended sequence.** New tests and SF1, then N8 → SF2 → SF3 → SF4, then
  rewrites, then merges, then deletions. That way coverage never dips below
  baseline partway through.

## `TestInstallEndToEnd` runtime

At baseline, `TestInstallEndToEnd` took 3.93 s of a 9.00 s
`just test gen_defs` run (44%).

No row exists only to cut runtime. Three rows remove whole installs as a side
effect, without losing coverage:

| Row | Tests removed or merged | Baseline duration | After |
|---|---|---|---|
| D8 | `test_no_installed_file_carries_the_tier_sentinel` | 0.09 s | 0 |
| D9 | `test_default_install_into_a_fresh_root_reports_integrity_ok` | 0.18 s | 0 |
| D14 | `test_the_removal_is_bounded_to_the_rows_the_surface_map_covers` | 0.09 s | 0 |
| M5 | the five one-line-report tests | 0.61 s | about 0.26 s |

Expected saving: about 0.7 s, roughly 18% of the class. Every install
`installation.install` makes renders the full set twice: once in `generate`,
and again in `all_renders`, only to count outputs. That is a larger lever, but
it is a source change outside this plan.

## Probes (only execution settles these)

| ID | Run | Settles |
|---|---|---|
| PR1 | `just test gen_defs` in a fresh `git worktree` | Whether mutation checks can run through the runner. The worktree's `_venv` recipe pip-installs pytest on first use. If it cannot, the mutation run needs a target this repository does not have; report that gap rather than improvising a bare pytest invocation |
| PR2 | N9 under m8 | Whether anything after `validate_family_anchors` already refuses a stray anchor. If N9 passes under m8, N9 is not done, and the CLI's anchor validation is redundant; report that as a finding |
| PR3 | M6's refuse table with the symlink case | Whether `test_a_root_reaching_the_source_through_a_symlink_is_refused` fits a `subTest` row or needs its own setup. If it stays separate, M6 is −5 and every final count is +1 (3086 / 435 / 358) |
| PR4 | An opencode agents-file install into a planted `~/.config/opencode` and into a project directory, then diff the two | Whether the two installs differ in anything a test can assert. Opencode's native name is `AGENTS.md`, so both write one file of the same name. This decides whether the opencode global-install clause (SPEC.md, Harness Agents File) can have a test with teeth |
| PR5 | `just test gen_defs --durations=0 -q -p no:cacheprovider` after every row has landed | The actual `TestInstallEndToEnd` saving against the estimate above |

## Considered, not planned

| Item | Why |
|---|---|
| Extract one tuning-context builder shared by `cli.main` and the five test sites that assemble it by hand | N8 and N9 drive the CLI's own assembly, so its validations gain coverage without the refactor. Where the builder would live in the import graph is a design choice of its own |
| Pass the package table into `package_pairs` instead of monkeypatching `product.SHIPPED_PACKAGES` | M7 still needs a planted table out of destination order. The monkeypatch carries that with no signature change |
| Tests for an unterminated `+++` fence, a fence declaring no outputs, and install with no package source found | Those refusals live in `gen_defs/discovery.py` and the `installation` docstring. No SPEC.md or ARCHITECTURE.md line states them |
| A test for nested `SHIPPED_PACKAGES` destinations (every destination removed before any write) | Both table rows are flat. It becomes testable when the table grows a nested row |
| A test for opencode's global agents-file install | Waits on PR4 |
| A CONVENTIONS.md line for the "imports at module level only" rule, which `test_gen_defs_structure::test_no_import_below_module_level` enforces | A contract-document change, not a test change |
| Making `install` render the set once | A source change; see the runtime section |
