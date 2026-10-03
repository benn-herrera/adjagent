"""Tests for the gen_defs package's pure logic — overlay anchor collection and resolution,
family-file loading and validation (including the required [tiers] table and
the member-reachability rule), family selection, scope resolution (model wins
over family), tier resolution (each output's model scope comes from the tier
its own pin site declares, through the effective tier map), the two map flags'
parse-and-merge semantics, surface-map construction, definition-selection globs
(matching, validation, accounting, and the filtered generate path),
the banner's !TUNING! line, the two body-hash banners
(!GENERATED! and !INSTALLED!) and the backup branches they gate, the
render-to-order generate round trip, and full-product install (copy set,
per-filetype banner placement, per-target write safety, the content-only write
path — in-place update, inode and mode preserved, exec bit on creation, backups
as plain content copies — and end-to-end installs of this repository — default,
tuned, and re-installed — whose report names problems only: a clean install
is one summary line).

The package is imported from the repository root, which `just test` puts on
PYTHONPATH. Filesystem-shaped cases build
scratch template/output trees with tempfile and drive the refactored
functions (surface_map / all_renders / generate) against them — the real
templates/ and deployed surfaces are never touched or written.
"""

import contextlib
import dataclasses
import fnmatch
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gen_defs import (
    agents_file,
    banners,
    chunks,
    cli,
    discovery,
    errors,
    generation,
    installation,
    markers,
    model_tuning,
    paths,
    product,
    pruning,
    rendering,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _quiet(func, *args, **kwargs):
    """Run a printing mode function, discarding its report."""
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


def _tiers_toml(mapping=None):
    """The [tiers] table every family file must carry, as TOML text."""
    mapping = model_tuning.DEFAULT_PIN_MAP if mapping is None else mapping
    return "[tiers]\n" + "".join(f'{tier} = "{mapping[tier]}"\n' for tier in model_tuning.TIERS)


def _tuning(family, *, tier_map=None, pin_map=None, entries=None, is_default=False):
    """A triple for a scratch render. Tier and pin maps default to the same
    claude-shaped map, which is the shipped default family's own state."""
    tier_map = dict(model_tuning.DEFAULT_PIN_MAP if tier_map is None else tier_map)
    return model_tuning.Tuning(
        family=Path(family),
        tier_map=tier_map,
        pin_map=dict(model_tuning.DEFAULT_PIN_MAP if pin_map is None else pin_map),
        stock=model_tuning.stock_tiers(entries or {}, tier_map),
        is_default=is_default,
    )


# The harness file the CLI loads by default: the shipped templates carry
# @!hrn.<key>!@ markers, so every in-process render of them needs one.
_DEFAULT_HARNESS = agents_file.load_harness(model_tuning.DEFAULT_HARNESS)


def _binding(chunks, pin_map=None):
    return model_tuning.tier_binding(
        chunks,
        pin_map=dict(model_tuning.DEFAULT_PIN_MAP if pin_map is None else pin_map),
        harness=_DEFAULT_HARNESS,
    )


def _expand(text, chunk_table, scope, overlays=None, dynamic=None):
    """`text` expanded under a surface render's routes, with `scope` bound as
    the top-level span's arguments."""
    routes = rendering.routing_table(chunk_table, {} if dynamic is None else dynamic, overlays)
    return markers.expand(text, routes, args=scope).text


def _shipped_renders(family_name, *, tier_spec=None, pin_spec=None):
    """Every real definition rendered under one tuning triple, in memory.

    The route generate and install both take, minus the write: nothing is
    created under the root named here. Returns the triple, the resolved overlay map
    per tier (the None key included — the resolution an output with no pin site
    runs under), and {relative path: rendered text}.
    """
    path = paths.FAMILY_DIR / f"{family_name}{paths.FAMILY_SUFFIX}"
    family = model_tuning.load_family(path)
    tuning = model_tuning.effective_tuning(path, family, tier_spec=tier_spec, pin_spec=pin_spec)
    resolve = model_tuning.tier_resolver(family.entries, tuning.tier_map)
    renders = rendering.all_renders(
        _binding(chunks.load_chunks(), tuning.pin_map),
        discovery.surface_map(paths.REPO_ROOT),
        overlays=resolve,
        tuning=tuning,
    )
    return (
        tuning,
        {tier: resolve(tier) for tier in (None, *model_tuning.TIERS)},
        {paths.rel(target): text for target, text in renders},
    )


class TestAnchorCollection(unittest.TestCase):
    def test_anchors_in_finds_overlay_markers(self):
        text = "a @!fam.one!@ b @!chunk!@ c @!fam.two-x!@"
        self.assertEqual(markers.anchors_in(text, namespace="fam", where="probe"), {"fam.one", "fam.two-x"})

    def test_anchors_in_ignores_other_markers_and_plain_text(self):
        self.assertEqual(markers.anchors_in('@!x!@ @!y variant="z"!@ overlay', namespace="fam", where="probe"), set())

    def test_collect_anchors_spans_templates_and_chunk_bodies(self):
        chunks = {
            "a": {"text": "x @!fam.from-text!@"},
            "b": {"variants": {"v": "@!fam.from-variant!@"}},
            "c": {"text": "t", "defaults": {"k": "@!fam.from-default!@"}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmpl = Path(tmp) / "t.tmpl.md"
            tmpl.write_text("---\n---\n@!fam.from-template!@\n")
            found = markers.collect_anchors(chunks, [tmpl], namespace="fam")
        self.assertEqual(found, {"fam.from-text", "fam.from-variant", "fam.from-default", "fam.from-template"})


class TestIdentifierClass(unittest.TestCase):
    """IDENTIFIER is the one kebab-case class shared by marker names, namespace
    prefixes, family anchor keys, and chunk-argument keys, built once and
    embedded in every regex site rather than re-spelled at each. The embedding
    test is the one that actually guards against divergence: a test that only
    exercised accept/reject behavior on each regex separately would not catch
    someone re-inlining a slightly different pattern by hand at one of the
    sites."""

    def test_identifier_is_embedded_in_every_site(self):
        self.assertIn(markers.IDENTIFIER, markers.MARKER.pattern)
        self.assertIn(markers.IDENTIFIER, markers.ARG.pattern)
        self.assertIn(markers.IDENTIFIER, model_tuning.ANCHOR_KEY.pattern)

    def test_the_namespace_separator_is_outside_the_class(self):
        # The whole of what keeps a namespace from ever being read as a name:
        # widening IDENTIFIER to admit "." would make `fam.gap` a legal chunk
        # name and the routing unrecoverable.
        self.assertIsNone(re.fullmatch(markers.IDENTIFIER, "fam.gap"))

    def test_every_registered_namespace_is_itself_an_identifier(self):
        for namespace in markers.NAMESPACES:
            with self.subTest(namespace=namespace):
                self.assertIsNotNone(re.fullmatch(markers.IDENTIFIER, namespace))

    def test_refuses_leading_digit_leading_or_trailing_or_doubled_hyphen_and_underscore(self):
        for candidate in ("1abc", "-abc", "abc-", "abc--def", "my_key"):
            with self.subTest(candidate=candidate):
                self.assertIsNone(re.fullmatch(markers.IDENTIFIER, candidate))

    def test_accepts_interior_digits_and_multi_segment_kebab_names(self):
        for candidate in ("gap2", "a1b2", "ask-vs-stipulate", "abc-2-def"):
            with self.subTest(candidate=candidate):
                self.assertIsNotNone(re.fullmatch(markers.IDENTIFIER, candidate))


class TestMarkerNamespace(unittest.TestCase):
    """A marker's namespace names the source its value comes from, and it is
    validated wherever a marker is read. It has to be: an overlay anchor no
    loaded source fills renders as NOTHING by design, so a misspelled namespace
    would otherwise be indistinguishable from a legitimately unfilled one."""

    def test_unknown_namespace_is_an_error_naming_the_registered_ones(self):
        for marker in ("@!famly.gap!@", "@!hrnx.key!@", "@!chk.x!@"):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(errors.InputError, "names no source.*arg, dyn, fam"):
                    markers.anchors_in(marker, namespace="fam", where="probe.tmpl.md")
                with self.assertRaisesRegex(errors.InputError, "names no source"):
                    _expand(marker, {}, {}, None)

    def test_a_malformed_namespaced_marker_is_not_a_marker_at_all(self):
        # Neither half may leave the IDENTIFIER class, and neither may the
        # separator repeat. render() consumes only what MARKER matches, so
        # these pass through as literal text — which the residual-marker guard
        # refuses at generation (TestResidualMarkerGuard).
        for marker in ("@!fam.!@", "@!.gap!@", "@!fam.a.b!@", "@!fam.Gap!@", "@!1x.gap!@", "@!fam.gap--x!@"):
            with self.subTest(marker=marker):
                self.assertEqual(_expand(marker, {}, {}, {}), marker)

    def test_a_known_namespace_with_an_unfilled_key_stays_silent(self):
        # The deliberate half: silence is the legal outcome for a key no loaded
        # source defines, which is why the namespace itself must be policed.
        self.assertEqual(_expand("a@!fam.nobody-fills-me!@b", {}, {}, {}), "ab")

    def test_the_namespace_routes_and_the_name_never_does(self):
        # One name, three sources, no precedence: what a marker resolves to is
        # decided by its prefix alone, so a collision has nothing to arbitrate.
        chunks = {"gap": {"text": "from the chunk"}}
        scope = {"gap": "from the argument"}
        dynamic = {"gap": "from the invocation"}
        overlays = {"fam.gap": ("from the family", "family")}
        text = "@!gap!@ / @!arg.gap!@ / @!dyn.gap!@ / @!fam.gap!@"
        self.assertEqual(
            _expand(text, chunks, scope, overlays, dynamic),
            "from the chunk / from the argument / from the invocation / from the family",
        )

    def test_a_bare_marker_never_falls_back_to_an_argument(self):
        # The fallback chain this replaced: a chunk-argument key matching a
        # chunk name silently won, and the chunk never rendered.
        self.assertEqual(_expand("@!gap!@", {"gap": {"text": "chunk"}}, {"gap": "arg"}), "chunk")
        with self.assertRaisesRegex(errors.InputError, "unknown chunk 'gap'"):
            _expand("@!gap!@", {}, {"gap": "arg"})

    def test_an_unbound_argument_names_itself(self):
        with self.assertRaisesRegex(errors.InputError, "no argument 'basis' is bound here"):
            _expand("@!arg.basis!@", {}, {})

    def test_an_unknown_invocation_parameter_names_what_there_is(self):
        with self.assertRaisesRegex(errors.InputError, "unknown invocation parameter 'tier-mid'.*tier-low"):
            _expand("@!dyn.tier-mid!@", {}, {}, None, {"tier-low": "haiku"})

    def test_a_namespaced_marker_takes_no_arguments(self):
        for marker in ('@!fam.gap wrap="70"!@', '@!arg.x variant="v"!@', '@!dyn.tier-low wrap="70"!@'):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(errors.InputError, "takes no arguments"):
                    _expand(marker, {}, {"x": "v"}, {}, {"tier-low": "haiku"})


class TestFamilyLoading(unittest.TestCase):
    def _load(self, toml_text, tiers=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "family.toml"
            path.write_text((_tiers_toml() if tiers is None else tiers) + toml_text, encoding="utf-8")
            return model_tuning.load_family(path)

    def _entries(self, toml_text):
        return self._load(toml_text).entries

    def test_family_and_model_entries_load(self):
        entries = self._entries('[family.gap]\ntext = "fam"\n[family.gap.models.haiku]\ntext = "mod"\n')
        self.assertEqual(entries["fam.gap"]["text"], "fam")
        self.assertEqual(entries["fam.gap"]["models"]["haiku"]["text"], "mod")

    def test_model_only_entry_loads(self):
        entries = self._entries('[family.gap.models.haiku]\ntext = "mod"\n')
        self.assertNotIn("text", entries["fam.gap"])

    def test_text_edge_newlines_stripped(self):
        entries = self._entries('[family.gap]\ntext = """\nfam\n"""\n')
        self.assertEqual(entries["fam.gap"]["text"], "fam")

    def test_missing_file_is_error(self):
        with self.assertRaisesRegex(errors.InputError, "does not exist"):
            model_tuning.load_family(Path("no/such/family.toml"))

    def test_invalid_toml_is_error(self):
        with self.assertRaisesRegex(errors.InputError, "invalid TOML"):
            self._load("[family.gap\n")

    def test_zero_entry_file_loads_cleanly(self):
        # A family name stays reservable before any observed failure motivates
        # an entry — but the [tiers] table is the price of the reservation now.
        for toml_text in ("", "# comments only\n", "[family]\n"):
            self.assertEqual(self._load(toml_text).entries, {})

    def test_tiers_table_is_returned_in_canonical_order(self):
        # Authored in reverse, so the canonical order has to come from the
        # loader rather than from the file.
        reverse = "[tiers]\n" + "".join(
            f'{tier} = "{model_tuning.DEFAULT_PIN_MAP[tier]}"\n' for tier in reversed(model_tuning.TIERS)
        )
        tiers = self._load("", tiers=reverse).tiers
        self.assertEqual(list(tiers), list(model_tuning.TIERS))
        self.assertEqual(tiers, model_tuning.DEFAULT_PIN_MAP)

    def test_missing_tiers_table_is_a_load_error_naming_the_five(self):
        with self.assertRaisesRegex(errors.InputError, r"no \[tiers\] table.*highest, high, medium, low, lowest"):
            self._load('[family.gap]\ntext = "t"\n', tiers="")

    def test_incomplete_tiers_table_is_a_load_error(self):
        with self.assertRaisesRegex(errors.InputError, "keys must be exactly"):
            self._load("", tiers='[tiers]\nhighest = "fable"\nhigh = "opus"\n')

    def test_unknown_tier_key_is_a_load_error(self):
        with self.assertRaisesRegex(errors.InputError, "keys must be exactly"):
            self._load("", tiers=_tiers_toml() + 'middling = "sonnet"\n')

    def test_empty_or_whitespace_member_is_a_load_error(self):
        for bad in ('""', '"two words"'):
            with self.subTest(member=bad):
                broken = _tiers_toml().replace('"sonnet"', bad)
                with self.assertRaisesRegex(errors.InputError, "non-empty member name"):
                    self._load("", tiers=broken)

    def test_duplicate_members_across_tiers_are_legal(self):
        # A family's ladder may staff two tiers with one member — the shipped
        # claude family does exactly that at low and lowest.
        self.assertEqual(self._load("").tiers["low"], self._load("").tiers["lowest"])

    def test_stray_top_level_table_is_error(self):
        with self.assertRaisesRegex(errors.InputError, "unknown top-level"):
            self._load('[family.gap]\ntext = "t"\n[other]\nx = "y"\n')

    def test_bad_anchor_key_is_error(self):
        with self.assertRaisesRegex(errors.InputError, "a-z0-9"):
            self._load('[family.BadName]\ntext = "t"\n')

    def test_entry_keys_load_under_their_full_anchor_name(self):
        # The table path IS the anchor: [family.gap] fills family.gap, so the
        # loaded map compares directly against what templates author.
        self.assertEqual(list(self._entries('[family.gap]\ntext = "t"\n')), ["fam.gap"])

    def test_unknown_entry_key_is_error(self):
        with self.assertRaisesRegex(errors.InputError, "only 'text'"):
            self._load('[family.gap]\ntext = "t"\nextra = "x"\n')

    def test_malformed_model_override_is_error(self):
        with self.assertRaisesRegex(errors.InputError, "exactly one key"):
            self._load('[family.gap.models.haiku]\ntext = "t"\nextra = "x"\n')

    def test_entry_filling_nothing_is_error(self):
        with self.assertRaisesRegex(errors.InputError, "fills nothing"):
            self._load("[family.gap]\n")


class TestFamilyValidation(unittest.TestCase):
    def test_known_anchors_pass(self):
        model_tuning.validate_family_anchors({"fam.gap": {}}, {"fam.gap", "fam.other"})

    def test_unknown_anchor_is_hard_error(self):
        with self.assertRaisesRegex(errors.InputError, "ghost"):
            model_tuning.validate_family_anchors({"fam.ghost": {}, "fam.gap": {}}, {"fam.gap"})


class TestMemberReachability(unittest.TestCase):
    """A [family.*.models.<member>] table no tier reaches can never render, and
    is a hard error rather than a tier that silently reports Stock."""

    PATH = Path("templates/family/probe.toml")

    def _family(self, member, tiers=None):
        return model_tuning.Family(
            entries={"fam.gap": {"models": {member: {"text": "t"}}}},
            tiers=dict(model_tuning.DEFAULT_PIN_MAP if tiers is None else tiers),
        )

    def test_member_the_family_maps_passes(self):
        model_tuning.validate_family_members(self._family("sonnet"), model_tuning.DEFAULT_PIN_MAP, self.PATH)

    def test_member_only_the_effective_tier_map_reaches_passes(self):
        # The union, not just [tiers]: a table authored for a member reachable
        # through --model-tier-map must not fail a default run.
        tier_map = {**model_tuning.DEFAULT_PIN_MAP, "medium": "probe-member"}
        model_tuning.validate_family_members(self._family("sonnet"), tier_map, self.PATH)
        model_tuning.validate_family_members(self._family("probe-member"), tier_map, self.PATH)

    def test_unreachable_member_names_itself_and_what_is_reachable(self):
        with self.assertRaises(errors.InputError) as caught:
            model_tuning.validate_family_members(self._family("sonnett"), model_tuning.DEFAULT_PIN_MAP, self.PATH)
        message = str(caught.exception)
        self.assertIn("no tier reaches: sonnett", message)
        self.assertIn("sonnet", message)


class TestFamilyResolution(unittest.TestCase):
    """resolve_family: --family NAME is a path or a family file, and nothing
    else — a bare model name has no reading left."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.family_dir = Path(self._tmp.name)

    def _family(self, filename):
        path = self.family_dir / filename
        path.write_text(_tiers_toml(), encoding="utf-8")
        return path

    def _resolve(self, name):
        return model_tuning.resolve_family(name, self.family_dir)

    def test_path_with_separator_passes_through(self):
        # Path-shaped names are never name-resolved, even when nonexistent —
        # load_family owns the existence error.
        self.assertEqual(self._resolve("no/such/family"), Path("no/such/family"))

    def test_toml_suffix_passes_through(self):
        self.assertEqual(self._resolve("fam.toml"), Path("fam.toml"))

    def test_bare_name_matches_the_family_file(self):
        planted = self._family("gem.toml")
        self.assertEqual(self._resolve("gem"), planted)

    def test_a_model_name_is_refused_and_the_families_are_listed(self):
        self._family("gem.toml")
        self._family("claude.toml")
        with self.assertRaises(errors.InputError) as caught:
            self._resolve("opus")
        message = str(caught.exception)
        for name in ("--family", "opus", "claude", "gem"):
            self.assertIn(name, message)

    def test_no_family_files_at_all_says_so(self):
        with self.assertRaisesRegex(errors.InputError, r"available: \(none\)"):
            self._resolve("ghost")


class TestMapMerge(unittest.TestCase):
    """effective_map: what a partial map flag does, and what it refuses."""

    FLAG = "--model-pin-map"

    def _merge(self, spec, defaults=None):
        return model_tuning.effective_map(
            model_tuning.DEFAULT_PIN_MAP if defaults is None else defaults, spec, flag=self.FLAG
        )

    def test_no_spec_is_the_defaults(self):
        self.assertEqual(self._merge(None), model_tuning.DEFAULT_PIN_MAP)

    def test_named_tier_masks_only_itself(self):
        # The whole-map-replacement bug looks identical in the happy path, so
        # this is the case that separates them.
        merged = self._merge("medium=fable")
        self.assertEqual(merged["medium"], "fable")
        self.assertEqual(
            {tier: merged[tier] for tier in model_tuning.TIERS if tier != "medium"},
            {tier: value for tier, value in model_tuning.DEFAULT_PIN_MAP.items() if tier != "medium"},
        )

    def test_all_covers_every_tier(self):
        self.assertEqual(self._merge("all=haiku"), {tier: "haiku" for tier in model_tuning.TIERS})

    def test_all_is_positional_independent(self):
        # Whichever side of the named tier `all` sits, the named tier wins.
        first = self._merge("all=haiku,high=opus")
        second = self._merge("high=opus,all=haiku")
        self.assertEqual(first, second)
        self.assertEqual(first["high"], "opus")
        self.assertEqual(first["lowest"], "haiku")

    def test_merged_map_is_always_total(self):
        for spec in (None, "low=x", "all=y", "all=y,highest=z"):
            with self.subTest(spec=spec):
                self.assertEqual(set(self._merge(spec)), set(model_tuning.TIERS))

    def test_surrounding_whitespace_is_tolerated(self):
        self.assertEqual(self._merge(" high = a , low = b ")["high"], "a")

    def test_unknown_tier_names_the_five_and_all(self):
        with self.assertRaises(errors.InputError) as caught:
            self._merge("mid=sonnet")
        message = str(caught.exception)
        for name in (self.FLAG, "mid=sonnet", *model_tuning.TIERS, "all"):
            self.assertIn(name, message)

    def test_duplicate_key_is_an_error(self):
        with self.assertRaisesRegex(errors.InputError, r"duplicate key 'low' — a map is 1:1\."):
            self._merge("low=a,low=b")

    def test_duplicate_all_is_an_error_too(self):
        with self.assertRaisesRegex(errors.InputError, "duplicate key 'all'"):
            self._merge("all=a,all=b")

    def test_malformed_pairs_are_errors(self):
        for spec in ("high", "high=", "=haiku", "", "high=a=b", "two words=a", "high=a b"):
            with self.subTest(spec=spec), self.assertRaises(errors.InputError):
                self._merge(spec)

    def test_the_flag_name_leads_every_error(self):
        with self.assertRaisesRegex(errors.InputError, "^--model-tier-map: "):
            model_tuning.effective_map(model_tuning.DEFAULT_PIN_MAP, "nope=x", flag="--model-tier-map")

    def test_pin_values_are_not_validated(self):
        # Deliberate accepted risk: nothing in-repo owns the set of legal
        # claude aliases, so the echo and the banner are the safety story.
        self.assertEqual(self._merge("high=not-a-real-model")["high"], "not-a-real-model")

    def test_map_spec_serializes_in_tier_order_never_sorted(self):
        self.assertEqual(
            model_tuning.map_spec(model_tuning.DEFAULT_PIN_MAP),
            "highest=fable,high=opus,medium=sonnet,low=haiku,lowest=haiku",
        )


class TestTierStates(unittest.TestCase):
    """The two render states §2.3 distinguishes, read off stock_tiers: Tuned
    (the member has tables) and Stock (the member has none at all)."""

    ENTRIES = {
        "fam.gap": {"text": "fam", "models": {"sonnet": {"text": "for sonnet"}}},
        "fam.other": {"text": "fam2"},
    }

    def test_a_mapped_member_with_tables_is_not_stock(self):
        self.assertNotIn("medium", model_tuning.stock_tiers(self.ENTRIES, model_tuning.DEFAULT_PIN_MAP))

    def test_every_other_tier_is_stock(self):
        self.assertEqual(
            model_tuning.stock_tiers(self.ENTRIES, model_tuning.DEFAULT_PIN_MAP),
            ("highest", "high", "low", "lowest"),
        )

    def test_a_family_with_no_member_tables_is_stock_at_every_tier(self):
        self.assertEqual(
            model_tuning.stock_tiers({"fam.gap": {"text": "f"}}, model_tuning.DEFAULT_PIN_MAP), model_tuning.TIERS
        )

    def test_retargeting_a_tier_moves_it_between_the_states(self):
        tuned_low = {**model_tuning.DEFAULT_PIN_MAP, "low": "sonnet"}
        self.assertNotIn("low", model_tuning.stock_tiers(self.ENTRIES, tuned_low))


class TestOverlayResolution(unittest.TestCase):
    ENTRIES = {
        "fam.both": {"text": "fam", "models": {"m1": {"text": "mod"}}},
        "fam.family-only": {"text": "fam-only"},
        "fam.model-only": {"models": {"m1": {"text": "mod-only"}}},
    }

    def test_no_member_resolves_family_scope_only(self):
        resolved = model_tuning.resolve_overlays(self.ENTRIES, None)
        self.assertEqual(
            resolved,
            {"fam.both": ("fam", "family"), "fam.family-only": ("fam-only", "family")},
        )

    def test_model_scope_wins_over_family(self):
        resolved = model_tuning.resolve_overlays(self.ENTRIES, "m1")
        self.assertEqual(resolved["fam.both"], ("mod", "model"))
        self.assertEqual(resolved["fam.model-only"], ("mod-only", "model"))
        # A model with no override still gets the family text.
        self.assertEqual(resolved["fam.family-only"], ("fam-only", "family"))

    def test_unmatched_model_falls_back_to_family_or_nothing(self):
        resolved = model_tuning.resolve_overlays(self.ENTRIES, "other-model")
        self.assertEqual(resolved["fam.both"], ("fam", "family"))
        self.assertNotIn("fam.model-only", resolved)


class TestFrontmatterPin(unittest.TestCase):
    """frontmatter_pin: an output's own model pin, read out of its RENDERED
    frontmatter — however the pin got there."""

    def test_literal_frontmatter_pin(self):
        self.assertEqual(rendering.frontmatter_pin("---\nname: x\nmodel: opus\n---\nbody\n"), "opus")

    def test_quoted_pin(self):
        self.assertEqual(rendering.frontmatter_pin('---\nmodel: "haiku"\n---\nbody\n'), "haiku")

    def test_frontmatter_without_a_model_key_is_unpinned(self):
        self.assertIsNone(rendering.frontmatter_pin("---\nname: x\n---\nbody\n"))
        self.assertIsNone(rendering.frontmatter_pin("---\n---\n\nbody\n"))

    def test_file_without_frontmatter_is_unpinned(self):
        self.assertIsNone(rendering.frontmatter_pin("Do the thing.\n\n## Behavior\n"))

    def test_a_model_line_in_the_body_is_not_a_pin(self):
        self.assertIsNone(rendering.frontmatter_pin("---\nname: x\n---\nmodel: sonnet\n"))


class TestTierDiscovery(unittest.TestCase):
    """output_tier: what a discovery render's frontmatter pin means."""

    def _probe(self, pin):
        return f"---\nname: x\nmodel: {pin}\n---\nbody\n"

    def test_sentinel_yields_the_tier(self):
        for tier in model_tuning.TIERS:
            self.assertEqual(rendering.output_tier(self._probe(f"{model_tuning.TIER_SENTINEL}{tier}")), tier)

    def test_no_pin_site_declares_no_tier(self):
        self.assertIsNone(rendering.output_tier("---\nname: x\n---\nbody\n"))
        self.assertIsNone(rendering.output_tier("bare body\n"))

    def test_the_tier_tokens_expand_from_the_pin_map_alone(self):
        # The one thing a family-member name must never reach: a model: line.
        binding = _binding({}, pin_map={**model_tuning.DEFAULT_PIN_MAP, "medium": "sonnet-probe"})
        self.assertEqual(_expand("@!dyn.tier-medium!@", {}, {}, None, binding.real), "sonnet-probe")
        self.assertEqual(_expand("@!dyn.tier-medium!@", {}, {}, None, binding.probe), "tier:medium")

    def test_a_tier_token_expands_inside_a_chunk_body(self):
        # The dynamic table is routed to every span, so a token reaches a chunk
        # body where an argument — bound only at the call site — would not.
        binding = _binding({"c": {"text": "pin @!dyn.tier-low!@"}})
        self.assertEqual(_expand("@!c!@", binding.chunks, {}, None, binding.real), "pin haiku")

    def test_nothing_is_reserved_so_tier_low_and_overlay_are_ordinary_chunks(self):
        # The tier tokens are the invocation's parameters and the overlay is
        # spelled by its namespace, so a chunk named tier-low or overlay is an
        # ordinary chunk rather than a collision to reserve against, and a BARE
        # tier-low never resolves to a pin.
        binding = _binding({"tier-low": {"text": "an ordinary chunk"}, "overlay": {"text": "another"}})
        self.assertEqual(binding.chunks["tier-low"], {"text": "an ordinary chunk"})
        self.assertEqual(set(binding.real), {f"tier-{tier}" for tier in model_tuning.TIERS})
        self.assertEqual(_expand("@!tier-low!@", binding.chunks, {}, None, binding.real), "an ordinary chunk")
        self.assertEqual(_expand("@!dyn.tier-low!@", binding.chunks, {}, None, binding.real), "haiku")
        self.assertEqual(_expand("@!overlay!@", binding.chunks, {}, {}, binding.real), "another")


class TestTierResolver(unittest.TestCase):
    """tier_resolver: model scope belongs to the output's own TIER, through the
    effective tier map; family scope stays render-wide."""

    FAMILY = (
        '[family.gap]\ntext = "family-wide"\n'
        '[family.gap.models.opus]\ntext = "for opus"\n'
        '[family.other]\ntext = "other family-wide"\n'
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.family_dir = Path(self._tmp.name)
        self.family = self.family_dir / "fam.toml"
        self.family.write_text(_tiers_toml() + self.FAMILY, encoding="utf-8")
        self.entries = model_tuning.load_family(self.family).entries

    def _resolver(self, tier_map=None):
        return model_tuning.tier_resolver(self.entries, dict(tier_map or model_tuning.DEFAULT_PIN_MAP))

    def test_member_scope_wins_over_family_scope_at_the_same_anchor(self):
        resolve = self._resolver()
        self.assertEqual(resolve("high")["fam.gap"], ("for opus", "model"))
        # Anchors the member does not override still take the family text.
        self.assertEqual(resolve("high")["fam.other"], ("other family-wide", "family"))

    def test_tier_whose_member_has_no_entry_takes_family_scope(self):
        self.assertEqual(self._resolver()("low")["fam.gap"], ("family-wide", "family"))

    def test_no_tier_takes_family_scope_only(self):
        # An output with no pin site is outside the pinning system, not inside
        # it holding an empty pin — and still gets every family-wide anchor.
        resolved = self._resolver()(None)
        self.assertEqual(resolved["fam.gap"], ("family-wide", "family"))
        self.assertEqual(resolved["fam.other"], ("other family-wide", "family"))

    def test_the_tier_map_decides_which_member_a_tier_resolves(self):
        # The same tier, retargeted: nothing about the output changed.
        retargeted = self._resolver({**model_tuning.DEFAULT_PIN_MAP, "lowest": "opus"})
        self.assertEqual(retargeted("lowest")["fam.gap"], ("for opus", "model"))
        self.assertEqual(self._resolver()("lowest")["fam.gap"], ("family-wide", "family"))

    def test_a_family_with_no_entries_resolves_to_nothing(self):
        resolve = model_tuning.tier_resolver({}, dict(model_tuning.DEFAULT_PIN_MAP))
        self.assertEqual(resolve(None), {})
        self.assertEqual(resolve("high"), {})

    def test_plain_map_stays_render_wide(self):
        # as_resolver is what keeps a caller that has already resolved one map
        # working: it reaches every output, tiered or not.
        resolve = model_tuning.as_resolver({"fam.gap": ("wide", "family")})
        self.assertEqual(resolve(None), resolve("high"))
        self.assertIsNone(model_tuning.as_resolver(None)("high"))


class TestRenderOverlay(unittest.TestCase):
    def test_unfilled_anchor_expands_to_nothing(self):
        for overlays in (None, {}):
            self.assertEqual(_expand("a @!fam.gap!@b", {}, {}, overlays), "a b")

    def test_filled_anchor_renders_the_family_text_verbatim(self):
        # Exact equality is the whole assertion: the anchor expands to the
        # family's own bytes and to nothing else — no lead-in, no wrapper.
        out = _expand("@!fam.gap!@", {}, {}, {"fam.gap": ("watch it", "family")})
        self.assertEqual(out, "watch it")

    def test_base_text_never_modified_around_anchor(self):
        # The never-touches-base invariant at render level: filling an anchor
        # adds the family's text and changes nothing else.
        template = "base line\n@!fam.gap!@\nmore base"
        bare = _expand(template, {}, {}, None)
        filled = _expand(template, {}, {}, {"fam.gap": ("t", "model")})
        self.assertEqual(bare, "base line\n\nmore base")
        self.assertEqual(filled, "base line\nt\nmore base")

    def test_overlay_text_is_marker_expanded(self):
        chunks = {"c": {"text": "chunked"}}
        out = _expand("@!fam.gap!@", chunks, {}, {"fam.gap": ("see @!c!@", "family")})
        self.assertEqual(out, "see chunked")

    def test_typo_in_overlay_text_fails_loudly(self):
        with self.assertRaisesRegex(errors.InputError, "unknown chunk"):
            _expand("@!fam.gap!@", {}, {}, {"fam.gap": ("see @!nope!@", "family")})

    def test_render_output_resolves_against_its_own_declared_tier(self):
        # render_output reads the tier out of its own discovery pass, so a tier
        # token bound as an outputs-table parameter resolves exactly as a
        # literal one does.
        body = "---\nname: @!arg.name!@\nmodel: @!arg.model!@\n---\n@!fam.gap!@\n"
        params = {"name": "x", "model": "@!dyn.tier-high!@"}
        text, tier = rendering.render_output(body, _binding({}), params, lambda t: {"fam.gap": (str(t), "model")})
        self.assertEqual(tier, "high")
        self.assertIn("\nhigh\n", text)
        # The shipped pin, never the tier and never a family member.
        self.assertEqual(rendering.frontmatter_pin(text), "opus")

    def test_render_output_of_a_body_with_no_pin_site_takes_the_no_tier_map(self):
        body = "---\nname: @!arg.name!@\n---\n@!fam.gap!@\n"
        text, tier = rendering.render_output(
            body, _binding({}), {"name": "x"}, lambda t: {"fam.gap": (str(t), "model")}
        )
        self.assertIsNone(tier)
        self.assertIn("\nNone\n", text)

    def test_pass_b_is_unconditional_so_no_sentinel_ever_ships(self):
        # The overlay set is identical for every tier here, which is exactly when
        # the retired "re-render only if the overlay set changed" optimization would
        # have returned the discovery render — sentinel text and all.
        body = "---\nname: @!arg.name!@\nmodel: @!dyn.tier-low!@\n---\nrun on @!dyn.tier-low!@\n"
        text, tier = rendering.render_output(body, _binding({}), {"name": "x"}, lambda t: {})
        self.assertEqual(tier, "low")
        self.assertNotIn(model_tuning.TIER_SENTINEL, text)
        self.assertIn("run on haiku", text)

    def test_anchor_inside_chunk_body_resolves(self):
        chunks = {"c": {"text": "chunk @!fam.gap!@tail"}}
        self.assertEqual(_expand("@!c!@", chunks, {}, None), "chunk tail")
        self.assertEqual(
            _expand("@!c!@", chunks, {}, {"fam.gap": ("filled", "family")}),
            "chunk filledtail",
        )


class TestExpander(unittest.TestCase):
    """markers.expand over a routing table: lexical `arg`, the three value
    kinds, and the depth cap."""

    def _routes(self, chunk_table=None, dynamic=None, overlays=None, harness=None):
        routes = rendering.routing_table(chunk_table or {}, dynamic or {}, overlays)
        if harness is not None:
            routes = {**routes, "hrn": markers.TableSource(harness, "hrn", "harness key")}
        return routes

    def test_a_chunk_body_reads_its_own_call_arguments(self):
        routes = self._routes({"c": {"text": "@!arg.x!@ @!fam.g!@"}}, overlays={"fam.g": ("fam:@!arg.x!@", "family")})
        out = markers.expand('@!arg.x!@ @!c x="inner"!@', routes, args={"x": "outer"})
        self.assertEqual(out.text, "outer inner fam:inner")

    def test_an_authored_value_is_expanded(self):
        routes = self._routes({"c": {"text": "C"}}, dynamic={"d": "<@!c!@>"}, harness={"h": "[@!c!@]"})
        self.assertEqual(markers.expand("@!dyn.d!@ @!hrn.h!@", routes, args={}).text, "<C> [C]")

    def test_a_verbatim_value_is_final_and_unchecked(self):
        dynamic = {"v": markers.Verbatim("@!c!@ !@"), "e": markers.Verbatim("")}
        out = markers.expand("a @!dyn.v!@ b@!dyn.e!@", self._routes(dynamic=dynamic), args={})
        self.assertEqual(out.text, "a @!c!@ !@ b")
        self.assertEqual(
            out.verbatim,
            (
                markers.VerbatimSpan(2, "@!c!@ !@", "@!dyn.v!@"),
                markers.VerbatimSpan(len("a @!c!@ !@ b"), "", "@!dyn.e!@"),
            ),
        )
        markers.assert_no_residual_markers(out, path=paths.REPO_ROOT / "probe.tmpl.md", name="probe")

    def test_a_cycle_hits_the_depth_cap(self):
        for text, routes in (
            ("@!loop!@", self._routes({"loop": {"text": "x @!loop!@"}})),
            ("@!dyn.self!@", self._routes(dynamic={"self": "@!dyn.self!@"})),
        ):
            with self.subTest(text=text):
                with self.assertRaisesRegex(errors.InputError, r"cycle\?"):
                    markers.expand(text, routes, args={})

    def test_a_call_binds_its_own_value_and_an_omitted_key_falls_back_to_the_default(self):
        routes = self._routes({"c": {"text": "k=@!arg.k!@", "defaults": {"k": "default"}}})
        self.assertEqual(markers.expand('@!c k="bound"!@', routes, args={}).text, "k=bound")
        self.assertEqual(markers.expand("@!c!@", routes, args={}).text, "k=default")

    def test_a_variant_call_selects_its_variant_and_every_misuse_is_refused(self):
        routes = self._routes({"v": {"variants": {"first": "one", "second": "two"}}, "t": {"text": "plain"}})
        self.assertEqual(markers.expand('@!v variant="second"!@', routes, args={}).text, "two")
        # A bare call, an unknown variant, and a variant asked of a text chunk.
        for marker in ("@!v!@", '@!v variant="third"!@', '@!t variant="first"!@'):
            with self.subTest(marker=marker), self.assertRaises(errors.InputError):
                markers.expand(marker, routes, args={})

    def test_a_chunk_with_both_a_text_body_and_variants_is_refused_at_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            planted = Path(tmp) / "shared-chunks.toml"
            planted.write_text('[chunks.both]\ntext = "t"\n[chunks.both.variants]\nv = "x"\n', encoding="utf-8")
            with mock.patch.object(chunks, "SHARED_CHUNKS", planted):
                with self.assertRaisesRegex(errors.InputError, "chunk 'both'"):
                    chunks.load_chunks()

    def test_wrap_wraps_the_expanded_chunk_body(self):
        # Wrapped before expansion, the lone marker has no space to break on
        # and the words would come out on one line.
        routes = self._routes({"c": {"text": "@!arg.w!@"}})
        out = markers.expand('@!c w="one two three four" wrap="9"!@', routes, args={})
        self.assertEqual(out.text, "one two\nthree\nfour")

    def test_wrap_refuses_verbatim_text(self):
        routes = self._routes({"c": {"text": "a @!dyn.v!@"}}, dynamic={"v": markers.Verbatim("operator text")})
        with self.assertRaisesRegex(errors.InputError, "wrap="):
            markers.expand('@!c wrap="9"!@', routes, args={})


class TestHarnessSurfaceRender(unittest.TestCase):
    """A surface render routes `hrn` to the harness its invocation loaded."""

    BODY = "---\nname: @!arg.name!@\n---\nread @!hrn.agents-file!@\n"

    def _render(self, harness):
        binding = model_tuning.tier_binding({}, pin_map=dict(model_tuning.DEFAULT_PIN_MAP), harness=harness)
        text, _ = rendering.render_output(self.BODY, binding, {"name": "x"}, lambda tier: {})
        return text

    def test_a_harness_marker_resolves_in_a_surface_render_given_a_harness(self):
        self.assertIn("read AGENTS.md\n", self._render(agents_file.load_harness("opencode")))

    def test_the_default_harness_supplies_the_claude_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            for verb in ("generate", "install"):
                with self.subTest(verb=verb):
                    default = cli.build_parser().parse_args([verb, tmp]).harness
                    self.assertIn("read CLAUDE.md\n", self._render(agents_file.load_harness(default)))


class TestSurfaceMap(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_an_output_root_maps_both_surfaces_beneath_it(self):
        smap = discovery.surface_map(self.root)
        self.assertEqual(set(smap), {"agents", "commands"})
        self.assertEqual(smap["agents"][1], self.root / "agents")

    def test_surfaces_filters_to_one(self):
        self.assertEqual(set(discovery.surface_map(self.root, surfaces="agents")), {"agents"})
        self.assertEqual(set(discovery.surface_map(self.root, surfaces="commands")), {"commands"})

    def test_unknown_surface_is_error(self):
        with self.assertRaises(errors.InputError):
            discovery.surface_map(self.root, surfaces="nope")

    def test_output_root_must_exist(self):
        with self.assertRaisesRegex(errors.InputError, "existing directory"):
            discovery.surface_map(output_root=Path("no/such/root"))

    def test_explicit_roots_route_both_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            smap = discovery.surface_map(templates_root=Path(tmp) / "tsrc", output_root=Path(tmp))
            self.assertEqual(smap["agents"][0], Path(tmp) / "tsrc" / "agents")
            self.assertEqual(smap["commands"][1], Path(tmp) / "commands")


class TestSelectionMatching(unittest.TestCase):
    """What a selection glob covers: surface-relative keys without the .md
    suffix, fnmatch semantics (`*` crosses `/`), `|`-alternation as a union,
    and an unglobbed surface passing whole."""

    def test_output_key_is_surface_relative_and_suffixless(self):
        root = Path("/out/agents")
        self.assertEqual(discovery.output_key(root / "go-coder.md", root), "go-coder")
        self.assertEqual(
            discovery.output_key(root / "mad" / "participant-contract.md", root),
            "mad/participant-contract",
        )

    def test_single_pattern_selects_its_matches_only(self):
        globs = {"agents": ["*-coder*"]}
        self.assertTrue(discovery.selected("agents", "go-coder", globs))
        self.assertFalse(discovery.selected("agents", "architect", globs))

    def test_alternation_selects_the_union(self):
        globs = {"agents": discovery.split_globs("*app-expert*|*-coder*")}
        for key in ("ios-app-expert", "rust-coder"):
            self.assertTrue(discovery.selected("agents", key, globs), key)
        self.assertFalse(discovery.selected("agents", "architect", globs))

    def test_star_crosses_the_path_separator(self):
        # A nested output is addressable by its full key and by any pattern
        # spanning the separator — that is what makes mad/participant-contract
        # reachable at all.
        for pattern in ("mad/participant-contract", "mad/*", "*participant-contract", "*contract*"):
            self.assertTrue(
                discovery.selected("agents", "mad/participant-contract", {"agents": [pattern]}),
                pattern,
            )
        # The subdirectory is still part of the key: a top-level definition
        # with a similar name is not swept in by mad/*.
        self.assertFalse(discovery.selected("agents", "mad-participant-opus", {"agents": ["mad/*"]}))

    def test_unglobbed_surface_and_empty_selection_pass_whole(self):
        self.assertTrue(discovery.selected("commands", "kb-start", {"agents": ["*-coder*"]}))
        for nothing in (None, {}):
            self.assertTrue(discovery.selected("agents", "architect", nothing))

    def test_matching_does_not_depend_on_host_case_rules(self):
        self.assertFalse(discovery.selected("agents", "go-coder", {"agents": ["GO-*"]}))


class TestSelectionValidationAndAccounting(unittest.TestCase):
    """A pattern matching nothing is a hard error, per `|`-segment; a run that
    selects states what it selected, per surface."""

    KEYS = {
        "agents": ["architect", "go-coder", "mad/participant-contract"],
        "commands": ["kb-start"],
    }

    def test_matching_patterns_validate(self):
        discovery.validate_selection(self.KEYS, {"agents": ["*-coder", "mad/*"]})

    def test_zero_match_names_the_pattern_and_lists_the_surface(self):
        with self.assertRaisesRegex(
            errors.InputError,
            r"--agent-glob pattern '\*-codr\*' matches none of the 3 agents "
            r"output\(s\): architect, go-coder, mad/participant-contract",
        ):
            discovery.validate_selection(self.KEYS, {"agents": ["*-codr*"]})

    def test_every_alternation_segment_is_held_to_the_rule(self):
        # A typo cannot hide behind a sibling pattern that does match.
        with self.assertRaisesRegex(errors.InputError, "'ghost'"):
            discovery.validate_selection(self.KEYS, {"agents": ["*-coder", "ghost"]})

    def test_each_surface_error_names_its_own_flag(self):
        with self.assertRaisesRegex(errors.InputError, r"--command-glob pattern 'nope'"):
            discovery.validate_selection(self.KEYS, {"commands": ["nope"]})

    def test_accounting_states_selected_of_declared_per_surface(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            discovery.report_selection(self.KEYS, {"agents": ["*-coder", "mad/*"], "commands": ["kb-*"]})
        self.assertIn("agents: 2 of 3 outputs selected by --agent-glob", buf.getvalue())
        self.assertIn("commands: 1 of 1 outputs selected by --command-glob", buf.getvalue())


class TestSelectedGeneration(unittest.TestCase):
    """Selection over a scratch tree: per-output filtering of a multi-output
    template, nested-path selection, unselected outputs left untouched, and
    composition with tier tuning."""

    CHUNKS = {"shared": {"text": "shared text"}}
    PINNED = "---\nname: @!arg.name!@\nmodel: @!dyn.tier-high!@\n---\nbody @!shared!@\n@!fam.probe!@\n"
    UNPINNED = "---\nname: @!arg.name!@\n---\nbody @!shared!@\n" "@!fam.probe!@\n"
    MULTI = (
        "+++\n"
        "[outputs.multi-one]\n"
        'model = "@!dyn.tier-high!@"\n'
        "[outputs.multi-two]\n"
        'model = "@!dyn.tier-low!@"\n'
        "+++\n"
        "---\nname: @!arg.name!@\nmodel: @!arg.model!@\n---\nbody @!shared!@\n"
    )
    FAMILY = (
        '[family.probe]\ntext = "family"\n'
        '[family.probe.models.opus]\ntext = "opus text"\n'
        '[family.probe.models.haiku]\ntext = "haiku text"\n'
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        agents = self.tsrc / "agents"
        (agents / "mad").mkdir(parents=True)
        (agents / "go-coder.tmpl.md").write_text(self.PINNED, encoding="utf-8")
        (agents / "architect.tmpl.md").write_text(self.UNPINNED, encoding="utf-8")
        (agents / "multi.tmpl.md").write_text(self.MULTI, encoding="utf-8")
        self.nested_template = agents / "mad" / "participant-contract.tmpl.md"
        self.nested_template.write_text(self.UNPINNED, encoding="utf-8")
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.family_dir = root / "family"
        self.family_dir.mkdir()
        self.family = self.family_dir / "fam.toml"
        self.family.write_text(_tiers_toml() + self.FAMILY, encoding="utf-8")

    def _generate(self, globs=None, chunks=None, **kwargs):
        kwargs.setdefault("overlays", None)
        kwargs.setdefault("tuning", _tuning(self.family))
        return _quiet(
            generation.generate,
            _binding(self.CHUNKS if chunks is None else chunks),
            self.smap,
            globs=globs,
            **kwargs,
        )

    def _rendered(self):
        return sorted(path.relative_to(self.out).as_posix() for path in self.out.rglob("*.md"))

    def test_output_keys_span_both_surfaces_and_nested_paths(self):
        self.assertEqual(
            discovery.output_keys(self.smap)["agents"],
            ["architect", "go-coder", "mad/participant-contract", "multi-one", "multi-two"],
        )

    def test_glob_renders_only_its_matches(self):
        self.assertTrue(self._generate({"agents": ["*-coder"]}))
        self.assertEqual(self._rendered(), ["agents/go-coder.md"])

    def test_multi_output_template_filters_per_output(self):
        self.assertTrue(self._generate({"agents": ["multi-one"]}))
        self.assertEqual(self._rendered(), ["agents/multi-one.md"])

    def test_nested_output_is_addressable_by_its_key(self):
        self.assertTrue(self._generate({"agents": ["mad/*"]}))
        self.assertEqual(self._rendered(), ["agents/mad/participant-contract.md"])

    def test_unselected_outputs_are_left_untouched_on_disk(self):
        self._generate()
        before = {name: (self.out / name).read_bytes() for name in self._rendered()}
        stamps = {name: (self.out / name).stat().st_mtime_ns for name in before}
        # A chunk change every output would pick up, applied under a selection
        # that covers exactly one of them.
        self.assertTrue(self._generate({"agents": ["multi-one"]}, chunks={"shared": {"text": "changed text"}}))
        self.assertIn("changed text", (self.out / "agents" / "multi-one.md").read_text(encoding="utf-8"))
        for name, content in before.items():
            if name == "agents/multi-one.md":
                continue
            self.assertEqual((self.out / name).read_bytes(), content, name)
            self.assertEqual((self.out / name).stat().st_mtime_ns, stamps[name], name)

    def test_a_selection_writes_its_matches_byte_for_byte_and_no_others(self):
        # Both halves of what a selection promises, stated against the render
        # each target came from: a selected output lands as exactly those
        # bytes, and an unselected one is not written at all.
        tuning = _tuning(self.family)
        globs = {"agents": ["*-coder"]}
        self.assertTrue(self._generate(globs))
        selected = rendering.all_renders(_binding(self.CHUNKS), self.smap, overlays=None, globs=globs, tuning=tuning)
        self.assertTrue(selected)
        for target, rendered in selected:
            self.assertEqual(target.read_text(encoding="utf-8"), rendered, paths.rel(target))
        every = rendering.all_renders(_binding(self.CHUNKS), self.smap, overlays=None, tuning=tuning)
        unselected = {target for target, _ in every} - {target for target, _ in selected}
        self.assertTrue(unselected)
        for target in unselected:
            self.assertFalse(target.exists(), paths.rel(target))

    def test_selection_composes_with_tier_tuning(self):
        entries = model_tuning.load_family(self.family).entries
        resolve = model_tuning.tier_resolver(entries, dict(model_tuning.DEFAULT_PIN_MAP))
        tuning = _tuning(self.family, entries=entries)
        globs = {"agents": ["go-coder", "architect"]}
        self.assertTrue(self._generate(globs, overlays=resolve, tuning=tuning))
        self.assertEqual(self._rendered(), ["agents/architect.md", "agents/go-coder.md"])
        tiered = (self.out / "agents" / "go-coder.md").read_text(encoding="utf-8")
        untiered = (self.out / "agents" / "architect.md").read_text(encoding="utf-8")
        # Selection changes which outputs are rendered and nothing about how:
        # the tier still owns its model scope, an output with no pin site still
        # takes family-wide text, and the banner still records both.
        # Anchored against the base line above the anchor, which is what makes
        # these say "verbatim, in place" rather than merely "present".
        self.assertIn("body shared text\nopus text\n", tiered)
        self.assertIn("body shared text\nfamily\n", untiered)
        self.assertEqual(banners.tuning_claim(tiered).seat, "high")
        self.assertEqual(banners.tuning_claim(tiered).member, "opus")
        self.assertEqual(banners.tuning_claim(untiered).seat, "none")
        self.assertEqual(banners.tuning_claim(untiered).member, "none")
        self.assertTrue(banners.body_untouched(tiered))
        for target, rendered in rendering.all_renders(
            _binding(self.CHUNKS), self.smap, overlays=resolve, globs=globs, tuning=tuning
        ):
            self.assertEqual(target.read_text(encoding="utf-8"), rendered, paths.rel(target))

    def test_the_banner_records_the_member_the_run_tuned_against(self):
        # Two renders of one template under two tier maps. The seat is the
        # template's own declaration and does not move; the member follows the
        # map that produced the render, which is what makes a definition's
        # tuning readable from the definition alone.
        entries = model_tuning.load_family(self.family).entries
        globs = {"agents": ["go-coder"]}
        target = self.out / "agents" / "go-coder.md"
        self._generate(globs, overlays=model_tuning.tier_resolver(entries, dict(model_tuning.DEFAULT_PIN_MAP)))
        default = banners.tuning_claim(target.read_text(encoding="utf-8"))
        retargeted = {**model_tuning.DEFAULT_PIN_MAP, "high": "haiku"}
        self._generate(
            globs,
            overlays=model_tuning.tier_resolver(entries, retargeted),
            tuning=_tuning(self.family, tier_map=retargeted, entries=entries),
        )
        moved = banners.tuning_claim(target.read_text(encoding="utf-8"))
        self.assertEqual((default.seat, default.member), ("high", "opus"))
        self.assertEqual((moved.seat, moved.member), ("high", "haiku"))
        # …and the overlay text followed it, so the claim is not decorative.
        self.assertIn("haiku text", target.read_text(encoding="utf-8"))


class TestSelectionCLI(unittest.TestCase):
    """The verbs and their flags as shipped, driven through `python3 -m gen_defs` itself:
    the required verb and root, surface implication, both-glob runs, the one
    surviving conflict error, the per-verb flags a verb does not declare, and
    the loud no-match."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "gen_defs", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=_REPO_ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(_REPO_ROOT)},
        )

    def _rendered(self):
        return sorted(path.relative_to(self.out).as_posix() for path in self.out.rglob("*.md"))

    def test_the_verb_is_required_and_every_verb_names_its_root(self):
        # No bare invocation and no implicit default mode; and there is no
        # checked-in tree for a root to default to. Exit 2 — an unusable
        # invocation, not a verdict about a tree — which is the distinction a
        # caller keys on.
        bare = self._run()
        self.assertEqual(bare.returncode, 2, bare.stderr)
        self.assertIn("the following arguments are required", bare.stderr)
        for verb in ("generate", "install"):
            done = self._run(verb)
            self.assertEqual(done.returncode, 2, f"{verb}: {done.stderr}")
            self.assertIn("the following arguments are required: ROOT", done.stderr, verb)

    def test_flag_abbreviation_is_off(self):
        # A prefix would keep a renamed flag alive as an abbreviation of the
        # spelling that replaced it. install-agents-file declares no `--` flag.
        for verb in ("generate", "install"):
            with self.subTest(verb=verb):
                done = self._run(verb, str(self.out), "--fam", "claude")
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertEqual(sorted(self.out.rglob("*")), [])

    def test_a_missing_output_root_is_refused_rather_than_created(self):
        absent = self.out / "not-there"
        done = self._run("generate", str(absent))
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertFalse(absent.exists())

    def test_a_refused_target_exits_1_and_is_left_unchanged(self):
        # 1 is the verdict "the run completed and the answer is no", distinct
        # from 2, a run that could not proceed at all.
        target = self.out / "agents" / "go-coder.md"
        target.parent.mkdir()
        target.write_text("hand-maintained\n", encoding="utf-8")
        done = self._run("generate", str(self.out), "--agent-glob", "go-coder")
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), "hand-maintained\n")

    def test_agent_glob_alone_excludes_the_commands_surface(self):
        done = self._run("generate", str(self.out), "--agent-glob", "*-coder*")
        self.assertEqual(done.returncode, 0, done.stderr)
        rendered = self._rendered()
        self.assertTrue(rendered)
        for name in rendered:
            self.assertTrue(fnmatch.fnmatchcase(name, "agents/*-coder*.md"), name)
        self.assertFalse((self.out / "commands").exists())

    def test_both_globs_filter_each_surface_and_report_the_accounting(self):
        done = self._run(
            "generate",
            str(self.out),
            "--agent-glob",
            "mad/participant-*",
            "--command-glob",
            "kb-*",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        rendered = self._rendered()
        agents = [name for name in rendered if name.startswith("agents/")]
        commands = [name for name in rendered if name.startswith("commands/")]
        # Each surface filtered by its own patterns, and both present.
        self.assertEqual(agents, ["agents/mad/participant-contract.md"])
        self.assertTrue(commands)
        for name in commands:
            self.assertTrue(Path(name).name.startswith("kb-"), name)
        self.assertRegex(done.stdout, r"agents: 1 of \d+ outputs selected by --agent-glob")
        self.assertRegex(done.stdout, r"commands: \d+ of \d+ outputs selected by --command-glob")

    def test_surfaces_is_subsumed_and_refused(self):
        # The one exclusion that survives as logic: both flags live on the one
        # selecting verb, so nothing structural separates them.
        done = self._run("generate", str(self.out), "--agent-glob", "*", "--surfaces", "agents")
        self.assertEqual(done.returncode, 2)
        self.assertIn("drop --surfaces", done.stderr)

    def test_install_cannot_be_narrowed_by_a_glob(self):
        # Not refused by a check inside the install path: `install` declares no
        # selection glob at all, so a partial install is unrepresentable.
        done = self._run("install", str(self.out), "--agent-glob", "*")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unrecognized arguments: --agent-glob", done.stderr)
        self.assertEqual(self._rendered(), [])

    def test_an_unknown_harness_is_refused_before_anything_is_written(self):
        for verb in ("generate", "install"):
            with self.subTest(verb=verb):
                done = self._run(verb, str(self.out), "--harness", "nope")
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn("unknown harness 'nope' — available: claude, opencode", done.stderr)
                self.assertEqual(self._rendered(), [])

    def test_install_cannot_be_narrowed_by_surfaces(self):
        done = self._run("install", str(self.out), "--surfaces", "agents")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unrecognized arguments: --surfaces", done.stderr)
        self.assertEqual(self._rendered(), [])

    def test_surfaces_still_narrows_generate(self):
        generated = self._run("generate", str(self.out), "--surfaces", "commands")
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.assertTrue(self._rendered())
        self.assertFalse((self.out / "agents").exists())

    def test_zero_match_is_a_hard_error_listing_the_surface(self):
        done = self._run("generate", str(self.out), "--agent-glob", "*-codr*")
        self.assertEqual(done.returncode, 2)
        self.assertIn("--agent-glob pattern '*-codr*' matches none of", done.stderr)
        self.assertIn("go-coder", done.stderr)
        self.assertEqual(self._rendered(), [])


class TestTuningCLI(unittest.TestCase):
    """The three tuning flags as shipped, driven through `python3 -m gen_defs` itself.

    Against an isolated COPY of the repo's templates, not the real tree: the
    member-scope route needs a family declaring member tables, neither shipped
    family does, and a fixture planted in the real templates/family/ would be
    reachable as real input by unrelated runs.
    """

    PROBE = (
        _tiers_toml({**model_tuning.DEFAULT_PIN_MAP, "lowest": "probe-member"})
        + '[family.ask-vs-stipulate]\ntext = "probe family text"\n'
        '[family.ask-vs-stipulate.models.probe-member]\ntext = "probe member text"\n'
        '[family.ask-vs-stipulate.models.opus]\ntext = "probe opus text"\n'
    )
    # applied-mathematician authors ask-vs-stipulate and carries a pin site;
    # gap-aversion is authored in kb-claim-scorer.tmpl.md.
    SELECT = ("--agent-glob", "applied-mathematician|mad/participant-contract")

    @classmethod
    def setUpClass(cls):
        cls._class_tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls._class_tmp.name) / "repo"
        cls.repo.mkdir()
        shutil.copytree(
            paths.TEMPLATES_DIR,
            cls.repo / "templates",
            ignore=shutil.ignore_patterns("tests", "__pycache__"),
        )
        shutil.copytree(_REPO_ROOT / "gen_defs", cls.repo / "gen_defs", ignore=shutil.ignore_patterns("__pycache__"))
        cls.family_dir = cls.repo / "templates" / "family"
        (cls.family_dir / "probe.toml").write_text(cls.PROBE, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._class_tmp.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name)

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "gen_defs", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=self.repo,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(self.repo)},
        )

    def _generate(self, *tuning_args):
        return self._run("generate", str(self.out), *self.SELECT, *tuning_args)

    def _bodies(self):
        return {
            path.relative_to(self.out).as_posix(): path.read_text(encoding="utf-8") for path in self.out.rglob("*.md")
        }

    def _claim(self, name="agents/applied-mathematician.md"):
        return banners.tuning_claim(self._bodies()[name])

    def test_the_default_run_needs_no_flag_at_all(self):
        done = self._generate()
        self.assertEqual(done.returncode, 0, done.stderr)
        claim = self._claim()
        self.assertEqual(claim.family, "templates/family/claude.toml")
        self.assertEqual(claim.tier, model_tuning.map_spec(model_tuning.DEFAULT_PIN_MAP))
        self.assertEqual(claim.pin, model_tuning.map_spec(model_tuning.DEFAULT_PIN_MAP))

    def test_family_name_loads_that_family(self):
        done = self._generate("--family", "probe")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._claim().family, "templates/family/probe.toml")
        self.assertIn("probe opus text", self._bodies()["agents/applied-mathematician.md"])

    def test_path_shaped_family_loads_the_file(self):
        done = self._generate("--family", "templates/family/probe.toml")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._claim().family, "templates/family/probe.toml")

    def test_a_model_name_as_a_family_is_refused(self):
        done = self._generate("--family", "opus")
        self.assertEqual(done.returncode, 2)
        self.assertIn("Bare model names are not family names", done.stderr)
        self.assertIn("available: claude, gemma-4, probe", done.stderr)
        self.assertEqual(self._bodies(), {})

    def test_an_unknown_family_is_refused(self):
        done = self._generate("--family", "ghost")
        self.assertEqual(done.returncode, 2)
        self.assertIn("--family 'ghost' names no family file", done.stderr)
        self.assertEqual(self._bodies(), {})

    def test_the_tier_map_retargets_a_tier_without_touching_its_pin(self):
        # The whole point of two maps: what a definition is TUNED for and what
        # it DISPATCHES on move independently.
        done = self._generate("--family", "probe", "--model-tier-map", "highest=opus")
        self.assertEqual(done.returncode, 0, done.stderr)
        claim = self._claim()
        self.assertIn("highest=opus", claim.tier)
        self.assertIn("highest=fable", claim.pin)

    def test_the_pin_map_changes_rendered_pins_and_says_so(self):
        done = self._generate("--model-pin-map", "all=haiku")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self._claim().pin, ",".join(f"{tier}=haiku" for tier in model_tuning.TIERS))

    def test_a_bad_map_key_is_a_hard_error_before_anything_is_written(self):
        for flag in ("--model-tier-map", "--model-pin-map"):
            with self.subTest(flag=flag):
                done = self._generate(flag, "mid=sonnet")
                self.assertEqual(done.returncode, 2)
                self.assertIn(f"{flag}: 'mid=sonnet' names no tier", done.stderr)
                self.assertEqual(self._bodies(), {})

    def test_a_family_missing_its_tiers_table_refuses_to_render(self):
        broken = self.family_dir / "broken.toml"
        broken.write_text('[family.gap-aversion]\ntext = "x"\n', encoding="utf-8")
        self.addCleanup(broken.unlink)
        done = self._generate("--family", "broken")
        self.assertEqual(done.returncode, 2)
        self.assertIn("no [tiers] table", done.stderr)
        self.assertEqual(self._bodies(), {})

    def test_an_unreachable_member_table_refuses_to_render(self):
        # Ripple 1: a mis-spelled member would otherwise render as an ordinary
        # Stock tier, silently.
        broken = self.family_dir / "typo.toml"
        broken.write_text(
            _tiers_toml() + '[family.gap-aversion.models.oppus]\ntext = "x"\n',
            encoding="utf-8",
        )
        self.addCleanup(broken.unlink)
        done = self._generate("--family", "typo")
        self.assertEqual(done.returncode, 2)
        self.assertIn("no tier reaches: oppus", done.stderr)
        # …and the tier map is the union, so mapping a tier to it fixes the run.
        fixed = self._generate("--family", "typo", "--model-tier-map", "lowest=oppus")
        self.assertEqual(fixed.returncode, 0, fixed.stderr)

    def test_a_family_naming_an_anchor_nothing_authors_refuses_to_render(self):
        stray = self.family_dir / "stray.toml"
        stray.write_text(
            _tiers_toml({**model_tuning.DEFAULT_PIN_MAP, "lowest": "probe-member"})
            + '[family.no-such-anchor]\ntext = "x"\n',
            encoding="utf-8",
        )
        self.addCleanup(stray.unlink)
        done = self._generate("--family", "stray")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("no-such-anchor", done.stderr)
        self.assertEqual(self._bodies(), {})

    def test_an_install_renders_under_the_tuning_it_was_given(self):
        # The install route's own wiring of the triple and the tier resolver,
        # through the CLI: the definitions an install delivers carry the
        # family's member overrides, and the claim a generate under the same
        # flags writes.
        for source, _ in product.SHIPPED_PACKAGES:
            planted = self.repo / source / "probe_tool.py"
            planted.parent.mkdir(exist_ok=True)
            planted.write_text('"""a probe tool."""\n', encoding="utf-8")
        done = self._run("install", str(self.out), "--family", "probe")
        self.assertEqual(done.returncode, 0, done.stderr)
        installed = self._bodies()["agents/applied-mathematician.md"]
        self.assertIn("probe opus text", installed)
        with tempfile.TemporaryDirectory() as generated:
            self.assertEqual(self._run("generate", generated, *self.SELECT, "--family", "probe").returncode, 0)
            expected = (Path(generated) / "agents" / "applied-mathematician.md").read_text(encoding="utf-8")
        self.assertEqual(banners.tuning_claim(installed), banners.tuning_claim(expected))

    def test_a_tuned_render_reproduces_itself_and_a_retuned_one_does_not(self):
        # Two independently produced renders of the same templates: under the
        # identical triple they are byte-equal, and under another family they
        # differ and each banner names the family that produced it. That is
        # what makes a set's tuning answerable from the set itself.
        self.assertEqual(self._generate("--family", "probe").returncode, 0)
        probe = self._bodies()
        self.assertEqual(self._claim().family, "templates/family/probe.toml")

        self.assertEqual(self._generate("--family", "probe").returncode, 0)
        self.assertEqual(self._bodies(), probe)

        self.assertEqual(self._generate().returncode, 0)
        self.assertNotEqual(self._bodies(), probe)
        self.assertEqual(self._claim().family, "templates/family/claude.toml")

    def test_the_run_echoes_its_triple_and_neither_notice_fires(self):
        stock = self._generate()
        [echo] = [line for line in stock.stdout.splitlines() if line.startswith("tuning:")]
        self.assertIn("templates/family/claude.toml", echo)
        # Both maps, each serialized whole.
        self.assertEqual(echo.count(model_tuning.map_spec(model_tuning.DEFAULT_PIN_MAP)), 2)
        self.assertRegex(echo, r"\bharness\W+claude\b")
        # Every tier of the shipped claude family is stock and the two maps
        # agree, so the triple is the whole of what a default run says. The
        # stock state is what the banner's stock= field is for; the run's
        # report does not mention it at all.
        self.assertEqual([line for line in stock.stdout.splitlines() if line.startswith("notice:")], [])
        self.assertNotIn("stock", stock.stdout)

    def test_the_divergence_notice_is_a_notice_and_gates_nothing(self):
        done = self._generate("--model-tier-map", "medium=haiku")
        self.assertEqual(done.returncode, 0, done.stderr)
        # The tier, the member it is tuned for, and the pin it dispatches on.
        [notice] = [line for line in done.stdout.splitlines() if line.startswith("notice:")]
        for name in ("medium", "haiku", "sonnet"):
            self.assertIn(name, notice)
        # It rendered: a notice never refuses.
        self.assertTrue(self._bodies())

    def test_the_floor_rung_prints_no_notice_at_all(self):
        # The floor's flags. Two maps collapsed onto one value cannot
        # diverge, and haiku is a member the claude family declares nothing
        # for, so the rung renders stock at every tier and stays silent.
        done = self._generate("--model-tier-map", "all=haiku", "--model-pin-map", "all=haiku")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([line for line in done.stdout.splitlines() if line.startswith("notice:")], [])
        self.assertEqual(rendering.frontmatter_pin(self._bodies()["agents/applied-mathematician.md"]), "haiku")

    def test_the_divergence_notice_is_confined_to_the_claude_family(self):
        # For any other family the two maps diverge at every tier by
        # construction — members against claude aliases — so a notice there
        # would fire five times a run carrying no information.
        done = self._generate("--family", "gemma-4")
        self.assertEqual(done.returncode, 0, done.stderr)
        # The triple pins that the reporting block ran at all, so the absent
        # notice is a decision and not an unreached print.
        self.assertIn("tuning: family=templates/family/gemma-4.toml", done.stdout)
        self.assertEqual([line for line in done.stdout.splitlines() if line.startswith("notice:")], [])

    def test_the_tuned_notice_names_the_override_bearing_tiers_and_no_others(self):
        # probe.toml declares member tables for opus and probe-member alone,
        # and its [tiers] table staffs high and lowest with those two; the
        # other three tiers map to members it says nothing about. The tier
        # list parsed out of the line is the "and no others" half — a fourth
        # tier or a stray member reaching it fails here.
        done = self._generate("--family", "probe")
        self.assertEqual(done.returncode, 0, done.stderr)
        [notice] = [line for line in done.stdout.splitlines() if line.startswith("notice:")]
        self.assertEqual(re.findall(r"\b([a-z]+) \(([^)]+)\)", notice), [("high", "opus"), ("lowest", "probe-member")])
        self.assertIn("templates/family/probe.toml", notice)


class TestTunedBanner(unittest.TestCase):
    TMPL = paths.TEMPLATES_DIR / "agents" / "x.tmpl.md"
    FAMILY = paths.TEMPLATES_DIR / "family" / "fam.toml"

    def _stamped(self, *, seat=None, tuning=None):
        body = "name: x\n---\nbody\n"
        tuning = _tuning(self.FAMILY) if tuning is None else tuning
        stamp = banners.banner(self.TMPL, body_hash=banners.sha256_text(body), tuning=tuning, seat=seat)
        return "---\n" + stamp + "\n" + body

    def test_the_generated_line_carries_only_the_template_and_the_chunks(self):
        # The tuning moved onto its own line: the origin clause is one claim.
        stamp = self._stamped()
        self.assertIn(
            "# !GENERATED! from templates/agents/x.tmpl.md and templates/shared-chunks.toml — edit those.",
            stamp,
        )

    def test_the_block_is_five_lines_with_tuning_above_the_hash(self):
        # BODY_HASH_CLAIM matches the hash line together with the `#` closing
        # the block, so anything added has to go above it.
        lines = self._stamped().split("\n")
        self.assertEqual(lines[0], "---")
        self.assertEqual(lines[1], "#")
        self.assertTrue(lines[2].startswith("# !GENERATED! "))
        self.assertTrue(lines[3].startswith("# !TUNING! "))
        self.assertTrue(lines[4].startswith("# !BODY-SHA256! "))
        self.assertEqual(lines[5], "#")

    def test_claims_round_trip(self):
        text = self._stamped(seat="high")
        self.assertEqual(banners.banner_claim(text), "templates/agents/x.tmpl.md")
        self.assertEqual(
            banners.tuning_claim(text),
            banners.TuningClaim(
                family="templates/family/fam.toml",
                seat="high",
                member="opus",
                tier=model_tuning.map_spec(model_tuning.DEFAULT_PIN_MAP),
                pin=model_tuning.map_spec(model_tuning.DEFAULT_PIN_MAP),
                stock=",".join(model_tuning.TIERS),
                harness="claude",
            ),
        )
        self.assertTrue(banners.body_untouched(text))

    def test_the_claim_records_the_harness_rendered_under(self):
        tuning = dataclasses.replace(_tuning(self.FAMILY), harness="opencode")
        self.assertEqual(banners.tuning_claim(self._stamped(tuning=tuning)).harness, "opencode")

    def test_a_banner_written_before_the_harness_field_still_parses(self):
        text = self._stamped(seat="high")
        older = text.replace(" harness=claude\n", "\n")
        self.assertNotEqual(older, text)
        claim = banners.tuning_claim(older)
        self.assertEqual((claim.seat, claim.member, claim.harness), ("high", "opus", None))

    def test_an_output_with_no_pin_site_records_none_for_both(self):
        claim = banners.tuning_claim(self._stamped())
        self.assertEqual((claim.seat, claim.member), ("none", "none"))

    def test_the_member_is_recorded_so_the_tier_never_has_to_be_inverted(self):
        # An all= pin map collapses every tier onto one pin, so neither the
        # seat nor the member can be recovered from it: both are recorded.
        # The tier map names a different member at each seat, and neither is
        # the pin, so a member read off the wrong map shows.
        pin_map = {tier: "haiku" for tier in model_tuning.TIERS}
        tier_map = {**model_tuning.DEFAULT_PIN_MAP, "low": "member-low", "lowest": "member-lowest"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = root / "templates" / "agents"
            agents.mkdir(parents=True)
            for seat in ("low", "lowest"):
                (agents / f"at-{seat}.tmpl.md").write_text(
                    f"---\nname: @!arg.name!@\nmodel: @!dyn.tier-{seat}!@\n---\nbody\n", encoding="utf-8"
                )
            out = root / "out"
            out.mkdir()
            _quiet(
                generation.generate,
                _binding({}, pin_map),
                discovery.surface_map(templates_root=root / "templates", output_root=out),
                overlays=None,
                tuning=_tuning(self.FAMILY, tier_map=tier_map, pin_map=pin_map),
            )
            claims = [
                banners.tuning_claim((out / "agents" / f"at-{seat}.md").read_text(encoding="utf-8"))
                for seat in ("low", "lowest")
            ]
        self.assertEqual([claim.seat for claim in claims], ["low", "lowest"])
        for claim in claims:
            self.assertEqual(claim.member, tier_map[claim.seat])

    def test_stock_none_when_every_tier_is_tuned(self):
        entries = {"fam.gap": {"models": {member: {"text": "t"} for member in model_tuning.DEFAULT_PIN_MAP.values()}}}
        claim = banners.tuning_claim(self._stamped(tuning=_tuning(self.FAMILY, entries=entries)))
        self.assertEqual(claim.stock, "none")

    def test_a_file_with_no_tuning_line_has_no_claim_to_read(self):
        self.assertIsNone(banners.tuning_claim("---\nname: x\n---\nbody\n"))


class TestGenerateRoundTrip(unittest.TestCase):
    """End-to-end over a scratch template tree: a family with no entry fills
    nothing, a family with one fills the anchor, and the banner records which
    family produced the bytes on disk."""

    CHUNKS = {"shared": {"text": "shared text"}}
    BODY = "---\nname: @!arg.name!@\n---\n" "body @!shared!@\n@!fam.probe!@\ntail\n"
    ENTRIES = {"fam.probe": {"text": "family fill", "models": {"sonnet": {"text": "model fill"}}}}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        (self.tsrc / "agents").mkdir(parents=True)
        (self.tsrc / "agents" / "probe.tmpl.md").write_text(self.BODY, encoding="utf-8")
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.family = root / "family.toml"
        self.family.write_text(
            _tiers_toml() + '[family.probe]\ntext = "family fill"\n[family.probe.models.sonnet]\ntext = "model fill"\n',
            encoding="utf-8",
        )
        self.other = root / "other.toml"
        self.other.write_text(_tiers_toml(), encoding="utf-8")

    def _target(self):
        return self.out / "agents" / "probe.md"

    def _generate(self, **kwargs):
        kwargs.setdefault("overlays", None)
        kwargs.setdefault("tuning", _tuning(self.family))
        return _quiet(generation.generate, _binding(self.CHUNKS), self.smap, **kwargs)

    def test_two_families_render_two_files_each_naming_its_own_family(self):
        # An output with no pin site takes family-wide text; retarget nothing.
        overlays = model_tuning.tier_resolver(self.ENTRIES, dict(model_tuning.DEFAULT_PIN_MAP))
        self.assertTrue(self._generate(overlays=overlays, tuning=_tuning(self.family, entries=self.ENTRIES)))
        tuned = self._target().read_text(encoding="utf-8")
        self.assertIn("body shared text\nfamily fill\ntail", tuned)
        self.assertNotIn("model fill", tuned)  # one text per anchor, and no tier here
        claim = banners.tuning_claim(tuned)
        self.assertEqual(claim.family, paths.rel(self.family))
        self.assertEqual(claim.stock, "highest,high,low,lowest")

        # The same templates under a family that fills nothing: different
        # bytes, and a banner naming the file that produced them.
        self.assertTrue(self._generate(tuning=_tuning(self.other)))
        untuned = self._target().read_text(encoding="utf-8")
        self.assertNotEqual(untuned, tuned)
        self.assertNotIn("family fill", untuned)
        self.assertEqual(banners.tuning_claim(untuned).family, paths.rel(self.other))

    def test_an_agents_template_without_frontmatter_fails_at_generation(self):
        # A definition that would not extract fails where it is built, before
        # anything is written.
        (self.tsrc / "agents" / "bare.tmpl.md").write_text("No frontmatter here.\n", encoding="utf-8")
        with self.assertRaisesRegex(errors.InputError, "bare.tmpl.md"):
            self._generate()
        self.assertEqual(sorted(self.out.rglob("*")), [])


class TestRefactorBlastRadius(unittest.TestCase):
    """The question a chunk extraction has to answer: which definitions did it
    move, and how. Two render sets — the templates before the extraction and
    the templates after — compared output by output, with the expected answer
    written out rather than taken from a verdict. A refactor meant to touch
    two definitions that quietly reflows a third is the failure this catches,
    so the assertions are about WHICH outputs moved and WHAT changed in them.
    """

    OLD_PHRASE = "Recieve the input and process it."
    NEW_PHRASE = "Receive the input and process it."
    ALPHA = f"---\nname: @!arg.name!@\n---\nAlpha body. {OLD_PHRASE}\n"
    BETA = f"---\nname: @!arg.name!@\n---\nBeta body. {OLD_PHRASE}\n"
    GAMMA = "---\nname: @!arg.name!@\n---\nGamma body, unrelated text entirely.\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        (self.tsrc / "agents").mkdir(parents=True)
        for name, body in (("alpha", self.ALPHA), ("beta", self.BETA), ("gamma", self.GAMMA)):
            (self.tsrc / "agents" / f"{name}.tmpl.md").write_text(body, encoding="utf-8")
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.family = root / "fam.toml"
        self.family.write_text(_tiers_toml(), encoding="utf-8")
        self.tuning = _tuning(self.family)
        # The before side: alpha and beta still carry the duplicated (typo'd)
        # phrase inline. Held in memory — nothing needs to be on disk for two
        # render sets to be compared.
        self.before = self._render(_binding({}))

    def _render(self, binding):
        """{output key: rendered text} for the templates as they stand now."""
        return {
            target.relative_to(self.out).as_posix(): text
            for target, text in rendering.all_renders(binding, self.smap, overlays=None, tuning=self.tuning)
        }

    def _refactor(self):
        """Lift the duplicated phrase into a chunk, correcting its typo once,
        and reference it from the two templates that carried it. gamma, which
        never had the phrase, is left untouched — the intended shape of a
        scoped refactor."""
        (self.tsrc / "agents" / "alpha.tmpl.md").write_text(
            "---\nname: @!arg.name!@\n---\nAlpha body. @!shared-receive!@\n", encoding="utf-8"
        )
        (self.tsrc / "agents" / "beta.tmpl.md").write_text(
            "---\nname: @!arg.name!@\n---\nBeta body. @!shared-receive!@\n", encoding="utf-8"
        )
        return _binding({"shared-receive": {"text": self.NEW_PHRASE}})

    def _moved(self):
        after = self._render(self._refactor())
        self.assertEqual(set(after), set(self.before))
        return after, {key for key, text in after.items() if text != self.before[key]}

    def test_exactly_the_two_refactored_outputs_move_and_the_third_is_byte_identical(self):
        after, moved = self._moved()
        self.assertEqual(moved, {"agents/alpha.md", "agents/beta.md"})
        for key, lead in (("agents/alpha.md", "Alpha body."), ("agents/beta.md", "Beta body.")):
            with self.subTest(output=key):
                self.assertIn(f"{lead} {self.OLD_PHRASE}", self.before[key])
                self.assertIn(f"{lead} {self.NEW_PHRASE}", after[key])
                self.assertNotIn(self.OLD_PHRASE, after[key])
        # The negative control, and the reason the whole render is compared
        # rather than the two templates the refactor names: a chunk landing in
        # a third definition would show up here as a changed gamma.
        self.assertEqual(after["agents/gamma.md"], self.before["agents/gamma.md"])


class TestMixedTierRender(unittest.TestCase):
    """A mixed render over a scratch tree — one tiered agent, one command with
    no pin site, one family file — resolving each output against its own tier."""

    CHUNKS = {}
    TIERED = "---\nname: @!arg.name!@\nmodel: @!dyn.tier-high!@\n---\n@!fam.probe!@\n"
    # A frontmatter-less command: the surface that carries no pin site today.
    NO_PIN_SITE = "@!fam.probe!@\n"
    FAMILY = (
        '[family.probe]\ntext = "family"\n'
        '[family.probe.models.opus]\ntext = "opus text"\n'
        '[family.probe.models.haiku]\ntext = "haiku text"\n'
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        (self.tsrc / "agents").mkdir(parents=True)
        (self.tsrc / "commands").mkdir(parents=True)
        (self.tsrc / "agents" / "tiered.tmpl.md").write_text(self.TIERED, encoding="utf-8")
        (self.tsrc / "commands" / "plain.tmpl.md").write_text(self.NO_PIN_SITE, encoding="utf-8")
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.family = root / "fam.toml"
        self.family.write_text(_tiers_toml() + self.FAMILY, encoding="utf-8")
        self.entries = model_tuning.load_family(self.family).entries

    def _generate(self, *, tier_map=None):
        tier_map = dict(tier_map or model_tuning.DEFAULT_PIN_MAP)
        resolve = model_tuning.tier_resolver(self.entries, tier_map)
        tuning = _tuning(self.family, tier_map=tier_map, entries=self.entries)
        ok = _quiet(generation.generate, _binding(self.CHUNKS), self.smap, overlays=resolve, tuning=tuning)
        return ok, resolve, tuning

    def _bodies(self):
        return (
            banners.banner_body((self.out / "agents" / "tiered.md").read_text(encoding="utf-8")),
            banners.banner_body((self.out / "commands" / "plain.md").read_text(encoding="utf-8")),
        )

    def test_each_output_resolves_against_its_own_tier(self):
        ok, _, _ = self._generate()
        self.assertTrue(ok)
        tiered, plain = self._bodies()
        self.assertIn("\nopus text\n", tiered)
        self.assertNotIn("haiku text", tiered)
        # An output with no pin site still takes the family-wide text — only
        # MEMBER-scoped entries require a tier.
        self.assertIn("\nfamily\n", plain)

    def test_the_rendered_pin_is_the_pin_map_value_not_the_member(self):
        self._generate(tier_map={**model_tuning.DEFAULT_PIN_MAP, "high": "haiku"})
        text = (self.out / "agents" / "tiered.md").read_text(encoding="utf-8")
        self.assertEqual(rendering.frontmatter_pin(text), "opus")
        self.assertIn("\nhaiku text\n", text)

    def test_the_mixed_render_is_deterministic_across_runs(self):
        # What a "round trip" is worth asserting for: the same templates under
        # the same triple produce the same bytes, on a tree where the two
        # surfaces resolve differently (one output has a tier, the other has
        # no pin site at all). A per-run value anywhere in the banner, or an
        # ordering that depended on iteration, breaks here.
        self._generate()
        first = self._bodies()
        self._generate()
        self.assertEqual(self._bodies(), first)

    def test_a_family_with_no_entries_renders_byte_identically_to_anchor_free(self):
        # SPEC's additive-only guarantee at render level: an unfilled anchor
        # leaves not a trace, so the bare render must equal — byte for byte —
        # the render of the same templates with the anchors deleted outright.
        bare = self.family.with_name("bare.toml")
        bare.write_text(_tiers_toml(), encoding="utf-8")
        self.assertTrue(
            _quiet(
                generation.generate,
                _binding(self.CHUNKS),
                self.smap,
                overlays=model_tuning.tier_resolver({}, dict(model_tuning.DEFAULT_PIN_MAP)),
                tuning=_tuning(bare),
            )
        )
        bare_bodies = self._bodies()

        marker = "@!fam.probe!@"
        (self.tsrc / "agents" / "tiered.tmpl.md").write_text(self.TIERED.replace(marker, ""), encoding="utf-8")
        (self.tsrc / "commands" / "plain.tmpl.md").write_text(self.NO_PIN_SITE.replace(marker, ""), encoding="utf-8")
        _quiet(generation.generate, _binding(self.CHUNKS), self.smap, overlays=None, tuning=_tuning(bare))
        self.assertEqual(bare_bodies, self._bodies())


class TestNestedTemplateMirroring(unittest.TestCase):
    """Recursive discovery and path mirroring: a template's relative subpath
    within its surface tree is its output's relative subpath within the
    surface, and every other mechanism applies unchanged at that nested path.
    """

    CHUNKS = {"shared": {"text": "shared text"}}
    BODY = "---\nname: @!arg.name!@\n---\nbody @!shared!@\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        self.agent_templates = self.tsrc / "agents"
        self.nested_template = self.agent_templates / "mad" / "participant-contract.tmpl.md"
        self.nested_template.parent.mkdir(parents=True)
        for template in (
            self.agent_templates / "flat.tmpl.md",
            self.nested_template,
        ):
            template.write_text(self.BODY, encoding="utf-8")
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)

    TUNING = _tuning(paths.FAMILY_DIR / "claude.toml")

    def _generate(self):
        return _quiet(generation.generate, _binding(self.CHUNKS), self.smap, overlays=None, tuning=self.TUNING)

    def test_nested_template_renders_to_mirrored_path(self):
        # The mirrored subdirectory does not exist beforehand — generation
        # creates it, since placement is declared by the template tree.
        self.assertFalse((self.out / "agents" / "mad").exists())
        self.assertTrue(self._generate())
        nested = self.out / "agents" / "mad" / "participant-contract.md"
        text = nested.read_text(encoding="utf-8")
        self.assertIn("name: participant-contract\n", text)
        self.assertIn("body shared text\n", text)
        self.assertTrue(banners.banner_claim(text).endswith("agents/mad/participant-contract.tmpl.md"))

    def test_top_level_template_unaffected(self):
        self.assertTrue(self._generate())
        flat = self.out / "agents" / "flat.md"
        self.assertIn("name: flat\n", flat.read_text(encoding="utf-8"))
        self.assertFalse((self.out / "agents" / "mad" / "flat.md").exists())

    def test_the_nested_output_is_provably_the_tools_own_and_reproduces(self):
        # Every mechanism applies unchanged at a nested path, and these are the
        # two that a mirrored subdirectory could plausibly break: the banner's
        # hash covers the body it was stamped over, and a second render of the
        # same templates lands the same bytes.
        self._generate()
        nested = self.out / "agents" / "mad" / "participant-contract.md"
        first = nested.read_text(encoding="utf-8")
        self.assertTrue(banners.body_untouched(first))
        self._generate()
        self.assertEqual(nested.read_text(encoding="utf-8"), first)


class TestBodyHashBanner(unittest.TestCase):
    """The banner's !BODY-SHA256! line: what it covers, and what it proves."""

    CHUNKS = {}
    TMPL = paths.TEMPLATES_DIR / "agents" / "x.tmpl.md"

    TUNING = _tuning(paths.FAMILY_DIR / "claude.toml")

    def _stamped(self, body):
        stamp = banners.banner(self.TMPL, body_hash=banners.sha256_text(body), tuning=self.TUNING)
        return "---\n" + stamp + "\n" + body

    def test_hash_covers_everything_after_the_banner(self):
        body = "name: x\n---\nthe prompt body\n"
        self.assertEqual(banners.banner_body(self._stamped(body)), body)

    def test_untouched_output_is_provable(self):
        self.assertTrue(banners.body_untouched(self._stamped("name: x\n---\nb\n")))

    def test_edited_body_breaks_the_proof(self):
        text = self._stamped("name: x\n---\nb\n") + "appended by hand\n"
        self.assertFalse(banners.body_untouched(text))

    def test_pre_hash_banner_proves_nothing(self):
        old = (
            "---\n#\n# !GENERATED! from templates/agents/x.tmpl.md and "
            "templates/shared-chunks.toml — edit those. DO NOT HAND EDIT "
            "THIS FILE.\n#\nname: x\n---\nb\n"
        )
        self.assertIsNotNone(banners.banner_claim(old))  # still a banner
        self.assertIsNone(banners.banner_body(old))
        self.assertFalse(banners.body_untouched(old))

    @classmethod
    def setUpClass(cls):
        # The whole real set, rendered once in memory under the shipped default
        # triple and kept per template, so each output can be held to the
        # template that actually produced it. Nothing is written under the root
        # named here.
        cls.binding = _binding(chunks.load_chunks())
        cls.real = [
            (template, target, text)
            for surface, template, out_dir in discovery.template_targets(discovery.surface_map(paths.REPO_ROOT))
            for target, text in rendering.render_template(
                template, cls.binding, out_dir, surface=surface, overlays=None, tuning=cls.TUNING
            )
        ]

    def test_every_real_render_carries_a_true_hash_no_sentinel_and_claims_its_own_template(self):
        self.assertTrue(self.real)
        for template, target, text in self.real:
            with self.subTest(output=paths.rel(target)):
                self.assertTrue(banners.body_untouched(text))
                # The discovery pass's binding must never reach a written file.
                self.assertNotIn(model_tuning.TIER_SENTINEL, text)
                self.assertEqual(banners.banner_claim(text), paths.rel(template))

    def test_a_frontmatter_less_command_keeps_its_first_line_first_in_the_body(self):
        # Claude Code lists such a command by its first body line, so the
        # banner's frontmatter block goes above it and never displaces it.
        routes = rendering.routing_table(self.binding.chunks, self.binding.real, None, self.binding.harness)
        bare = [
            (template, text)
            for template, _, text in self.real
            if template.is_relative_to(paths.TEMPLATES_DIR / "commands")
            and not template.read_text(encoding="utf-8").startswith(("---", "+++"))
        ]
        self.assertTrue(bare)
        for template, text in bare:
            with self.subTest(template=paths.rel(template)):
                first = template.read_text(encoding="utf-8").split("\n", 1)[0]
                front = banners.frontmatter_of(text)
                self.assertIsNotNone(front)
                body = text[len("---\n" + front + "\n---\n") :]
                self.assertEqual(body.split("\n", 1)[0], markers.expand(first, routes, args={}).text)

    def test_nothing_under_agents_mad_carries_a_dispatch_key(self):
        mad = [(target, text) for _, target, text in self.real if paths.rel(target).startswith("agents/mad/")]
        self.assertTrue(mad)
        for target, text in mad:
            with self.subTest(output=paths.rel(target)):
                front = banners.frontmatter_of(text)
                self.assertIsNotNone(front)
                self.assertEqual(re.findall(r"^(?:name|description|model):", front, re.MULTILINE), [])

    def test_line_endings_are_translated_so_there_is_one_reading(self):
        # Generation reads its targets through read_text, whose universal
        # newlines hand a CRLF target here already translated; install reads
        # raw bytes and hands the CRLF through. Two answers to one question is
        # what made a tree nobody edited unprovable to one caller and provable
        # to the other.
        text = self._stamped("name: x\n---\nb\n")
        self.assertTrue(banners.body_untouched(text.replace("\n", "\r\n")))
        self.assertTrue(banners.body_untouched(text.replace("\n", "\r")))
        # Translating is not forgiving: an edit inside the widened file is
        # still an edit.
        self.assertFalse(banners.body_untouched(text.replace("\n", "\r\n") + "by hand\r\n"))


class TestWriteSafetyBackupBranches(unittest.TestCase):
    """Regenerating over provably-untouched output writes no backup;
    regenerating over hand-edited bannered content still does."""

    CHUNKS = {"shared": {"text": "shared text"}}
    BODY = "---\nname: @!arg.name!@\n---\nbody @!shared!@\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        (self.tsrc / "agents").mkdir(parents=True)
        self.template = self.tsrc / "agents" / "probe.tmpl.md"
        self.template.write_text(self.BODY, encoding="utf-8")
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.target = self.out / "agents" / "probe.md"

    def _generate(self, chunks=None):
        return _quiet(
            generation.generate,
            _binding(self.CHUNKS if chunks is None else chunks),
            self.smap,
            overlays=None,
            tuning=_tuning(paths.FAMILY_DIR / "claude.toml"),
        )

    def _backups(self):
        return sorted(p.name for p in (self.out / "agents").glob("*.bak"))

    def test_untouched_target_is_overwritten_without_a_backup(self):
        self._generate()
        self.assertTrue(banners.body_untouched(self.target.read_text("utf-8")))
        self._generate({"shared": {"text": "changed text"}})
        self.assertIn("changed text", self.target.read_text(encoding="utf-8"))
        self.assertEqual(self._backups(), [])

    def test_hand_edited_target_is_backed_up_before_overwrite(self):
        self._generate()
        edited = self.target.read_text(encoding="utf-8") + "hand-added line\n"
        self.target.write_text(edited, encoding="utf-8")
        self._generate({"shared": {"text": "changed text"}})
        self.assertEqual(self._backups(), ["probe.md.00.bak"])
        backup = (self.out / "agents" / "probe.md.00.bak").read_text(encoding="utf-8")
        self.assertEqual(backup, edited)

    def test_identical_render_still_writes_nothing(self):
        self._generate()
        stamp = self.target.stat().st_mtime_ns
        self._generate()
        self.assertEqual(self.target.stat().st_mtime_ns, stamp)
        self.assertEqual(self._backups(), [])

    def test_a_target_without_the_generated_banner_is_refused_and_left_unwritten(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text("hand-maintained\n", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = generation.generate(
                _binding(self.CHUNKS), self.smap, overlays=None, tuning=_tuning(paths.FAMILY_DIR / "claude.toml")
            )
        self.assertFalse(ok)
        self.assertIn("REFUSED", buf.getvalue())
        self.assertEqual(self.target.read_text(encoding="utf-8"), "hand-maintained\n")

    def _hand_edit(self):
        self.target.write_text(self.target.read_text(encoding="utf-8") + "hand-added line\n", encoding="utf-8")

    def test_backup_serials_count_up_from_the_highest_and_are_never_reused(self):
        self._generate()
        for expected in (["probe.md.00.bak"], ["probe.md.00.bak", "probe.md.01.bak"]):
            self._hand_edit()
            self._generate()
            self.assertEqual(self._backups(), expected)
        # A gap is never filled: the next serial is the highest plus one.
        (self.out / "agents" / "probe.md.01.bak").rename(self.out / "agents" / "probe.md.02.bak")
        self._hand_edit()
        self._generate()
        self.assertEqual(self._backups(), ["probe.md.00.bak", "probe.md.02.bak", "probe.md.03.bak"])

    def test_both_overwrite_rows_keep_the_targets_inode_and_mode(self):
        self._generate()
        self.target.chmod(0o640)
        identity = (self.target.stat().st_ino, 0o640)
        # Hash-matching row: overwritten in place, no backup.
        self._generate({"shared": {"text": "changed text"}})
        self.assertIn("changed text", self.target.read_text(encoding="utf-8"))
        self.assertEqual((self.target.stat().st_ino, stat.S_IMODE(self.target.stat().st_mode)), identity)
        # Hand-edited row: backed up, then overwritten in place.
        self._hand_edit()
        self._generate()
        self.assertEqual(self._backups(), ["probe.md.00.bak"])
        self.assertNotIn("hand-added line", self.target.read_text(encoding="utf-8"))
        self.assertEqual((self.target.stat().st_ino, stat.S_IMODE(self.target.stat().st_mode)), identity)

    def test_a_banner_without_a_hash_line_is_backed_up_before_overwrite(self):
        prior = (
            "---\n#\n# !GENERATED! from templates/agents/probe.tmpl.md and templates/shared-chunks.toml"
            " — edit those. DO NOT HAND EDIT THIS FILE.\n#\nname: probe\n---\nolder body\n"
        )
        self.target.parent.mkdir(parents=True)
        self.target.write_text(prior, encoding="utf-8")
        self.assertTrue(self._generate())
        self.assertEqual(self._backups(), ["probe.md.00.bak"])
        self.assertEqual((self.out / "agents" / "probe.md.00.bak").read_text(encoding="utf-8"), prior)
        [(_, rendered)] = rendering.all_renders(
            _binding(self.CHUNKS), self.smap, overlays=None, tuning=_tuning(paths.FAMILY_DIR / "claude.toml")
        )
        self.assertEqual(self.target.read_text(encoding="utf-8"), rendered)


class TestInstallExclusions(unittest.TestCase):
    """The exclusion list an install applies to a shipped package's source,
    matched on the source-relative path at any depth."""

    def test_exclusion_predicate_is_depth_independent(self):
        for excluded in (
            "kb_tools/tests/fixtures/deep/note.md",
            "a/b/__pycache__/x.pyc",
            "x.md.07.bak",
            "sub/.DS_Store",
            "kb_tools/CONVENTIONS.md",
            "liaison_tools/docs/SPEC.md",
        ):
            self.assertTrue(product.excluded_from_install(Path(excluded)), excluded)
        # README is the one project-doc name a package writes for its consumer,
        # and a `.tmpl` is payload rather than documentation.
        for kept in (
            "hand.md",
            "agents/mad/review-topics/t.md",
            "kb_tools/kb_util.py",
            "kb_tools/README.md",
            "kb_tools/installed/CONVENTIONS.tmpl.md",
        ):
            self.assertFalse(product.excluded_from_install(Path(kept)), kept)


class TestShippedPackageMapping(unittest.TestCase):
    """A shipped package lands at the destination its SHIPPED_PACKAGES row
    names, and is read from the source that row names — two facts, not one, so
    a package's source can move within this repository while a consuming
    project's tree does not.

    The destination `.claude/agents/kb_tools/…` is a consumer contract: runner
    snippets already installed in consuming projects import against it. The
    copy set is keyed and ordered by that destination, never by where a source
    sits, so an install's accounting does not shift when a source moves."""

    PACKAGE_FILES = (
        "kb_tools/kb_util.py",
        "kb_tools/runner-snippets/kb.just",
        "kb_tools/tests/test_kb_util.py",  # excluded: tests/, at any source depth
        "liaison_tools/post-openai.py",
    )
    # In REVERSE destination order, so a copy set that follows the table
    # rather than the destinations comes back unsorted.
    ROWS = (("liaison_tools", "agents/liaison_tools"), ("kb_tools", "agents/kb_tools"))

    def test_each_row_reads_its_own_source_and_lands_at_its_frozen_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            for name in self.PACKAGE_FILES:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"content of {name}\n", encoding="utf-8")
            (root / "templates" / "agents").mkdir(parents=True)
            out = root / "out"
            out.mkdir()
            smap = discovery.surface_map(templates_root=root / "templates", output_root=out)
            with mock.patch.object(product, "SHIPPED_PACKAGES", self.ROWS):
                pairs = product.package_pairs(smap, source_root=source)
        keys = [key for key, _, _ in pairs]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual(
            {key: (read_from, target) for key, read_from, target in pairs},
            {
                "agents/kb_tools/kb_util.py": (
                    source / "kb_tools" / "kb_util.py",
                    out / "agents" / "kb_tools" / "kb_util.py",
                ),
                "agents/kb_tools/runner-snippets/kb.just": (
                    source / "kb_tools" / "runner-snippets" / "kb.just",
                    out / "agents" / "kb_tools" / "runner-snippets" / "kb.just",
                ),
                "agents/liaison_tools/post-openai.py": (
                    source / "liaison_tools" / "post-openai.py",
                    out / "agents" / "liaison_tools" / "post-openai.py",
                ),
            },
        )


class TestInstallSourceGuard(unittest.TestCase):
    """`install ROOT` refuses a ROOT that writes the product into its own source.

    Two propositions, tested differently. ROOT *is* the repository root — an
    untracked render beside the templates that produced it. ROOT is *inside* a
    package source — where the next run's copy set names files its own
    destination removal deletes underneath it.

    The first is equality rather than containment because the sanctioned
    deployment layout clones this repository into the consuming project's
    `.claude/`, which makes ROOT a directory containing every package source.
    That layout, and the justfile's `<target>/.claude` shape, are the cases that
    must keep working."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.src = self.root / "src"
        for name in (
            "agents/hand.md",
            "kb_tools/kb_util.py",
            "kb_tools/kb_driver/run.py",
            "nested/pack/tool.sh",
            "commands/guest.md",
        ):
            path = self.src / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"content of {name}\n", encoding="utf-8")

    def _refuses(self, root: Path):
        with self.assertRaises(errors.InputError) as caught:
            product.assert_install_root(root, source_root=self.src)
        return str(caught.exception)

    def test_a_root_the_repository_sits_under_or_beside_is_accepted(self):
        # The sanctioned layout: this repository cloned into the consuming
        # project's gitignored .claude/adjagent/ and used as the install source,
        # so `just install <project>` resolves ROOT to <project>/.claude — a
        # directory containing every package source by construction, which is
        # why the repository-root test is equality and not containment.
        clone = self.root / "consumer" / ".claude" / "adjagent"
        for name in ("kb_tools/kb_util.py", "liaison_tools/post.py"):
            path = clone / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"content of {name}\n", encoding="utf-8")
        for label, root, source_root in (
            ("clone in <project>/.claude", clone.parent, clone),
            ("dogfood install from inside the clone", clone / ".claude", clone),
            ("render slot under the clone", clone / "rendered" / "latest", clone),
            # The deliberate cost of equality: indistinguishable from the
            # sanctioned layout, so it proceeds.
            ("above the repository", self.src.parent, self.src),
            # agents/ and commands/ are not directories in this repository.
            ("named like the agents surface", self.src / "agents", self.src),
            ("named like the commands surface", self.src / "commands", self.src),
            ("justfile <target>/.claude shape", self.root / "elsewhere" / ".claude", self.src),
            ("a sibling of the source root", self.root / "elsewhere", self.src),
        ):
            with self.subTest(root=label):
                product.assert_install_root(root, source_root=source_root)  # no raise

    def test_a_root_that_is_the_repository_or_inside_a_package_source_is_refused(self):
        # Resolution happens before comparison, so neither a link nor a `..`
        # segment routes around either test.
        link = self.root / "link-to-src"
        link.symlink_to(self.src, target_is_directory=True)
        for label, root, expected in (
            ("the repository root", self.src, "this repository's own root"),
            ("a package source", self.src / "kb_tools", "kb_tools/ package source"),
            ("inside a package source", self.src / "kb_tools" / "kb_driver", "kb_tools/ package source"),
            ("the repository root through a symlink", link, "this repository's own root"),
            ("a package source through `..`", self.src / "agents" / ".." / "kb_tools", "kb_tools/ package source"),
        ):
            with self.subTest(root=label):
                self.assertIn(expected, self._refuses(root))

    def test_install_into_the_repo_root_refuses_before_writing_anything(self):
        # The real thing, end to end and against the real repository: no file
        # is touched, because the guard runs before the copy set is built.
        out = self.root / "out"
        out.mkdir()
        smap = discovery.surface_map(output_root=out)
        with self.assertRaises(errors.InputError):
            _quiet(
                installation.install,
                _binding(chunks.load_chunks()),
                smap,
                root=paths.REPO_ROOT,
                overlays=None,
                tuning=_tuning(paths.FAMILY_DIR / "claude.toml"),
            )
        self.assertEqual(sorted(out.rglob("*")), [])


class TestInstalledBanner(unittest.TestCase):
    """The !INSTALLED! banner a copied file carries: where each filetype puts
    it, and the hash mechanics it shares with the !GENERATED! banner."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.src = Path(self._tmp.name)

    def _source(self, name, text):
        path = self.src / name
        path.write_text(text, encoding="utf-8")
        return path

    def _lines(self, name, text, surface="agents"):
        content = installation.install_content(self._source(name, text), surface=surface)
        return content.split("\n")

    def test_frontmatter_banner_sits_inside_the_block(self):
        lines = self._lines("hand.md", "---\nname: hand\n---\nprompt body\n")
        self.assertEqual(lines[0], "---")
        self.assertIn(banners.INSTALLED_NOTICE, lines[2])
        self.assertTrue(lines[3].startswith("# !BODY-SHA256! "))
        self.assertEqual(lines[5], "name: hand")

    def test_bare_command_gets_a_banner_only_frontmatter_block(self):
        # A frontmatter-less command's first BODY line is the description
        # Claude Code lists the slash command by: the banner has to go above
        # it in frontmatter, not in front of it.
        lines = self._lines("guest-end.md", "End the session.\n\n## Behavior\n", surface="commands")
        self.assertEqual(lines[0], "---")
        self.assertIn(banners.INSTALLED_NOTICE, lines[2])
        self.assertEqual(lines[5], "---")
        self.assertEqual(lines[6], "End the session.")

    def test_hash_comment_banner_tops_the_file(self):
        for name, first in (
            ("tool.py", '"""docstring."""'),
            ("kb.just", "# KB recipes"),
            ("kb.mk", "# KB targets"),
            ("conf.toml", "[table]"),
        ):
            lines = self._lines(name, first + "\n")
            self.assertIn(banners.INSTALLED_NOTICE, lines[1], name)
            self.assertEqual(lines[4], first, name)

    def test_hash_comment_banner_sits_below_a_shebang(self):
        lines = self._lines("tool.sh", "#!/usr/bin/env bash\nset -eu\n")
        self.assertEqual(lines[0], "#!/usr/bin/env bash")
        self.assertIn(banners.INSTALLED_NOTICE, lines[2])
        self.assertEqual(lines[5], "set -eu")

    def test_html_banner_wraps_agents_material_without_frontmatter(self):
        # A shipped package's README.md takes an HTML comment, never a
        # frontmatter block: frontmatter would present a package document as a
        # definition, which it is not.
        lines = self._lines("README.md", "# kb_tools\n")
        self.assertEqual(lines[0], "<!--")
        self.assertIn(banners.INSTALLED_NOTICE, lines[1])
        self.assertEqual(lines[3], "-->")
        self.assertEqual(lines[4], "# kb_tools")

    def test_every_style_hashes_the_content_below_it(self):
        for surface, name, text in (
            ("agents", "hand.md", "---\nname: hand\n---\nprompt\n"),
            ("agents", "topic.md", "# TOPIC\n\ncontent\n"),
            ("commands", "bare.md", "Do the thing.\n"),
            ("agents", "tool.py", '"""d."""\ncode()\n'),
            ("agents", "tool.sh", "#!/bin/sh\nexec true\n"),
        ):
            stamped = installation.install_content(self._source(name, text), surface=surface)
            # The shared mechanics read either banner kind: the body is what
            # follows the block, and it hashes to the block's own claim.
            self.assertTrue(banners.body_untouched(stamped), name)
            self.assertTrue(stamped.endswith(banners.banner_body(stamped)), name)
            self.assertFalse(banners.body_untouched(stamped + "edit\n"), name)

    def test_generated_definition_is_exempt(self):
        template = paths.TEMPLATES_DIR / "agents" / "x.tmpl.md"
        body = "name: x\n---\nbody\n"
        stamp = banners.banner(
            template, body_hash=banners.sha256_text(body), tuning=_tuning(paths.FAMILY_DIR / "claude.toml")
        )
        generated = "---\n" + stamp + "\n" + body
        self.assertIsNone(installation.install_content(self._source("gen.md", generated), surface="agents"))

    def test_vendor_carve_out_matches_a_directory_at_any_depth(self):
        for key in ("agents/kb_tools/_vendor/x.py", "agents/kb_tools/_vendor/pkg/deep/x.py"):
            self.assertTrue(installation.vendored(Path(key)), key)
        # A file NAMED _vendor is not a vendored tree, and the carve-out reaches
        # no further than one.
        for key in ("agents/kb_tools/kb_util.py", "agents/kb_tools/_vendor", "agents/_vendored/x.py"):
            self.assertFalse(installation.vendored(Path(key)), key)

    def test_unbannerable_suffixes_take_no_banner(self):
        # A filetype admitting no comment, and a shipped template — `.tmpl`
        # prompt or `.tmpl.md` document — whose whole content is payload a
        # banner would change.
        for name, text in (("s.json", "{}\n"), ("prompt.tmpl", "Prompt text.\n"), ("doc.tmpl.md", "# Doc\n")):
            with self.subTest(name=name):
                self.assertFalse(installation.bannerable(Path(name)))
                self.assertIsNone(installation.install_content(self._source(name, text), surface="agents"))
        for kept in ("a.md", "a.py", "a.sh", "a.toml", "a.mk", "a.just"):
            self.assertTrue(installation.bannerable(Path(kept)), kept)


class TestInstallWritePath(unittest.TestCase):
    """A copied file is always a freshly created one — its destination
    directory went whole before the first write — so the only metadata
    question left is the source's executable bit, which an installed tool has
    to land with."""

    SOURCE = "---\nname: hand\n---\nprompt body\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.source = self.root / "hand.md"
        self.source.write_text(self.SOURCE, encoding="utf-8")
        self.target = self.root / "out" / "hand.md"

    def _install(self, source=None, target=None):
        source = self.source if source is None else source
        target = self.target if target is None else target
        installation.install_file(source, target, installation.install_content(source, surface="agents"))

    def _mode(self, path):
        return stat.S_IMODE(path.stat().st_mode)

    def test_creation_lands_the_content_and_its_banner(self):
        self._install()
        text = self.target.read_text(encoding="utf-8")
        self.assertIn(banners.INSTALLED_NOTICE, text)
        self.assertTrue(banners.body_untouched(text))
        # The parent directory is made on the way: a package's subdirectories
        # went with its destination and nothing else recreates them.
        self.assertTrue(self.target.parent.is_dir())

    def test_creation_carries_the_sources_exec_bit(self):
        # An installed tool has to land runnable, and stamping rewrites the
        # content rather than copying it. The source is a shell script because
        # no shipped package holds one any more: `.sh` is in the set the
        # generator stamps, and this fixture is the only thing exercising it.
        source = self.root / "tool.sh"
        source.write_text("#!/usr/bin/env bash\nexec true\n", encoding="utf-8")
        source.chmod(0o755)
        target = self.target.with_name("tool.sh")
        self._install(source, target)
        self.assertTrue(self._mode(target) & 0o111)
        self.assertIn(banners.INSTALLED_NOTICE, target.read_text(encoding="utf-8"))

    def test_creation_leaves_a_non_executable_source_non_executable(self):
        self.assertFalse(self._mode(self.source) & 0o111)
        self._install()
        self.assertFalse(self._mode(self.target) & 0o111)


class TestBackupIdentity(unittest.TestCase):
    """The numbered .bak a generation write leaves when its target is not
    provably this tool's own output. A recovery artifact, not a mirror."""

    def test_backup_is_a_content_copy_with_its_own_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "probe.md"
            target.write_text("their content\n", encoding="utf-8")
            target.chmod(0o646)
            backup = generation.back_up(target)

            self.assertEqual(backup, root / "probe.md.00.bak")
            self.assertEqual(backup.read_text(encoding="utf-8"), "their content\n")
            # Its own inode, and the mode this process gives a file it creates
            # — nothing cloned off the target, which cloning would have
            # required ownership of.
            self.assertNotEqual(backup.stat().st_ino, target.stat().st_ino)
            probe = root / "probe"
            probe.write_bytes(b"")
            mode = lambda path: stat.S_IMODE(path.stat().st_mode)  # noqa: E731
            self.assertEqual(mode(backup), mode(probe))
            # The target is untouched by the copy: back_up only reads it.
            self.assertEqual(mode(target), 0o646)


class TestQuietPass(unittest.TestCase):
    """The install passes' output buffer: held back when there is nothing to
    say, released when there is — including when the pass raises."""

    def _drive(self, run, *, verbose=False):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with contextlib.suppress(errors.InputError):
                ok = installation.quiet_pass(run, verbose=verbose)
                self.assertIsInstance(ok, bool)
        return buf.getvalue()

    def test_a_clean_pass_says_nothing(self):
        self.assertEqual(self._drive(lambda: (print("every file OK"), True)[1]), "")

    def test_a_clean_pass_still_says_everything_under_verbose(self):
        self.assertIn("every file OK", self._drive(lambda: (print("every file OK"), True)[1], verbose=True))

    def test_an_unclean_pass_releases_its_report(self):
        self.assertIn("DRIFT", self._drive(lambda: (print("DRIFT here"), False)[1]))

    def test_a_raising_pass_releases_its_report_too(self):
        # The buffer is the only copy of how far the pass got, and the run that
        # raises is the one where that matters most. Without the finally, the
        # operator gets an error naming a template and no indication of what
        # the pass had already covered.
        def run():
            print("  OK      agents/first.md")
            raise errors.InputError("unknown chunk or placeholder 'no-such-chunk'")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(errors.InputError):
            installation.quiet_pass(run, verbose=False)
        self.assertIn("agents/first.md", buf.getvalue())


class TestInstallPassContract(unittest.TestCase):
    """What install()'s render pass renders under, and what the operator is
    told when it raises.

    A scratch repository stands in for this one: one template whose output
    declares a tier the family gives overlay overrides for, and a source tree
    holding that output's render — the state a render leaves behind.
    """

    CHUNKS: dict[str, dict] = {}
    BODY = "---\nname: probe\nmodel: @!dyn.tier-medium!@\n---\nbody\n@!fam.probe!@\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.src = root / "src"
        self.templates = self.src / "templates"
        (self.templates / "agents").mkdir(parents=True)
        (self.templates / "commands").mkdir()
        self.template = self.templates / "agents" / "probe.tmpl.md"
        self.template.write_text(self.BODY, encoding="utf-8")
        family_dir = self.templates / "family"
        family_dir.mkdir()
        self.family = family_dir / "fam.toml"
        self.family.write_text(
            _tiers_toml() + '[family.probe.models.sonnet]\ntext = "watch the tier"\n', encoding="utf-8"
        )

        entries = model_tuning.load_family(self.family).entries
        self.overlays = model_tuning.tier_resolver(entries, dict(model_tuning.DEFAULT_PIN_MAP))
        self.tuning = _tuning(self.family, entries=entries)
        self.binding = _binding(self.CHUNKS)
        self.src.mkdir(exist_ok=True)
        # A shipped package source, because the copy half is exactly the
        # shipped packages now: an install finding none refuses before writing.
        (self.src / "kb_tools").mkdir()
        self.source_tool = self.src / "kb_tools" / "probe_tool.py"
        self.source_tool.write_text('"""a probe tool."""\n', encoding="utf-8")
        surfaces = discovery.surface_map(templates_root=self.templates, output_root=self.src)
        _quiet(generation.generate, self.binding, surfaces, overlays=self.overlays, tuning=self.tuning)
        self.source_def = self.src / "agents" / "probe.md"
        self.assertIn("watch the tier", self.source_def.read_text(encoding="utf-8"))

        self.root = root / "consumer"
        self.root.mkdir()
        self.smap = discovery.surface_map(templates_root=self.templates, output_root=self.root)

    def _install(self, **kwargs):
        kwargs.setdefault("tuning", self.tuning)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = installation.install(
                self.binding, self.smap, root=self.root, source_root=self.src, overlays=self.overlays, **kwargs
            )
        return ok, buf.getvalue()

    def test_byte_perfect_install_of_a_tiered_output_is_clean(self):
        ok, report = self._install()
        self.assertTrue(ok)
        installed = self.root / "agents" / "probe.md"
        self.assertEqual(installed.read_bytes(), self.source_def.read_bytes())
        self.assertNotIn("NOT CLEAN", report)
        self.assertEqual(len(report.splitlines()), 1, report)

    def test_the_install_banner_records_the_seat_and_member_it_rendered_under(self):
        # The render pass stamps the triple the install was handed, so the
        # installed definition's banner names the family, its own seat, and the
        # member that seat resolved to.
        ok, _ = self._install()
        self.assertTrue(ok)
        claim = banners.tuning_claim((self.root / "agents" / "probe.md").read_text(encoding="utf-8"))
        self.assertEqual(claim.family, paths.rel(self.family))
        self.assertEqual((claim.seat, claim.member), ("medium", "sonnet"))

    def test_a_raising_pass_still_names_what_landed(self):
        # The copy completes before the render runs, so a template that cannot
        # render still leaves the shipped packages live under ROOT. An operator
        # shown only "error: unknown chunk" reads that as "nothing happened".
        self.template.write_text(self.BODY.replace("body\n", "body @!no-such-chunk!@\n"), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(errors.InputError):
                installation.install(
                    self.binding,
                    self.smap,
                    root=self.root,
                    source_root=self.src,
                    overlays=self.overlays,
                    tuning=self.tuning,
                )
        report = buf.getvalue()
        self.assertIn(f"installed: 1 under agents/ → {paths.rel(self.root)}", report)
        self.assertIn("the packages are in place", report)
        # Said because it is true: the package really is live, and stamped.
        landed = (self.root / "agents" / "kb_tools" / "probe_tool.py").read_text(encoding="utf-8")
        self.assertIn(banners.INSTALLED_NOTICE, landed)
        self.assertEqual(banners.banner_body(landed), self.source_tool.read_text(encoding="utf-8"))
        # And the render really did not happen.
        self.assertFalse((self.root / "agents" / "probe.md").exists())


class TestInstallEndToEnd(unittest.TestCase):
    """Real installs of this repository into scratch targets: default-triple,
    tuned, and re-installed."""

    # Third-party source as a shipped package would vendor it. The vendored
    # file and its non-vendored sibling are byte-identical on purpose: what
    # decides whether a banner is stamped is where the file lands, and nothing
    # else about it.
    VENDOR_SOURCE = '"""Upstream module: ours to ship, never ours to claim."""\n\n\ndef parse(text):\n    return text\n'

    @classmethod
    def setUpClass(cls):
        cls.chunks = chunks.load_chunks()
        # The triple `just install <target>` runs under, built the way main()
        # builds it, so an end-to-end install here is the shipped default one.
        family_path = paths.FAMILY_DIR / "claude.toml"
        cls.family = model_tuning.load_family(family_path)
        cls.tuning = model_tuning.effective_tuning(family_path, cls.family)
        # staticmethod: a plain function on a class would bind as a method and
        # arrive at render_output with `self` prepended.
        cls.overlays = staticmethod(model_tuning.tier_resolver(cls.family.entries, cls.tuning.tier_map))
        cls.binding = model_tuning.tier_binding(cls.chunks, pin_map=cls.tuning.pin_map, harness=_DEFAULT_HARNESS)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / ".claude"
        self.root.mkdir()
        self.smap = discovery.surface_map(output_root=self.root)

    def _defaults(self, kwargs):
        kwargs.setdefault("overlays", self.overlays)
        kwargs.setdefault("tuning", self.tuning)
        kwargs.setdefault("binding", self.binding)
        return kwargs.pop("binding"), kwargs

    def _install(self, **kwargs):
        binding, kwargs = self._defaults(kwargs)
        return _quiet(installation.install, binding, self.smap, root=self.root, **kwargs)

    def _install_report(self, **kwargs) -> str:
        binding, kwargs = self._defaults(kwargs)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            installation.install(binding, self.smap, root=self.root, **kwargs)
        return buf.getvalue()

    def _installed(self):
        return {path.relative_to(self.root).as_posix() for path in self.root.rglob("*") if path.is_file()}

    def test_plain_install_delivers_the_whole_product(self):
        self.assertTrue(self._install())
        installed = self._installed()
        # The failing case this mode exists for: /kb-start references
        # @.claude/agents/kb-docent.md, which no rendered set contains.
        for expected in (
            "agents/kb-docent.md",
            "agents/security-reviewer.md",
            "agents/guest-liaison.md",
            "agents/python-coder.md",
            "agents/mad/participant-contract.md",
            "agents/kb_tools/kb_util.py",
            "agents/kb_tools/installed/CONVENTIONS.tmpl.md",
            "agents/kb_tools/runner-snippets/kb.just",
            "agents/liaison_tools/post-openai.py",
            "commands/guest.md",
        ):
            self.assertIn(expected, installed)
        self.assertTrue(any(name.startswith("agents/mad/design-topics/") for name in installed))
        # A consuming project installs the code, not the project it came from:
        # no file documenting THIS repository to its own developers reaches a
        # consumer tree. Swept over the whole manifest rather than over one
        # package's directory, because the rule is a filename vocabulary and
        # not a placement — a doc reappearing one level down would pass a
        # directory-scoped pin. The vocabulary is spelled out here rather than
        # read off gen_defs, so a name quietly leaving the exclusion set fails
        # against a second statement of it instead of agreeing with itself.
        project_docs = {"SPEC.md", "ARCHITECTURE.md", "CONVENTIONS.md", "ROADMAP.md", "AGENTS.md", "CLAUDE.md"}
        self.assertEqual(sorted(name for name in installed if Path(name).name in project_docs), [])
        # The suffix is what keeps the sweep off the payload: this template is
        # a file a build writes into a consuming project's own KB, and it must
        # keep shipping.
        self.assertIn("agents/kb_tools/installed/AGENTS.tmpl.md", installed)

    def test_plain_install_carries_no_test_suites_or_caches(self):
        # A planted package source holding one of each thing that must not
        # travel beside one file that must, asserted by literal path rather
        # than through the exclusion predicate under test.
        src = Path(self._tmp.name) / "exclusion-src"
        strays = (
            "__pycache__/x.pyc",
            ".pytest_cache/x",
            ".DS_Store",
            "x.md.00.bak",
            "tests/test_x.py",
            "ROADMAP.md",
        )
        for name in (*strays, "shipped.py"):
            path = src / "kb_tools" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{name}\n", encoding="utf-8")
        self.assertTrue(self._install(source_root=src))
        self.assertTrue((self.root / "agents" / "kb_tools" / "shipped.py").is_file())
        for name in strays:
            self.assertFalse((self.root / "agents" / "kb_tools" / name).exists(), name)

    def test_every_installed_banner_claims_the_triple_the_install_ran_under(self):
        self._install()
        claims = {
            path: banners.tuning_claim(path.read_text(encoding="utf-8"))
            for path in sorted((self.root / "agents").glob("*.md"))
            if banners.banner_claim(path.read_text(encoding="utf-8")) is not None
        }
        self.assertTrue(claims)
        for path, claim in claims.items():
            self.assertEqual(claim.family, paths.rel(self.tuning.family), paths.rel(path))
            self.assertEqual(claim.pin, model_tuning.map_spec(self.tuning.pin_map), paths.rel(path))

    def test_a_fresh_install_is_one_summary_line(self):
        # Report by exception: a fresh install is a non-event. A default triple
        # renders like any other but earns no clause, and nothing was there to
        # replace or set aside.
        report = self._install_report()
        self.assertEqual(len(report.splitlines()), 1, report)
        self.assertNotIn("rendered", report)
        self.assertNotIn("replaced", report)
        self.assertIn("!GENERATED!", (self.root / "agents" / "python-coder.md").read_text(encoding="utf-8"))
        self.assertEqual(sorted(self.root.rglob("*.bak")), [])

    def test_a_clean_reinstall_is_one_line_naming_the_package_destinations_it_replaced(self):
        # A clean overwrite is as much a non-event as a fresh install, but every
        # package destination it replaced whole is named. The unbannered set is
        # a property of the copy set's filetypes, so it is not reported.
        self._install()
        report = self._install_report()
        self.assertEqual(len(report.splitlines()), 1, report)
        for _, destination in product.SHIPPED_PACKAGES:
            self.assertIn(destination, report)
        self.assertNotIn("pruned", report)
        self.assertNotIn("unbannered", report)
        self.assertNotIn(".tmpl", report)

    def test_a_local_edit_inside_a_package_destination_goes_with_the_directory(self):
        # The package destinations are this repository's whole, so the unit
        # that is replaced is the directory. No numbered backup reaches inside
        # one, and the report says so on its summary line rather than setting
        # anything aside.
        self._install()
        edited = self.root / "agents" / "kb_tools" / "kb_util.py"
        original = edited.read_text(encoding="utf-8")
        edited.write_text(original + "\n# local edit\n", encoding="utf-8")
        report = self._install_report()
        self.assertEqual(edited.read_text(encoding="utf-8"), original)
        self.assertEqual(sorted(self.root.rglob("*.bak")), [])
        self.assertNotIn("replaced: ", report)
        # Still one line — replacing a package directory is the ordinary path —
        # but the directories whose contents went are named on it.
        lines = report.splitlines()
        self.assertEqual(len(lines), 1, report)
        self.assertIn("replaced whole, local edits included: agents/kb_tools, agents/liaison_tools", lines[0])

    def test_verbose_lists_every_file_and_names_the_unbannered_ones(self):
        report = self._install_report(verbose=True)
        # Both halves report: a copied package file by its ROOT-relative key,
        # a rendered definition by the generation pass's own created/updated
        # line, which names an absolute target.
        self.assertIn("  written    agents/kb_tools/kb_util.py", report)
        self.assertIn(f"  created    {paths.rel(self.root / 'agents' / 'python-coder.md')}", report)
        [unbannered] = [line for line in report.splitlines() if line.startswith("unbannered")]
        # A shipped template is payload consumed verbatim, so it installs
        # unstamped, byte for byte, and the verbose report names it.
        key = "agents/kb_tools/installed/AGENTS.tmpl.md"
        self.assertIn(key, unbannered.split(" — ", 1)[1].split(", "))
        self.assertEqual(
            (self.root / key).read_text(encoding="utf-8"),
            (paths.REPO_ROOT / "kb_tools" / "installed" / "AGENTS.tmpl.md").read_text(encoding="utf-8"),
        )

    def _vendoring_source_root(self) -> Path:
        """A scratch shipped-package source carrying a `_vendor/` tree beside an
        ordinary module, travelling the real SHIPPED_PACKAGES row for kb_tools.
        Built here rather than read from the repository: the carve-out belongs
        to the path class, not to any package currently vendoring anything."""
        src = Path(self._tmp.name) / "vendor-src"
        vendor = src / "kb_tools" / "_vendor"
        (vendor / "upstream").mkdir(parents=True)
        (vendor / "upstream" / "walker.py").write_text(self.VENDOR_SOURCE, encoding="utf-8")
        (vendor / "LICENSE.txt").write_text("MIT, upstream's.\n", encoding="utf-8")
        (src / "kb_tools" / "sibling.py").write_text(self.VENDOR_SOURCE, encoding="utf-8")
        return src

    def test_vendored_source_ships_verbatim_and_its_sibling_is_still_stamped(self):
        src = self._vendoring_source_root()
        self._install(source_root=src)
        vendored = self.root / "agents" / "kb_tools" / "_vendor" / "upstream" / "walker.py"
        # It ships: a stamping carve-out, never an exclusion.
        self.assertTrue(vendored.is_file())
        self.assertEqual(vendored.read_bytes(), self.VENDOR_SOURCE.encode("utf-8"))
        self.assertNotIn(banners.INSTALLED_NOTICE, vendored.read_text(encoding="utf-8"))
        self.assertEqual(
            (self.root / "agents" / "kb_tools" / "_vendor" / "LICENSE.txt").read_text(encoding="utf-8"),
            "MIT, upstream's.\n",
        )
        # Narrow: identical bytes one directory up are stamped exactly as ever.
        sibling = (self.root / "agents" / "kb_tools" / "sibling.py").read_text(encoding="utf-8")
        self.assertIn(banners.INSTALLED_NOTICE, sibling)
        self.assertTrue(banners.body_untouched(sibling))
        self.assertEqual(banners.banner_body(sibling), self.VENDOR_SOURCE)
        # Re-vendoring the same bytes is a no-op: an unstamped file is never
        # provably ours, so only a CHANGED one can cost a numbered backup.
        self._install(source_root=src)
        self.assertEqual(sorted(self.root.rglob("*.bak")), [])

    def test_verbose_report_names_the_vendored_file_as_unstamped(self):
        report = self._install_report(source_root=self._vendoring_source_root(), verbose=True)
        unstamped = [line for line in report.splitlines() if line.startswith("unstamped")]
        unbannered = [line for line in report.splitlines() if line.startswith("unbannered")]
        self.assertEqual(len(unstamped), 1, report)
        self.assertEqual(len(unbannered), 1, report)
        self.assertIn("agents/kb_tools/_vendor/upstream/walker.py", unstamped[0])
        # One bucket per file, one reason each: the vendored .txt is verbatim
        # because its type admits no comment, which is the older reason and
        # still the right one for it.
        self.assertNotIn("LICENSE", unstamped[0])
        self.assertIn("agents/kb_tools/_vendor/LICENSE.txt", unbannered[0])
        self.assertNotIn("walker.py", unbannered[0])

    def _package_key(self, name: str) -> bool:
        return any(name.startswith(f"{key.as_posix()}/") for _, key, _ in product.package_destinations(self.smap))

    def test_reinstall_is_idempotent(self):
        self._install()
        first = {
            name: ((self.root / name).read_bytes(), (self.root / name).stat().st_mtime_ns) for name in self._installed()
        }
        self._install()
        second = {
            name: ((self.root / name).read_bytes(), (self.root / name).stat().st_mtime_ns) for name in self._installed()
        }
        # Byte-stable everywhere: the banner text is deterministic, so the same
        # sources re-install to the same tree.
        self.assertEqual(
            {name: content for name, (content, _) in first.items()},
            {name: content for name, (content, _) in second.items()},
        )
        # Not even rewritten, on the surfaces: an identical target is skipped
        # outright. Inside a package destination there is nothing to skip —
        # the directory went and the file is new — so the mtimes move there and
        # only there, which is the visible edge of the two granularities.
        surfaces = {name: stamp for name, (_, stamp) in first.items() if not self._package_key(name)}
        self.assertEqual(surfaces, {name: stamp for name, (_, stamp) in second.items() if not self._package_key(name)})
        packages = [name for name in first if self._package_key(name)]
        self.assertTrue(packages)
        self.assertTrue(all(first[name][1] != second[name][1] for name in packages))
        self.assertEqual(sorted(self.root.rglob("*.bak")), [])

    def test_installed_copies_are_bannered_and_sources_are_not(self):
        # Every source an install COPIES is a shipped package at the repository
        # top level, stamped on its way into the installed tree and never here:
        # every byte of every source file is as the install found it. Bytecode
        # caches are left out because any interpreter importing a package
        # rewrites them, install or not.
        sources = [paths.REPO_ROOT / source for source, _ in product.SHIPPED_PACKAGES]

        def snapshot():
            return {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for source in sources
                for path in sorted(source.rglob("*"))
                if path.is_file() and "__pycache__" not in path.parts
            }

        before = snapshot()
        self.assertTrue(before)
        self._install()
        self.assertEqual(snapshot(), before)
        notice = banners.INSTALLED_NOTICE.encode("utf-8")
        for path in before:
            self.assertNotIn(notice, path.read_bytes(), paths.rel(path))
        # One row per banner style the real product exercises: `#` comments in
        # a shipped .py, and the exempt case, a generated definition arriving
        # with its own !GENERATED! banner. The frontmatter and HTML styles have
        # no row because no shipped package holds a *.md that takes either
        # today; a package README.md would ship and take the HTML style. Both
        # are unit cases over install_content, in TestInstalledBanner.
        for name, bannered in (
            ("agents/kb_tools/kb_util.py", True),
            ("agents/python-coder.md", False),
        ):
            text = (self.root / name).read_text(encoding="utf-8")
            self.assertEqual(banners.INSTALLED_NOTICE in text, bannered, name)
            self.assertTrue(banners.body_untouched(text), name)

    def _extract(self, path):
        """The extraction the liaison definitions run, verbatim: drop every line
        through the one that closes the frontmatter block. Run as a subprocess
        rather than reimplemented in python, because the command line in those
        definitions is the thing under test."""
        return subprocess.run(
            ["sed", "1,/^---$/d", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )

    @unittest.skipUnless(shutil.which("sed"), "extraction needs sed")
    def test_every_generated_definition_extracts_frontmatter_free(self):
        # SPEC's Guest-Extraction Contract, enforced where a definition is
        # BUILT rather than where it is read: one that would reach a guest
        # model truncated fails here. Every rendered *.md under agents/, not a
        # sample — the property is a claim about the surface, and a sampled
        # check would pass on the day one definition broke it.
        self._install()
        rendered = [
            path
            for path in sorted((self.root / "agents").rglob("*.md"))
            if banners.banner_claim(path.read_text(encoding="utf-8")) is not None
        ]
        self.assertGreater(len(rendered), 20, "the walk found no definitions to check")
        for path in rendered:
            with self.subTest(definition=path.relative_to(self.root).as_posix()):
                done = self._extract(path)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertNotIn("!GENERATED!", done.stdout)
                self.assertNotIn("!BODY-SHA256!", done.stdout)
                # No body content lost: the frontmatter block and what came
                # out reconstitute the file byte for byte.
                text = path.read_text(encoding="utf-8")
                front = banners.frontmatter_of(text)
                self.assertEqual(text, "---\n" + front + "\n---\n" + done.stdout)

    def test_a_non_default_triple_renders_and_earns_its_summary_clause(self):
        family_path = paths.FAMILY_DIR / "gemma-4.toml"
        family = model_tuning.load_family(family_path)
        tuning = model_tuning.effective_tuning(family_path, family)
        self.assertFalse(tuning.is_default)
        binding = model_tuning.tier_binding(self.chunks, pin_map=tuning.pin_map, harness=_DEFAULT_HARNESS)
        overlays = model_tuning.tier_resolver(family.entries, tuning.tier_map)

        # The default-triple render to compare against, produced the same way:
        # a comparison between two delivered artifacts, not a reconstruction.
        base_root = Path(self._tmp.name) / "base"
        base_root.mkdir()
        _quiet(
            installation.install,
            self.binding,
            discovery.surface_map(base_root),
            root=base_root,
            overlays=self.overlays,
            tuning=self.tuning,
        )
        plain_body = banners.banner_body((base_root / "agents" / "go-coder.md").read_text(encoding="utf-8"))

        report = self._install_report(binding=binding, overlays=overlays, tuning=tuning)
        # A non-default render IS an event: the one summary line says how many
        # and under what — and the pass's own file-by-file report stays back.
        self.assertEqual(len(report.splitlines()), 1, report)
        self.assertRegex(report, r"; \d+ rendered under family templates/family/gemma-4\.toml, tier\[")
        # No backups anywhere: every rendered target was a fresh copy, and so
        # provably this tool's own output.
        self.assertEqual(sorted(self.root.rglob("*.bak")), [])
        # Each anchor lands in the one definition that authors it. The text
        # renders verbatim, so the family's own first line is what to look
        # for — read out of the family file rather than transcribed.
        scorer_tuned = (self.root / "agents" / "kb-claim-scorer.md").read_text(encoding="utf-8")
        self.assertIn(family.entries["fam.gap-aversion"]["text"].splitlines()[0], scorer_tuned)
        tuned = (self.root / "agents" / "applied-mathematician.md").read_text(encoding="utf-8")
        self.assertIn(family.entries["fam.ask-vs-stipulate"]["text"].splitlines()[0], tuned)
        claim = banners.tuning_claim(tuned)
        self.assertEqual(claim.family, "templates/family/gemma-4.toml")
        self.assertIn("gemma-4-31B-it", claim.tier)
        # A family member never reaches a pin: the tokens come from the pin map
        # alone, so the rendered pins are claude-legal under any family.
        self.assertEqual(claim.pin, model_tuning.map_spec(model_tuning.DEFAULT_PIN_MAP))
        # A definition the family does not touch keeps a byte-identical body;
        # only its banner records the triple it was rendered under.
        untouched = (self.root / "agents" / "go-coder.md").read_text(encoding="utf-8")
        self.assertEqual(banners.banner_body(untouched), plain_body)

    # ── the stale-output prune ───────────────────────────────────────────────
    #
    # One rule and its three complements. `_retire` is how every case below
    # stages its subject: a definition this repository really did install, moved
    # to a path no template declares — which is byte-for-byte the state an
    # installed tree is left in when a template is deleted here, and the only
    # state the prune's delete branch is allowed to fire on.

    def _retire(self, name: str, to: str) -> Path:
        """Move an installed definition to a path no template declares, and
        return it. Its banner still hashes to its own body: it IS this tool's
        output, just output nothing produces any more."""
        retired = self.root / to
        retired.parent.mkdir(parents=True, exist_ok=True)
        (self.root / "agents" / name).rename(retired)
        return retired

    def _prune_lines(self, report: str, head: str) -> list[str]:
        """The indented keys under the report block `head` opens, or []."""
        lines = report.splitlines()
        starts = [i for i, line in enumerate(lines) if line.startswith(head)]
        if not starts:
            return []
        keys = []
        for line in lines[starts[0] + 1 :]:
            if not line.startswith("  "):
                break
            keys.append(line.strip())
        return keys

    def test_prune_deletes_output_no_template_declares_any_more(self):
        self._install()
        retired = self._retire("python-coder.md", "agents/retired-coder.md")
        report = self._install_report()
        self.assertFalse(retired.exists())
        self.assertEqual(self._prune_lines(report, "pruned:"), ["agents/retired-coder.md"])
        # Deleted, not set aside: provably unmodified output is reproducible
        # from the template at will, so a copy of it protects nothing — the
        # same reading that keeps the overwrite path from writing a .bak.
        self.assertEqual(sorted(self.root.rglob("*.bak")), [])
        # The live definition it was moved out of came back, and everything
        # else the install delivers is still there.
        self.assertTrue((self.root / "agents" / "python-coder.md").is_file())
        self.assertIn("agents/kb-docent.md", self._installed())

    def test_prune_never_deletes_a_hand_edited_file(self):
        # Complement one: the banner is ours, the body does not hash to it.
        # Unreproducible content, and a template no longer claiming it makes it
        # more the consumer's rather than less.
        self._install()
        retired = self._retire("go-coder.md", "agents/retired-edited.md")
        edited = retired.read_text(encoding="utf-8") + "\nA local paragraph nothing here can regenerate.\n"
        retired.write_text(edited, encoding="utf-8")
        report = self._install_report()
        self.assertTrue(retired.exists())
        self.assertEqual(retired.read_text(encoding="utf-8"), edited)
        self.assertEqual(self._prune_lines(report, "kept:"), ["agents/retired-edited.md"])
        self.assertEqual(self._prune_lines(report, "pruned:"), [])

    def test_prune_never_deletes_a_file_with_no_banner_of_ours(self):
        # Complement two: a consuming project's .claude/ holds other people's
        # files, and the install has no opinion about any of them — including
        # the silence, which is why the report never names them.
        self._install()
        theirs = self.root / "agents" / "their-own-agent.md"
        body = "---\nname: their-own-agent\n---\n\nSomeone else wrote this.\n"
        theirs.write_text(body, encoding="utf-8")
        report = self._install_report()
        self.assertEqual(theirs.read_text(encoding="utf-8"), body)
        self.assertNotIn("their-own-agent", report)
        self.assertEqual(self._prune_lines(report, "pruned:"), [])

    def test_a_hand_edit_to_a_LIVE_definition_takes_the_backup_path_not_the_prune(self):
        # Complement three: membership in the write set is decided on path
        # identity before content is read at all, so the one file state that
        # looks most like a prune candidate — our banner, body not hashing to
        # it — is still written and backed up rather than deleted.
        self._install()
        live = self.root / "agents" / "prompt-engineer.md"
        live.write_text(live.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
        report = self._install_report()
        self.assertTrue(live.is_file())
        self.assertEqual([path.name for path in self.root.rglob("*.bak")], ["prompt-engineer.md.00.bak"])
        self.assertEqual(self._prune_lines(report, "pruned:"), [])
        self.assertEqual(self._prune_lines(report, "kept:"), [])

    def test_prune_removes_a_directory_it_empties_and_spares_one_it_does_not(self):
        # An emptied directory is exactly as stale as the file that was in it:
        # `diff -rq` between two render slots reports it just as loudly.
        self._install()
        self._retire("kb-docent.md", "agents/mad/retired-topics/topic.md")
        kept = self._retire("kb-maintainer.md", "agents/mad/mixed-topics/topic.md")
        theirs = kept.parent / "notes.md"
        theirs.write_text("Not ours, no banner.\n", encoding="utf-8")
        self._install()
        self.assertFalse((self.root / "agents" / "mad" / "retired-topics").exists())
        # Pruned out from under, but the directory holds a file that is not
        # ours, so neither it nor its parent goes anywhere.
        self.assertFalse(kept.exists())
        self.assertTrue(theirs.is_file())
        self.assertTrue((self.root / "agents" / "mad" / "participant-contract.md").is_file())

    def test_prune_does_not_walk_into_a_shipped_package_destination(self):
        # The package destinations are the OTHER rule's, so the prune never
        # sorts a file inside one into the three states. Driven against
        # prune_stale directly, because an install would also remove the
        # fixture by replacing the directory whole — and this asserts which of
        # the two rules did it.
        self._install()
        inside = self.root / "agents" / "kb_tools" / "kb_util.py"
        self.assertTrue(
            banners.body_untouched(inside.read_text(encoding="utf-8")),
            "the fixture must be a file the prune WOULD take",
        )
        # A write set holding every installed file EXCEPT this one: the single
        # condition that would otherwise make it a candidate.
        written = {path for path in self.root.rglob("*") if path.is_file()} - {inside}
        stale = pruning.prune_stale(self.smap, written=written)
        self.assertTrue(inside.is_file())
        self.assertEqual(stale.pruned, [])
        self.assertEqual(stale.kept_edited, [])

    # ── the wholesale package replacement ────────────────────────────────────

    def test_a_package_file_with_no_source_does_not_survive_a_reinstall(self):
        # The gap the wholesale replacement exists to close: a per-file copy
        # writes what the package holds now and has no way to notice what it
        # used to hold, so a file whose source here was deleted used to sit in
        # a consumer's tree forever. Removing the directory retires it by
        # construction, and the banner it happens to carry has nothing to do
        # with it — this fixture's does still hash to its own claim.
        self._install()
        orphan = self.root / "agents" / "kb_tools" / "retired_tool.py"
        orphan.write_bytes((self.root / "agents" / "kb_tools" / "kb_util.py").read_bytes())
        self.assertTrue(banners.body_untouched(orphan.read_text(encoding="utf-8")))
        self._install()
        self.assertFalse(orphan.exists())
        self.assertTrue((self.root / "agents" / "kb_tools" / "kb_util.py").is_file())

    def test_a_file_with_no_banner_inside_a_package_destination_goes_too(self):
        # Inside a package destination the three states are not consulted at
        # all: the directory is the unit, so a file the banner prune would have
        # kept on a deployed surface goes with it.
        self._install()
        theirs = self.root / "agents" / "liaison_tools" / "their-notes.txt"
        theirs.write_text("No banner anywhere in this.\n", encoding="utf-8")
        self._install()
        self.assertFalse(theirs.exists())
        self.assertTrue((self.root / "agents" / "liaison_tools" / "post-openai.py").is_file())

    def test_the_replacement_reaches_exactly_the_destinations_the_table_names(self):
        # Not a parent, not a sibling, nothing pattern-matched. The two
        # neighbours are the ones a careless rmtree target would take with it.
        self._install()
        sibling = self.root / "agents" / "kb_tools_notes.md"
        sibling.write_text("A consuming project's own file, named like a package.\n", encoding="utf-8")
        nested = self.root / "agents" / "mad" / "their-own.md"
        nested.write_text("Also theirs.\n", encoding="utf-8")
        self._install()
        self.assertTrue(sibling.is_file())
        self.assertTrue(nested.is_file())
        # The parent above all: the whole agents/ surface is not a package.
        self.assertTrue((self.root / "agents" / "python-coder.md").is_file())


class TestShippedFamilyFiles(unittest.TestCase):
    """The two families this repository ships, held to the schema every family
    file now has to satisfy."""

    def test_the_default_family_is_the_default_triple(self):
        path = paths.FAMILY_DIR / f"{model_tuning.DEFAULT_FAMILY}{paths.FAMILY_SUFFIX}"
        tuning = model_tuning.effective_tuning(path, model_tuning.load_family(path))
        self.assertTrue(tuning.is_default)
        self.assertEqual(tuning.harness, "claude")
        # The two maps coincide inside claude, which is what makes a divergence
        # there a deliberate act worth naming.
        self.assertEqual(tuning.tier_map, tuning.pin_map)

    def test_another_harness_is_not_the_default(self):
        path = paths.FAMILY_DIR / f"{model_tuning.DEFAULT_FAMILY}{paths.FAMILY_SUFFIX}"
        tuning = model_tuning.effective_tuning(path, model_tuning.load_family(path), harness="opencode")
        self.assertFalse(tuning.is_default)

    def test_an_explicit_no_op_override_is_still_the_default_triple(self):
        # `is_default` is a comparison by VALUE, not "was a flag passed": an
        # override that changes nothing must not turn an install into an event.
        path = paths.FAMILY_DIR / f"{model_tuning.DEFAULT_FAMILY}{paths.FAMILY_SUFFIX}"
        tuning = model_tuning.effective_tuning(path, model_tuning.load_family(path), pin_spec="high=opus")
        self.assertTrue(tuning.is_default)


#: A pin site as a TEMPLATE spells it, in either of the two spellings a
#: template has: a literal frontmatter line (`model: @!dyn.tier-high!@`) and an
#: outputs-fence parameter (`model = "@!dyn.tier-high!@"`). Deliberately this
#: module's own regex over the template SOURCE rather than a call into the
#: generator: the value it yields has to reach the comparison below without
#: having passed through the render whose answer it is there to hold to
#: account.
_DECLARED_PIN_SITE = re.compile(r'^\s*model\s*[:=]\s*"?@!dyn\.tier-([a-z]+)!@"?\s*$', re.MULTILINE)


def declared_pins(templates_root: Path, pin_map: dict) -> dict[str, list[str]]:
    """``{template path: the pins its declared tier tokens resolve to, sorted}``.

    The template side of the comparison, read straight out of the sources.
    """
    return {
        paths.rel(path): sorted(pin_map[tier] for tier in _DECLARED_PIN_SITE.findall(path.read_text(encoding="utf-8")))
        for path in sorted(templates_root.rglob("*.tmpl.md"))
    }


def rendered_pins(renders: dict, known: dict) -> dict[str, list[str]]:
    """``{template path: the pins its outputs actually rendered, sorted}``.

    The rendered side, grouped by each output's own banner claim to the
    template it came from — so the two sides are joined by what the output says
    about itself rather than by a name this module derives.

    Both this and :func:`declared_pins` take their corpus as a parameter so the
    same comparison runs over the shipped tree and over a planted one, which is
    what makes its teeth testable rather than assumed.
    """
    grouped: dict[str, list[str]] = {key: [] for key in known}
    for text in renders.values():
        pin = rendering.frontmatter_pin(text)
        if pin is not None:
            grouped.setdefault(banners.banner_claim(text), []).append(pin)
    return {key: sorted(pins) for key, pins in grouped.items()}


class TestDeclaredPinsAgainstRenderedPins(unittest.TestCase):
    """The tier a template DECLARES against the pin its render carries — two
    independently produced values, joined only by the run's pin map.

    A definition whose pin site stopped resolving, a fence parameter that
    stopped being a tier token, a tier token bound to the wrong map entry, or
    an output that lost its `model:` line altogether all land here as an
    inequality naming the template.

    Run at three tunings, because a pin map that is a constant function hides a
    misrouted tier: the shipped default (five tiers, four distinct pins), the
    floor (`all=haiku`, what a map collapsed with `all=` has to survive), and a
    non-claude family, whose tier map names members that must never reach a
    pin.
    """

    TUNINGS = (
        ("default", "claude", None, None),
        ("floor", "claude", "all=haiku", "all=haiku"),
        ("gemma-4", "gemma-4", None, None),
    )

    def test_every_template_renders_the_pins_its_tier_tokens_declare(self):
        for label, family, tier_spec, pin_spec in self.TUNINGS:
            with self.subTest(tuning=label):
                tuning, _, renders = _shipped_renders(family, tier_spec=tier_spec, pin_spec=pin_spec)
                declared = declared_pins(paths.TEMPLATES_DIR, tuning.pin_map)
                self.assertEqual(rendered_pins(renders, declared), declared)

    def test_the_comparison_is_not_vacuous(self):
        # Floors rather than fixtures: a fortieth template and a sixth tier
        # must not require editing these, only a sweep that has quietly stopped
        # reaching the tree.
        declared = declared_pins(paths.TEMPLATES_DIR, model_tuning.DEFAULT_PIN_MAP)
        pinned = {key: pins for key, pins in declared.items() if pins}
        self.assertGreaterEqual(len(pinned), 30)
        # More than one distinct pin under the default map, or the comparison
        # would hold whatever the render did with a tier.
        self.assertGreater(len({pin for pins in pinned.values() for pin in pins}), 1)
        # mad-participant.tmpl.md is the one template declaring its pins in an
        # outputs fence, so the second spelling is reached rather than assumed.
        self.assertEqual(len(declared["templates/agents/mad-participant.tmpl.md"]), 4)

    def test_a_render_that_ignores_the_declared_tier_is_caught(self):
        # The teeth, over a planted tree: one template declaring `tier-high`,
        # and a render of it carrying the `medium` pin instead. This is the
        # class a re-render-and-compare verb was structurally unable to see —
        # it would have produced the same wrong pin on both sides.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "probe.tmpl.md"
            template.write_text("---\nname: probe\nmodel: @!dyn.tier-high!@\n---\nbody\n", encoding="utf-8")
            declared = declared_pins(root, model_tuning.DEFAULT_PIN_MAP)
            self.assertEqual(list(declared.values()), [[model_tuning.DEFAULT_PIN_MAP["high"]]])

            banner = f"# !GENERATED! from {paths.rel(template)} and x\n"
            honest = {"probe.md": f"---\n{banner}model: {model_tuning.DEFAULT_PIN_MAP['high']}\n---\nbody\n"}
            wrong = {"probe.md": f"---\n{banner}model: {model_tuning.DEFAULT_PIN_MAP['medium']}\n---\nbody\n"}

            self.assertEqual(rendered_pins(honest, declared), declared)
            self.assertNotEqual(rendered_pins(wrong, declared), declared)

    def test_an_output_that_loses_its_pin_line_is_caught_too(self):
        # The other direction: the template still declares a tier and the
        # render carries no `model:` key at all.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "probe.tmpl.md"
            template.write_text("---\nname: probe\nmodel: @!dyn.tier-low!@\n---\nbody\n", encoding="utf-8")
            declared = declared_pins(root, model_tuning.DEFAULT_PIN_MAP)
            unpinned = {"probe.md": f"---\n# !GENERATED! from {paths.rel(template)} and x\n---\nbody\n"}
            self.assertNotEqual(rendered_pins(unpinned, declared), declared)


class TestFloorRung(unittest.TestCase):
    """The floor, over the real definition set: both maps collapsed onto one
    member with `all=`.

    What it proves is the `all=` merge reaching every tier a real definition
    sits at. Nothing is asserted about `lowest`: no pin site carries that
    token, so the assertion would pass vacuously whatever the merge did.
    """

    FLOOR = "haiku"

    @classmethod
    def setUpClass(cls):
        _, _, cls.renders = _shipped_renders(
            "claude",
            tier_spec=f"all={cls.FLOOR}",
            pin_spec=f"all={cls.FLOOR}",
        )
        cls.pinned = {key: text for key, text in cls.renders.items() if rendering.frontmatter_pin(text)}
        cls.unpinned = {key: text for key, text in cls.renders.items() if key not in cls.pinned}

    def test_every_pin_site_pins_the_floor_and_tunes_against_it(self):
        for key, text in self.pinned.items():
            with self.subTest(output=key):
                self.assertEqual(rendering.frontmatter_pin(text), self.FLOOR)
                claim = banners.tuning_claim(text)
                self.assertEqual(claim.member, self.FLOOR)
                self.assertIn(claim.seat, model_tuning.TIERS)

    def test_the_merge_reached_every_tier_a_definition_sits_at(self):
        # The tiers the templates declare, read out of their sources.
        declared = {
            tier
            for path in paths.TEMPLATES_DIR.rglob("*.tmpl.md")
            for tier in _DECLARED_PIN_SITE.findall(path.read_text(encoding="utf-8"))
        }
        seats = {banners.tuning_claim(text).seat for text in self.pinned.values()}
        self.assertEqual(seats, declared)

    def test_an_output_with_no_pin_site_gains_none(self):
        # A map cannot pin an output that has no pin site: no command carries
        # model frontmatter, and neither does anything under agents/mad/ —
        # the participant contract is forbidden one, and a methodology topic
        # is prose a referee reads, not a seat something dispatches.
        self.assertEqual([key for key in self.pinned if key.startswith("commands/")], [])
        self.assertEqual(
            sorted(key for key in self.unpinned if not key.startswith("commands/")),
            sorted(
                ["agents/mad/participant-contract.md"]
                + [key for key in self.renders if key.startswith("agents/mad/") and "-topics/" in key]
            ),
        )
        for key, text in self.unpinned.items():
            with self.subTest(output=key):
                claim = banners.tuning_claim(text)
                self.assertEqual((claim.seat, claim.member), ("none", "none"))


class TestStockRung(unittest.TestCase):
    """The stock state, over the real definition set: the gemma-4 family,
    whose five tiers name real members the family declares no overrides for —
    the stock state, which every banner records and the run's notice, having
    nothing member-scoped to name, says nothing about."""

    ANCHORS = ("fam.ask-vs-stipulate", "fam.gap-aversion")

    @classmethod
    def setUpClass(cls):
        _, cls.overlays, cls.renders = _shipped_renders("gemma-4")
        cls.tiers = model_tuning.load_family(paths.FAMILY_DIR / "gemma-4.toml").tiers
        cls.members = set(cls.tiers.values())

    def test_every_banner_records_the_family_the_tier_map_and_a_stock_render(self):
        for key, text in self.renders.items():
            with self.subTest(output=key):
                claim = banners.tuning_claim(text)
                self.assertEqual(claim.family, "templates/family/gemma-4.toml")
                # Serialized here in canonical tier order, not through
                # map_spec, so a map_spec that reorders still shows.
                self.assertEqual(claim.tier, ",".join(f"{tier}={self.tiers[tier]}" for tier in model_tuning.TIERS))
                self.assertEqual(claim.stock, ",".join(model_tuning.TIERS))

    def test_both_family_wide_anchors_fill_at_every_tier_and_at_none(self):
        # The no-tier resolution is what the outputs with no pin site run
        # under, and family scope fills both anchors there exactly as it does
        # for a tiered output — only MODEL-scoped entries require a tier.
        for tier, filled in self.overlays.items():
            with self.subTest(tier=tier):
                self.assertEqual(
                    {anchor: scope for anchor, (_, scope) in filled.items()}, dict.fromkeys(self.ANCHORS, "family")
                )

    def test_the_family_wide_text_reaches_the_rendered_tree(self):
        for anchor in self.ANCHORS:
            lead = self.overlays[None][anchor][0].splitlines()[0]
            with self.subTest(anchor=anchor):
                # An empty lead would make the search below match everything.
                self.assertTrue(lead)
                self.assertTrue([key for key, text in self.renders.items() if lead in text])

    def test_no_rendered_body_carries_a_member_scoped_word(self):
        # Stock is a claim about the MEMBER, so this is its proof: the family
        # declares no [family.*.models.*] table for any of the five, and a member
        # name never reaches rendered text in any case — the pin map is the
        # sole source of pin text. Over the body, since the banner's own tier=
        # field names all five by design.
        for key, text in self.renders.items():
            body = banners.banner_body(text)
            for member in self.members:
                with self.subTest(output=key, member=member):
                    self.assertNotIn(member, body)


class TestResidualMarkerGuard(unittest.TestCase):
    """A rendered output must carry no leftover marker delimiter ('@!', '!@') — the
    guard against a marker mistyped past MARKER's own grammar (wrong case, an
    underscore) shipping verbatim into what becomes an agent's system prompt,
    with no chunk, no overlay, and no error to say so otherwise."""

    CLEAN = "---\nname: @!arg.name!@\n---\nbody\n"
    # Capitalized and underscored: valid-looking, but outside MARKER's
    # IDENTIFIER name grammar, so render() never touches it at all.
    RESIDUAL = "---\nname: @!arg.name!@\n---\nbody mentioning @!Guest_Extraction_Contract!@ verbatim.\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        (self.tsrc / "agents").mkdir(parents=True)
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.family = root / "fam.toml"
        self.family.write_text(_tiers_toml(), encoding="utf-8")

    def _write(self, body):
        (self.tsrc / "agents" / "probe.tmpl.md").write_text(body, encoding="utf-8")

    def _generate(self):
        return _quiet(generation.generate, _binding({}), self.smap, overlays=None, tuning=_tuning(self.family))

    def test_a_clean_render_is_unaffected(self):
        self._write(self.CLEAN)
        self.assertTrue(self._generate())

    def test_a_malformed_marker_is_refused_naming_the_file_and_line(self):
        self._write(self.RESIDUAL)
        with self.assertRaises(errors.InputError) as caught:
            self._generate()
        message = str(caught.exception)
        self.assertIn("templates/agents/probe.tmpl.md", message)
        self.assertIn("line 4", message)
        self.assertIn("Guest_Extraction_Contract", message)
        # Nothing lands: the guard fires before generate writes its target.
        self.assertFalse((self.out / "agents" / "probe.md").exists())

    def test_a_regression_after_a_clean_baseline_is_refused_too(self):
        # The guard is on the render, not on the absence of a target: a
        # template that regresses to a malformed marker once a good definition
        # already exists is refused exactly as a fresh one is, and the good
        # definition on disk is left as it was rather than overwritten.
        self._write(self.CLEAN)
        self.assertTrue(self._generate())
        target = self.out / "agents" / "probe.md"
        clean = target.read_text(encoding="utf-8")
        self._write(self.RESIDUAL)
        with self.assertRaises(errors.InputError):
            self._generate()
        self.assertEqual(target.read_text(encoding="utf-8"), clean)


class TestArgumentKeyIdentifierClass(unittest.TestCase):
    """The behavior change tightening ARG's key class actually causes. Before,
    ARG's key grammar ([a-z_]+) was looser than MARKER's own name grammar, so
    `@!some-chunk my_key="x"!@` parsed fine and bound "my_key" into the
    chunk's scope — and since a chunk body is never required to reference
    every bound key, an unused off-convention key like this rendered clean
    with no error at all. Now that ARG draws from the same IDENTIFIER class as
    MARKER, the whole marker no longer matches MARKER's grammar (the argument
    segment does not parse), so it ships as literal '@!...!@' text and the
    residual-marker guard (TestResidualMarkerGuard) refuses it instead of
    letting it through unused."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        (self.tsrc / "agents").mkdir(parents=True)
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.family = root / "fam.toml"
        self.family.write_text(_tiers_toml(), encoding="utf-8")
        (self.tsrc / "agents" / "probe.tmpl.md").write_text(
            '---\nname: @!arg.name!@\n---\nbody @!some-chunk my_key="x"!@ tail\n', encoding="utf-8"
        )

    def test_underscored_argument_key_no_longer_binds_and_is_refused(self):
        # "some-chunk"'s own body never references my_key, so the only way
        # this ever surfaces is through the marker's own grammar, not through
        # an unknown-placeholder error inside the chunk body.
        chunks = {"some-chunk": {"text": "expanded"}}
        with self.assertRaises(errors.InputError) as caught:
            _quiet(generation.generate, _binding(chunks), self.smap, overlays=None, tuning=_tuning(self.family))
        message = str(caught.exception)
        self.assertIn("templates/agents/probe.tmpl.md", message)
        self.assertIn("my_key", message)
        # Nothing lands: the guard fires before generate writes its target.
        self.assertFalse((self.out / "agents" / "probe.md").exists())


class TestLiteralPinGuard(unittest.TestCase):
    """A pin site must resolve a tier — the standing guard against a template
    landing with a literal pin, which renders the bytes its token would have
    and costs the definition its model scope in silence."""

    TOKENIZED = "---\nname: @!arg.name!@\nmodel: @!dyn.tier-high!@\n---\nbody\n"
    LITERAL = "---\nname: @!arg.name!@\nmodel: opus\n---\nbody\n"
    NO_PIN_SITE = "---\nname: @!arg.name!@\n---\nbody\n"
    LITERAL_PARAM = (
        "+++\n[outputs.probe]\n" 'model = "opus"\n' "+++\n" "---\nname: @!arg.name!@\nmodel: @!arg.model!@\n---\nbody\n"
    )

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.tsrc = root / "templates"
        (self.tsrc / "agents").mkdir(parents=True)
        self.out = root / "out"
        self.out.mkdir()
        self.smap = discovery.surface_map(templates_root=self.tsrc, output_root=self.out)
        self.family = root / "fam.toml"
        self.family.write_text(_tiers_toml(), encoding="utf-8")

    def _generate(self, body):
        (self.tsrc / "agents" / "probe.tmpl.md").write_text(body, encoding="utf-8")
        return _quiet(generation.generate, _binding({}), self.smap, overlays=None, tuning=_tuning(self.family))

    def _rendered(self):
        return (self.out / "agents" / "probe.md").read_text(encoding="utf-8")

    def _refused(self, body):
        with self.assertRaises(errors.InputError) as caught:
            self._generate(body)
        # Nothing lands: the render raises before generate writes its first
        # target, so a refused template leaves no half-tuned tree behind.
        self.assertFalse((self.out / "agents" / "probe.md").exists())
        return str(caught.exception)

    def test_a_literal_pin_is_refused_naming_the_output_and_the_pin(self):
        message = self._refused(self.LITERAL)
        self.assertIn("templates/agents/probe.tmpl.md", message)
        self.assertIn("output 'probe'", message)
        self.assertIn("'model: opus'", message)
        self.assertIn("@!dyn.tier-high!@", message)

    def test_a_literal_pin_bound_as_an_outputs_parameter_is_refused_too(self):
        # The pin is read out of the RENDER, so the two spellings of a pin site
        # are one thing here exactly as they are to the discovery pass.
        self.assertIn("'model: opus'", self._refused(self.LITERAL_PARAM))

    def test_a_tokenized_pin_site_renders(self):
        self.assertTrue(self._generate(self.TOKENIZED))
        self.assertEqual(banners.tuning_claim(self._rendered()).seat, "high")

    def test_an_output_with_no_pin_site_renders(self):
        # The guard is about a pin site that resolves nothing, never about the
        # absence of one: no `model:` key is a property of the output's type.
        self.assertTrue(self._generate(self.NO_PIN_SITE))
        self.assertEqual(banners.tuning_claim(self._rendered()).seat, "none")

    def test_every_shipped_pin_site_resolves_a_tier(self):
        # The guard's positive half, over the real set: the whole tree renders,
        # which under the rule above is itself the assertion that no shipped
        # definition holds a literal pin.
        _, _, renders = _shipped_renders("claude")
        for key, text in renders.items():
            with self.subTest(output=key):
                seat = banners.tuning_claim(text).seat
                if rendering.frontmatter_pin(text) is None:
                    self.assertEqual(seat, "none")
                else:
                    self.assertIn(seat, model_tuning.TIERS)


if __name__ == "__main__":
    unittest.main()
