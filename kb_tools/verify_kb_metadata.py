#!/usr/bin/env python3
"""Mechanical integrity check for the knowledge-base claim-quality framework.

Read-only. Never modifies any file. Reads each document's frontmatter through
``kb_index_lib``, the canonical reader of it.

Seventeen checks, all hard fail-loud:

    0. Quality-block integrity: every ``### Quality`` heading in a
       ``claim-quality.md`` register sits within a ``---``-delimited section
       that also carries the claim's ``## <title>`` heading and its
       ``<!-- id: clm-xxxxxx -->`` marker. An orphan ``### Quality`` block is
       a hard failure. (Not refresh-fixable; delete the orphan or restore the
       missing title/id.)
    1. Tier 1 coverage: every leaf declares its content via at least one of
       ``{claims:, no-claim:, experiment-nodes:}`` (hosting an experiment node
       satisfies coverage on its own). ``claims`` and ``no-claim`` stay mutually
       exclusive with each other; ``experiment-nodes`` is orthogonal and may
       co-exist with either.
    2. Tier 2 coverage: every multi-claim leaf has proximal inline markers
       (``<!-- claim-quality: <id> ... -->``) for each ID in its claims list.
    3. ID uniqueness: no canonical ``<!-- id: clm-xxxxxx -->`` appears twice
       in any ``claim-quality.md`` register.
    4. Orphan refs: every Tier 1 ID resolves to a canonical entry.
    5. Frontmatter presence: every non-excluded .md file has a frontmatter
       block. (Not refresh-fixable for any document, index or leaf: refresh
       splices a field into a block that already exists, so a document with
       no block at all needs one written.) A document still carrying a
       ``0.9.0`` comment block is listed with the block named: no current
       reader takes it as frontmatter, and refresh migrates only a KB stamped
       older, never one document. ``--skip-frontmatter-presence``
       excludes this one check, for graph-init's fused verify pass alone —
       see that flag's help text.
    6. Subtree consistency: each ``kind: index`` file's ``subtree-claims``
       equals the union of leaf claims under its directory; entry-point's
       equals the global union. (refresh-fixable.)
    7. Bidirectional coverage: every canonical ``clm-`` entry is back-linked
       by at least one leaf's frontmatter. An external-work entry is the
       stated exception — no leaf hosts a work — and is covered from the
       other direction instead; see :func:`check_uncited_entries`.
    8. No-claim/claims exclusivity: no leaf carries both fields.
    9. Index files well-formed: each ``.index/*.yaml`` stream exists, every
       line is ``--- `` and a JSON object, and the file ends with exactly one
       ``\\n``. Missing files and EOF defects are refresh-fixable; a malformed
       line is not (indicates a bug or merge corruption).
   10. Index freshness: each ``.index/*.yaml`` matches the canonical
       byte-for-byte serialization of the in-memory record set built from
       the canonical KB sources. (refresh-fixable.)
   11. Index referential integrity: every id referenced in depends-on /
       strengthen-by / cites / subtree-aggregates resolves to a record in
       claims.yaml (which holds claim, framework and external-work nodes),
       and every depends-on edge's target_kind matches the resolved node's
       node_type. Per edge class, which of ``strength`` / ``fraction`` must be
       null and which must carry a value in range is checked here too, and a
       ``demoted`` row's ``origin`` must be one of
       ``kb_schema.DEMOTED_ORIGINS``. (Not refresh-fixable; symptom of a build
       bug or a hand edit.)
   12. Solidity-graph acyclicity: the claim depends-on graph must be a DAG.
       A cycle makes solidity undefined for its members. (Not refresh-fixable;
       the cycle must be broken in the claim depends-on declarations.)
   13. Solidity freshness: every claim entry's on-disk ``solidity`` line and
       the depends-on ``(solidity X)`` annotations must equal what
       ``kb_index_lib.compute_solidity`` derives, and the ``.index/claims.yaml``
       solidity fields must match. ``solidity`` is a derived field — drift
       means refresh has not been run. (refresh-fixable.)
   14. Leaf-references freshness: every claim-quality entry's on-disk
       ``> **Leaf references:**`` footer must equal what
       ``kb_index_lib.build_leaf_references`` derives from the reverse-citation
       map (which leaves host the entry's id). The footer is a derived field;
       a hand-edited, stale, or missing footer is drift. (refresh-fixable.)
   15. Register census: in every ``claim-quality.md`` register the count of
       canonical ``<!-- id: -->`` markers equals the count of records the
       production parser returns, per node kind, AND every marker is the first
       line under its own ``## <title>`` heading. A marker that produces no
       record is a lost entry; a marker bound to the *previous* entry's heading
       produces a record under the wrong title and leaves the counts equal.
       (Not refresh-fixable; restore the heading above the marker.)
   16. Support fan-out reconciliation: the ``supports:`` relationship is the one
       edge the schema records at two authored ends — staged in the ``sup-``
       register entry and declared in the hosting leaf's frontmatter. Where a
       register stages a fan-out for a support whose leaf exists, the two ends
       must name the same beneficiaries at the same on-point fractions. (Not
       refresh-fixable; the two authored blocks disagree.)

Every ``demoted`` edge the registers record is reported as one ``[finding]``
line: structure the KB carries, never a failure, so it changes no exit code.

Checks 15 and 16 are taken in ONE walk of the registers, and that walk is
``kb_index_lib.walk_registers`` — which returns what it found as data.
:func:`check_register_walk` here only decides which of those findings are gate
failures, rather than re-implementing a grammar this toolchain defines once.

Future / queued (not implemented):

* A relative-link integrity check — verify that each Markdown
  cross-reference in a leaf resolves to an existing file, and surface dead
  *forward* links (a foundational common/ or vol1 leaf pointing to a
  not-yet-migrated later-volume leaf) as an optional warning rather than a
  hard failure. Such forward links are intentional threads for later
  cross-reference stitching passes; only their dead-ness is worth flagging,
  not their existence.

A KB in an older metadata format is reported stale and nothing else is
checked: ``kb-refresh`` migrates it. A newer one is refused (exit 2).

Failure categories are tagged refresh-fixable or manual-fix. If any
refresh-fixable failures are present, the report ends with a hint to run
the project's refresh target first; verify is read-only and never auto-fixes.

Run via the project's verify target, or directly::

    python3 -m kb_tools.verify_kb_metadata
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from kb_tools import __version__, kb_index_lib, kb_load, kb_migrate, kb_schema, kb_util

# The KB root this run operates on. Bound in main() — from --kb-root when
# given, else by lazy repo-root discovery (kb_util.kb_root()) — never at
# import time.
KB: Path = None  # type: ignore[assignment]

# Walk-exclusion vocabulary — single-sourced in kb_index_lib.
EXCLUDE_DIRS = kb_index_lib.EXCLUDE_DIRS
EXCLUDE_NAMES = kb_index_lib.EXCLUDE_NAMES

# Navigation convention — single-sourced in the same place, and read from there
# by the survey validator's reachability check and the driver as well, so the
# node one of them calls the root is the node the others do.
ENTRY_POINT_FILENAME = kb_index_lib.ENTRY_POINT_FILENAME
INDEX_FILENAME = kb_index_lib.INDEX_FILENAME

# The id grammar — the hash body and the clm/exp/sup kind tokens — is
# single-sourced in `kb_schema.id_body`; every pattern below adds only its own
# anchors, capture group and comment-marker context. Re-spelling the hash body
# by hand in any of them leaves one file carrying two conventions.
CANONICAL_ID = re.compile(rf"<!-- id: ({kb_schema.id_body('clm')}) -->")
# A claim, support OR external-work entry marker — all three carry a
# `### Quality` block, so the quality-block integrity check accepts any of them.
CANONICAL_ANY_ID = re.compile(rf"<!-- id: ({kb_schema.id_body('clm', 'sup')}|{kb_schema.WORK_ID_RE}) -->")
TIER2_INLINE = re.compile(r"<!--\s*claim-quality:\s*(.*?)\s*-->", re.DOTALL)
ID_RE = re.compile(rf"\b({kb_schema.id_body('clm')})\b")
# Bare-match exp-/sup-id patterns (no capture group).
EXP_ID_RE = re.compile(rf"\b{kb_schema.id_body('exp')}\b")
SUP_ID_RE = re.compile(rf"\b{kb_schema.id_body('sup')}\b")
WORK_ID_RE = re.compile(kb_schema.WORK_ID_RE)


# The 2-dp value formatter is single-sourced in kb_index_lib, so the checker
# reports and the emitter writes the same rendering of the same number.
# Interpolating an on-disk float bare while formatting the expected value
# `{:.2f}` prints "solidity 0.2, expected 0.20" — two identical numbers reading
# as a mismatch, on the very line an operator consults to decide whether refresh
# is broken.
_fmt = kb_index_lib.format_solidity


def set_frontmatter_cmd() -> str:
    """The sanctioned call that stamps a frontmatter block into a document that has none.

    Built from the CLI's own constants like every other rendered invocation in
    this toolchain — a hand-written command line here would advertise a
    spelling the parser need not have.
    """
    return f"{kb_util.invocation()} {kb_util.OP_SET_FRONTMATTER} {kb_util.VALUES_FLAG} <path.toml>"


def strip_code_fences(text: str) -> str:
    """Blank out lines inside fenced code blocks.

    One delegation, one scanner. A private copy here — recognising only
    column-0 triple backticks, say — makes this module disagree with
    ``kb_index_lib`` about what a fence is, in a file that already calls that
    module's version elsewhere.
    """
    return kb_index_lib._strip_code_fences(text)


# One delegation, one reader, like `strip_code_fences` above. A local copy
# handling single-line id-lists only makes this module and the library disagree
# about what a wrapped or YAML-block `claims:` list declares, and the checker
# reads one "claim id" per character.
parse_frontmatter = kb_index_lib.parse_frontmatter


def collect_files() -> list[tuple[Path, dict | None]]:
    out: list[tuple[Path, dict | None]] = []
    for root, dirs, files in os.walk(KB):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith(".md") or f in EXCLUDE_NAMES:
                continue
            p = Path(root) / f
            text = p.read_text(encoding="utf-8")
            out.append((p, parse_frontmatter(text)))
    return out


def collect_canonical_ids() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for p in KB.rglob("claim-quality.md"):
        if any(part in EXCLUDE_DIRS for part in p.relative_to(KB).parts[:-1]):
            continue
        scrubbed = strip_code_fences(p.read_text(encoding="utf-8"))
        for m in CANONICAL_ID.findall(scrubbed):
            out.append((m, str(p.relative_to(KB))))
    return out


# Three authored score fields, one grammar. `strength` is an external work's
# standing (`kb_index_lib.ExternalWork`); it shares the domain and the pending
# literal with the two local-rigor spellings, so it shares the gate.
_CONFIDENCE_LINE_RE = re.compile(r"^\s*-\s+(confidence|quality|strength):\s*(\S.*?)\s*$")


def check_confidence_values():
    """Every authored ``confidence:`` / ``quality:`` / ``strength:`` is a float in [0,1] or *pending*.

    The rubric's named grades are an authoring convention; what is MECHANICAL
    is the range and the pending literal. Unchecked, a typo'd ``3.7`` or
    ``-0.5`` parses, bands, and propagates silently — the parser takes the
    first numeric token and asks nothing else of it.

    Returns (register_path, line, reason) per violation.
    """
    failures: list[tuple[str, int, str]] = []
    for p in sorted(KB.rglob("claim-quality.md")):
        if any(part in EXCLUDE_DIRS for part in p.relative_to(KB).parts[:-1]):
            continue
        text = kb_index_lib._strip_code_fences(p.read_text(encoding="utf-8"))
        for line_no, line in enumerate(text.split("\n"), start=1):
            match = _CONFIDENCE_LINE_RE.match(line)
            if match is None:
                continue
            field, raw = match.group(1), match.group(2)
            if raw == kb_index_lib.PENDING_LITERAL:
                continue
            number = re.match(r"^[-+]?[0-9]*\.?[0-9]+", raw)
            if number is None:
                failures.append(
                    (str(p.relative_to(KB)), line_no, f"{field}: {raw!r} is neither a number nor *pending*")
                )
                continue
            value = float(number.group(0))
            if not 0.0 <= value <= 1.0:
                failures.append((str(p.relative_to(KB)), line_no, f"{field}: {value} is outside [0, 1]"))
    return failures


def check_quality_block_integrity():
    """Every `### Quality` heading must sit in a well-formed claim section.

    Walks each ``claim-quality.md`` register, splits it into ``---``-delimited
    sections (after blanking fenced code blocks so the Quality Convention
    preamble's format-example snippet does not count), and requires that any
    section carrying a ``### Quality`` heading also carries a ``## <title>``
    heading AND a ``<!-- id: clm-xxxxxx -->`` marker. An orphan ``### Quality``
    block — one with no claim title and no canonical id — is a hard failure;
    it is the defect this check makes non-recurring.

    Returns a list of (register_path, line, reason) for each malformed block.
    Line numbers are 1-based and point at the offending ``### Quality``
    heading. Scoped to the registers; the preamble's ``## Quality Convention``
    section is exempt because its example ``### Quality`` lives inside a code
    fence (blanked by ``strip_code_fences``).
    """
    failures: list[tuple[str, int, str]] = []
    for p in sorted(KB.rglob("claim-quality.md")):
        if any(part in EXCLUDE_DIRS for part in p.relative_to(KB).parts[:-1]):
            continue
        rel = str(p.relative_to(KB))
        # Scrub fenced code blocks so the preamble's format-example snippet
        # (a fenced `### Quality` / `<!-- id: clm-xxxxxx -->`) is not parsed
        # as a real claim section.
        lines = strip_code_fences(p.read_text(encoding="utf-8")).splitlines()

        # Split into `---`-delimited sections, tracking 1-based start lines.
        # A bare `---` line is a section separator.
        sections: list[tuple[int, list[str]]] = []
        current: list[str] = []
        current_start = 1
        for lineno, line in enumerate(lines, start=1):
            if line.strip() == "---":
                sections.append((current_start, current))
                current = []
                current_start = lineno + 1
            else:
                current.append(line)
        sections.append((current_start, current))

        for sec_start, sec_lines in sections:
            quality_idx = next(
                (i for i, ln in enumerate(sec_lines) if ln.strip() == "### Quality"),
                None,
            )
            if quality_idx is None:
                continue
            has_title = any(ln.startswith("## ") for ln in sec_lines)
            has_id = any(CANONICAL_ANY_ID.match(ln.strip()) for ln in sec_lines)
            if has_title and has_id:
                continue
            missing = []
            if not has_title:
                missing.append("`## <title>` heading")
            if not has_id:
                missing.append("`<!-- id: clm-... -->` marker")
            failures.append(
                (
                    rel,
                    sec_start + quality_idx,
                    "orphan/malformed `### Quality` block — missing " + " and ".join(missing),
                )
            )
    return failures


def check_frontmatter_presence(files: list[tuple[Path, dict | None]]) -> list[tuple[str, bool]]:
    """Each file without frontmatter, and whether it carries a 0.9.0 comment block instead."""
    return [
        (str(p.relative_to(KB)), kb_migrate.holds_superseded_frontmatter(p.read_text(encoding="utf-8")))
        for p, fm in files
        if fm is None
    ]


def check_tier1_coverage(files: list[tuple[Path, dict | None]]):
    """Leaf coverage: a leaf must declare its content via at least one of
    ``{claims, no-claim, experiment-nodes}``.

    Hosting an experiment node (an ``experiment-nodes`` entry) satisfies
    coverage on its own — a leaf that originates only an experiment needs
    neither ``claims:`` nor ``no-claim:``. ``claims`` and ``no-claim`` remain
    mutually exclusive *with each other*; ``experiment-nodes`` is orthogonal to
    both and may co-exist with either.
    """
    failures = []
    for p, fm in files:
        if fm is None:
            continue
        kind = fm.get("kind")
        if kind != "leaf":
            continue
        has_claims = "claims" in fm and bool(fm["claims"])
        has_no_claim = "no-claim" in fm and bool(fm["no-claim"])
        has_exp = bool(fm.get(kb_schema.EXPERIMENT_NODES_KEY))
        if not has_claims and not has_no_claim and not has_exp:
            failures.append((str(p.relative_to(KB)), f"none of claims / no-claim / {kb_schema.EXPERIMENT_NODES_KEY}"))
        elif has_claims and has_no_claim:
            failures.append((str(p.relative_to(KB)), "BOTH claims and no-claim"))
    return failures


def equation_node_ids(state) -> set[str]:
    """Every claim id whose register title says it stands for a referenced equation.

    The title is where that fact lives, because the node is an ordinary ``clm-``
    entry in every other respect — same prefix, same register, same fields — and
    :func:`kb_schema.equation_label` is the one reading of it, shared with the
    builder that composed it so the two cannot drift apart.
    """
    return {entry.id for entry in state.claim_entries if kb_schema.equation_label(entry.title) is not None}


def check_tier2_coverage(files: list[tuple[Path, dict | None]], equation_ids: set[str]):
    """Marker coverage, over the claims a marker can actually be placed on.

    **An equation node is outside this check at both ends**, and the exemption
    has the same shape as the external work's in :func:`check_uncited_entries`:
    the marker exists to make a claim's position in its document recoverable,
    and an equation's position is its ``\\label`` — which is already in the
    node's title and inside a maths fence in the document, a place no
    block-level metadata may be written without altering the mathematics the
    fence is a guarantee of. So such a node neither needs a marker nor may push
    the document it lands in over the threshold that demands one of every claim
    beside it; a leaf hosting one block claim and four equations is a leaf with
    one claim as far as this rule is concerned, exactly as it was before the
    equations were minted.
    """
    failures = []
    for p, fm in files:
        if fm is None:
            continue
        ids = [i for i in fm.get("claims", []) if i not in equation_ids]
        if len(ids) < 2:
            continue
        text = p.read_text(encoding="utf-8")
        # Scrub the frontmatter block so its own claims line doesn't count
        scrubbed = kb_index_lib.strip_frontmatter(text)
        markers = TIER2_INLINE.findall(scrubbed)
        missing = [i for i in ids if not any(re.search(rf"\b{re.escape(i)}\b", body) for body in markers)]
        if missing:
            failures.append((str(p.relative_to(KB)), ids, missing))
    return failures


def check_id_uniqueness(canonical: list[tuple[str, str]]):
    locations: dict[str, list[str]] = defaultdict(list)
    for cid, path in canonical:
        locations[cid].append(path)
    return {cid: paths for cid, paths in locations.items() if len(paths) > 1}


def check_orphan_refs(files: list[tuple[Path, dict | None]], canonical_set: set[str]):
    orphans: dict[str, list[str]] = defaultdict(list)
    for p, fm in files:
        if fm is None:
            continue
        for i in fm.get("claims", []):
            if i not in canonical_set:
                orphans[i].append(str(p.relative_to(KB)))
    return dict(orphans)


def check_subtree_consistency(state) -> list[tuple[str, list, list]]:
    """Declared ``subtree-claims`` must equal the computed owned union.

    For a ``kind: index`` node that union is the claims of every leaf under its
    directory; for ``kind: entry-point`` it is the whole KB. Both come from
    ``kb_index_lib.compute_subtree_aggregates`` — the SAME shared computation
    refresh writes from, exactly as ``check_subtree_experiments_consistency``
    already does for the experiments half.

    Re-deriving that union locally here would be a second implementation
    nothing makes agree with the emitter's: each free to drift on the next
    change to what counts as a leaf, and a checker that re-derives what the
    emitter derived is not checking the emitter.

    Returns ``(node_path, missing_from_declared, extra_in_declared)`` tuples.
    (refresh-fixable.)
    """
    aggregates = kb_index_lib.compute_subtree_aggregates(state)
    failures: list[tuple[str, list, list]] = []
    for idx in state.indexes:
        expected_claims, _ = aggregates.get(idx.path, ([], []))
        expected = set(expected_claims)
        declared = set(idx.declared_subtree_claims)
        if declared != expected:
            failures.append((idx.path, sorted(expected - declared), sorted(declared - expected)))
    return failures


def check_experiments_ref_integrity(
    files: list[tuple[Path, dict | None]],
    experiment_ids: set[str],
    claim_ids: set[str],
):
    """Every leaf ``experiments:`` ref must resolve to an experiment node.

    A leaf may carry an optional ``experiments: [exp-xxxxxx, ...]`` field that
    REFERENCES experiments it does not own (the analog of ``claims:`` for
    claims). Each referenced id must:

    * be a well-formed ``exp-`` id — the grammar :func:`kb_schema.id_body`
      defines and :data:`EXP_ID_RE` wraps — and
    * resolve to an actual experiment node (an ``exp-id``-declaring leaf).

    Two hard-failure modes are reported per (leaf, id):

    * ``orphan`` — the id matches no experiment node (and is not a known claim
      id either): a dangling reference.
    * ``kind-mismatch`` — the id resolves to a CLAIM (``clm-``) rather than an
      experiment: an id that points at the wrong node class.
    * ``malformed`` — the id is not a syntactically valid exp-id.

    Returns a list of ``(leaf_path, id, reason)`` tuples. Mirrors the style of
    ``check_orphan_refs`` / the index referential-integrity check. NOT
    refresh-fixable — the leaf's ``experiments:`` field must be corrected.
    """
    failures: list[tuple[str, str, str]] = []
    for p, fm in files:
        if fm is None:
            continue
        refs = fm.get("experiments", [])
        if not refs:
            continue
        rel = str(p.relative_to(KB))
        for rid in refs:
            if not EXP_ID_RE.fullmatch(rid):
                if rid in claim_ids or ID_RE.fullmatch(rid):
                    failures.append((rel, rid, "resolves to a claim, not an experiment"))
                else:
                    failures.append((rel, rid, f"malformed exp-id (expected {kb_schema.id_body('exp')})"))
                continue
            if rid not in experiment_ids:
                failures.append((rel, rid, "no such experiment node (orphan reference)"))
    return failures


def check_subtree_experiments_consistency(state) -> list[tuple[str, list, list]]:
    """Declared ``subtree-experiments`` must equal the computed owned union.

    Owned-only, parallel to ``check_subtree_consistency`` for subtree-claims:
    each index / entry-point node's declared ``subtree-experiments`` must equal
    the union of exp-ids OWNED by experiment leaves under it (a leaf's
    ``experiments:`` REFERENCES do NOT contribute). The expected union comes
    from ``kb_index_lib.compute_subtree_aggregates`` — the SAME shared
    computation refresh writes from, so this checker and the emitter cannot
    drift. (refresh-fixable.)

    Returns ``(node_path, missing_from_declared, extra_in_declared)`` tuples.
    """
    aggregates = kb_index_lib.compute_subtree_aggregates(state)
    failures: list[tuple[str, list, list]] = []
    for idx in state.indexes:
        _, expected_exp = aggregates.get(idx.path, ([], []))
        declared = set(idx.declared_subtree_experiments)
        expected = set(expected_exp)
        if declared != expected:
            failures.append(
                (
                    idx.path,
                    sorted(expected - declared),
                    sorted(declared - expected),
                )
            )
    return failures


def check_uncited_entries(canonical: list[tuple[str, str]], files: list[tuple[Path, dict | None]]):
    """Bidirectional coverage: every canonical entry is back-linked by a leaf.

    ``canonical`` is :func:`collect_canonical_ids`' list, which is ``clm-`` ids
    alone, and that scope is the check's whole domain of application.

    **The external work is the stated exception, and it is an exception with
    precedent.** A ``work-`` entry is a register entry like any other, but no
    leaf can ever name it in a ``claims:`` list: the node is a paper this corpus
    does not contain, cited by the claims that rest on it rather than hosted by
    a document. Requiring a hosting leaf would be requiring the corpus to
    contain the thing whose absence the node exists to record. Framework nodes
    are exempt for the same reason and by the same mechanism — they are not
    register entries at all — so this is one more node kind outside the
    leaf-hosting relation rather than a schema without precedent. What stands in
    for coverage on a work is :func:`kb_index_lib._assert_work_node_coverage`,
    which is the other direction: every ``rests-on`` edge's target has an entry.
    """
    cited: set[str] = set()
    for _, fm in files:
        if fm:
            cited.update(fm.get("claims", []))
    return [(cid, path) for cid, path in canonical if cid not in cited]


def _index_records(name: str) -> list[dict]:
    """The index stream ``name``'s records, ``[]`` where it is missing; bad lines are the well-formed check's."""
    try:
        records, _ = kb_load.read_index(KB, name)
    except FileNotFoundError:
        return []
    return records


def check_index_well_formed():
    """Validate each index stream: exists, every line a record, clean EOF.

    Returns (missing, malformed, eof_defects):

    * ``missing``: list of stream names absent from disk. Refresh-fixable.
    * ``malformed``: list of (name, lineno, detail) for lines that are not
      ``--- `` and a JSON object. NOT refresh-fixable; signals a deeper bug.
    * ``eof_defects``: list of (name, reason) for files with a missing or
      doubled trailing newline. Refresh-fixable.
    """
    missing: list[str] = []
    malformed: list[tuple[str, int, str]] = []
    eof_defects: list[tuple[str, str]] = []
    for name in kb_index_lib.INDEX_FILES:
        path = kb_load.index_path(KB, name)
        if not path.exists():
            missing.append(name)
            continue
        raw = path.read_text(encoding="utf-8")
        if not raw:
            # An empty stream holds no records; whether it should is the
            # freshness check's question.
            continue
        if not raw.endswith("\n"):
            eof_defects.append((name, "missing final newline"))
        elif raw.endswith("\n\n"):
            eof_defects.append((name, "multiple trailing newlines"))
        _, problems = kb_load.read_index(KB, name)
        malformed.extend((name, problem.line, problem.detail) for problem in problems)
    return missing, malformed, eof_defects


def check_index_fresh():
    """Diff each on-disk index stream against canonical serialization of expected records.

    Returns a list of (name, expected_count, actual_count) for files
    whose bytes diverge from canonical. Refresh-fixable.

    Files that are missing are skipped here — the well-formed check already
    surfaces those.
    """
    state = kb_index_lib.discover_kb(KB, diagnostic_stream=None)
    expected = kb_index_lib.build_all_records(state)

    drift: list[tuple[str, int, int]] = []
    for name in kb_index_lib.INDEX_FILES:
        path = kb_load.index_path(KB, name)
        if not path.exists():
            continue
        expected_text = kb_index_lib.serialize_records(expected[name])
        actual_text = path.read_text(encoding="utf-8")
        if actual_text == expected_text:
            continue
        expected_count = len(expected[name])
        actual_count = len(_index_records(name))
        drift.append((name, expected_count, actual_count))
    return drift, expected


def check_index_referential_integrity():
    """Every id referenced in any non-claims index stream resolves in claims.yaml.

    ``claims.yaml`` is a type-tagged union over
    :data:`kb_schema.NODE_KINDS`. This check spans every kind in it:

    * ``depends-on`` ``source`` must resolve to a record (it is always a
      claim); ``target`` must resolve to a record AND its ``target_kind``
      must equal the resolved record's ``node_type``.
    * ``strengthen-by`` / ``cites`` ``claim_id`` and ``subtree-aggregates``
      ``subtree_claims`` ids must each resolve to a record. (These reference
      claim ids only, which are a subset of the node id space.)

    Returns a list of (short_name, id, location) tuples for orphan or
    kind-mismatched references. NOT refresh-fixable; indicates a build bug
    (refresh should never emit one).

    A location is the record's 1-based position in its stream. Skipped
    silently if claims.yaml is missing or a record in it carries no id — the
    well-formed check surfaces a missing stream and a malformed line.
    """
    claim_records = _index_records("claims")
    if not claim_records:
        return []
    try:
        node_type_by_id: dict[str, str] = {rec["id"]: rec.get("node_type", "claim") for rec in claim_records}
    except KeyError:
        return []

    canonical = set(node_type_by_id)
    violations: list[tuple[str, str, str]] = []

    def _check_lines(short: str, key_funcs):
        for number, rec in enumerate(_index_records(short), start=1):
            for key, getter in key_funcs:
                ids = getter(rec)
                for cid in ids:
                    if cid not in canonical:
                        violations.append((short, cid, f"record {number}, {key}"))

    _check_lines(
        "depends-on",
        [
            ("source", lambda r: [r.get("source")] if r.get("source") else []),
            ("target", lambda r: [r.get("target")] if r.get("target") else []),
        ],
    )
    _check_lines(
        "strengthen-by",
        [("claim_id", lambda r: [r.get("claim_id")] if r.get("claim_id") else [])],
    )
    _check_lines(
        "cites",
        [("claim_id", lambda r: [r.get("claim_id")] if r.get("claim_id") else [])],
    )
    _check_lines(
        "supported-by",
        [
            ("claim_id", lambda r: [r.get("claim_id")] if r.get("claim_id") else []),
            ("sup_id", lambda r: [r.get("sup_id")] if r.get("sup_id") else []),
        ],
    )
    _check_lines(
        "subtree-aggregates",
        [
            ("subtree_claims", lambda r: list(r.get("subtree_claims") or [])),
            (
                "subtree_experiments",
                lambda r: list(r.get("subtree_experiments") or []),
            ),
        ],
    )

    # Per-edge consistency, relation-aware (depends vs strengthens).
    #
    # * depends:     source resolves to a claim OR a support (a support's own
    #                deps are depends edges sourced at the sup-id); target
    #                resolves to any node; target_kind == resolved target
    #                node_type (kind-match); strength is null; fraction is null.
    # * strengthens: source resolves to an experiment; target resolves to a
    #                claim AND target_kind == "claim"; an experiment node is
    #                never an edge target; strength is non-null and in [0, 1];
    #                fraction null.
    # * supports:    source resolves to a SUPPORT; target resolves to a claim
    #                AND target_kind == "claim"; strength is null; fraction is
    #                in [0, 1] OR the literal "*pending*".
    for number, rec in enumerate(_index_records("depends-on"), start=1):
        source = rec.get("source")
        target = rec.get("target")
        kind = rec.get("target_kind")
        relation = rec.get("relation")
        strength = rec.get("strength")
        fraction = rec.get("fraction")
        src_type = node_type_by_id.get(source)
        tgt_type = node_type_by_id.get(target)

        if relation == "supports":
            if src_type is not None and src_type != "support":
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, supports edge source resolves to " f"{src_type!r}, expected support",
                    )
                )
            if tgt_type is not None and tgt_type != "claim":
                violations.append(
                    (
                        "depends-on",
                        target,
                        f"record {number}, supports edge target resolves to " f"{tgt_type!r}, expected claim",
                    )
                )
            if kind != "claim":
                violations.append(
                    ("depends-on", target, f"record {number}, supports edge target_kind {kind!r} " f"!= 'claim'")
                )
            if strength is not None:
                violations.append(
                    ("depends-on", source, f"record {number}, supports edge has non-null strength " f"{strength!r}")
                )
            # A pending on-point fraction (literal "*pending*") is a valid
            # authored value (intended-but-unassessed); it is distinct from
            # a depends edge's null fraction. A numeric fraction must be in
            # [0, 1]; null or out-of-range is a violation.
            if fraction == kb_index_lib.PENDING_LITERAL:
                pass
            elif not isinstance(fraction, (int, float)) or isinstance(fraction, bool) or not (0.0 <= fraction <= 1.0):
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, supports edge on-point fraction " f"{fraction!r} not in [0, 1] or *pending*",
                    )
                )
        elif relation == "strengthens":
            if src_type is not None and src_type != "experiment":
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, strengthens edge source resolves to " f"{src_type!r}, expected experiment",
                    )
                )
            if tgt_type is not None and tgt_type != "claim":
                violations.append(
                    (
                        "depends-on",
                        target,
                        f"record {number}, strengthens edge target resolves to " f"{tgt_type!r}, expected claim",
                    )
                )
            if kind != "claim":
                violations.append(
                    ("depends-on", target, f"record {number}, strengthens edge target_kind {kind!r} " f"!= 'claim'")
                )
            # A strengthens edge carries no pending form, so the value is
            # required; its magnitude is checked here because a strength
            # outside [0, 1] lifts the claim off the build-band ladder.
            if strength is None:
                violations.append(("depends-on", source, f"record {number}, strengthens edge has null strength"))
            elif not isinstance(strength, (int, float)) or isinstance(strength, bool) or not (0.0 <= strength <= 1.0):
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, strengthens edge strength {strength!r} not in [0, 1]",
                    )
                )
        elif relation == "rests-on":
            # The off-graph endcap. Which of the two edge-level scores may
            # be non-null is the whole of what distinguishes it from the
            # classes above: `strength` is null — a work's standing lives on
            # the node, not on each of its pairings — and `fraction` carries
            # the pairing's applicability, in [0, 1] or the pending literal.
            if src_type is not None and src_type != "claim":
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, rests-on edge source resolves to {src_type!r}, expected claim",
                    )
                )
            if tgt_type is not None and tgt_type != "work":
                violations.append(
                    (
                        "depends-on",
                        target,
                        f"record {number}, rests-on edge target resolves to {tgt_type!r}, expected work",
                    )
                )
            if kind != "work":
                violations.append(
                    ("depends-on", target, f"record {number}, rests-on edge target_kind {kind!r} != 'work'")
                )
            if strength is not None:
                violations.append(
                    ("depends-on", source, f"record {number}, rests-on edge has non-null strength {strength!r}")
                )
            if fraction == kb_index_lib.PENDING_LITERAL:
                pass
            elif not isinstance(fraction, (int, float)) or isinstance(fraction, bool) or not (0.0 <= fraction <= 1.0):
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, rests-on edge applicability {fraction!r} not in [0, 1] or *pending*",
                    )
                )
        elif relation in ("references", "demoted"):
            # A cross-reference the corpus states, or a `depends` edge the
            # build's cycle breaking cut: one claim naming another either way.
            # Neither carries an edge-level score — there is nothing to grade
            # about a mention — and neither is under the acyclicity
            # constraint, which is checked over `depends` alone.
            if src_type is not None and src_type != "claim":
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, {relation} edge source resolves to {src_type!r}, expected claim",
                    )
                )
            if tgt_type is not None and tgt_type != "claim":
                violations.append(
                    (
                        "depends-on",
                        target,
                        f"record {number}, {relation} edge target resolves to {tgt_type!r}, expected claim",
                    )
                )
            if kind != "claim":
                violations.append(
                    ("depends-on", target, f"record {number}, {relation} edge target_kind {kind!r} != 'claim'")
                )
            if strength is not None:
                violations.append(
                    ("depends-on", source, f"record {number}, {relation} edge has non-null strength {strength!r}")
                )
            if fraction is not None:
                violations.append(
                    ("depends-on", source, f"record {number}, {relation} edge has non-null fraction {fraction!r}")
                )
            if relation == "demoted" and rec.get("origin") not in kb_schema.DEMOTED_ORIGINS:
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, demoted edge origin {rec.get('origin')!r} is not one of "
                        f"{', '.join(kb_schema.DEMOTED_ORIGINS)}",
                    )
                )
        elif relation == "depends":
            if src_type is not None and src_type not in ("claim", "support"):
                violations.append(
                    (
                        "depends-on",
                        source,
                        f"record {number}, depends edge source resolves to " f"{src_type!r}, expected claim or support",
                    )
                )
            if tgt_type is not None and kind != tgt_type:
                violations.append(
                    ("depends-on", target, f"record {number}, target_kind {kind!r} != " f"node_type {tgt_type!r}")
                )
            if tgt_type == "experiment":
                violations.append(
                    (
                        "depends-on",
                        target,
                        f"record {number}, depends edge targets an experiment "
                        f"node (experiments are never edge targets)",
                    )
                )
            if strength is not None:
                violations.append(
                    ("depends-on", source, f"record {number}, depends edge has non-null strength " f"{strength!r}")
                )
        else:
            violations.append(("depends-on", source or "?", f"record {number}, unknown relation {relation!r}"))

    # exp-id format + experiment-node placement: every experiment node id must
    # match the exp- id grammar, and no experiment id may appear in cites /
    # subtree-aggregates (those reference claim ids only). depends-on target
    # placement is covered above.
    for nid, ntype in node_type_by_id.items():
        if ntype == "experiment" and not EXP_ID_RE.fullmatch(nid):
            violations.append(("claims", nid, f"experiment node id is not {kb_schema.id_body('exp')}"))
        if ntype == "support" and not SUP_ID_RE.fullmatch(nid):
            violations.append(("claims", nid, f"support node id is not {kb_schema.id_body('sup')}"))
        if ntype == "work" and not WORK_ID_RE.fullmatch(nid):
            violations.append(("claims", nid, f"external-work node id is not {kb_schema.WORK_ID_RE}"))

    experiment_ids = {nid for nid, t in node_type_by_id.items() if t == "experiment"}
    for short in ("cites", "subtree-aggregates"):
        for number, rec in enumerate(_index_records(short), start=1):
            if short == "cites":
                ids = [rec.get("claim_id")]
            else:
                ids = list(rec.get("subtree_claims") or [])
            for cid in ids:
                if cid in experiment_ids:
                    violations.append(
                        (short, cid, f"record {number}, experiment node referenced where a " f"claim id is expected")
                    )
            # subtree-aggregates subtree_experiments holds exp-ids only; each
            # must resolve to an experiment node (a claim id here is a kind
            # mismatch — the inverse of the subtree_claims check above).
            if short == "subtree-aggregates":
                for eid in list(rec.get("subtree_experiments") or []):
                    if eid in node_type_by_id and eid not in experiment_ids:
                        violations.append(
                            (
                                short,
                                eid,
                                f"record {number}, subtree_experiments id resolves to "
                                f"{node_type_by_id[eid]!r}, expected experiment",
                            )
                        )

    # supported-by kind-match: claim_id must resolve to a claim, sup_id to a
    # support. The reverse view is untraversed for solidity, but
    # a kind mismatch still signals a build bug.
    for number, rec in enumerate(_index_records("supported-by"), start=1):
        cid = rec.get("claim_id")
        sid = rec.get("sup_id")
        if cid in node_type_by_id and node_type_by_id[cid] != "claim":
            violations.append(
                (
                    "supported-by",
                    cid,
                    f"record {number}, claim_id resolves to " f"{node_type_by_id[cid]!r}, expected claim",
                )
            )
        if sid in node_type_by_id and node_type_by_id[sid] != "support":
            violations.append(
                (
                    "supported-by",
                    sid,
                    f"record {number}, sup_id resolves to " f"{node_type_by_id[sid]!r}, expected support",
                )
            )

    return violations


def check_leaf_references_fresh(state) -> list[tuple[str, str, str, str]]:
    """Verify each entry's on-disk leaf-references footer matches the derived one.

    The ``> **Leaf references:**`` footer is a derived field — recomputed,
    never authored:
    regenerated by the refresh target from the reverse-citation map
    (which leaves host the entry's id) and gated here. The reverse map comes
    from the SAME ``kb_index_lib.build_leaf_references`` the refresher writes
    from, so this checker and the emitter cannot drift.

    For every ``clm-`` / ``sup-`` entry in every register, locates the footer
    line in the band between the entry's ``<!-- id: ... -->`` marker and its
    ``### Quality`` heading and compares it byte-for-byte to the regenerated
    footer. Three drift kinds (all refresh-fixable):

    * a present footer whose text disagrees with the regenerated one (the rot
      this gate eliminates — a hand-edited or stale footer);
    * a MISSING footer where the entry should carry one;
    * an entry whose id has no citing leaf at all (the footer regenerates to the
      explicit ``*(none …)*`` marker; bidirectional-coverage flags the deeper
      defect, but the footer drift is still reported).

    Returns ``(register_path, node_id, got, want)`` tuples. ``got`` is the
    on-disk footer (or ``"(missing)"``); ``want`` is the regenerated footer.
    Code fences are scrubbed so a fenced example footer is never parsed.
    """
    leaf_references = kb_index_lib.build_leaf_references(state)
    drift: list[tuple[str, str, str, str]] = []
    for p in sorted(KB.rglob("claim-quality.md")):
        if any(part in EXCLUDE_DIRS for part in p.relative_to(KB).parts[:-1]):
            continue
        register_rel = p.relative_to(KB).as_posix()
        text = p.read_text(encoding="utf-8")
        lines = text.split("\n")

        # The band and the footer line come from the library locator the
        # EMITTER also calls, so refresh and verify cannot reach different
        # conclusions about which line is this entry's footer. That split makes
        # refresh overwrite a fenced example while this gate reports the real
        # footer missing on every run.
        for node_id, band in kb_index_lib.locate_leaf_reference_footers(text).items():
            want = kb_index_lib.render_leaf_references(register_rel, leaf_references.get(node_id, []))
            if band.footer_line is None:
                drift.append((register_rel, node_id, "(missing)", want))
                continue
            got = lines[band.footer_line]
            if got != want:
                drift.append((register_rel, node_id, got, want))
    return drift


def _fraction_text(fraction) -> str:
    """Render one on-point fraction, or say the end did not record it."""
    if fraction is None:
        return "(absent)"
    if fraction is kb_index_lib.PENDING_FRACTION:
        return kb_index_lib.PENDING_LITERAL
    return kb_index_lib.format_solidity(fraction)


def _fan_out_reason(record) -> str:
    """Say which end of a double-entered fan-out edge is missing or differs."""
    if record.declared is None:
        return (
            f"staged in the register at f={_fraction_text(record.staged)}, missing "
            f"from the hosting leaf's `supports:` block — the claim graph carries "
            f"no such edge"
        )
    if record.staged is None:
        return (
            f"declared by the hosting leaf at f={_fraction_text(record.declared)}, "
            f"missing from the register's staged `- supports:` block"
        )
    return (
        f"register stages f={_fraction_text(record.staged)}, hosting leaf declares "
        f"f={_fraction_text(record.declared)} — the leaf's value is the one the "
        f"graph uses"
    )


def check_register_walk(state):
    """The census, its binding half, and the fan-out reconciliation — one walk.

    A thin consumer: the walk itself is
    :func:`kb_index_lib.walk_registers`, which reads each register once and
    returns what it found as data. This function only decides which of those
    findings are gate failures — the same split ``check_subtree_consistency``
    and ``check_solidity_cycle`` already keep with their library computations,
    and the reason the claim-graph renderer can ask the same question without
    re-walking the registers behind this module's back.

    The three failure classes, and why each is one:

    * **census** — a canonical marker that produces no record is an entry the
      KB has lost. Enforcing that rule only on the hot path of a write leaves a
      KB nobody is writing into unmeasured, so its markers can outnumber its
      records with every gate green; this gate measures it on every run.
    * **binding** — a marker bound to the WRONG heading leaves
      the counts equal and every title in the file off by one entry, so the
      count alone cannot see it.
    * **fan-out** — where a support's two authored ends are both live, they are
      double bookkeeping and must agree. A register that stages nothing is not
      participating (staging is optional, and a fan-out authored only in its
      leaf is the ordinary case), and staged pairs with no hosting leaf yet are
      the documented pre-leaf stage — neither is a defect, and
      :attr:`kb_index_lib.FanOutRecord.double_entered` is what says so.

    None of the three is refresh-fixable: all three are authored layout or
    authored content, and ``refresh`` writes derived fields only.
    """
    return kb_index_lib.walk_registers(state, KB)


def check_solidity_cycle(state) -> list[str]:
    """Detect a cycle in the claim depends-on graph.

    ``solidity`` is computed bottom-up over the claim depends-on DAG, and the
    cycle check is that walk's — every claim and support is a node, so a cycle
    is caught whether or not its members carry a score yet. Returns the sorted
    list of cycle-member claim ids (empty when the graph is acyclic). Not
    refresh-fixable — the cycle must be broken in the claim declarations.
    """
    try:
        kb_index_lib.compute_solidity(state.claim_entries, state.experiments, state.supports, state.works)
    except kb_index_lib.SolidityCycleError as exc:
        return exc.cycle_members
    return []


def _approx(a: float | None, b: float | None) -> bool:
    """Compare two 2-dp solidity values with a tiny tolerance."""
    if a is None or b is None:
        return a is b
    return abs(a - b) < 1e-9


def check_solidity_fresh(state):
    """Verify on-disk solidity matches ``compute_solidity``'s derived output.

    ``solidity``, the build-status phrase, and depends-on ``(solidity X)``
    annotations are derived fields — regenerated by the refresh target.
    This check recomputes them and diffs against what is written on disk.

    Three drift kinds are reported (all refresh-fixable):

    * ``line``  — a claim entry's ``- solidity:`` value or build-status phrase
      disagrees with the computed value.
    * ``annotation`` — a depends-on ``(solidity X)`` annotation disagrees with
      its target claim's computed solidity.
    * ``index`` — a ``claims.yaml`` record's ``solidity`` field disagrees with
      the computed value.

    Returns ``(line_drift, annotation_drift, index_drift)``. A claim with no
    computable solidity — its confidence is ``*pending*`` OR a dependency is
    ``*pending*`` (pending-ness propagates transitively, like NaN) — must
    carry the ``*pending*`` solidity line on disk; a numeric on-disk value
    for such a claim IS drift (a stale value left behind after a dependency
    went pending). Returns empty lists when the graph has a cycle (the cycle
    check already fails loudly in that case).
    """
    try:
        full = kb_index_lib.compute_solidity_full(state.claim_entries, state.experiments, state.supports, state.works)
    except kb_index_lib.SolidityCycleError:
        return [], [], []
    solidity = {cid: r.final for cid, r in full.items() if r.final is not None}
    sup_solidity = {sid: sol for sid, sol in full.sup_solidity.items() if sol is not None}

    line_drift: list[tuple[str, str, str]] = []
    annotation_drift: list[tuple[str, str, str, str]] = []

    # Support entries carry the same derived ``- solidity:`` line + claim-target
    # depends-on annotations; their solidity is sup_solidity.
    for sup in state.supports:
        computed = sup_solidity.get(sup.id)
        if computed is None:
            if sup.solidity is not None:
                line_drift.append((sup.id, f"solidity {_fmt(sup.solidity)}", "expected *pending*"))
        elif not _approx(sup.solidity, computed):
            line_drift.append((sup.id, f"solidity {_fmt(sup.solidity)}", f"expected {_fmt(computed)}"))
        else:
            # A support has no experimental branch: its trace is the plain
            # weakest link over its own quality and dep finals.
            want_trace = kb_index_lib.render_min_trace(sup.quality, kb_index_lib.min_dependency_solidity(sup, solidity))
            if sup.solidity_trace != want_trace:
                line_drift.append(
                    (
                        sup.id,
                        f"trace {sup.solidity_trace.strip() or '(none)'}",
                        f"expected {want_trace.strip() or '(none)'}",
                    )
                )
        for edge in sup.depends_on:
            if edge.target_kind != "claim":
                continue
            target_solidity = solidity.get(edge.target)
            if target_solidity is None:
                if edge.target_solidity_recorded is not None:
                    annotation_drift.append(
                        (sup.id, edge.target, f"recorded {_fmt(edge.target_solidity_recorded)}", "expected *pending*")
                    )
                continue
            if edge.target_solidity_recorded is None:
                continue
            if not _approx(edge.target_solidity_recorded, target_solidity):
                annotation_drift.append(
                    (
                        sup.id,
                        edge.target,
                        f"recorded {_fmt(edge.target_solidity_recorded)}",
                        f"expected {_fmt(target_solidity)}",
                    )
                )

    for entry in state.claim_entries:
        computed = solidity.get(entry.id)
        if computed is None:
            # No computable solidity (pending confidence OR a pending
            # dependency): the on-disk solidity must be the *pending* form
            # (parsed as None). A numeric on-disk value is stale drift.
            if entry.solidity is not None:
                line_drift.append(
                    (
                        entry.id,
                        f"solidity {_fmt(entry.solidity)}",
                        "expected *pending*",
                    )
                )
            continue
        expected_phrase = kb_index_lib.build_status_phrase(computed)
        if not _approx(entry.solidity, computed):
            line_drift.append(
                (
                    entry.id,
                    f"solidity {_fmt(entry.solidity)}",
                    f"expected {_fmt(computed)}",
                )
            )
        elif entry.build_status != expected_phrase:
            line_drift.append(
                (
                    entry.id,
                    f"build-status {entry.build_status!r}",
                    f"expected {expected_phrase!r}",
                )
            )
        else:
            # The arithmetic trace is a derived field like the value and the
            # phrase, and is checked like them. Left unread, a trace can
            # contradict its own value, be hand-mangled, or be deleted outright
            # with this gate still passing — and then a green verify does not
            # imply refresh is a fixed point.
            want_trace = kb_index_lib.render_solidity_trace(full[entry.id])
            if entry.solidity_trace != want_trace:
                line_drift.append(
                    (
                        entry.id,
                        f"trace {entry.solidity_trace.strip() or '(none)'}",
                        f"expected {want_trace.strip() or '(none)'}",
                    )
                )
        # Depends-on (solidity X) annotation freshness.
        for edge in entry.depends_on:
            if edge.target_kind != "claim":
                continue
            target_solidity = solidity.get(edge.target)
            if target_solidity is None:
                # Target has no computable solidity (pending confidence OR a
                # pending dependency). Its annotation must be the *pending*
                # form (parsed as None); a stale numeric value is drift.
                if edge.target_solidity_recorded is not None:
                    annotation_drift.append(
                        (
                            entry.id,
                            edge.target,
                            f"recorded {_fmt(edge.target_solidity_recorded)}",
                            "expected *pending*",
                        )
                    )
                continue
            if edge.target_solidity_recorded is None:
                continue  # no annotation present — nothing to verify
            if not _approx(edge.target_solidity_recorded, target_solidity):
                annotation_drift.append(
                    (
                        entry.id,
                        edge.target,
                        f"recorded {_fmt(edge.target_solidity_recorded)}",
                        f"expected {_fmt(target_solidity)}",
                    )
                )

    # claims.yaml solidity field freshness.
    index_drift: list[tuple[str, str, str]] = []
    for rec in _index_records("claims"):
        node_type = rec.get("node_type", "claim")
        if node_type == "support":
            # A support record's solidity must equal its computed
            # sup_solidity (null when pending).
            sid = rec.get("id")
            computed = sup_solidity.get(sid)
            if computed is None:
                if rec.get("solidity") is not None:
                    index_drift.append((sid, f"solidity {_fmt(rec.get('solidity'))}", "expected null"))
            elif not _approx(rec.get("solidity"), computed):
                index_drift.append((sid, f"solidity {_fmt(rec.get('solidity'))}", f"expected {_fmt(computed)}"))
            continue
        if node_type != "claim":
            continue
        cid = rec.get("id")
        computed = solidity.get(cid)
        if computed is None:
            # No computable solidity: the record's solidity must be
            # null. A numeric value is stale drift.
            if rec.get("solidity") is not None:
                index_drift.append(
                    (
                        cid,
                        f"solidity {_fmt(rec.get('solidity'))}",
                        "expected null",
                    )
                )
            continue
        if not _approx(rec.get("solidity"), computed):
            index_drift.append(
                (
                    cid,
                    f"solidity {_fmt(rec.get('solidity'))}",
                    f"expected {_fmt(computed)}",
                )
            )

    return line_drift, annotation_drift, index_drift


def main(argv: list[str] | None = None) -> int:
    global KB
    parser = argparse.ArgumentParser(description="Mechanical KB claim-quality and derived-index verifier.")
    parser.add_argument("--version", action="version", version=f"%(prog)s (kb_tools {__version__})")
    parser.add_argument(
        "--kb-root",
        type=Path,
        default=None,
        help=(
            "KB root directory to operate on. Defaults to the repo-root KB "
            "directory (resolved via kb_util). Used by tests to point "
            "the verifier at a synthetic fixture KB instead of the canonical one."
        ),
    )
    parser.add_argument(
        "--skip-frontmatter-presence",
        action="store_true",
        help=(
            "Skip check 5 (frontmatter presence) alone. For graph-init's fused verify pass "
            "only: kb_docgraph's tree carries no frontmatter block by contract (SPEC.md, "
            "Document-Tree Contract point 14), so the check fails by construction on the "
            "freshly-seeded spine graph-init verifies, before any claim-graph stage has "
            "stamped one. Every other caller of kb-verify — the runner target, phase-3a's "
            "gate — keeps this check as a real gate; it is not disabled globally."
        ),
    )
    args = parser.parse_args(argv)
    if args.kb_root is not None:
        KB = args.kb_root
        # kb-root/ sits directly under the repo root by convention, so the
        # runner-hint probe looks beside an explicit --kb-root.
        hint_root = KB.parent
    else:
        try:
            hint_root = kb_util.find_repo_root()
        except kb_util.RepoRootError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 2
        KB = kb_util.kb_root(hint_root)
    refresh_hint = kb_util.refresh_cmd(hint_root)

    if not KB.is_dir():
        print(f"FAIL: KB directory {KB} not found.", file=sys.stderr)
        return 2
    unmigrated = kb_index_lib.unmigrated_agents_file(KB)
    if unmigrated is not None:
        print(f"FAIL: {unmigrated}", file=sys.stderr)
        return 2
    # The format first: a newer KB is not read at all, and an older one is
    # stale as a whole — every derived byte is in a form refresh rewrites — so
    # nothing below would report anything refresh does not already fix.
    try:
        kb_format = kb_load.open_kb(KB)
    except kb_load.FormatRefusal as refusal:
        print(f"FAIL: {refusal}", file=sys.stderr)
        return 2
    if not kb_format.current:
        print(
            f"\n[FAIL] index stale: the KB's metadata is in format {kb_format.version}, and this kb_tools "
            f"reads and writes {kb_schema.FORMAT_VERSION}. No other check ran."
        )
        print(f"  -> Refresh-fixable: run `{refresh_hint}`, which migrates the KB, then re-run verify.")
        print("\n[claim-quality] FAIL — fix the above and re-run.")
        return 1

    files = collect_files()
    canonical = collect_canonical_ids()
    canonical_set = {cid for cid, _ in canonical}
    kb_state = kb_index_lib.discover_kb(KB, diagnostic_stream=None)

    if args.skip_frontmatter_presence:
        fm_missing: list[tuple[str, bool]] = []
        print(
            "[claim-quality] NOTE: check 5 (frontmatter presence) skipped by "
            "--skip-frontmatter-presence — this run verifies the claim-graph spine over the "
            "document tree, not whether the KB is complete."
        )
    else:
        fm_missing = check_frontmatter_presence(files)
    quality_block_failures = check_quality_block_integrity()
    confidence_failures = check_confidence_values()
    t1_failures = check_tier1_coverage(files)
    t2_failures = check_tier2_coverage(files, equation_node_ids(kb_state))
    id_dupes = check_id_uniqueness(canonical)
    orphans = check_orphan_refs(files, canonical_set)
    subtree_failures = check_subtree_consistency(kb_state)
    uncited = check_uncited_entries(canonical, files)

    n_files = len(files)
    n_with_fm = sum(1 for _, fm in files if fm is not None)
    n_leaves = sum(1 for _, fm in files if fm and fm.get("kind") == "leaf")
    n_with_claims = sum(1 for _, fm in files if fm and fm.get("claims"))
    n_no_claim = sum(1 for _, fm in files if fm and fm.get("no-claim"))
    n_multi = sum(1 for _, fm in files if fm and len(fm.get("claims", [])) >= 2)

    print(
        f"[claim-quality] Scanned {n_files} files "
        f"({n_with_fm} with frontmatter, {n_leaves} leaves, "
        f"{n_with_claims} with claims, {n_no_claim} no-claim, "
        f"{n_multi} multi-claim) and {len(canonical)} canonical entries."
    )

    # Acyclicity, before anything derived from the graph is asked for. A cycle
    # leaves solidity undefined, so every check below it either recomputes over
    # the cycle and raises out of the run — `check_index_fresh` reaches
    # `compute_solidity_full` — or compares against a value that does not
    # exist. Report the cycle and stop, rather than ending in a traceback with
    # no [FAIL] line at all.
    solidity_cycle = check_solidity_cycle(kb_state)
    if solidity_cycle:
        print(f"\n[FAIL] claim depends-on graph has a cycle ({len(solidity_cycle)} claim(s) involved):")
        for cid in solidity_cycle:
            print(f"  {cid}")
        print(
            "  -> solidity is undefined for cycle members. Not refresh-fixable; "
            "break the cycle in the claim depends-on declarations. This run "
            "reports nothing else — re-run for the rest of the checks once the "
            "graph is acyclic."
        )
        print("\n[claim-quality] FAIL — fix the above and re-run.")
        return 1

    # Index-state checks.
    missing_index, malformed_index, eof_defects = check_index_well_formed()
    fresh_drift, expected_records = check_index_fresh()
    ref_violations = check_index_referential_integrity()

    # Solidity content. ``solidity`` is a derived field; this verifies the
    # on-disk values match what ``compute_solidity`` derives.
    sol_line_drift, sol_anno_drift, sol_index_drift = check_solidity_fresh(kb_state)

    # Leaf-references footer freshness. The `> **Leaf references:**` footer is a
    # derived field, never authored; this recomputes it from the reverse-citation
    # map and diffs against on-disk. A hand-edited or stale footer is drift.
    leaf_ref_drift = check_leaf_references_fresh(kb_state)

    # One walk of the registers, three questions of the same bytes: the census,
    # its binding half, and the two-end reconciliation of the `supports:`
    # fan-out. See `check_register_walk`.
    register_walk = check_register_walk(kb_state)

    # Experiments-reference checks (the optional `experiments:` leaf field):
    # every reference must resolve to an experiment node, and the derived
    # subtree-experiments aggregate must match the owned union.
    experiment_ids = {exp.id for exp in kb_state.experiments}
    claim_ids = {entry.id for entry in kb_state.claim_entries}
    exp_ref_failures = check_experiments_ref_integrity(files, experiment_ids, claim_ids)
    subtree_exp_failures = check_subtree_experiments_consistency(kb_state)

    # Index summary line — counts come from the canonical (expected) record
    # set so the line is meaningful even when on-disk files are stale.
    # claims.yaml is a type-tagged union; report the node-type breakdown.
    node_type_counts = Counter(rec.get("node_type", "claim") for rec in expected_records["claims"])
    # The breakdown iterates the vocabulary, so it names every kind the total
    # counts and reports an unpopulated one as zero rather than omitting it.
    breakdown = " / ".join(
        f"{node_type_counts.get(kind, 0)} {kb_schema.node_kind_plural(kind)}" for kind in kb_schema.NODE_KINDS
    )
    print(
        f"[index] {len(kb_index_lib.INDEX_FILES)} index streams "
        f"({len(expected_records['claims'])} nodes: {breakdown}, "
        f"{len(expected_records['depends-on'])} depends-on, "
        f"{len(expected_records['strengthen-by'])} strengthen-by, "
        f"{len(expected_records['supported-by'])} supported-by, "
        f"{len(expected_records['cites'])} citations, "
        f"{len(expected_records['subtree-aggregates'])} aggregates)."
    )
    for entry in kb_state.claim_entries:
        for edge in entry.demoted:
            print(
                f"[finding] demoted {entry.canonical_path}: {edge.source} -> {edge.target} "
                f"(origin {edge.origin or 'none'})"
            )

    has_failures = False
    refresh_fixable = False

    if fm_missing:
        has_failures = True
        print(f"\n[FAIL] {len(fm_missing)} files missing frontmatter:")
        superseded_note = f" (carries a {kb_schema.UNSTAMPED_FORMAT_VERSION} comment block instead)"
        for p, superseded in fm_missing:
            print(f"  {p}" + (superseded_note if superseded else ""))
        print(
            f"  -> Not refresh-fixable, for an index no less than for a leaf: "
            f"refresh splices a derived field into an existing block and leaves "
            f"a document carrying no block untouched. Stamp one on each "
            f"document above with `{set_frontmatter_cmd()}`; where a document "
            f"carries a comment block, put its fields in the values file and "
            f"delete the block."
        )

    if confidence_failures:
        has_failures = True
        print(f"\n[FAIL] {len(confidence_failures)} out-of-range confidence/quality value(s):")
        for rel, line, reason in confidence_failures:
            print(f"  {rel}:{line}: {reason}")
        print(
            "  -> An authored confidence/quality is a number in [0, 1] or the "
            "literal *pending*. The rubric's named grades are an authoring "
            "convention; the range and the pending literal are enforced. Not "
            "refresh-fixable; correct the authored value."
        )

    if quality_block_failures:
        has_failures = True
        print(
            f"\n[FAIL] {len(quality_block_failures)} orphan/malformed "
            f"`### Quality` block(s) in claim-quality registers:"
        )
        for rel, line, reason in quality_block_failures:
            print(f"  {rel}:{line}: {reason}")
        print(
            "  -> Each `### Quality` block must sit within a `---`-delimited "
            "section that also carries the claim's `## <title>` heading and "
            "its `<!-- id: clm-... -->` marker. Not refresh-fixable; delete "
            "the orphan block or restore its missing title/id."
        )

    if t1_failures:
        has_failures = True
        print(f"\n[FAIL] {len(t1_failures)} leaves with malformed claims/no-claim:")
        for p, reason in t1_failures:
            print(f"  {p}: {reason}")

    if t2_failures:
        has_failures = True
        print(f"\n[FAIL] {len(t2_failures)} multi-claim leaves missing Tier 2 markers:")
        for p, ids, miss in t2_failures:
            print(f"  {p}")
            print(f"    claims: {ids}, missing inline markers for: {miss}")

    if id_dupes:
        has_failures = True
        print(f"\n[FAIL] {len(id_dupes)} duplicate canonical IDs:")
        for cid, paths in id_dupes.items():
            print(f"  {cid} ({len(paths)} occurrences)")
            for path in paths:
                print(f"    in {path}")

    if orphans:
        has_failures = True
        print(f"\n[FAIL] {len(orphans)} Tier 1 IDs don't resolve to a canonical entry:")
        for cid, paths in orphans.items():
            n = len(paths)
            print(f"  {cid} (cited by {n} leaf{'s' if n != 1 else ''})")
            for path in paths[:3]:
                print(f"    {path}")
            if n > 3:
                print(f"    ... and {n - 3} more")

    if subtree_failures:
        has_failures = True
        refresh_fixable = True
        print(f"\n[FAIL] {len(subtree_failures)} indexes with subtree-claims drift:")
        for p, missing, extra in subtree_failures:
            print(f"  {p}")
            if missing:
                print(f"    missing from declared: {missing}")
            if extra:
                print(f"    extra in declared: {extra}")

    if subtree_exp_failures:
        has_failures = True
        refresh_fixable = True
        print(f"\n[FAIL] {len(subtree_exp_failures)} indexes with " f"subtree-experiments drift:")
        for p, missing, extra in subtree_exp_failures:
            print(f"  {p}")
            if missing:
                print(f"    missing from declared: {missing}")
            if extra:
                print(f"    extra in declared: {extra}")

    if exp_ref_failures:
        has_failures = True
        print(
            f"\n[FAIL] {len(exp_ref_failures)} leaf experiments: reference(s) " f"do not resolve to an experiment node:"
        )
        for rel, rid, reason in exp_ref_failures:
            print(f"  {rel}: {rid} — {reason}")
        print(
            "  -> Not refresh-fixable. Every id in a leaf's experiments: field "
            "must resolve to an exp-id-declaring experiment leaf. Fix the "
            "reference or add the experiment."
        )

    if uncited:
        has_failures = True
        print(f"\n[FAIL] {len(uncited)} canonical entries have no leaf citation:")
        for cid, path in uncited:
            print(f"  {cid} (in {path})")
        print(
            "  -> Either back-link from a leaf's claims, or remove the entry. "
            "Meta-claims and reading-hazards belong in AGENTS.md / "
            "CONVENTIONS.md / LIVING_REFERENCE.md, not here."
        )

    if missing_index:
        has_failures = True
        refresh_fixable = True
        print(f"\n[FAIL] {len(missing_index)} .index stream(s) missing:")
        for short in missing_index:
            print(f"  {kb_load.index_path(KB, short)}")

    if eof_defects:
        has_failures = True
        refresh_fixable = True
        print(f"\n[FAIL] {len(eof_defects)} .index file(s) with EOF defects:")
        for short, reason in eof_defects:
            print(f"  {short}.yaml: {reason}")

    if malformed_index:
        has_failures = True
        print(f"\n[FAIL] {len(malformed_index)} malformed line(s) in .index (not `--- ` and a JSON object):")
        for short, lineno, detail in malformed_index:
            print(f"  {short}.yaml:{lineno}: {detail}")
        print(
            "  -> This is not refresh-fixable. Investigate the build pipeline "
            "or a merge corruption; the file should be regenerable from "
            "canonical sources only after the cause is identified."
        )

    if fresh_drift:
        has_failures = True
        refresh_fixable = True
        print(f"\n[FAIL] {len(fresh_drift)} .index file(s) stale vs canonical state:")
        for short, expected_count, actual_count in fresh_drift:
            print(f"  {short}.yaml: {expected_count} expected vs " f"{actual_count} actual records")

    if ref_violations:
        has_failures = True
        print(
            f"\n[FAIL] {len(ref_violations)} referential-integrity violation(s) "
            f"in .index/ — an id no claims.yaml record holds, or an edge breaking its class's "
            f"kinds, scores or origin:"
        )
        # Group by (short, cid) to keep output compact.
        grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
        for short, cid, location in ref_violations:
            grouped[(short, cid)].append(location)
        for (short, cid), locations in grouped.items():
            n = len(locations)
            print(f"  {short}.yaml: {cid!r} ({n} occurrence{'s' if n != 1 else ''})")
            for loc in locations[:3]:
                print(f"    {loc}")
            if n > 3:
                print(f"    ... and {n - 3} more")
        print(
            "  -> Not refresh-fixable. Indicates a bug in the index builder or a "
            "hand edit (refresh never emits one)."
        )

    if sol_line_drift or sol_anno_drift or sol_index_drift:
        has_failures = True
        refresh_fixable = True
        total = len(sol_line_drift) + len(sol_anno_drift) + len(sol_index_drift)
        print(
            f"\n[FAIL] {total} solidity freshness defect(s) — derived solidity "
            f"is stale vs canonical confidence + depends-on graph:"
        )
        for cid, got, want in sol_line_drift:
            print(f"  {cid}: solidity line — {got}, {want}")
        for cid, target, got, want in sol_anno_drift:
            print(f"  {cid}: depends-on annotation for {target} — {got}, {want}")
        for cid, got, want in sol_index_drift:
            print(f"  {cid}: claims.yaml — {got}, {want}")
        print(f"  -> Run `{refresh_hint}` to regenerate solidity.")

    if leaf_ref_drift:
        has_failures = True
        refresh_fixable = True
        print(
            f"\n[FAIL] {len(leaf_ref_drift)} leaf-references footer(s) stale vs "
            f"the reverse-citation map (which leaves host the entry's id):"
        )
        for rel, nid, got, want in leaf_ref_drift:
            print(f"  {rel}:{nid}")
            print(f"    - {got.strip()}")
            print(f"    + {want.strip()}")
        print(
            f"  -> The `> **Leaf references:**` footer is a derived field; do not "
            f"hand-edit it. Run `{refresh_hint}` to regenerate."
        )

    census_drift = [entry for entry in register_walk.census if not entry.consistent]
    if census_drift:
        has_failures = True
        print(
            f"\n[FAIL] {len(census_drift)} register/kind pair(s) losing "
            f"canonical entries — marker count != parsed record count:"
        )
        for entry in census_drift:
            print(
                f"  {entry.register_path}: {entry.kind} markers "
                f"{len(entry.markers)} vs records {len(entry.records)}"
            )
            if entry.lost:
                print(f"    no record produced for: {', '.join(entry.lost)}")
        print(
            "  -> Not refresh-fixable. A canonical `<!-- id: ... -->` marker "
            "that yields no record is an entry the KB has lost: its id is "
            "registered and nothing reads it. The usual cause is a marker "
            "authored ABOVE its `## <title>` heading — the parser binds a "
            "marker to the PRECEDING heading, so the first such marker in a "
            "file binds to nothing. Move each heading above its marker."
        )

    if register_walk.mis_bound:
        has_failures = True
        print(
            f"\n[FAIL] {len(register_walk.mis_bound)} canonical marker(s) bound " f"to a heading that is not their own:"
        )
        for rel, entry in register_walk.mis_bound:
            shape = (
                "its `### Quality` is beyond the next `## `"
                if entry.quality_line is None
                else "another marker shares that heading"
            )
            print(
                f"  {rel}:{entry.marker_line + 1}: {entry.node_id} binds to "
                f"`## {entry.heading_title}` at line {entry.heading_line + 1} — {shape}"
            )
        print(
            "  -> Not refresh-fixable, and NOT visible to the count above: a "
            "marker one heading out of place still produces a record, under "
            "the wrong title. Write each entry as `## <title>` THEN its "
            "`<!-- id: ... -->` marker, one marker per heading. This is the "
            "same binding the write API refuses an edit into, so a register "
            "reported here is one no metadata op will write to either."
        )

    if register_walk.unreconciled:
        has_failures = True
        print(
            f"\n[FAIL] {len(register_walk.unreconciled)} support fan-out edge(s) "
            f"on which the register's staged `- supports:` block and the hosting "
            f"leaf's `supports:` frontmatter disagree:"
        )
        for record in register_walk.unreconciled:
            print(f"  {record.sup_id} -> {record.claim_id}")
            print(f"    register {record.register_path}, hosting leaf {record.leaf_path}")
            print(f"    recorded at: {', '.join(record.ends)}")
            print(f"    {_fan_out_reason(record)}")
        print(
            "  -> Not refresh-fixable. The fan-out is authored at two ends and "
            "the hosting leaf is the canonical one — it is the end the claim "
            "graph reads. Transcribe the staged pairs into the leaf, or drop "
            "the staged block once the leaf carries them."
        )

    if has_failures:
        if refresh_fixable:
            print(
                f"\n[claim-quality] FAIL — some failures are derivation-only "
                f"(subtree drift, stale .index/, stale derived fields). Try "
                f"`{refresh_hint}` first; if anything remains, "
                f"those are real defects."
            )
        else:
            print("\n[claim-quality] FAIL — fix the above and re-run.")
        return 1

    print("[claim-quality] PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
