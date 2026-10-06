"""The overview document's substitution, and the refusal that guards it.

``<kb-root>/README.md`` is filled once and never re-rendered, so the values
:mod:`kb_tools.kb_readme` fills it with are the ones that stay true as the KB is
edited. A template and a value set written by different hands can disagree, and
the failure that must never be quiet is a knowledge base shipping a document with
a slot's own name in it.
"""

from pathlib import Path

import pytest

from kb_tools import kb_pipeline, kb_readme


def test_a_slot_nothing_computes_is_refused_by_name() -> None:
    """The one failure that must not be quiet: a slot's own name shipped as content."""
    with pytest.raises(kb_readme.TemplateError) as raised:
        kb_readme.fill("{known} known, {invented-fact} of them blue", {"known": "3"})

    assert "invented-fact" in str(raised.value)
    assert "known" not in str(raised.value).partition("nothing computes")[2].partition("—")[0]


def test_a_computed_value_the_template_never_names_is_not_an_error() -> None:
    """The value set is the toolchain's; which of it to state is the template's."""
    assert kb_readme.fill("{known}", {"known": "3", "unnamed": "9"}) == "3"


def test_substitution_is_one_pass_so_a_value_is_content_and_never_a_slot() -> None:
    """A seat's prose naming a slot is prose: the pass that placed it does not re-read it."""
    values = {kb_readme.PROSE_SLOT: "read {known} first", "known": "9"}
    filled = kb_readme.fill("{" + kb_readme.PROSE_SLOT + "}", values)

    assert filled == "read {known} first"


def test_the_slots_of_a_template_are_first_appearance_order_without_repeats() -> None:
    assert kb_readme.slots("{b} {a} {b}") == ("b", "a")


def test_the_project_name_slot_is_the_one_the_packaged_readiness_docs_take() -> None:
    """One name for one fact across every template under ``installed/``."""
    assert "{" + kb_readme.PROJECT_NAME_SLOT + "}" == kb_pipeline.PROJECT_NAME_FIELD


def test_every_slot_the_packaged_template_names_is_a_value_or_the_seats_passage() -> None:
    """The shipped pair, held against each other — the interlock the runtime refusal also makes.

    The template and the value set are written by different hands, so this is
    the one place their agreement is a checked property rather than a
    convention: every slot the shipped document names is served either by a
    value the toolchain fills or by the one answer the stage asks a seat for.
    """
    served = set(kb_readme.facts(project_name="fixture-kb")) | {kb_readme.PROSE_SLOT}

    assert set(kb_readme.slots(kb_readme.template_text())) <= served


def test_the_assembled_document_is_the_template_with_no_slot_left() -> None:
    """The shipped template, the toolchain's values and a seat's passage make a whole document."""
    passage = "Start at the introduction."
    document = kb_readme.assemble(project_name="fixture-kb", prose={kb_readme.PROSE_SLOT: passage})

    assert document.startswith("# fixture-kb Knowledge Base\n\nStart at the introduction.\n")
    assert not kb_readme.slots(document)


# ---------------------------------------------------------------------------
# The excerpts the passage is written from
# ---------------------------------------------------------------------------

#: A two-volume tree in the shape a build leaves it: the entry point and each
#: index under a frontmatter block, every non-root document's up-link on the line
#: after it, or on line 1 where it has none. The first volume has its own opening prose; the second has none,
#: and links a document titled otherwise, which the excerpts must not read.
TREE = {
    "entry-point.md": (
        "---\nkind: entry-point\nsubtree-claims: [clm-aaaaaa]\n---\n\n# Knowledge Base\n\n"
        "- [First Volume](first-volume/index.md)\n- [Second Volume](second-volume/index.md)\n"
    ),
    "first-volume/index.md": (
        "---\nkind: index\n---\n[↑ Knowledge Base](../entry-point.md)\n\n# First Volume\n\n"
        "- [Overview](overview.md)\n- [Part I](part-i/index.md)\n"
    ),
    "first-volume/overview.md": (
        "---\nkind: leaf\nclaims: []\n---\n[↑ First Volume](index.md)\n\n# Overview\n\n"
        "The volume argues one thing, building on [Part I](part-i/index.md).\n\nIt leaves *another* aside.\n"
    ),
    "second-volume/index.md": (
        "---\nkind: index\n---\n[↑ Knowledge Base](../entry-point.md)\n\n# Second Volume\n\n"
        "- [Introduction](introduction.md)\n"
    ),
    "second-volume/introduction.md": "[↑ Second Volume](index.md)\n\n# Introduction\n\nNot an excerpt.\n",
}

#: What :data:`TREE` composes to, byte for byte.
GOLDEN = (
    "==> Knowledge Base <==\n# Knowledge Base\n\n- First Volume\n- Second Volume"
    "\n\n==> First Volume <==\n# First Volume\n\n- Overview\n- Part I"
    "\n\n==> First Volume › Overview <==\n# Overview\n\n"
    "The volume argues one thing, building on Part I.\n\nIt leaves *another* aside."
    "\n\n==> Second Volume <==\n# Second Volume\n\n- Introduction"
)


def _tree(root: Path) -> Path:
    for relative, text in TREE.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text, encoding="utf-8")
    return root


def test_the_excerpts_are_the_entry_point_then_each_index_and_its_own_prose_with_no_path_or_link(
    tmp_path: Path,
) -> None:
    """Reading order, each boundary carrying a title, every metadata block, up-link and link destination gone."""
    excerpts = kb_readme.compose_excerpts(_tree(tmp_path))

    assert excerpts.text == GOLDEN
    assert excerpts.cuts == ()


def test_the_same_tree_composes_the_same_bytes(tmp_path: Path) -> None:
    first = kb_readme.compose_excerpts(_tree(tmp_path / "a")).text
    second = kb_readme.compose_excerpts(_tree(tmp_path / "b")).text

    assert first == second


def test_a_document_over_its_cap_is_cut_at_a_paragraph_boundary_and_the_cut_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The overview's body is three paragraphs; a cap the first two fit and the third does not keeps two."""
    body = "# Overview\n\nThe volume argues one thing, building on Part I."
    monkeypatch.setattr(kb_readme, "EXCERPT_DOCUMENT_CHARS", len(body) + 1)

    excerpts = kb_readme.compose_excerpts(_tree(tmp_path))

    assert f"==> First Volume › Overview <==\n{body}\n\n==> Second Volume <==" in excerpts.text
    assert "It leaves" not in excerpts.text
    cut = len("It leaves *another* aside.") + len("\n\n")
    assert excerpts.cuts == (
        kb_readme.ExcerptCut(title="First Volume › Overview", kept_chars=len(body), cut_chars=cut),
    )


def test_the_total_cap_cuts_where_the_whole_runs_out_and_leaves_out_what_no_room_is_left_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Documents past the total are left out whole, and each is listed among the cuts."""
    head = GOLDEN.partition("\n\n==> First Volume › Overview <==")[0]
    monkeypatch.setattr(kb_readme, "EXCERPTS_TOTAL_CHARS", len(head) + 1)

    excerpts = kb_readme.compose_excerpts(_tree(tmp_path))

    assert excerpts.text == head
    assert [cut.title for cut in excerpts.cuts] == ["First Volume › Overview", "Second Volume"]
    assert all(cut.kept_chars == 0 for cut in excerpts.cuts)
