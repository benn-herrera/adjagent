"""The discovered pass: its entry condition, and dependency attribution end to end.

**Every test here runs against a fake reader.** The seam is
:class:`kb_tools.kb_claimgraph.letters.LetterReader` — a composed letter
question in, a reply out — and the fake answers from a fixed table keyed by the
candidate the question names. So the narrowing, the classify asks, the re-ask
and the default, the classification record, ring demotion and the write are all
exercised, and none of it needs a model to be reachable: a check that cannot run
without one is a check that does not run.

The consuming repository is stood up the way a consumer's is: the real runner
snippet, imported by the line the installer writes, over the installed package.
That is what makes the last stage's targets the real ones rather than a
justfile this file invented.
"""

import re
import shutil
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_pipeline, kb_util, refresh_kb_metadata, verify_kb_metadata
from kb_tools.inference import liaison_tools
from kb_tools.kb_claimgraph import __main__ as cli
from kb_tools.kb_claimgraph import (
    ask,
    assemble,
    attribute,
    classify,
    conform,
    depends,
    graph,
    inventory,
    letters,
    report,
    tree,
    write,
)
from kb_tools.kb_claimgraph.build import build
from kb_tools.kb_driver import prompt_templates
from kb_tools.kb_write import render
from kb_tools.tests._claimgraph_consumer import install_claimgraph_consumer
from kb_tools.tests._fixture_templates import compose_from_fixture_templates
from kb_tools.tests._shared_builds import copy_build, held_unchanged

# The last stage reaches the KB through the consuming project's runner targets,
# which is the mechanism and not a detail this file may route around.
pytestmark = [
    pytest.mark.skipif(
        shutil.which("just") is None,
        reason="the discovered pass's last stage runs the consuming project's runner targets",
    ),
    pytest.mark.usefixtures("claimgraph_gate_in_process"),
]


# ---------------------------------------------------------------------------
# A five-leaf corpus: one claim each in three leaves, two in a fourth, none in
# the fifth, and cross-references arranged so every rule this stage applies is
# exercised — a proof bound to its claim by adjacency and another by the result
# its opening run names, an eqref into an equation inside a claim body, a
# section reference into a single-claim document and another into a two-claim
# one, a reference inside a proof that resolves to no claim at all, an anchor
# naming a definition block in each of a single-claim and a two-claim document,
# and one naming a remark block from inside a proof — the shapes that used to
# fall past the identifier route onto a claim nobody pointed at, the last of
# them with both ends settled, which is what makes it an edge rather than a
# candidate.
#
# Every anchor carries all three of the attributes SPEC.md's cross-reference
# join states, in that order, because that is what a rewritten reference is.
# ---------------------------------------------------------------------------

_ENTRY_POINT = "# Knowledge Base\n\n- [Vol](vol/index.md)\n"
_VOLUME_INDEX = (
    "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n"
    "- [Alpha](alpha.md)\n- [Beta](beta.md)\n- [Gamma](gamma.md)\n- [Delta](delta.md)\n"
    "- [Epsilon](epsilon.md)\n"
)
_UPLINK = "[↑ Vol](index.md)"

_ALPHA = f"""{_UPLINK}

# Alpha

> <span id="thm:alpha">**theorem**</span>
>
> **Theorem 1** (Alpha result). *Alpha holds for every admissible state.*
>
> ``` math
> \\begin{{equation}}
> \\label{{eq:one}}
>  a = b
> \\end{{equation}}
> ```

> <span id="def:alpha">**definition**</span>
>
> **Definition 1** (Admissible state). *A state is admissible when it is bounded.*

> <span id="rem:alpha">**remark**</span>
>
> **Remark 1** (Numerical evidence). *The bound is sharp in simulation.*

Alpha is argued from
<a href="beta.md#thm:beta" data-reference-type="ref" data-reference="thm:beta">Lemma 2</a>,
and it reads a term settled in
<a href="gamma.md#def:gamma" data-reference-type="ref" data-reference="def:gamma">Definition 2</a>.
"""

_BETA = f"""{_UPLINK}

# Beta

> <span id="thm:beta">**lemma**</span>
>
> **Lemma 2** (Beta lemma). *Beta holds on the interior.*

> **proof**
>
> *Proof.* Beta rests on
> <a href="gamma.md#thm:g2" data-reference-type="ref" data-reference="thm:g2">Lemma 1</a> and on
> <a href="epsilon.md#epsilon" data-reference-type="ref" data-reference="sec:epsilon">Section 5</a>,
> which states no result of its own. The evidence is collected in
> <a href="alpha.md#rem:alpha" data-reference-type="ref" data-reference="rem:alpha">Remark 1</a>. ◻

Beta is read beside
<a href="gamma.md#thm:g1" data-reference-type="ref" data-reference="thm:g1">Theorem 1</a>,
over the states of
<a href="alpha.md#def:alpha" data-reference-type="ref" data-reference="def:alpha">Definition 1</a>.
"""

_GAMMA = f"""{_UPLINK}

# Gamma

> <span id="thm:g1">**theorem**</span>
>
> **Theorem 1** (Gamma one). *The first gamma result.*

> <span id="thm:g2">**lemma**</span>
>
> **Lemma 1** (Gamma two). *The second gamma result.*

> **proof**
>
> *Proof of
> <a href="gamma.md#thm:g1" data-reference-type="ref" data-reference="thm:g1">Theorem 1</a>.*
> It follows from equation
> <a href="alpha.md" data-reference-type="eqref" data-reference="eq:one">1</a>. ◻

> <span id="def:gamma">**definition**</span>
>
> **Definition 2** (Interior). *The interior is the set of non-boundary states.*

Both are read beside
<a href="alpha.md#thm:alpha" data-reference-type="ref" data-reference="thm:alpha">Theorem 1</a>.
"""

_DELTA = f"""{_UPLINK}

# Delta

> <span id="thm:delta">**proposition**</span>
>
> **Proposition 1** (Delta result). *Delta stands on its own.*

Delta names no result of anyone else's. It points at two whole sections —
<a href="alpha.md#alpha" data-reference-type="ref" data-reference="sec:alpha">Section 1</a>,
which hosts one claim and can therefore mean no other, and
<a href="gamma.md#gamma" data-reference-type="ref" data-reference="sec:gamma">Section 3</a>,
which hosts two and stays ambiguous.
"""

_EPSILON = f"""{_UPLINK}

# Epsilon

The author marked no result here, so the declared pass writes its plain
reason and the node pass is what would read it.
"""

_TREE = {
    "entry-point.md": _ENTRY_POINT,
    "vol/index.md": _VOLUME_INDEX,
    "vol/alpha.md": _ALPHA,
    "vol/beta.md": _BETA,
    "vol/gamma.md": _GAMMA,
    "vol/delta.md": _DELTA,
    "vol/epsilon.md": _EPSILON,
}


# ---------------------------------------------------------------------------
# The fake inference
# ---------------------------------------------------------------------------


