"""Tests for the `dupe_sweep` package — the one-idea-two-places candidate sweep.

The load-bearing one is :func:`test_the_known_seven_way_duplicate_is_found`. Seven
copies of one sentence once lived in seven agent templates, and a pass that cannot
surface a duplicate somebody already found by hand is not working whatever else it
reports. :data:`KNOWN_ANSWER_TREE` restates that shape as a fixture, with copies the
pass must not read planted beside the ones it must. The prose detector's recall
bound — every shared run of fifteen non-article words, shorter ones by alignment — is stated as
a table in :func:`test_a_short_run_is_found_only_when_a_stride_head_falls_inside_it`.

Corpus-shaped cases pass a `{path: source}` mapping straight to the extractors
rather than building a tree — the sweep reads its corpus from git, and a
filesystem is not on the path between a source file and a candidate.
"""

import io

import pytest

from devtools.dupe_sweep import (
    cli,
    clustering,
    constants,
    doc_sentences,
    normalization,
    passes,
    prose_corpus,
    report,
    shapes,
    window_index,
)
from devtools.dupe_sweep.window_index import WINDOW, Span

KNOWN_ANSWER_SENTENCE = (
    "If you cannot complete the task as scoped, report immediately rather than proceeding with assumptions."
)
#: Duplicated at sites that each break it at a different column, and once unwrapped.
WRAPPED_SENTENCE = (
    "A rule honoured completely inside one definition can still be broken across two of them, and"
    " nothing inside either one reports it."
)
NEAR_COPY = (
    "If you cannot complete the task as scoped (missing context, ambiguous requirements, file conflict"
    " risk), report this immediately rather than proceeding with assumptions."
)

#: A tree as `corpus` would read it. Every copy outside the golden sites is one the
#: pass must skip: frontmatter, fenced code, a file outside the template surfaces,
#: a file without the template suffix.
KNOWN_ANSWER_TREE = {
    "templates/shared-chunks.toml": (
        f"[chunks.report-early]\ntext = '''\n{KNOWN_ANSWER_SENTENCE}\n'''\n"
        "\n[chunks.wrapped-rule]\ntext = '''\nA rule honoured completely inside one definition can still be broken\n"
        "across two of them, and nothing inside either one reports it.\n'''\n"
    ),
    "templates/agents/a.tmpl.md": "\n".join(
        [
            "+++",
            "[outputs.a]",
            "model = 'high'",
            "+++",
            "---",
            "name: a",
            f"description: {KNOWN_ANSWER_SENTENCE}",
            "---",
            "",
            KNOWN_ANSWER_SENTENCE,
        ]
    ),
    "templates/agents/b.tmpl.md": (
        f"Opening line.\n\n```text\n{KNOWN_ANSWER_SENTENCE}\n```\n- {KNOWN_ANSWER_SENTENCE}\n"
    ),
    "templates/agents/c.tmpl.md": f"- {KNOWN_ANSWER_SENTENCE}\n",
    "templates/agents/d.tmpl.md": f"## Scope\n\n{KNOWN_ANSWER_SENTENCE} Then stop.\n",
    "templates/agents/nested/e.tmpl.md": f"1. {KNOWN_ANSWER_SENTENCE}\n",
    "templates/commands/f.tmpl.md": f"> {KNOWN_ANSWER_SENTENCE}\n",
    "templates/harness/AGENTS.tmpl.md": f"{KNOWN_ANSWER_SENTENCE}\n",
    "templates/agents/notes.txt": f"{KNOWN_ANSWER_SENTENCE}\n",
    "templates/agents/h.tmpl.md": (
        "Opening paragraph.\n\nA rule honoured completely inside one\ndefinition can still be broken across two"
        " of them, and nothing\ninside either one reports it.\n\nClosing paragraph.\n"
    ),
    "templates/agents/i.tmpl.md": (
        "- A rule honoured\n  completely inside one definition can still be broken across two of them, and\n"
        "  nothing inside either one reports it.\n"
    ),
    "templates/commands/w.tmpl.md": f"{WRAPPED_SENTENCE}\n",
}
KNOWN_ANSWER_SITES = [
    "templates/agents/a.tmpl.md:10",
    "templates/agents/b.tmpl.md:6",
    "templates/agents/c.tmpl.md:1",
    "templates/agents/d.tmpl.md:3",
    "templates/agents/nested/e.tmpl.md:1",
    "templates/commands/f.tmpl.md:1",
    "templates/shared-chunks.toml:1 chunks.report-early",
]
WRAPPED_SITES = [
    "templates/agents/h.tmpl.md:3",
    "templates/agents/i.tmpl.md:1",
    "templates/commands/w.tmpl.md:1",
    "templates/shared-chunks.toml:6 chunks.wrapped-rule",
]


