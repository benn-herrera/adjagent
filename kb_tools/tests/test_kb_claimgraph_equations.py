"""The equation node: which equations get one, how it is named, and what can reach it.

A referenced equation that no claim-bearing block and no proof holds is minted as
an ordinary ``clm-`` node so that the corpus's own cross-references to it resolve.
Three properties carry this module, and each is a place where a rule that reads
right in the abstract is wrong on the corpus:

**Which equations.** The population is bounded at both ends — by the author's
cross-references, so an equation nobody cites mints nothing, and by what already
holds the equation, so one labelled inside a theorem or inside a proof mints
nothing either. Get either bound wrong and the graph gains a node per numbered
formula in the corpus.

**What can reach it.** A minted node is reachable through the label-to-fence join
and through nothing else: not the identifier route, not the sole-claim fallback,
and not the prose source end's ``tuple(hosted)``. Measured over the staged
corpus, letting it be an ordinary hosted claim cost 205 existing sole-claim edges
and manufactured 132 references onto equations no author pointed at, so the
restriction is a measured requirement rather than a preference.

**That it is terminal.** The only reference that could run *from* an equation is
one sealed inside a maths fence, and such a reference reaches the tree as no
anchor at all — so an equation node is named and names nothing, whatever the
corpus does.

The tree below is written to put each of those on a different document, so a
failure names which one.
"""

import os
import shutil
from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_schema, kb_util, verify_kb_metadata
from kb_tools.kb_claimgraph import attribute, equation, graph, inventory, tree
from kb_tools.kb_claimgraph.build import build

_PACKAGE_ROOT = Path(kb_util.__file__).resolve().parent

pytestmark = pytest.mark.skipif(
    shutil.which("just") is None,
    reason="the declared pass's last stage runs the consuming project's runner targets",
)

_UPLINK = "[↑ Vol](index.md)"
_ENTRY_POINT = "# Knowledge Base\n\n- [Vol](vol/index.md)\n"
_VOLUME_INDEX = (
    "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n"
    "- [Alpha](alpha.md)\n- [Beta](beta.md)\n- [Gamma](gamma.md)\n- [Delta](delta.md)\n"
)

# Alpha carries four labelled equations across the three homes that decide the
# question, plus the one nobody cites:
#   eq:held  — inside a claim-bearing block, which already holds it
#   eq:free  — free-standing and cited, which is the whole mint population
#   eq:quiet — free-standing and cited by nobody, which is scaffolding
#   eq:twice — free-standing, cited twice, and one node rather than two
_ALPHA = f"""{_UPLINK}

# Alpha

> <span id="thm:alpha">**theorem**</span>
>
> **Theorem 1** (Alpha result). *Alpha holds for every admissible state.*
>
> ``` math
> \\begin{{equation}}
> \\label{{eq:held}}
>  a = b
> \\end{{equation}}
> ```

The approximation is

``` math
\\begin{{equation}}
\\label{{eq:free}}
 u = v + w
\\end{{equation}}
```

and a step nobody returns to is

``` math
\\begin{{equation}}
\\label{{eq:quiet}}
 p = q
\\end{{equation}}
```

and one two references share is

``` math
\\begin{{equation}}
\\label{{eq:twice}}
 r = s
\\end{{equation}}
```
"""

# Beta states a lemma, proves it, and the proof both cites alpha's equations and
# labels one of its own — eq:step, which the proof's own subject holds.
_BETA = f"""{_UPLINK}

# Beta

> <span id="thm:beta">**lemma**</span>
>
> **Lemma 2** (Beta lemma). *Beta holds on the interior.*

> **proof**
>
> *Proof.* Substituting
> <a href="alpha.md" data-reference-type="eqref" data-reference="eq:free">2</a>
> and <a href="alpha.md" data-reference-type="eqref" data-reference="eq:held">1</a>
> and <a href="alpha.md" data-reference-type="eqref" data-reference="eq:twice">4</a>
> and <a href="gamma.md" data-reference-type="ref" data-reference="eq:lone">6</a> gives
>
> ``` math
> \\begin{{equation}}
> \\label{{eq:step}}
>  x = y
> \\end{{equation}}
> ```
>
> which closes the argument. ◻

Beta's own step is restated at
<a href="beta.md" data-reference-type="eqref" data-reference="eq:step">5</a>, and
alpha's shared one again at
<a href="alpha.md" data-reference-type="eqref" data-reference="eq:twice">4</a>, and
delta's estimate at
<a href="delta.md" data-reference-type="eqref" data-reference="eq:delta">7</a>.
"""

# Gamma states no result at all and carries one cited equation, which is the
# case `narrow` used to drop before it ran the join: a document with nothing in
# `hosted_by` to bail on.
_GAMMA = f"""{_UPLINK}

# Gamma

A construction used elsewhere:

``` math
\\begin{{equation}}
\\label{{eq:lone}}
 m = n
\\end{{equation}}
```
"""