class FakeReader:
    """A :class:`letters.LetterReader` answering from a table keyed by ``(source title, target title)``.

    A value is the reply text on every call, or a tuple of replies, one per
    call, for a candidate whose first answer and re-ask differ. A candidate the
    table does not name is answered ``default``. ``fail_on`` names a source
    whose group's calls never complete, which is how a stop mid-stage is
    expressed without a subprocess.
    """

    def __init__(
        self,
        repo: Path,
        answers: dict[tuple[str, str], str | tuple[str, ...]] | None = None,
        *,
        default: str = ask.ClassifyLetter.MENTION,
        fail_on: str | None = None,
    ):
        _, _, authored = _read(repo)
        self._titles = {node.id: node.title for node in authored.nodes.values()}
        self._answers = answers or {}
        self._default = default
        self._fail_on = fail_on
        self._calls: Counter[tuple[str, str]] = Counter()
        self.questions: list[letters.LetterQuestion] = []

    def __call__(self, question: letters.LetterQuestion) -> letters.Reply:
        key = (self._titles[question.group], self._titles[question.item])
        if key[0] == self._fail_on:
            raise ask.AskError("inference-failed", f"{key}: the call never completed")
        self.questions.append(question)
        answer = self._answers.get(key, self._default)
        if isinstance(answer, tuple):
            answer = answer[self._calls[key]]
        self._calls[key] += 1
        return letters.Reply(text=answer)

    def asked(self) -> set[tuple[str, str]]:
        """Every candidate put to this reader, as ``(source title, target title)``."""
        return {(self._titles[question.group], self._titles[question.item]) for question in self.questions}


def _closing_letters(prompt: str) -> set[str]:
    """The letters a classify prompt's closing question names, past the candidate's statement."""
    return set(re.findall(r"\b[A-Z]\b", prompt.rsplit("````````````", maxsplit=1)[1]))


# ---------------------------------------------------------------------------
# The consuming repository, and the declared pass over it
# ---------------------------------------------------------------------------


@pytest.fixture
def consumer(tmp_path: Path) -> Path:
    """A repo carrying the tree, the installed package and the real runner targets."""
    return install_claimgraph_consumer(tmp_path / "consumer", _TREE)


def _scratch(repo: Path) -> Path:
    return repo / kb_util.scratch_dirname() / "claimgraph"


def test_a_build_completes_over_a_document_carrying_an_unknown_environment(consumer: Path, runner_gate: None) -> None:
    """The property a sweep over an unfamiliar corpus depends on: a build, not a stop.

    Driven through the whole declared pass rather than through stage B alone,
    because what an unclassified name used to cost was the *build*: every stage
    after the inventory has to accept a block nobody classified, and the gates
    at the end have to stay green over the KB it produced.

    ``Setup`` is a name of that shape and a measured one — one paper of the
    35-paper arXiv survey declares ``\newtheorem{setup}{Setup}``, and it sits in
    the survey's residue of one-offs that no table admits.
    """
    unfamiliar = consumer / "kb-root" / "vol" / "epsilon.md"
    unfamiliar.write_text(
        unfamiliar.read_text(encoding="utf-8")
        + "\n> **Setup**\n>\n> **Setup 1** (Bounded arrivals). *Arrivals are bounded.*\n",
        encoding="utf-8",
    )

    report = build(kb_root=consumer / "kb-root", repo_root=consumer, scratch=_scratch(consumer))

    assert not report.failed, "\n".join(report.lines())
    census = [line for line in report.lines() if "stage-B-unclassified" in line]
    assert census and "Setup=1" in census[0], report.lines()
    # Not claim-bearing, so it mints nothing — the omission the census line is
    # reporting, and the state a later pass with the name classified would find.
    assert "clm-" not in unfamiliar.read_text(encoding="utf-8")


def test_the_calibrated_corpus_reports_no_unclassified_name(consumer: Path) -> None:
    """The line stays quiet where every name is classified, so it means something when it is not."""
    report = build(kb_root=consumer / "kb-root", repo_root=consumer, scratch=_scratch(consumer))

    census = [line for line in report.lines() if "stage-B-unclassified" in line]
    assert census and "none" in census[0], report.lines()


@pytest.fixture(scope="module")
def declared_build(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    repo = install_claimgraph_consumer(tmp_path_factory.mktemp("pass2-declared") / "consumer", _TREE)
    outcome = build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo))
    assert not outcome.failed, outcome.lines()
    with held_unchanged(repo, name="pass2 declared"):
        yield repo


@pytest.fixture
def declared(declared_build: Path, tmp_path: Path) -> Path:
    """This test's own copy of ``consumer`` after the declared pass has run and its gates are green."""
    return copy_build(declared_build, tmp_path / "consumer")


def _read(repo: Path):
    documents = tree.read(repo / "kb-root")
    sites = inventory.scan(documents)
    return documents, sites, graph.read(documents, sites)


def _titles(authored: graph.AuthoredGraph) -> dict[str, str]:
    return {node.title: node.id for node in authored.nodes.values()}


def _register_edges(repo: Path) -> set[tuple[str, str]]:
    """The edges on disk, read back through the production parser."""
    entries = kb_index_lib.parse_claim_quality_file(repo / "kb-root" / "vol" / "claim-quality.md", repo / "kb-root")
    return {(entry.id, edge.target) for entry in entries for edge in entry.depends_on}


# ---------------------------------------------------------------------------
# 1 — the entry condition
# ---------------------------------------------------------------------------


def test_the_entry_condition_accepts_the_declared_pass_s_own_output(declared: Path):
    """The tree pass 1 wrote is exactly what pass 2 must admit — frontmatter and all."""
    state = conform.pass_two_gate(tree.read(declared / "kb-root"))
    assert sorted(state.hosting) == ["vol/alpha.md", "vol/beta.md", "vol/delta.md", "vol/gamma.md"]
    assert state.determined == ("vol/epsilon.md",)
    assert state.undeclared == ()


def test_the_declared_pass_s_own_gate_refuses_that_same_tree(declared: Path):
    """The two guards are different questions, and only the first one is about the tree."""
    with pytest.raises(conform.ConformanceError) as refusal:
        conform.gate(tree.read(declared / "kb-root"))
    assert refusal.value.check == "point-14"


@pytest.mark.parametrize(
    "fields, verdict",
    [
        ({"claims": ["clm-aaaaaa"]}, conform.Determination.HOSTS_CLAIMS),
        ({"no-claim": assemble.BLOCKLESS_REASON}, conform.Determination.AUTHORED_NO_CLAIM),
        ({"no-claim": "The section is a bibliography."}, conform.Determination.AUTHORED_NO_CLAIM),
        ({}, conform.Determination.UNDECLARED),
        ({"no-claim": ""}, conform.Determination.UNDECLARED),
    ],
)
def test_no_reason_is_compared_by_identity(fields, verdict):
    """The declared pass's reason is a reason like any other: what a leaf was read to is the record's."""
    assert conform.determination(fields) is verdict


def test_a_tree_the_declared_pass_has_not_run_over_reads_as_leaves_declaring_nothing(consumer: Path):
    """No frontmatter is not a refusal here: it is five leaves declaring nothing.

    Which five is the tree's own answer rather than the missing frontmatter's —
    the entry point and the volume index are excluded by their path shape, the
    way their ``kind:`` would have excluded them had the declared pass stamped
    one. A document in none of the three partitions is invisible to both
    drivers' census lines, and keying the partition on a field that may be
    absent is how one gets there.
    """
    state = conform.pass_two_gate(tree.read(consumer / "kb-root"))

    assert state.undeclared == ("vol/alpha.md", "vol/beta.md", "vol/delta.md", "vol/epsilon.md", "vol/gamma.md")
    assert state.hosting == ()
    assert state.determined == ()