def unit(text: str, *, path: str = "a.md", line: int = 1) -> clustering.Unit:
    return clustering.Unit(path, line, "", text, normalization.prose_tokens(text))


def prose(body: str, *, path: str = "a.tmpl.md") -> normalization.ProseText:
    return normalization.prose_text(path, "", body, line_of=lambda offset: offset + 1)


def words(prefix: str, count: int) -> str:
    """`count` words no other prefix's words equal, so a run's ends are where the test puts them."""
    return " ".join(f"{prefix}{number}" for number in range(count))


def overlaps(*texts: normalization.ProseText, **settings) -> list[tuple[Span, Span]]:
    return window_index.overlaps(texts, **{**passes.PROSE_DEFAULTS, **settings})


def sites(texts: list[normalization.ProseText], found: list[tuple[Span, Span]]) -> list[list[str]]:
    return [
        sorted(member.site for member, _ in cluster.members) for cluster in window_index.overlap_clusters(texts, found)
    ]


# ── the known answer ─────────────────────────────────────────────────────────


@pytest.fixture
def known_answer_clusters(monkeypatch) -> list[clustering.Cluster]:
    def corpus(*, rev, prefixes, suffix):
        return {
            path: text
            for path, text in sorted(KNOWN_ANSWER_TREE.items())
            if path.startswith(tuple(prefixes)) and path.endswith(suffix)
        }

    monkeypatch.setattr(prose_corpus, "corpus", corpus)
    texts = prose_corpus.prose_texts(rev=None)
    found = window_index.overlap_clusters(texts, window_index.overlaps(texts, **passes.PROSE_DEFAULTS))
    assert len(found) == 2, "each duplicated sentence must be one candidate, not several"
    return found


def cluster_of(found: list[clustering.Cluster], sentence: str) -> clustering.Cluster:
    wanted = prose(sentence).words
    matching = [cluster for cluster in found if cluster.representative.tokens == wanted]
    assert len(matching) == 1, f"no single candidate for {sentence!r}"
    return matching[0]


def test_the_known_seven_way_duplicate_is_found(known_answer_clusters):
    found = cluster_of(known_answer_clusters, KNOWN_ANSWER_SENTENCE)
    assert sorted(member.site for member, _ in found.members) == KNOWN_ANSWER_SITES
    wanted = prose(KNOWN_ANSWER_SENTENCE).words
    assert all(member.tokens == wanted for member, _ in found.members), "every site must be the whole sentence"


def test_a_sentence_wrapped_at_a_different_column_at_each_site_is_one_candidate(known_answer_clusters):
    found = cluster_of(known_answer_clusters, WRAPPED_SENTENCE)
    assert sorted(member.site for member, _ in found.members) == WRAPPED_SITES
    wanted = prose(WRAPPED_SENTENCE).words
    assert all(member.tokens == wanted for member, _ in found.members), "every site must be the whole sentence"


# ── the prose overlap detector ───────────────────────────────────────────────


def test_a_shared_run_is_one_passage_whatever_its_wrap_punctuation_and_case():
    texts = [
        prose(
            "Opening words here.\n\nA Rule, honoured completely inside ONE definition —\n"
            "can still be broken across two of them; and nothing inside either one reports it!\n\nClosing.",
            path="a.tmpl.md",
        ),
        prose(
            "- a rule honoured completely\n  inside one definition can still be broken across\n"
            "  two of them, and nothing inside\n  either one reports it.\nAnother thought entirely.",
            path="b.tmpl.md",
        ),
    ]
    found = overlaps(*texts)
    assert found == [(Span(0, 3, 24), Span(1, 0, 21))]
    assert sites(texts, found) == [["a.tmpl.md:3", "b.tmpl.md:1"]]
    assert window_index.overlap_clusters(texts, found)[0].representative.tokens == prose(WRAPPED_SENTENCE).words


def test_passages_differing_only_in_their_articles_are_one_passage():
    texts = [
        prose(
            "Notes first.\nThe bound holds for the window that a stride head opens in an index of every text.",
            path="a",
        ),
        prose("A bound holds for a window that the stride head opens in the index of every text. Done.", path="b"),
    ]
    found = overlaps(*texts, min_tokens=WINDOW)
    assert found == [(Span(0, 2, 15), Span(1, 0, 13))]
    assert window_index.overlap_clusters(texts, found)[0].representative.text == (
        "bound holds for window that stride head opens in index of every text"
    )


