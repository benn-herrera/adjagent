"""Reading order, claim positions and adjacency links over an in-memory tree."""

from pathlib import Path

import pytest

from kb_tools.kb_claimgraph import inventory, order
from kb_tools.kb_claimgraph.graph import AuthoredGraph, ClaimNode
from kb_tools.kb_claimgraph.tree import Document, Tree
from kb_tools.kb_write import render

_LEAF = "v/leaf.md"
_M = render.render_tier2_marker

#: clm-b and clm-d share a paragraph, a non-claim paragraph follows, then clm-a, then the fence of equation
#: node clm-e (line 10), then clm-c, then the theorem block of clm-t (line 18). Id order differs from line order.
_LEAF_TEXT = "\n".join(
    [
        "[↑ Vol](index.md)",
        "# Leaf",
        "",
        "Beta holds. " + _M("clm-b"),
        "Delta holds too. " + _M("clm-d"),
        "",
        "A remark that states nothing.",
        "",
        "Alpha holds. " + _M("clm-a"),
        "",
        "``` math",
        "x = 1 \\label{eq:one}",
        "```",
        "",
        "Gamma holds. " + _M("clm-c"),
        "",
        "More prose.",
        "",
        '> <span id="thm:t">**theorem**</span>',
        ">",
        "> **Theorem 1** (Tau). *Tau holds.*",
        "",
    ]
)


def _fixture(*ids: str) -> tuple[Tree, AuthoredGraph, inventory.Inventory]:
    documents = {
        "entry-point.md": Document("entry-point.md", "# KB\n\n- [Vol](v/index.md)\n"),
        "v/index.md": Document("v/index.md", "[↑ KB](../entry-point.md)\n\n# Vol\n\n- [Leaf](leaf.md)\n"),
        _LEAF: Document(_LEAF, _LEAF_TEXT),
    }
    tree = Tree(
        root=Path("kb-root"),
        documents=documents,
        children={"entry-point.md": ("v/index.md",), "v/index.md": (_LEAF,), _LEAF: ()},
        parents={"v/index.md": "entry-point.md", _LEAF: "v/index.md"},
    )
    sites = inventory.scan(tree)
    (block,) = sites.claim_blocks()
    every = {
        "clm-a": ClaimNode("clm-a", _LEAF, "Alpha", None, None),
        "clm-b": ClaimNode("clm-b", _LEAF, "Beta", None, None),
        "clm-c": ClaimNode("clm-c", _LEAF, "Gamma", None, None),
        "clm-d": ClaimNode("clm-d", _LEAF, "Delta", None, None),
        "clm-e": ClaimNode("clm-e", _LEAF, "(eq:one)", "eq:one", None, equation="eq:one"),
        "clm-t": ClaimNode("clm-t", _LEAF, "Tau", block.display, "thm:t"),
        "clm-z": ClaimNode("clm-z", _LEAF, "Unmarked", None, None),
    }
    return tree, AuthoredGraph(nodes={node_id: every[node_id] for node_id in ids}), sites


def test_reading_order_is_preorder_over_children_as_each_document_lists_them():
    tree = Tree(
        root=Path("kb-root"),
        documents={},
        children={
            "entry-point.md": ("z/index.md", "a/index.md"),
            "z/index.md": ("z/b.md", "z/a.md"),
            "a/index.md": ("a/x.md",),
        },
        parents={},
    )
    assert order.reading_order(tree) == ["entry-point.md", "z/index.md", "z/b.md", "z/a.md", "a/index.md", "a/x.md"]


@pytest.mark.parametrize(
    "claim, want",
    [
        ("clm-b", order.Position(2, 3)),
        ("clm-d", order.Position(2, 3)),
        ("clm-a", order.Position(2, 8)),
        ("clm-e", order.Position(2, 10)),
        ("clm-t", order.Position(2, 18)),
        ("clm-z", order.Position(2, order.UNREACHED_LINE)),
    ],
    ids=["prose", "prose-sharing-a-paragraph", "prose-later", "equation-at-fence", "block", "reached-by-nothing"],
)
def test_a_claim_sits_at_its_body_or_fence_first_line_and_one_neither_reaches_last(claim, want):
    tree, authored, sites = _fixture("clm-a", "clm-b", "clm-d", "clm-e", "clm-t", "clm-z")
    assert order.claim_positions(tree, authored, sites)[claim] == want


@pytest.mark.parametrize(
    "ids, marked, want",
    [
        (("clm-b", "clm-d"), set(), [("clm-b", "clm-d")]),
        (("clm-d", "clm-a"), set(), [("clm-a", "clm-d")]),
        (("clm-a", "clm-e", "clm-c"), set(), [("clm-a", "clm-c")]),
        (
            ("clm-a", "clm-b", "clm-c", "clm-d"),
            {order.link("clm-d", "clm-a")},
            [("clm-a", "clm-c"), ("clm-b", "clm-d")],
        ),
    ],
    ids=["sharing-a-paragraph", "across-a-non-claim-paragraph", "across-an-equation-node", "a-marked-pair-left-out"],
)
def test_adjacency_links_consecutive_non_equation_claims_of_a_leaf(ids, marked, want):
    tree, authored, sites = _fixture(*ids)
    assert order.adjacent_links(authored, order.claim_positions(tree, authored, sites), marked) == want