def test_a_marker_on_a_wrapped_anchor_s_first_line_leaves_the_anchor_checked(declared: Path):
    """Pass 2 is the one reader that meets marker bytes, and the anchor check must survive them.

    SPEC.md's cross-reference join admits an anchor hard-wrapped between its
    attributes, and ``kb_write.ops._insert_marker`` appends to the end of the
    located line — so a marker on such an anchor's first line sits between two
    attributes :data:`tree.ANCHOR_RE` requires adjacent. Read raw, the pattern
    matches nothing there and the anchor goes *unchecked* rather than reported,
    which is the one way this check can fail: no other gate in the toolchain
    sees this link form, ``verify_md_links`` reading ``[text](target)`` alone.
    """
    leaf = declared / "kb-root" / "vol" / "alpha.md"
    text = leaf.read_text(encoding="utf-8")
    marker = render.render_tier2_marker(kb_index_lib.parse_frontmatter(text)["claims"][0])
    planted = (
        f'Alpha is also read beside\n<a href="nowhere.md#thm:nowhere" data-reference-type="ref" {marker}\n'
        'data-reference="thm:nowhere">Theorem 9</a>.\n'
    )
    assert not tree.ANCHOR_RE.search(planted), "the marker must land between two attributes or this passes vacuously"
    leaf.write_text(text + planted, encoding="utf-8")

    with pytest.raises(conform.ConformanceError) as refusal:
        conform.pass_two_gate(tree.read(declared / "kb-root"))

    assert refusal.value.check == "point-7"
    assert "nowhere.md#thm:nowhere" in refusal.value.detail


# ---------------------------------------------------------------------------
# 2 — the mechanical narrowing: candidates, classes and drafts
# ---------------------------------------------------------------------------


def _narrowed(declared: Path):
    documents, sites, authored = _read(declared)
    return _titles(authored), attribute.narrow(documents, authored, sites)


def _pairs(narrowed: attribute.Attribution) -> set[tuple[str, str]]:
    return {candidate.pair for candidate in narrowed.candidates}


def _candidate(narrowed: attribute.Attribution, source: str, target: str) -> attribute.Candidate:
    return next(candidate for candidate in narrowed.candidates if candidate.pair == (source, target))


def _settled(ids: dict[str, str]) -> set[tuple[str, str]]:
    """The two pairs the fixture's proofs direct, drafted *supported by* per the tests below."""
    return {(ids["Beta lemma"], ids["Gamma two"]), (ids["Gamma one"], ids["Alpha result"])}


def _open(ids: dict[str, str]) -> set[tuple[str, str]]:
    """The six pairs containment directs nothing about, drafted *mention*."""
    return {
        # a single-claim document's prose reference, resolved at both ends —
        # neither of which says which way an edge between them runs
        (ids["Alpha result"], ids["Beta lemma"]),
        (ids["Beta lemma"], ids["Gamma one"]),
        # a two-claim document leaves the SOURCE open
        (ids["Gamma two"], ids["Alpha result"]),
        # a section reference into a single-claim document names that claim, and
        # one into a two-claim document offers both
        (ids["Delta result"], ids["Alpha result"]),
        (ids["Delta result"], ids["Gamma one"]),
        (ids["Delta result"], ids["Gamma two"]),
    }


def test_every_pair_a_reference_reaches_is_one_candidate(declared: Path):
    """Settled or open, a pair is one candidate; Gamma one's pair with Alpha is reached twice and merged."""
    ids, narrowed = _narrowed(declared)

    assert _pairs(narrowed) == _settled(ids) | _open(ids)
    assert len(narrowed.candidates) == len(_pairs(narrowed))
    assert all(candidate.harvests == {attribute.Harvest.REFERENCE} for candidate in narrowed.candidates)


def test_containment_drafts_supported_by_and_everything_else_drafts_mention(declared: Path):
    """Both arms of the proof-to-claim binding, and the route each target resolved by.

    Beta's proof carries no opening argument, so it binds to the block directly
    above it; Gamma's names its own theorem in its opening run, which is what
    lets a proof bind across a block it does not follow. A draft is what a run
    with no reader writes, and nothing more: every candidate is still asked.
    """
    ids, narrowed = _narrowed(declared)

    assert set(narrowed.edges) == _settled(ids)
    assert set(narrowed.references) == _open(ids)
    assert narrowed.routes == {attribute.BY_IDENTIFIER: 1, attribute.BY_EQUATION: 1}


def test_an_eqref_into_an_equation_inside_a_claim_body_names_that_claim(declared: Path):
    """The equation is no node; the block it is labelled inside states the claim it asserts.

    Asserted through the anchor as well, so a fixture that stopped carrying the
    ``eqref`` — whose fragment is empty, the label riding the third attribute —
    fails here rather than passing vacuously.
    """
    documents, sites, authored = _read(declared)
    ids = _titles(authored)
    equation = [anchor for anchor in sites.anchors if anchor.label.startswith("eq:")]
    assert [(anchor.fragment, anchor.label, anchor.target) for anchor in equation] == [("", "eq:one", "vol/alpha.md")]

    narrowed = attribute.narrow(documents, authored, sites)
    assert (ids["Gamma one"], ids["Alpha result"]) in narrowed.edges


def test_a_reference_inside_a_proof_that_resolves_to_no_claim_contributes_nothing(declared: Path):
    """Beta's proof names two documents; only the one hosting a claim yields an edge.

    A reference is a dependency only where there is something to depend on, and
    a document the author marked no result in is that case rather than a defect.
    """
    documents, sites, authored = _read(declared)
    ids = _titles(authored)
    dangling = [
        (anchor.document, anchor.hosting_environment) for anchor in sites.anchors if anchor.target == "vol/epsilon.md"
    ]
    assert dangling == [("vol/beta.md", "proof")], "the fixture stopped carrying the reference this is about"

    narrowed = attribute.narrow(documents, authored, sites)
    assert {target for source, target in narrowed.edges if source == ids["Beta lemma"]} == {ids["Gamma two"]}


def test_the_anchor_naming_what_a_proof_proves_is_not_read_as_a_dependency(declared: Path):
    """Gamma's proof opens by naming Theorem 1; that reference is its subject, not its warrant."""
    ids, narrowed = _narrowed(declared)
    assert (ids["Gamma one"], ids["Gamma one"]) not in _pairs(narrowed)
    assert (ids["Gamma two"], ids["Gamma one"]) not in _pairs(narrowed)


