"""Tests for the `dupe_sweep` package — the one-idea-two-places candidate sweep.

Corpus-shaped cases pass a `{path: source}` mapping straight to the extractors
rather than building a tree — the sweep reads its corpus from git, and a
filesystem is not on the path between a source file and a candidate.
"""

import io

import pytest

from devtools.dupe_sweep import cli, clustering, constants, doc_sentences, normalization, passes, report, shapes

KNOWN_ANSWER_SENTENCE = (
    "If you cannot complete the task as scoped, report immediately rather than proceeding with assumptions."
)
NEAR_COPY = (
    "If you cannot complete the task as scoped (missing context, ambiguous requirements, file conflict"
    " risk), report this immediately rather than proceeding with assumptions."
)


def unit(text: str, *, path: str = "a.md", line: int = 1) -> clustering.Unit:
    return clustering.Unit(path, line, "", text, normalization.prose_tokens(text))


# ── the metric ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "left, right, floor, ceiling",
    [
        ("the same sentence exactly", "the same sentence exactly", 1.0, 1.0),
        # The known near-copy: an inserted parenthetical and one added word.
        (KNOWN_ANSWER_SENTENCE, NEAR_COPY, 0.90, 1.0),
        ("a sentence about parsing markdown links", "an unrelated remark concerning venv layout", 0.0, 0.4),
    ],
)
def test_containment_scores_a_restatement_high_and_a_stranger_low(left, right, floor, ceiling):
    score = clustering.containment(normalization.prose_tokens(left), normalization.prose_tokens(right))
    assert floor <= score <= ceiling


def test_containment_is_symmetric():
    long_side = normalization.prose_tokens("the rule holds at every seat and in every definition without exception")
    short_side = normalization.prose_tokens("the rule holds at every seat")
    assert clustering.containment(long_side, short_side) == clustering.containment(short_side, long_side)


# ── sentence-unit clustering (docstrings and comments) ───────────────────────


def test_seven_copies_report_as_one_candidate_with_seven_sites():
    copies = [unit(KNOWN_ANSWER_SENTENCE, path=f"t{index}.md") for index in range(7)]
    found = clustering.clusters(copies, **passes.DOC_DEFAULTS)
    assert len(found) == 1
    assert len(found[0].members) == 7


def test_the_representative_is_the_shortest_statement_of_the_shared_idea():
    short = unit("Declare the files you will modify before you start, and stay inside that set.", path="a.md")
    long = unit(
        "Declare the files you will modify before you start, and stay inside that set, because another"
        " agent may be editing one.",
        path="b.md",
    )
    found = clustering.clusters([long, short], **passes.DOC_DEFAULTS)
    assert len(found) == 1
    assert found[0].representative.path == "a.md"


def test_a_short_span_inside_a_long_one_does_not_chain_them():
    """`length_ratio`'s job. Containment alone links a fragment to everything that
    quotes it, and the cluster becomes a rope rather than a finding."""
    fragment = unit("never invoke the compiler directly when a target covers it", path="a.md")
    quoting = unit(
        "Use the project's runner targets for every build, test, lint and integration operation, and"
        " never invoke the compiler directly when a target covers it, whichever runner the project has"
        " chosen for itself and however tempting the naked command line looks.",
        path="b.md",
    )
    assert clustering.containment(fragment.tokens, quoting.tokens) == 1.0
    assert clustering.clusters([fragment, quoting], **passes.DOC_DEFAULTS) == []


def test_a_span_shorter_than_min_tokens_is_not_compared():
    pair = [unit("Stdlib-first, always.", path=f"t{index}.md") for index in range(2)]
    assert clustering.clusters(pair, **passes.DOC_DEFAULTS) == []


def test_the_same_units_in_any_order_render_the_same_report():
    units = [unit(KNOWN_ANSWER_SENTENCE, path=f"t{index}.md") for index in range(4)] + [
        unit(
            "A dependency is a permanent maintenance obligation, so justify it before you add one.", path=f"d{index}.md"
        )
        for index in range(3)
    ]

    def rendered(ordered):
        out = io.StringIO()
        report.render_clusters("t", clustering.clusters(ordered, **passes.DOC_DEFAULTS), out=out)
        return out.getvalue()

    assert rendered(units) == rendered(list(reversed(units)))


def test_the_file_pair_tally_counts_a_pair_once_per_candidate():
    units = [
        unit(KNOWN_ANSWER_SENTENCE, path="a.md"),
        unit(KNOWN_ANSWER_SENTENCE, path="b.md"),
        unit("A dependency is a permanent maintenance obligation, so justify it before you add one.", path="a.md"),
        unit("A dependency is a permanent maintenance obligation, so justify it before adding one.", path="b.md"),
    ]
    found = clustering.clusters(units, **passes.DOC_DEFAULTS)
    assert report.file_pairs(found) == [(2, "a.md", "b.md")]


def test_hard_wrapped_prose_is_rejoined_before_it_is_split():
    numbered = [(10, "A rule that spans"), (11, "two physical lines."), (12, ""), (13, "A separate block.")]
    assert list(doc_sentences.block_sentences(numbered)) == [
        (10, "A rule that spans two physical lines."),
        (13, "A separate block."),
    ]


# ── prose tokens ─────────────────────────────────────────────────────────────


