"""Unit tests over the cross-reference anchor reading: which types it admits and
how many labels one anchor names.

Two boundary conditions carry this module, and both are places where a rule that
looks right in the general case is wrong on real input.

The first is the *type* class. Pandoc spells ``data-reference-type`` four ways
over the staged corpus — ``ref``, ``eqref``, and ``ref+label`` / ``ref+Label``
for the cleveref family — and a pattern enumerating a vocabulary the contract
does not state refuses whichever spelling it did not anticipate.

The second is the *label* split. ``\\cref{a,b}`` names two targets, and cleveref
splits its own argument on the comma, so a cleveref label can never contain one.
A ``\\ref`` label can: the staged corpus carries ``\\ref{cor: decay, hyper,
unif}``. A split keyed on the comma rather than on the type turns those anchors
into dead fragments, which is why the type is what decides.
"""

import pytest

from kb_tools.kb_claimgraph import inventory, tree

_UPLINK = "[↑ Vol](index.md)"
_ENTRY_POINT = "# Knowledge Base\n\n- [Vol](vol/index.md)\n"
_VOLUME_INDEX = "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n- [Leaf](leaf.md)\n"


def _anchor(*, href: str, kind: str, label: str) -> str:
    return f'<a href="{href}" data-reference-type="{kind}" data-reference="{label}">text</a>'


def _tree(tmp_path, leaf_body: str):
    root = tmp_path / "kb-root"
    for path, text in {
        "entry-point.md": _ENTRY_POINT,
        "vol/index.md": _VOLUME_INDEX,
        "vol/leaf.md": f"{_UPLINK}\n\n# Leaf\n\n{leaf_body}\n",
    }.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return tree.read(root)


@pytest.mark.parametrize(
    "kind, label, expected",
    [
        ("ref", "thm:main", ("thm:main",)),
        ("eqref", "eq:one", ("eq:one",)),
        ("ref+label", "thm:main", ("thm:main",)),
        ("ref+Label", "thm:main", ("thm:main",)),
        ("ref+label", "thm:a,thm:b", ("thm:a", "thm:b")),
        ("ref+Label", "a,b,c", ("a", "b", "c")),
        ("ref+label", "thm:a, thm:b", ("thm:a", "thm:b")),
        # The label a `\ref` may legitimately spell with commas. Splitting it
        # would name three labels the tree declares none of.
        ("ref", "cor: decay, hyper, unif", ("cor: decay, hyper, unif",)),
        ("eqref", "eq: a, b", ("eq: a, b",)),
        # A label that is nothing but separators still names whatever it names,
        # rather than yielding no label at all.
        ("ref+label", ",", (",",)),
        ("ref+label", "", ("",)),
    ],
)
def test_an_anchor_names_several_labels_only_where_a_cleveref_named_several(kind, label, expected):
    assert tree.anchor_labels(kind, label) == expected


@pytest.mark.parametrize("kind", ["ref", "eqref", "ref+label", "ref+Label"])
def test_the_pattern_reads_every_type_spelling_pandoc_writes(kind):
    """The type is read back as the attribute spells it, whichever macro wrote it."""
    found = tree.ANCHOR_RE.search(_anchor(href="vol/leaf.md#thm:main", kind=kind, label="thm:main"))
    assert found is not None
    assert found.group(2) == kind


def test_a_cleveref_list_becomes_one_anchor_per_label(tmp_path):
    """One element naming two targets is two readings, alike but for the label.

    Everything else about the anchor is the element's own — the reader emitted
    one tag — so a consumer joining on position or on href sees both.
    """
    read = _tree(tmp_path, _anchor(href="#thm:a,thm:b", kind="ref+label", label="thm:a,thm:b"))
    anchors = inventory.scan(read).anchors

    assert [anchor.label for anchor in anchors] == ["thm:a", "thm:b"]
    assert {anchor.href for anchor in anchors} == {"#thm:a,thm:b"}
    assert len({(anchor.document, anchor.line, anchor.fragment) for anchor in anchors}) == 1


def test_a_single_label_carrying_commas_stays_one_anchor(tmp_path):
    """The `\\ref` case the comma rule would have shattered, read end to end."""
    label = "cor: decay, hyper, unif"
    read = _tree(tmp_path, _anchor(href=f"leaf.md#{label}", kind="ref", label=label))
    anchors = inventory.scan(read).anchors

    assert [anchor.label for anchor in anchors] == [label]
    assert anchors[0].target == "vol/leaf.md"


def test_a_proof_headed_by_a_cleveref_list_reads_both_labels_as_its_subject(tmp_path):
    """What a proof *proves* is never read as something it rests on.

    ``Proof.names`` joins the opening run's anchors to the scan's on ``(href,
    label)``, so the two readings have to split alike. Read whole on one side and
    per label on the other, the join misses and the proof's own subjects come
    back as premises — an edge pointing the wrong way, from one rule, silently.
    """
    head = _anchor(href="#thm:a,thm:b", kind="ref+label", label="thm:a,thm:b")
    rests_on = _anchor(href="leaf.md#thm:c", kind="ref+label", label="thm:c")
    read = _tree(tmp_path, f"> **proof**\n>\n> *Proof of {head}.* It uses {rests_on}. ◻")

    found = inventory.scan(read)
    (proof,) = found.proofs
    by_label = {anchor.label: anchor for anchor in found.anchors}

    assert sorted(by_label) == ["thm:a", "thm:b", "thm:c"]
    assert proof.names(by_label["thm:a"])
    assert proof.names(by_label["thm:b"])
    assert not proof.names(by_label["thm:c"])