def test_an_anchor_naming_a_definition_block_contributes_no_pair(declared: Path):
    """The author pointed at a block somebody classified as stating no result.

    Both shapes the corpus carries, on two documents so a failure names which:
    Beta names Alpha's definition and Alpha hosts one claim, so the sole-claim
    route would have answered with that claim; Alpha names Gamma's and Gamma
    hosts two, so the multi-claim enumeration would have offered both. Neither
    is what the reference resolves to, and the exact candidate set asserted
    above is the other half of this — a regression puts these pairs back there.
    """
    documents, sites, authored = _read(declared)
    ids = _titles(authored)

    naming = {
        (anchor.document, anchor.target, anchor.fragment)
        for anchor in sites.anchors
        if anchor.fragment.startswith("def:")
    }
    assert naming == {
        ("vol/beta.md", "vol/alpha.md", "def:alpha"),
        ("vol/alpha.md", "vol/gamma.md", "def:gamma"),
    }, "the fixture stopped carrying the references this is about"
    named = [block for block in sites.blocks if block.identifier in {"def:alpha", "def:gamma"}]
    assert len(named) == 2 and not any(block.claim_bearing for block in named)
    # The refusal may only spend a judgement somebody made, so these blocks have
    # to carry a name stage B classified rather than one nobody has looked at.
    assert {block.environment.casefold() for block in named} <= inventory.NOT_A_CLAIM_TARGET

    reached = _pairs(attribute.narrow(documents, authored, sites))
    assert (ids["Beta lemma"], ids["Alpha result"]) not in reached
    assert (ids["Alpha result"], ids["Gamma one"]) not in reached
    assert (ids["Alpha result"], ids["Gamma two"]) not in reached


def test_an_anchor_naming_a_remark_block_from_a_proof_authors_no_edge(declared: Path, monkeypatch: pytest.MonkeyPatch):
    """The refusal's other shape: both ends settled, so the pair would be drafted an *edge*.

    Beta's proof names a remark in alpha.md: containment directs the source end
    onto the claim that proof establishes, and alpha hosts exactly one claim, so
    the sole-claim route would settle the target and draft Beta's lemma as
    resting on a result nobody referenced.

    The monkeypatch is the non-vacuity guard. Asserting only that the edge is
    absent would pass just as well on a fixture whose anchor never reached the
    route at all; taking ``remark`` back out of the refusal has to put the edge
    back, or this test is asserting nothing.
    """
    documents, sites, authored = _read(declared)
    ids = _titles(authored)

    naming = [anchor for anchor in sites.anchors if anchor.fragment == "rem:alpha"]
    assert [(anchor.document, anchor.target, anchor.hosting_environment) for anchor in naming] == [
        ("vol/beta.md", "vol/alpha.md", "proof")
    ], "the fixture stopped carrying the reference this is about"
    remark = next(block for block in sites.blocks if block.identifier == "rem:alpha")
    assert not remark.claim_bearing and remark.environment.casefold() in inventory.NOT_A_CLAIM_TARGET

    manufactured = (ids["Beta lemma"], ids["Alpha result"])
    assert manufactured not in _pairs(attribute.narrow(documents, authored, sites))

    monkeypatch.setattr(attribute, "NOT_A_CLAIM_TARGET", inventory.NOT_A_CLAIM_TARGET - {"remark"})
    assert manufactured in set(attribute.narrow(documents, authored, sites).edges)


def test_a_fragment_naming_a_block_resolves_the_target_to_that_block_s_claim(declared: Path):
    """gamma.md hosts two claims; beta's prose reference names one of them by its source label.

    Gamma two is Beta's candidate too, through its proof — not through the prose
    reference, which would have offered both had its fragment named neither.
    """
    ids, narrowed = _narrowed(declared)
    beta = {
        candidate.target.id: candidate for candidate in narrowed.candidates if candidate.source.id == ids["Beta lemma"]
    }
    assert set(beta) == {ids["Gamma one"], ids["Gamma two"]}
    assert beta[ids["Gamma one"]].draft is attribute.Relation.MENTION
    assert beta[ids["Gamma two"]].draft is attribute.Relation.SUPPORTED_BY


def test_a_section_reference_resolves_only_where_the_target_hosts_one_claim(declared: Path):
    """Delta's two section references: one document with a single claim, one with two."""
    ids, narrowed = _narrowed(declared)
    assert {candidate.target.id for candidate in narrowed.candidates if candidate.source.id == ids["Delta result"]} == {
        ids["Alpha result"],
        ids["Gamma one"],
        ids["Gamma two"],
    }


def test_the_passage_is_the_anchor_s_paragraph_and_not_the_wrap_it_landed_in(declared: Path):
    """A candidate's passage carries the words around the anchor, not one hard-wrapped line.

    Alpha's closing paragraph is four physical lines and each anchor sits alone on
    one of them, so the words stating what the reference is doing — *Alpha is
    argued from* — are on the line above it. Reading the anchor's own line drops
    them: over the built ModernCorp tree that left 0 of 22 evidence values
    carrying any dependency cue, against 15 of 19 read a paragraph at a time.

    The blank line above the paragraph is the other half of the unit. The claim,
    definition and remark blockquotes above it are not the sentence the anchor
    sits in, and a run that reached them would be a second way of showing the
    seat something the candidate's statement already says.
    """
    ids, narrowed = _narrowed(declared)
    assert _candidate(narrowed, ids["Alpha result"], ids["Beta lemma"]).passages == (
        'Alpha is argued from <a href="beta.md#thm:beta" data-reference-type="ref" '
        'data-reference="thm:beta">Lemma 2</a>, and it reads a term settled in '
        '<a href="gamma.md#def:gamma" data-reference-type="ref" data-reference="def:gamma">Definition 2</a>.',
    )


def test_a_marker_on_a_reference_line_is_not_shown_to_the_seat_that_classifies_it(declared: Path):
    """A candidate's passage is authored prose, and a marker is not prose.

    The passage renders verbatim into the ask's reference-lines slot, and this
    stage always runs over a tree two earlier passes have minted into — so
    unlike the anchor check above, nothing has to go wrong for the two to meet.
    A Tier-2 marker is appended to the end of the line its claim is located by,
    which is the claim's own statement line, so an author who states a result by
    reference puts the anchor and the marker on one line. That is the shape
    planted here.

    Over the 51 built KBs of the staged corpus the shape does not yet occur — 0
    of 6738 anchor lines and 0 of 1675 evidence lines carry a marker, against
    468 markers standing in those trees — so this is a hardening, and the test
    is what keeps it from rotting. Reverting the ``strip_markers`` call in
    :func:`attribute._reference_line` fails the last assertion with the marker
    itself in the message.
    """
    leaf = declared / "kb-root" / "vol" / "gamma.md"
    text = leaf.read_text(encoding="utf-8")
    marker = render.render_tier2_marker(kb_index_lib.parse_frontmatter(text)["claims"][0])
    located = next((line for line in text.splitlines() if line.endswith(marker)), None)
    assert located is not None, "the declared pass stopped marking this leaf, so there is no line to plant on"
    reference = '<a href="beta.md#thm:beta" data-reference-type="ref" data-reference="thm:beta">Lemma 2</a>'
    leaf.write_text(text.replace(located, located.replace(marker, f"{reference} {marker}")), encoding="utf-8")
    assert f"{reference} {marker}" in leaf.read_text(encoding="utf-8"), "the marker must end the reference's own line"

    documents, sites, authored = _read(declared)
    narrowed = attribute.narrow(documents, authored, sites)

    shown = [
        line
        for candidate in narrowed.candidates
        for line in candidate.passages
        if "beta.md#thm:beta" in line and "Gamma one" in line
    ]
    assert len(shown) == 1, f"the planted reference reached no candidate, so this would pass vacuously: {shown}"
    assert marker not in shown[0], shown[0]