def test_a_chunk_marker_is_not_prose_and_a_code_span_is():
    assert normalization.prose_tokens('@!parallel-execution variant="platform"!@ Use `NSFileCoordinator` here.') == (
        "use",
        "nsfilecoordinator",
        "here",
    )


# ── python extraction ────────────────────────────────────────────────────────


TWO_SPELLINGS_OF_ONE_LOOP = {
    "one.py": (
        "def totals(rows):\n"
        "    '''A docstring the shape does not see.'''\n"
        "    out = {}\n"
        "    for row in rows:\n"
        "        if row.kind not in out:\n"
        "            out[row.kind] = 0\n"
        "        out[row.kind] += row.weight\n"
        "    return out\n"
    ),
    "two.py": (
        "def tally(entries):\n"
        "    counts = {}\n"
        "    for entry in entries:\n"
        "        if entry.sort not in counts:\n"
        "            counts[entry.sort] = 0\n"
        "        counts[entry.sort] += entry.size\n"
        "    return counts\n"
    ),
}


def test_two_spellings_of_one_loop_are_one_candidate():
    found = clustering.clusters(
        shapes.shape_units(TWO_SPELLINGS_OF_ONE_LOOP), **{**passes.CODE_DEFAULTS, "min_tokens": 10}
    )
    assert [member.site for member, _ in found[0].members] == ["one.py:1 totals()", "two.py:1 tally()"]


def test_unlike_functions_are_not_a_candidate():
    files = {
        "one.py": TWO_SPELLINGS_OF_ONE_LOOP["one.py"],
        "two.py": "def shout(text):\n    return text.upper()\n",
    }
    assert clustering.clusters(shapes.shape_units(files), **{**passes.CODE_DEFAULTS, "min_tokens": 10}) == []


def test_a_method_is_a_unit_and_a_nested_function_is_not():
    files = {
        "one.py": (
            "class Store:\n"
            "    def put(self, key):\n"
            "        def inner(value):\n"
            "            return value\n"
            "        return inner(key)\n"
        )
    }
    assert [unit.label for unit in shapes.shape_units(files)] == ["Store.put()"]


def test_a_docstring_and_a_comment_both_state_rules():
    files = {"one.py": '"""A module rule.\n\nA second sentence.\n"""\n\n# A commented rule.\nx = 1\n'}
    units = doc_sentences.doc_units(files)
    assert [(unit.label, unit.text) for unit in units] == [
        ("module docstring", "A module rule."),
        ("module docstring", "A second sentence."),
        ("comment", "A commented rule."),
    ]


def test_a_module_that_does_not_parse_is_reported_and_skipped(caplog):
    assert shapes.shape_units({"broken.py": "def (:\n"}) == []
    assert "does not parse" in caplog.text


@pytest.mark.parametrize(
    "source, expected",
    [
        ("WIDTH = 72\n", [("WIDTH", "72")]),
        ("TAG: str = 'survey'\n", [("TAG", "survey".join("''"))]),
        ("KINDS = ('clm', 'exp')\n", [("KINDS", "('clm', 'exp')")]),
        ("ENABLED = True\nEMPTY = ''\nZERO = 0\n", []),  # trivia
        ("VALUE = compute()\n", []),  # not a literal
        ("def f():\n    INNER = 4096\n", []),  # not module level
    ],
)
def test_module_level_literals_are_collected_and_trivia_is_not(source, expected):
    found = constants.constants({"one.py": source})
    assert [(constant.name, constant.value) for constant in found] == expected


def test_one_name_in_two_modules_is_a_candidate():
    found = constants.constants({"one.py": "EXCERPT_MAX_CHARS = 240\n", "two.py": "EXCERPT_MAX_CHARS = 240\n"})
    (why, sites), *rest = constants.constant_candidates(found)
    assert why == "one name bound in 2 modules: EXCERPT_MAX_CHARS"
    assert [site.path for site in sites] == ["one.py", "two.py"]
    assert rest == [], "the same sites must not be reported again as a repeated value"


def test_two_unrelated_uses_of_a_small_number_are_not_a_candidate():
    found = constants.constants({"one.py": "EXIT_USAGE = 2\n", "two.py": "EDGE_STROKE_WIDTH = 2\n"})
    assert constants.constant_candidates(found) == []


def test_one_distinctive_value_under_similar_names_is_a_candidate():
    found = constants.constants(
        {"one.py": "DEFAULT_SILENCE_SECONDS = 600\n", "two.py": "DEFAULT_SILENCE_SECONDS_LIMIT = 600\n"}
    )
    assert [why for why, _ in constants.constant_candidates(found)] == [
        "one value in 2 modules under similar names: 600"
    ]


# ── the command line ─────────────────────────────────────────────────────────


def test_a_pass_that_finds_candidates_still_exits_zero():
    """Candidates are not verdicts: a nonzero exit would be the judgment the sweep
    refuses to make, and would put it in the way of every checkpoint it runs at."""
    out = io.StringIO()
    assert cli.main(["python"], out=out) == 0
    assert "candidates, not verdicts" in out.getvalue()


def test_an_unreadable_revision_exits_two_rather_than_reporting_a_clean_tree():
    out = io.StringIO()
    assert cli.main(["python", "--rev", "no-such-revision"], out=out) == 2
    assert out.getvalue() == ""


def test_an_unknown_pass_is_refused():
    with pytest.raises(SystemExit):
        cli.main(["structure"])