def test_a_copied_sixty_word_paragraph_reports_once_with_its_length():
    paragraph = words("p", 60)
    texts = [prose(f"{words('a', 5)} {paragraph} {words('b', 3)}"), prose(f"{words('c', 11)} {paragraph}")]
    assert overlaps(*texts) == [(Span(0, 5, 65), Span(1, 11, 71))]


@pytest.mark.parametrize(
    "length, offset, found",
    [
        # The guarantee: 2 * WINDOW - 1 shared words are found at every offset.
        *((2 * WINDOW - 1, offset, True) for offset in range(WINDOW)),
        # Shorter runs are found when a stride head (a multiple of WINDOW in the
        # later text) starts a whole window inside them, and missed otherwise.
        (WINDOW, 0, True),
        (WINDOW, WINDOW, True),
        (WINDOW, 1, False),
        (2 * WINDOW - 2, 2, True),
        (2 * WINDOW - 2, 1, False),
        (WINDOW + 1, WINDOW - 1, True),
        (WINDOW + 1, WINDOW - 2, False),
        (WINDOW - 1, 0, False),
    ],
)
def test_a_short_run_is_found_only_when_a_stride_head_falls_inside_it(length, offset, found):
    run = words("r", length)
    earlier = prose(f"{words('x', 3)} {run} {words('q', 4)}")
    later = prose(f"{words('y', offset)} {run} {words('z', 5)}")
    expected = [(Span(0, 3, 3 + length), Span(1, offset, offset + length))] if found else []
    assert overlaps(earlier, later, min_tokens=WINDOW) == expected


PHRASE = "every definition opens with this same framing line"  # one window wide


def test_a_window_in_more_places_than_the_cap_finds_nothing_and_a_rarer_one_still_does():
    def framed(count):
        return [prose(f"{PHRASE} {words(f'f{index}x', 4)}", path=f"t{index:02}.md") for index in range(count)]

    assert len(PHRASE.split()) == WINDOW
    at_cap = framed(window_index.MAX_WINDOW_SITES)
    assert sites(at_cap, overlaps(*at_cap, min_tokens=WINDOW)) == [sorted(f"t{i:02}.md:1" for i in range(len(at_cap)))]

    copied = f"{PHRASE} {words('k', 16)}"
    over_cap = framed(window_index.MAX_WINDOW_SITES - 1) + [prose(copied, path="u.md"), prose(copied, path="v.md")]
    last = len(over_cap) - 1
    assert overlaps(*over_cap, min_tokens=WINDOW) == [(Span(last - 1, 0, 24), Span(last, 0, 24))]


def test_the_tail_of_a_text_is_indexed_and_a_text_under_one_window_is_not_an_error():
    # The run starts at the last offset a whole window does: inside the final, partial stride.
    earlier = prose(f"{words('x', 13)} {words('r', WINDOW)}")
    later = prose(f"{words('r', WINDOW)} {words('z', 3)}")
    assert overlaps(earlier, later, min_tokens=WINDOW) == [(Span(0, 13, 21), Span(1, 0, WINDOW))]

    # A whole text shorter than one stride plus one window.
    assert overlaps(prose(f"{words('x', 9)} {words('r', 11)} y"), prose(words("r", 11)), min_tokens=WINDOW) == [
        (Span(0, 9, 20), Span(1, 0, 11))
    ]
    assert overlaps(prose("too short to index"), prose("too short to index"), min_tokens=1) == []


def test_a_passage_repeated_inside_one_text_is_found_at_both_sites():
    passage = words("s", 20)
    texts = [prose(f"{passage}\n\nSomething said in between.\n\n{passage}", path="one.md")]
    found = overlaps(*texts)
    assert found == [(Span(0, 0, 20), Span(0, 24, 44))]
    assert sites(texts, found) == [["one.md:1", "one.md:5"]]


def test_spans_overlapping_inside_one_text_are_one_site():
    """Two texts each copy part of one passage — overlapping halves, sharing
    fewer than the reporting floor with each other. The source is one site, so
    the three are one candidate rather than two pairs that name it twice."""
    passage = words("p", 30)
    head, tail = " ".join(passage.split()[:20]), " ".join(passage.split()[10:])
    texts = [prose(passage, path="source.md"), prose(head, path="head.md"), prose(tail, path="tail.md")]
    assert sites(texts, overlaps(*texts)) == [["head.md:1", "source.md:1", "tail.md:1"]]


CORE_A, CORE_B = words("a", 16), words("b", 16)