@pytest.mark.parametrize(
    "directed, equation, expected",
    [
        (True, None, attribute.CandidateClass.PROOF_DIRECTED),
        (True, "eq:x", attribute.CandidateClass.PROOF_DIRECTED),
        (False, "eq:x", attribute.CandidateClass.EQUATION_TARGET),
        # An `eqref` resolving *through* an equation to a block's claim lands on
        # a node with no `equation`: a claim target, not a sink.
        (False, None, attribute.CandidateClass.CLAIM_TO_CLAIM),
    ],
)
def test_a_provenance_is_classed_on_containment_and_on_the_target_node(directed, equation, expected):
    target = graph.ClaimNode(
        id="clm-tttttt", document="vol/t.md", title="T", locator=None, identifier=None, equation=equation
    )
    assert attribute._class_of(directed=directed, target=target) is expected


def test_every_offered_subset_holds_supported_by_and_mention_and_only_a_claim_pair_is_offered_more():
    """Intersecting two subsets never empties, and the draft is always offered."""
    assert set(attribute.OFFERED) == set(attribute.CandidateClass)
    for subset in attribute.OFFERED.values():
        assert {attribute.Relation.SUPPORTED_BY, attribute.Relation.MENTION} <= subset
    assert [cls for cls, subset in attribute.OFFERED.items() if attribute.Relation.IN_SUPPORT_OF in subset] == [
        attribute.CandidateClass.CLAIM_TO_CLAIM
    ]


def test_each_class_is_offered_its_own_letters_on_the_composed_prompt(declared: Path, tmp_path: Path):
    """Beta's proof-directed pair is offered A or C; its prose pair A, B or C; a merged pair the intersection.

    Gamma one's pair with Alpha is reached by its proof (proof-directed) and by
    gamma's closing prose (claim to claim), so it is offered what both allow.
    The equation-target class has no instance in this corpus and is put to a
    reader directly.
    """
    ids, narrowed = _narrowed(declared)
    reader = FakeReader(declared)
    classify.classify(
        narrowed.candidates,
        graph=_read(declared)[2],
        statement=lambda node: node.title,
        reader=reader,
        repo_root=tmp_path,
    )
    offered = {(q.group, q.item): (q.offered, _closing_letters(q.prompt)) for q in reader.questions}

    two, three = ("A", "C"), ("A", "B", "C")
    assert offered[(ids["Beta lemma"], ids["Gamma two"])] == (two, set(two))
    assert offered[(ids["Gamma one"], ids["Alpha result"])] == (two, set(two))
    assert offered[(ids["Beta lemma"], ids["Gamma one"])] == (three, set(three))
    assert all(offered[pair] == (three, set(three)) for pair in _open(ids))

    source = graph.ClaimNode(id="clm-ssssss", document="vol/s.md", title="S", locator=None, identifier=None)
    sink = graph.ClaimNode(
        id="clm-eeeeee",
        document="vol/s.md",
        title="Equation (`eq:x`) — S",
        locator=None,
        identifier=None,
        equation="eq:x",
    )
    equation_reader = _Always("C")
    classify.classify(
        [_synthetic(source, sink, attribute.CandidateClass.EQUATION_TARGET)],
        graph=graph.AuthoredGraph(nodes={source.id: source, sink.id: sink}),
        statement=lambda node: node.title,
        reader=equation_reader,
        repo_root=tmp_path / "equation",
    )
    (question,) = equation_reader.questions
    assert question.offered == two and _closing_letters(question.prompt) == set(two)


#: Fixture templates for the classify ask, standing in for the working ones so
#: the goldens below pin the composer and move with nothing a wording edit
#: touches. They carry every slot kind the working template does: per-call
#: ``dyn.`` slots, composer-filled letters, the ``classify-options`` alternative
#: in both its letter sets, and the ``correction`` alternative — every
#: alternative's fragment ending without a newline.
_FIXTURE_TEMPLATES = {
    ask.LETTER_TEMPLATES[letters.Kind.CLASSIFY]: (
        "Source @!dyn.claim-line!@\n"
        "@!dyn.claim-text!@\n"
        "Passages:\n"
        "@!dyn.reference-lines!@\n"
        "Candidate @!dyn.candidate-line!@\n"
        "@!dyn.candidate-text!@\n"
        "Cited in @!dyn.candidate-passages!@.\n"
        "@!classify-options!@@!correction!@\n"
    ),
    prompt_templates.ALTERNATIVES["classify-options-three"]: (
        "Answer @!letter-supported-by!@, @!letter-in-support-of!@ or @!letter-mention!@."
    ),
    prompt_templates.ALTERNATIVES["classify-options-two"]: "Answer @!letter-supported-by!@ or @!letter-mention!@.",
    prompt_templates.ALTERNATIVES[ask.LETTER_CORRECTION]: "\n\nAgain; it read:\n@!dyn.returned!@\nOne letter.",
}

#: One group: a claim candidate offered all three letters, and an equation
#: candidate offered two whose passages share the group's numbering.
_GOLDEN_GROUP = ask.ClassifyGroup(
    graph.ClaimNode("clm-aaaaaa", "vol/a.md", "Theorem 1", "**Theorem 1**.", "thm:one"),
    "**Theorem 1**. The map has a unique fixed point.\n",
)
_GOLDEN_CANDIDATES = (
    ask.ClassifyItem(
        graph.ClaimNode("clm-bbbbbb", "vol/b.md", "Lemma 2", "**Lemma 2**.", "lem:two"),
        "**Lemma 2**. The map is a contraction.\n",
        ("vol/a.md:7: By Lemma 2 the map contracts.",),
        tuple(ask.ClassifyLetter),
    ),
    ask.ClassifyItem(
        graph.ClaimNode("clm-cccccc", "vol/b.md", "Equation (3)", None, None, equation="eq:three"),
        "$$ k = \\sup |f'| $$",
        ("vol/a.md:9: with $k$ as in (3).", "vol/a.md:7: By Lemma 2 the map contracts."),
        (ask.ClassifyLetter.SUPPORTED_BY, ask.ClassifyLetter.MENTION),
    ),
)

#: Every ask of the group opens with these bytes: the source claim and the
#: group's passages, numbered P1… across every candidate, end before the first
#: item slot.
_GOLDEN_PREFIX = """\
Source - `clm-aaaaaa` — Theorem 1 (stated in `vol/a.md`: **Theorem 1**.)
**Theorem 1**. The map has a unique fixed point.
Passages:
P1: vol/a.md:7: By Lemma 2 the map contracts.
P2: vol/a.md:9: with $k$ as in (3).
Candidate """

#: Each candidate names its own passages by the group's numbers, and its closing
#: line names exactly the letters it is offered.
_GOLDEN_ITEMS = (
    """\
- `clm-bbbbbb` — Lemma 2 (stated in `vol/b.md`: **Lemma 2**.)
**Lemma 2**. The map is a contraction.
Cited in P1.
Answer A, B or C.""",
    """\
- `clm-cccccc` — Equation (3) (stated in `vol/b.md`)
$$ k = \\sup |f'| $$
Cited in P1, P2.
Answer A or C.""",
)

#: A re-ask is the first ask with the correction after the question, carrying
#: what came back stripped.
_GOLDEN_CORRECTION = """

Again; it read:
I would say B, probably.
One letter."""


