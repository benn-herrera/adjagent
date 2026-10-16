"""A reference's passage over an in-memory tree."""

from pathlib import Path

import pytest

from kb_tools.kb_claimgraph import attribute
from kb_tools.kb_claimgraph.tree import Document, Tree

_DOCUMENT = "v/x.md"


@pytest.mark.parametrize(
    "line, want",
    [
        pytest.param(4, "We use [the bound](y.md).", id="body line below the up-link"),
        pytest.param(3, "", id="up-link line"),
        pytest.param(1, "", id="frontmatter line"),
    ],
)
def test_reference_line_stays_below_the_frontmatter(line: int, want: str):
    """A paragraph running on from the up-link line gives its own words alone; the up-link and frontmatter none."""
    text = "---\nkind: leaf\n---\n[up](../index.md)\nWe use [the bound](y.md).\n\n# Heading\n"
    tree = Tree(root=Path("kb-root"), documents={_DOCUMENT: Document(_DOCUMENT, text)}, children={}, parents={})
    assert attribute._reference_line(tree, _DOCUMENT, line) == want