# Delta's heading is the shape two papers of the staged corpus carry and that a
# first cut of this row failed on: an H1 is *rendered* LaTeX, so a section the
# author titled `Proof of Theorem~\ref{thm:x}` has an anchor and a non-breaking
# space in its heading. The anchor must not reach a register heading — its href
# is relative to this document and the heading is read elsewhere — and the
# non-breaking space must not survive the compose, because the register returns
# it as an ordinary one and the mint-order proof compares the two.
_DELTA = f"""{_UPLINK}

# Proof of Theorem <a href="alpha.md#thm:alpha" data-reference-type="ref" data-reference="thm:alpha">1</a>

The estimate used above is

``` math
\\begin{{equation}}
\\label{{eq:delta}}
 d = e
\\end{{equation}}
```
"""

_TREE = {
    "entry-point.md": _ENTRY_POINT,
    "vol/index.md": _VOLUME_INDEX,
    "vol/alpha.md": _ALPHA,
    "vol/beta.md": _BETA,
    "vol/gamma.md": _GAMMA,
    "vol/delta.md": _DELTA,
}


@pytest.fixture
def declared(tmp_path: Path) -> Path:
    """A consuming repo carrying the tree, after the declared pass has run green."""
    repo = tmp_path / "consumer"
    for relative, text in _TREE.items():
        target = repo / "kb-root" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / "justfile").write_text("default:\n    @true\n", encoding="utf-8")
    installed = repo / ".claude" / "agents"
    installed.mkdir(parents=True)
    os.symlink(_PACKAGE_ROOT, installed / _PACKAGE_ROOT.name)
    kb_util.install_targets(repo, "just")

    outcome = build(kb_root=repo / "kb-root", repo_root=repo, scratch=repo / kb_util.SCRATCH_DIRNAME / "claimgraph")
    assert not outcome.failed, outcome.lines()
    return repo


def _read(repo: Path):
    documents = tree.read(repo / "kb-root")
    sites = inventory.scan(documents)
    return documents, sites, graph.read(documents, sites)


def _by_title(authored: graph.AuthoredGraph) -> dict[str, graph.ClaimNode]:
    return {node.title: node for node in authored.nodes.values()}


# ---------------------------------------------------------------------------
# 1 — which equations get a node
# ---------------------------------------------------------------------------


def test_only_a_cited_equation_nothing_else_holds_gets_a_node(declared: Path):
    """Both bounds at once: cited, and held by neither a claim block nor a proof."""
    _, sites, _ = _read(declared)
    assert {(found.document, found.label) for found in equation.unheld(sites)} == {
        ("vol/alpha.md", "eq:free"),
        ("vol/alpha.md", "eq:twice"),
        ("vol/gamma.md", "eq:lone"),
        ("vol/delta.md", "eq:delta"),
    }


def test_an_equation_cited_twice_is_one_node(declared: Path):
    """Identity is the label, so the count follows the equations and not the references."""
    _, sites, _ = _read(declared)
    twice = [found for found in equation.unheld(sites) if found.label == "eq:twice"]
    citing = [anchor for anchor in sites.anchors if anchor.label == "eq:twice"]
    assert len(citing) == 2 and len(twice) == 1


# ---------------------------------------------------------------------------
# 2 — how it is named, and how the name survives the round trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label, heading",
    [
        ("Q-basic", "Residual of the approximate surface"),
        ("eq:1", "A heading with (parens) and a `backtick`"),
        ("a,b", "A label the cleveref split would have taken apart"),
        ("eq_under-score:2", "Punctuation a LaTeX label may carry"),
    ],
)
def test_a_title_carries_the_label_back(label, heading):
    assert kb_schema.equation_label(kb_schema.equation_title(label=label, heading=heading)) == label


@pytest.mark.parametrize(
    "title",
    [
        "Theorem 1 (Alpha result)",
        "Equation of state — a claim an author titled this way",
        "Equations (`eq:one`) — the plural is not the grammar",
        "",
    ],
)
def test_a_title_that_is_not_an_equation_node_s_reads_as_none(title):
    assert kb_schema.equation_label(title) is None


def test_the_node_is_titled_from_the_hosting_document_s_own_h1(declared: Path):
    _, _, authored = _read(declared)
    titles = {node.title for node in authored.nodes.values() if node.equation is not None}
    assert titles == {
        "Equation (`eq:free`) — Alpha",
        "Equation (`eq:twice`) — Alpha",
        "Equation (`eq:lone`) — Gamma",
        "Equation (`eq:delta`) — Proof of Theorem 1",
    }


def test_the_locator_is_the_label_and_the_identifier_is_not(declared: Path):
    """The third arm of ``graph.read``'s title-join: an equation has no display line."""
    node = _by_title(_read(declared)[2])["Equation (`eq:free`) — Alpha"]
    assert (node.document, node.locator, node.equation, node.identifier) == (
        "vol/alpha.md",
        "eq:free",
        "eq:free",
        None,
    )


# ---------------------------------------------------------------------------
# 3 — what can reach it
# ---------------------------------------------------------------------------