@pytest.mark.parametrize("returned", [None, "  I would say B, probably.\n"], ids=["first-ask", "re-ask"])
@pytest.mark.parametrize("candidate", [0, 1], ids=["three-letters", "two-letters"])
def test_the_classify_ask_composes_byte_for_byte_from_fixture_templates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, candidate: int, returned: str | None
):
    compose_from_fixture_templates(monkeypatch, tmp_path, _FIXTURE_TEMPLATES)
    entry = ask.classify_asks(_GOLDEN_GROUP, _GOLDEN_CANDIDATES)[candidate]

    correction = "" if returned is None else _GOLDEN_CORRECTION
    assert entry.compose(returned) == _GOLDEN_PREFIX + _GOLDEN_ITEMS[candidate] + correction + "\n"


# ---------------------------------------------------------------------------
# 3 — classification
# ---------------------------------------------------------------------------


class _Always:
    """A reader replying the same text to every call."""

    def __init__(self, text: str):
        self._text = text
        self.questions: list[letters.LetterQuestion] = []

    def __call__(self, question: letters.LetterQuestion) -> letters.Reply:
        self.questions.append(question)
        return letters.Reply(text=self._text)


def _synthetic(source: graph.ClaimNode, target: graph.ClaimNode, cls: attribute.CandidateClass) -> attribute.Candidate:
    offered = tuple(relation for relation in attribute.Relation if relation in attribute.OFFERED[cls])
    return attribute.Candidate(
        source=source,
        target=target,
        offered=offered,
        draft=attribute.Relation.MENTION,
        passages=("By (1) the bound holds.",),
        harvests=frozenset({attribute.Harvest.REFERENCE}),
    )


def test_an_equation_candidate_answering_b_is_malformed_and_takes_its_draft(tmp_path: Path):
    """*In support of* would originate an edge at a sink, so B is not offered and reads as no letter."""
    source = graph.ClaimNode(id="clm-ssssss", document="vol/s.md", title="S", locator=None, identifier=None)
    sink = graph.ClaimNode(
        id="clm-eeeeee",
        document="vol/s.md",
        title="Equation (`eq:x`) — S",
        locator=None,
        identifier=None,
        equation="eq:x",
    )
    reader = _Always(ask.ClassifyLetter.IN_SUPPORT_OF)

    classified = classify.classify(
        [_synthetic(source, sink, attribute.CandidateClass.EQUATION_TARGET)],
        graph=graph.AuthoredGraph(nodes={source.id: source, sink.id: sink}),
        statement=lambda node: node.title,
        reader=reader,
        repo_root=tmp_path,
    )

    assert len(reader.questions) == 2, "one re-ask, then the draft"
    assert classified.outcomes == {(source.id, sink.id): kb_pipeline.ClassifyOutcome.DEFAULTED}
    assert classified.relations == {(source.id, sink.id): attribute.Relation.MENTION}
    assert classified.edges == () and classified.references == ((source.id, sink.id),)


def test_b_writes_the_edge_target_to_source_and_no_reference(declared: Path, runner_gate: None):
    """*In support of*: Beta needs Alpha, so the edge lands in Beta's entry and Alpha's names nothing."""
    ids, _ = _narrowed(declared)
    reader = FakeReader(declared, {("Alpha result", "Beta lemma"): ask.ClassifyLetter.IN_SUPPORT_OF})

    outcome = depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=reader)

    assert not outcome.failed, outcome.lines()
    assert (ids["Beta lemma"], ids["Alpha result"]) in _register_edges(declared)
    assert (ids["Alpha result"], ids["Beta lemma"]) not in _register_edges(declared)
    references = _register_references(declared)
    assert (ids["Alpha result"], ids["Beta lemma"]) not in references
    assert (ids["Beta lemma"], ids["Alpha result"]) not in references


def test_a_malformed_reply_is_re_asked_once_then_takes_the_draft_named_on_the_report(declared: Path):
    """A reply that arrived is asked for again once; the second miss costs the candidate, not the stage."""
    ids, _ = _narrowed(declared)
    reader = FakeReader(declared, {("Beta lemma", "Gamma two"): ("I think A", "A, probably")})

    outcome = depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=reader)

    assert not outcome.failed, outcome.lines()
    assert [q.item for q in reader.questions].count(ids["Gamma two"]) == 3, "Beta's two asks, and Delta's one"
    assert (ids["Beta lemma"], ids["Gamma two"]) in _register_edges(declared), "the draft containment directed"
    defaulted = next(line for line in outcome.lines() if "stage-D-defaulted" in line)
    assert f"{ids['Beta lemma']} -> {ids['Gamma two']}" in defaulted


def _plant_a_mutual_prose_reference(declared: Path) -> None:
    """Alpha's prose already names Beta; this is Beta's prose naming Alpha back.

    In prose rather than in a proof, so containment directs neither and both are
    claim-to-claim candidates drafted *mention*.
    """
    beta = declared / "kb-root" / "vol" / "beta.md"
    beta.write_text(
        beta.read_text(encoding="utf-8")
        + '\nBeta is contrasted with\n<a href="alpha.md#thm:alpha" data-reference-type="ref" '
        'data-reference="thm:alpha">Theorem 1</a>, which it does not rest on.\n',
        encoding="utf-8",
    )


def test_a_classified_two_cycle_demotes_both_edges_to_references_and_names_them(declared: Path, runner_gate: None):
    """Two answers that cannot both be dependencies: both directions go, both relationships stay."""
    _plant_a_mutual_prose_reference(declared)
    ids, _ = _narrowed(declared)
    ring = {(ids["Alpha result"], ids["Beta lemma"]), (ids["Beta lemma"], ids["Alpha result"])}
    supported = ask.ClassifyLetter.SUPPORTED_BY
    reader = FakeReader(
        declared, {("Alpha result", "Beta lemma"): supported, ("Beta lemma", "Alpha result"): supported}
    )

    outcome = depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=reader)

    assert not outcome.failed, outcome.lines()
    assert ring.isdisjoint(_register_edges(declared))
    assert ring <= _register_references(declared)
    verdict = next(line for line in outcome.lines() if "stage-D-classify" in line)
    assert "2 classified edges lay on a cycle" in verdict
    assert all(f"{source} -> {target}" in verdict for source, target in ring)
    kb = declared / "kb-root"
    assert refresh_kb_metadata.main(["--kb-root", str(kb)]) == 0
    assert verify_kb_metadata.main(["--kb-root", str(kb)]) == 0


def test_a_classification_record_an_earlier_build_left_is_not_this_builds_resume_point(consumer: Path):
    """The declared pass starts this build's record empty, as it starts the node pass's record unread."""
    earlier = kb_pipeline.CandidateEntry(offered=("A", "C"), letter="A", outcome=kb_pipeline.ClassifyOutcome.ANSWERED)
    kb_pipeline.write_classification(
        consumer, kb_pipeline.ClassificationRecord().with_entries({("clm-aaaaaa", "clm-bbbbbb"): earlier})
    )

    outcome = build(kb_root=consumer / "kb-root", repo_root=consumer, scratch=_scratch(consumer))

    assert not outcome.failed, outcome.lines()
    assert dict(kb_pipeline.read_classification(consumer).candidates) == {}