@pytest.mark.parametrize(
    "left_middle, right_middle, coverage, expected",
    [
        # Three words reworded: 32 of 35 words, 0.91, merges at the default bar.
        ("alpha beta gamma", "delta epsilon zeta", 0.85, [(Span(0, 0, 35), Span(1, 0, 35))]),
        (
            "alpha beta gamma",
            "delta epsilon zeta",
            0.95,
            [(Span(0, 0, 16), Span(1, 0, 16)), (Span(0, 19, 35), Span(1, 19, 35))],
        ),
        # An inserted parenthetical: the shorter side is wholly contained.
        ("", "missing context ambiguous requirements risk", 1.0, [(Span(0, 0, 32), Span(1, 0, 37))]),
        # Past the gap limit the cores stay apart, whatever the containment.
        (
            "",
            words("g", window_index.MAX_MERGE_GAP + 1),
            0.0,
            [(Span(0, 0, 16), Span(1, 0, 16)), (Span(0, 16, 32), Span(1, 29, 45))],
        ),
    ],
)
def test_exact_cores_merge_across_a_small_gap_while_the_pair_keeps_its_coverage(
    left_middle, right_middle, coverage, expected
):
    left = prose(f"{CORE_A} {left_middle} {CORE_B}")
    right = prose(f"{CORE_A} {right_middle} {CORE_B}")
    assert overlaps(left, right, coverage=coverage) == expected


def test_fenced_code_is_not_prose_and_later_lines_keep_their_numbers():
    text = prose("A sentence.\n```sh\njust install target\n```\nAnother sentence.")
    assert text.words == ("sentence", "another", "sentence")
    assert text.lines == (1, 5, 5)


@pytest.mark.parametrize(
    "line, expected",
    [
        ("A rule, an idea and THE check.", ("rule", "idea", "and", "check")),
        # Demonstratives carry meaning and stay.
        ("These rules and this check, those and that.", tuple("these rules and this check those and that".split())),
        # An article's letters inside a word are part of the word.
        ("Analysis of data, then theory and anathema.", tuple("analysis of data then theory and anathema".split())),
    ],
)
def test_only_standalone_articles_leave_a_prose_text(line, expected):
    assert prose(line).words == expected


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


# ── prose extraction ─────────────────────────────────────────────────────────


def test_a_chunk_marker_is_not_prose_and_a_code_span_is():
    assert normalization.prose_tokens('@!parallel-execution variant="platform"!@ Use `NSFileCoordinator` here.') == (
        "use",
        "nsfilecoordinator",
        "here",
    )


def test_a_template_body_starts_after_the_fence_and_the_frontmatter():
    text = "\n".join(
        [
            "+++",
            "[outputs.one]",
            "model = 'high'",
            "+++",
            "---",
            "name: one",
            "description: a description that is prose but not a prompt body",
            "---",
            "",
            "The body proper.",
        ]
    )
    start, body = prose_corpus.template_body(text)
    assert body.strip() == "The body proper."
    assert text.splitlines()[start - 1 + 1] == "The body proper."


def test_a_template_with_neither_fence_nor_frontmatter_is_body_entire():
    assert prose_corpus.template_body("Just prose.\n") == (1, "Just prose.")


def test_an_unclosed_fence_leaves_the_file_readable_as_body(caplog):
    start, body = prose_corpus.template_body("+++\n[outputs.one]\nstill open\n")
    assert start == 1 and "still open" in body
    assert "unclosed" in caplog.text


def test_chunk_bodies_carry_every_variant_and_the_header_line():
    text = "\n".join(
        [
            "# a maintainer note",
            "[chunks.dissent]",
            "text = '''State the concern.'''",
            "",
            "[chunks.parallel-execution.variants]",
            "platform = '''Declare your files.'''",
            "shell = '''Declare your recipes.'''",
        ]
    )
    assert prose_corpus.chunk_bodies(text) == [
        ("chunks.dissent", 2, "State the concern."),
        ("chunks.parallel-execution.platform", 5, "Declare your files."),
        ("chunks.parallel-execution.shell", 5, "Declare your recipes."),
    ]


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
    assert cli.main(["prose"], out=out) == 0
    assert "candidates, not verdicts" in out.getvalue()


def test_an_unreadable_revision_exits_two_rather_than_reporting_a_clean_tree():
    out = io.StringIO()
    assert cli.main(["prose", "--rev", "no-such-revision"], out=out) == 2
    assert out.getvalue() == ""


def test_an_unknown_pass_is_refused():
    with pytest.raises(SystemExit):
        cli.main(["structure"])