def test_hosted_by_does_not_carry_an_equation_node(declared: Path):
    """The one accessor both of stage D's fallbacks stand on."""
    _, _, authored = _read(declared)
    assert {node.title for node in authored.hosted_by("vol/alpha.md")} == {"Alpha result"}
    assert authored.hosted_by("vol/gamma.md") == ()
    assert authored.equation_node("vol/gamma.md", "eq:lone") is not None
    assert authored.equation_node("vol/gamma.md", "eq:free") is None


def test_a_reference_to_an_unheld_equation_settles_on_its_node(declared: Path):
    """The label-to-fence join is the whole of an equation node's reachability."""
    documents, sites, authored = _read(declared)
    nodes = _by_title(authored)
    narrowed = attribute.narrow(documents, authored, sites)
    assert (nodes["Beta lemma"].id, nodes["Equation (`eq:free`) — Alpha"].id) in narrowed.edges
    assert narrowed.routes.get(attribute.BY_EQUATION)


def test_a_reference_into_a_document_hosting_only_an_equation_still_resolves(declared: Path):
    """``narrow`` used to bail on an empty ``hosted_by`` before the join could run."""
    documents, sites, authored = _read(declared)
    nodes = _by_title(authored)
    narrowed = attribute.narrow(documents, authored, sites)
    assert (nodes["Beta lemma"].id, nodes["Equation (`eq:lone`) — Gamma"].id) in narrowed.edges


def test_an_equation_inside_a_claim_block_resolves_to_that_claim_and_mints_nothing(declared: Path):
    documents, sites, authored = _read(declared)
    nodes = _by_title(authored)
    narrowed = attribute.narrow(documents, authored, sites)
    assert (nodes["Beta lemma"].id, nodes["Alpha result"].id) in narrowed.edges
    assert authored.equation_node("vol/alpha.md", "eq:held") is None


def test_an_equation_inside_a_proof_resolves_to_what_the_proof_establishes(declared: Path):
    """No node, because `inventory.Proof` already binds the proof to its subject."""
    documents, sites, authored = _read(declared)
    nodes = _by_title(authored)
    assert authored.equation_node("vol/beta.md", "eq:step") is None
    # Beta's prose restates its own proof's equation, so the pair would be the
    # claim on itself — which is dropped, leaving the reference contributing
    # nothing rather than contributing a self-edge.
    narrowed = attribute.narrow(documents, authored, sites)
    assert (nodes["Beta lemma"].id, nodes["Beta lemma"].id) not in set(narrowed.edges) | set(narrowed.references)


# ---------------------------------------------------------------------------
# 4 — terminality
# ---------------------------------------------------------------------------


def test_an_equation_node_sources_no_edge_and_no_reference(declared: Path):
    """Named and naming nothing, which is why a corpus of them cannot close a cycle."""
    documents, sites, authored = _read(declared)
    minted = {node.id for node in authored.nodes.values() if node.equation is not None}
    narrowed = attribute.narrow(documents, authored, sites)
    assert minted
    assert not [pair for pair in narrowed.edges if pair[0] in minted]
    assert not [pair for pair in narrowed.references if pair[0] in minted]
    assert not [question for question in narrowed.questions if question.source.id in minted]
    assert attribute.check_acyclic(authored, narrowed.edges) == ()


# ---------------------------------------------------------------------------
# 5 — the Tier-2 marker exemption, over the authored bytes
# ---------------------------------------------------------------------------


def test_an_equation_node_neither_takes_a_marker_nor_demands_one_of_its_neighbours(declared: Path):
    """Alpha declares one claim and two equations, and needs no marker for any of them.

    The claim this stands on is that the equation nodes are really there and
    really in the document's own ``claims:`` — a check that passed because
    nothing was minted would be no check at all.
    """
    kb_root = declared / "kb-root"
    alpha = kb_index_lib.parse_frontmatter((kb_root / "vol" / "alpha.md").read_text(encoding="utf-8")) or {}
    state = kb_index_lib.discover_kb(kb_root, diagnostic_stream=None)
    equations = verify_kb_metadata.equation_node_ids(state)

    assert len(alpha["claims"]) == 3
    assert len([node_id for node_id in alpha["claims"] if node_id in equations]) == 2
    assert verify_kb_metadata.check_tier2_coverage([(kb_root / "vol" / "alpha.md", alpha)], equations) == []


def test_a_heading_of_rendered_latex_reaches_the_title_as_the_words_it_shows(declared: Path):
    """Delta's H1 carries an anchor and a non-breaking space; neither may reach the register.

    The failure this closes is not cosmetic. The heading comes back off the
    register with its non-breaking space folded to an ordinary one, so a title
    composed from the raw line is a title the mint-order proof reads as the
    wrong entry — and two papers of the staged corpus stopped their whole build
    on exactly that.
    """
    node = _by_title(_read(declared)[2])["Equation (`eq:delta`) — Proof of Theorem 1"]
    assert "<a " not in node.title and "\u00a0" not in node.title
    landed = kb_index_lib.parse_claim_quality_file(
        declared / "kb-root" / "vol" / "claim-quality.md", declared / "kb-root"
    )
    assert {entry.title for entry in landed if entry.id == node.id} == {node.title}
