"""`label.render`'s paragraphs: the excluded region, and how a line finds its paragraph."""

import pytest

from kb_tools.kb_claimgraph import label

_DOCUMENT = (
    "\n".join(
        [
            "[↑ Up](../index.md)",
            "",
            "# Bistability",
            "",
            "The origin attracts from above. It repels from below, which is the whole",
            "of the bifurcation.",
            "",
            "A later paragraph states the origin attracts from above once more.",
        ]
    )
    + "\n"
)


# ---------------------------------------------------------------------------
# The excluded region, and a line's paragraph
# ---------------------------------------------------------------------------

#: A paragraph interrupted by a block the node pass does not read: lines 5 and 6
#: are the block, and the prose either side of it is two paragraphs, not one.
_INTERRUPTED = "\n".join(
    [
        "[↑ Up](index.md)",
        "",
        "# Heading",
        "",
        "The first paragraph opens here and",
        "> **proof**",
        "> *Proof.* A step.",
        "runs on past the block.",
        "",
        "A last paragraph.",
    ]
)


def test_an_excluded_line_carries_no_label_and_is_shown_as_it_stands():
    rendered = label.render(_INTERRUPTED, excluded=frozenset({5, 6}))

    assert all(sentence.line not in {5, 6} for sentence in rendered.sentences)
    assert "> *Proof.* A step." in rendered.text.splitlines()


def test_an_excluded_run_ends_the_paragraph_it_interrupts():
    rendered = label.render(_INTERRUPTED, excluded=frozenset({5, 6}))

    before, after = rendered.paragraph_at(4), rendered.paragraph_at(7)
    assert before is not None and after is not None and before != after
    assert rendered.paragraph_at(6) is None
    joined = label.render(_INTERRUPTED)
    assert joined.paragraph_at(4) == joined.paragraph_at(7)


@pytest.mark.parametrize(("line", "start"), [(2, 2), (4, 4), (7, 7), (9, 9)])
def test_a_paragraph_is_named_by_the_line_it_begins_on(line: int, start: int):
    paragraph = label.render(_INTERRUPTED, excluded=frozenset({5, 6})).paragraph_at(line)

    assert paragraph is not None and paragraph.start == start


def test_a_paragraph_s_span_is_every_sentence_it_holds_and_no_other():
    rendered = label.render(_DOCUMENT)
    paragraph = rendered.paragraph_at(5)

    assert paragraph is not None
    assert rendered.span_of(paragraph).sentences == tuple(
        sentence for sentence in rendered.sentences if sentence.paragraph == paragraph.index
    )
    assert paragraph.lines == frozenset({4, 5})


def test_a_line_outside_every_paragraph_names_none():
    rendered = label.render(_INTERRUPTED)

    assert rendered.paragraph_at(0) is None
    assert rendered.paragraph_at(3) is None