def test_a_stop_mid_stage_resumes_asking_only_the_candidates_not_recorded(declared: Path):
    """A call that never completes stops the stage; every group already answered stays answered."""
    ids, narrowed = _narrowed(declared)
    # Groups are asked in ascending source id and ids are minted at random, so
    # the stop is put on the last group: every other one lands before it.
    last = max(source for source, _ in _pairs(narrowed))
    stopping = FakeReader(declared, fail_on=next(title for title, node_id in ids.items() if node_id == last))

    stopped = depends.build(
        kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=stopping
    )

    assert stopped.failed and any("inference-failed" in line for line in stopped.lines()), stopped.lines()
    recorded = set(kb_pipeline.read_classification(declared).candidates)
    stopped_group = {pair for pair in _pairs(narrowed) if pair[0] == last}
    assert recorded and stopped_group and recorded.isdisjoint(stopped_group)

    resuming = FakeReader(declared)
    resumed = depends.build(
        kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=resuming
    )

    assert not resumed.failed, resumed.lines()
    asked = {(q.group, q.item) for q in resuming.questions}
    assert asked == _pairs(narrowed) - recorded
    assert set(kb_pipeline.read_classification(declared).candidates) == _pairs(narrowed)


@pytest.mark.parametrize(
    "edges, demoted",
    [
        # A chain settles nothing; nothing is on a ring.
        ((("a", "b"), ("b", "c")), ()),
        # The smallest ring: both members go, because nothing separates them.
        ((("a", "b"), ("b", "a")), (("a", "b"), ("b", "a"))),
        # A longer ring goes whole, and the edge entering it from outside stays:
        # it lies on no cycle and the ring says nothing about it.
        ((("x", "a"), ("a", "b"), ("b", "c"), ("c", "a")), (("a", "b"), ("b", "c"), ("c", "a"))),
        # A chord is on a ring of its own and goes with them.
        ((("a", "b"), ("b", "c"), ("c", "a"), ("a", "c")), (("a", "b"), ("a", "c"), ("b", "c"), ("c", "a"))),
        # Two rings sharing no edge; each goes, and the bridge between them
        # stays, being on neither.
        (
            (("a", "b"), ("b", "a"), ("b", "c"), ("c", "d"), ("d", "c")),
            (("a", "b"), ("b", "a"), ("c", "d"), ("d", "c")),
        ),
    ],
)
def test_every_edge_on_a_ring_is_demoted_and_no_other_edge_is(edges, demoted):
    """The rule is *on a cycle*, not a feedback set: a ring goes whole, its surroundings stand."""
    assert attribute.cycle_edges(edges) == demoted
    kept = [edge for edge in edges if edge not in demoted]
    assert attribute.cycle_edges(kept) == (), "what remains carries no cycle"


def test_the_demoted_set_is_a_property_of_the_edges_and_not_of_their_order():
    """Two runs over one corpus demote the same edges — no tie-break key to agree on."""
    edges = [("a", "b"), ("b", "c"), ("c", "a"), ("x", "a"), ("b", "y"), ("y", "b")]
    forward = attribute.cycle_edges(edges)

    assert forward == attribute.cycle_edges(list(reversed(edges)))
    assert forward == attribute.cycle_edges(sorted(edges, key=lambda edge: edge[1]))


def _plant_a_mutual_proof_cycle(declared: Path) -> None:
    """Alpha's proof rests on Beta and Beta's on Alpha: a ring of settled pairs alone.

    The tree is edited rather than fixtured because a corpus this shape is the
    pathology, not the norm.
    """
    kb = declared / "kb-root" / "vol"
    proof_of = (
        '\n> **proof**\n>\n> *Proof of <a href="{proved}" data-reference-type="ref" '
        'data-reference="{proved_label}">1</a>.* It rests on '
        '<a href="{rests_on}" data-reference-type="ref" data-reference="{rests_label}">2</a>. ◻\n'
    )
    for leaf, proved, rests_on in (("alpha.md", "thm:alpha", "thm:beta"), ("beta.md", "thm:beta", "thm:alpha")):
        other = "beta.md" if leaf == "alpha.md" else "alpha.md"
        (kb / leaf).write_text(
            (kb / leaf).read_text(encoding="utf-8")
            + proof_of.format(
                proved=f"{leaf}#{proved}", proved_label=proved, rests_on=f"{other}#{rests_on}", rests_label=rests_on
            ),
            encoding="utf-8",
        )


def test_a_containment_ring_drafts_mention_and_is_still_asked(declared: Path, tmp_path: Path):
    """Two proofs each proving what the other rests on: the ring cannot all be dependencies.

    That is not proof the corpus reasons circularly, and it says nothing about
    the paper's other pairs — so the ring's drafts become *mention*, the rest
    stand, and each ring pair is put to a reader like any other candidate.
    """
    _plant_a_mutual_proof_cycle(declared)

    documents, sites, authored = _read(declared)
    ids = _titles(authored)
    ring = {(ids["Alpha result"], ids["Beta lemma"]), (ids["Beta lemma"], ids["Alpha result"])}
    narrowed = attribute.narrow(documents, authored, sites)

    assert set(narrowed.demoted) == ring
    assert set(narrowed.edges) == _settled(ids), "the drafts off the ring are untouched"
    assert ring <= set(narrowed.references)
    assert attribute.cycle_edges(narrowed.edges) == ()

    reader = FakeReader(declared)
    classify.classify(
        narrowed.candidates, graph=authored, statement=lambda node: node.title, reader=reader, repo_root=tmp_path
    )
    assert ring <= {(q.group, q.item) for q in reader.questions}


# ---------------------------------------------------------------------------
# 4 — end to end
# ---------------------------------------------------------------------------


def test_the_discovered_pass_runs_end_to_end_against_a_fake_reader(declared: Path, runner_gate: None):
    """Pass 1's output in, edges authored through the write API, the runner's gates green.

    Every candidate is asked once, containment's drafts included; a candidate
    answered *supported by* writes a dependency and no reference beside it.
    """
    supported = ask.ClassifyLetter.SUPPORTED_BY
    reader = FakeReader(
        declared,
        {
            ("Beta lemma", "Gamma two"): supported,
            ("Gamma one", "Alpha result"): supported,
            ("Beta lemma", "Gamma one"): supported,
            ("Gamma two", "Alpha result"): supported,
        },
    )
    report = depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=reader)
    assert not report.failed, report.lines()

    _, _, authored = _read(declared)
    ids = _titles(authored)
    assert len(reader.questions) == len(_settled(ids) | _open(ids))
    raised = _settled(ids) | {(ids["Beta lemma"], ids["Gamma one"]), (ids["Gamma two"], ids["Alpha result"])}
    assert _register_edges(declared) == raised
    assert _register_references(declared) == _open(ids) - raised

    record = kb_pipeline.read_classification(declared)
    assert {entry.outcome for entry in record.candidates.values()} == {kb_pipeline.ClassifyOutcome.ANSWERED}

    kb = declared / "kb-root"
    assert refresh_kb_metadata.main(["--kb-root", str(kb)]) == 0
    assert verify_kb_metadata.main(["--kb-root", str(kb)]) == 0


def test_a_run_over_a_tree_the_declared_pass_never_wrote_asks_nobody_and_authors_no_edge(consumer: Path):
    """Refused at its own door: no node-pass record stands, so no declared pass ran.

    The source end of a reference in prose is read off the record's verdicts,
    and the declared pass is what writes it. Nothing is asked and no values file
    is composed on the way to the refusal.
    """
    reader = _Always("C")
    outcome = depends.build(kb_root=consumer / "kb-root", repo_root=consumer, scratch=_scratch(consumer), reader=reader)
    assert outcome.failed, outcome.lines()
    assert any("node-pass-record" in line for line in outcome.lines()), outcome.lines()
    assert reader.questions == []
    assert not (_scratch(consumer) / "3-add-depends-on.toml").exists()


def test_the_write_op_is_the_only_thing_that_composes_an_edge(declared: Path):
    """The values file carries ids; the bullet's bytes are the write API's."""
    _, _, authored = _read(declared)
    ids = _titles(authored)
    findings = write.write_edges(
        [(ids["Alpha result"], ids["Beta lemma"])], kb_root=declared / "kb-root", scratch=_scratch(declared)
    )
    assert [finding.status for finding in findings] == [report.PASS]
    values = (_scratch(declared) / "3-add-depends-on.toml").read_text(encoding="utf-8")
    assert "—" not in values and "depends-on" in values


# ---------------------------------------------------------------------------
# 5 — a run with no model reachable
# ---------------------------------------------------------------------------


def _entries(kb: Path) -> list[kb_index_lib.ClaimEntry]:
    """Every claim entry on disk, through the production parser."""
    return kb_index_lib.parse_claim_quality_file(kb / "vol" / "claim-quality.md", kb)


def _register_references(repo: Path) -> set[tuple[str, str]]:
    """The references on disk, read back through the production parser."""
    return {(entry.id, edge.target) for entry in _entries(repo / "kb-root") for edge in entry.references}


def test_a_run_with_no_model_writes_every_candidate_s_draft(declared: Path, monkeypatch, capsys):
    """Through the shipped command line, which is what a seat is told to run.

    The narrowing asks nobody, so its drafts are the corpus's answer whether or
    not a model is reachable: the pairs containment directs as dependencies, and
    every other pair as a reference, each recorded as drafted.
    """
    ids, narrowed = _narrowed(declared)
    monkeypatch.chdir(declared)

    assert cli.main(["--pass", "2", kb_util.NO_INFERENCE_FLAG]) == cli.EXIT_OK
    lines = capsys.readouterr().out

    assert _register_edges(declared) == _settled(ids) == set(narrowed.edges)
    assert _register_references(declared) == _open(ids) == set(narrowed.references)
    assert "no model was asked" in lines
    record = kb_pipeline.read_classification(declared)
    assert set(record.candidates) == _pairs(narrowed)
    assert {entry.outcome for entry in record.candidates.values()} == {kb_pipeline.ClassifyOutcome.DRAFTED}
    kb = declared / "kb-root"
    assert refresh_kb_metadata.main(["--kb-root", str(kb)]) == 0
    assert verify_kb_metadata.main(["--kb-root", str(kb)]) == 0


def test_a_drafted_candidate_is_asked_by_a_later_run_that_has_a_reader(declared: Path):
    """A draft records that no reader was there, not an answer a reader gave."""
    ids, narrowed = _narrowed(declared)
    assert not depends.build(
        kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=None
    ).failed

    reader = FakeReader(declared)
    depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=reader)

    assert {(q.group, q.item) for q in reader.questions} == _pairs(narrowed)


def test_a_reference_does_not_reach_the_solidity_of_any_claim(declared: Path):
    """A reference gates nothing — the same computation over the same corpus, twice."""
    kb = declared / "kb-root"
    before = kb_index_lib.compute_solidity(_entries(kb))

    outcome = depends.build(kb_root=kb, repo_root=declared, scratch=_scratch(declared), reader=None)
    assert not outcome.failed, outcome.lines()
    assert _register_references(declared), "the fixture must actually author references for this to bind"

    assert kb_index_lib.compute_solidity(_entries(kb)) == before


def test_a_mutual_reference_pair_does_not_stop_the_stage(declared: Path):
    """Two claims naming each other is the author's argument, not a dependency cycle.

    The acyclicity gate runs over ``depends`` alone, so a corpus whose claims
    name each other mutually builds and its registers verify.
    """
    _plant_a_mutual_prose_reference(declared)
    ids, narrowed = _narrowed(declared)
    ring = ((ids["Alpha result"], ids["Beta lemma"]), (ids["Beta lemma"], ids["Alpha result"]))
    assert set(ring) <= set(narrowed.references)

    # The counterfactual the class exists to avoid: the same two pairs read as
    # dependencies close a cycle. The gate never sees them, so it still passes.
    assert attribute.cycle_edges(list(ring)) != ()
    assert attribute.cycle_edges(narrowed.edges) == ()

    outcome = depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=None)

    assert not outcome.failed, outcome.lines()
    assert set(ring) <= _register_references(declared)
    kb = declared / "kb-root"
    assert refresh_kb_metadata.main(["--kb-root", str(kb)]) == 0
    assert verify_kb_metadata.main(["--kb-root", str(kb)]) == 0


def test_a_ring_among_the_settled_pairs_costs_its_own_edges_and_not_the_paper(declared: Path):
    """End to end, with nobody to ask: the paper still gets a graph, and it says which pairs went.

    This is the case a 50-paper sweep met three times, each of which produced no
    graph at all for the paper — the ring's edges are the only ones it may cost.
    """
    _plant_a_mutual_proof_cycle(declared)
    ids, narrowed = _narrowed(declared)
    ring = {(ids["Alpha result"], ids["Beta lemma"]), (ids["Beta lemma"], ids["Alpha result"])}

    outcome = depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=None)

    assert not outcome.failed, outcome.lines()
    assert _register_edges(declared) == _settled(ids)
    assert ring <= _register_references(declared)
    line = next(line for line in outcome.lines() if "stage-D-containment-ring" in line)
    assert "2 pairs containment directed lay on a cycle" in line
    assert all(f"{source} -> {target}" in line for source, target in narrowed.demoted)

    kb = declared / "kb-root"
    assert refresh_kb_metadata.main(["--kb-root", str(kb)]) == 0
    assert verify_kb_metadata.main(["--kb-root", str(kb)]) == 0


def test_claim_discovery_has_no_run_that_asks_nobody(declared: Path, monkeypatch, capsys):
    """Refused at the command line rather than run empty into its own exit condition."""
    monkeypatch.chdir(declared)

    assert cli.main(["--pass", "1", "--scope", "full", kb_util.NO_INFERENCE_FLAG]) == cli.EXIT_USAGE

    assert kb_util.NO_INFERENCE_FLAG in capsys.readouterr().err


@pytest.mark.parametrize("argv", [["--pass", "2"], ["--pass", "1", "--scope", "full"]], ids=["pass-2", "discovery"])
def test_a_run_spending_inference_with_no_server_named_exits_naming_the_variable(
    argv: list[str], declared: Path, monkeypatch, capsys
):
    """A message on stderr and the exit the driver reads as an environment fault, never a traceback."""
    monkeypatch.chdir(declared)

    assert cli.main(argv) == cli.EXIT_USAGE

    err = capsys.readouterr().err
    assert liaison_tools.BASE_URL_ENV in err
    assert "Traceback" not in err
