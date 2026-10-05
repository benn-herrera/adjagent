"""The node pass: one letter ask per paragraph, the verdicts, the record, and the node set it fixes.

**The inference is fixed at the :class:`~kb_tools.kb_claimgraph.letters.LetterReader`
seam.** The fake resolves the paragraph each question names against the leaf on
disk and answers by the phrases that paragraph holds. So which paragraphs are
asked, every default and its cause, the record-then-KB-then-landed order,
completion of a stopped run, the per-leaf write, stage D's use of the verdicts
and the equation stage's are all exercised, and none of it depends on the
wording of a prompt.

The corpus puts each case on its own leaf:

* **alpha** hosts a theorem and three paragraphs holding references — one a
  claim, one not, and one too short to open a claim that is asked all the same —
  and a fourth holding none, which is a claim;
* **beta** hosts no block, and its one reference-bearing paragraph is a claim
  carrying its own equation;
* **gamma** hosts no block, states nothing, carries a markup-only paragraph, and
  holds the one equation that only alpha's not-a-claim paragraph names;
* **delta** hosts a lemma and nothing else to read but its heading.
"""

import shutil
import subprocess
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_pipeline, kb_schema, kb_util, verify_kb_metadata
from kb_tools.kb_claimgraph import (
    ask,
    attribute,
    depends,
    discover,
    equations,
    graph,
    identify,
    inventory,
    letters,
    prose,
    tree,
    write,
)
from kb_tools.kb_claimgraph.assemble import BLOCKLESS_REASON
from kb_tools.kb_claimgraph.build import build
from kb_tools.kb_claimgraph.report import ClaimGraphError
from kb_tools.kb_write import ops, render
from kb_tools.tests._claimgraph_consumer import install_claimgraph_consumer
from kb_tools.tests._shared_builds import copy_build, held_unchanged

_ENTRY_POINT = "# Knowledge Base\n\n- [Vol](vol/index.md)\n"
_VOLUME_INDEX = (
    "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n"
    "- [Alpha](alpha.md)\n- [Beta](beta.md)\n- [Gamma](gamma.md)\n- [Delta](delta.md)\n"
)
_UPLINK = "[↑ Vol](index.md)"

_ALPHA = f"""{_UPLINK}

# Alpha

> <span id="thm:alpha">**theorem**</span>
>
> **Theorem 1** (Alpha result). *Alpha holds for every admissible state.*

The alpha bound follows from
<a href="delta.md#lem:delta" data-reference-type="ref" data-reference="lem:delta">Lemma 1</a>
and from the estimate
<a href="beta.md" data-reference-type="eqref" data-reference="eq:beta">1</a>, and it
is the sharpest bound the method gives.

This paragraph only points the reader at
<a href="gamma.md" data-reference-type="eqref" data-reference="eq:gamma">2</a>
for the notation used above, and at
<a href="delta.md#lem:delta" data-reference-type="ref" data-reference="lem:delta">Lemma 1</a>
for where it is set.

Compare <a href="delta.md#lem:delta" data-reference-type="ref" data-reference="lem:delta">Lemma 1</a>.

A closing remark states that the admissible set is closed under limits.
"""

_BETA = f"""{_UPLINK}

# Beta

Beta relies on
<a href="alpha.md#thm:alpha" data-reference-type="ref" data-reference="thm:alpha">Theorem 1</a>
together with the estimate
``` math
\\beta \\le 1 \\label{{eq:beta}}
```
which together give the beta bound on every interior state.
"""

_GAMMA = f"""{_UPLINK}

# Gamma

The notation below follows
<a href="alpha.md#thm:alpha" data-reference-type="ref" data-reference="thm:alpha">Theorem 1</a>
throughout.

<div class="center">

``` math
\\gamma = 0 \\label{{eq:gamma}}
```
"""

_DELTA = f"""{_UPLINK}

# Delta

> <span id="lem:delta">**lemma**</span>
>
> **Lemma 1** (Delta lemma). *Delta holds on the interior.*
"""

_TREE = {
    "entry-point.md": _ENTRY_POINT,
    "vol/index.md": _VOLUME_INDEX,
    "vol/alpha.md": _ALPHA,
    "vol/beta.md": _BETA,
    "vol/gamma.md": _GAMMA,
    "vol/delta.md": _DELTA,
}

#: Each title is its paragraph's first sentence as the page shows it — derived,
#: so these are what the rule yields over the corpus above, not what a seat chose.
_P1_TITLE = (
    "The alpha bound follows from Lemma 1 and from the estimate 1, and it is the sharpest bound the method gives."
)
_BETA_TITLE = "Beta relies on Theorem 1 together with the estimate"
_REMARK_TITLE = "A closing remark states that the admissible set is closed under limits."

_CLAIM = ask.ParagraphLetter.CLAIM.value
_NOT_A_CLAIM = ask.ParagraphLetter.NOT_A_CLAIM.value

#: What the seat says, keyed by a phrase of the paragraph it is said about. Any
#: paragraph holding none of them is answered not a claim.
_ANSWERS: dict[str, str] = {
    "The alpha bound follows": _CLAIM,
    "A closing remark states": _CLAIM,
    "Beta relies on": _CLAIM,
}


def _excerpt(repo: Path, document: str, locator: str) -> str:
    documents = tree.read(repo / "kb-root")
    rendered = identify.reading_of(documents.documents[document], inventory.scan(documents)).render
    return next(span.excerpt for span in map(rendered.span_of, rendered.paragraphs) if span.locator == locator)


class PhraseReader:
    """A :class:`letters.LetterReader` answering each paragraph by the phrases it holds.

    ``stop_on`` names a leaf whose first ask raises :class:`ask.AskError`, as a
    call that never completed would. ``asked`` is every question put, as the
    leaf and the paragraph's own words.
    """

    def __init__(self, repo: Path, answers: Mapping[str, str] | None = None, *, stop_on: str | None = None):
        self._repo = repo
        self._answers = _ANSWERS if answers is None else answers
        self._stop_on = stop_on
        self.asked: list[tuple[str, str]] = []

    def __call__(self, question: letters.LetterQuestion) -> letters.Reply:
        if question.group == self._stop_on:
            self._stop_on = None
            raise ask.AskError("inference-failed", f"{question.group}: the call never completed")
        excerpt = _excerpt(self._repo, question.group, question.item)
        self.asked.append((question.group, excerpt))
        return letters.Reply(text=next((said for phrase, said in self._answers.items() if phrase in excerpt), "B"))

    def groups(self) -> list[str]:
        return list(dict.fromkeys(group for group, _ in self.asked))


# ---------------------------------------------------------------------------
# The consuming repository, and the stages over it
# ---------------------------------------------------------------------------


@pytest.fixture
def consumer(tmp_path: Path) -> Path:
    return install_claimgraph_consumer(tmp_path / "consumer", _TREE)


def _scratch(repo: Path) -> Path:
    return repo / kb_util.scratch_dirname() / "claimgraph"


def _declare(repo: Path) -> None:
    report = build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo))
    assert not report.failed, report.lines()


def _discover(repo: Path, reader: letters.LetterReader) -> list[str]:
    """The run's report lines where it failed, and nothing where it did not."""
    report = discover.build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo), reader=reader)
    return report.lines() if report.failed else []


def _discover_report(repo: Path, reader: letters.LetterReader) -> list[str]:
    report = discover.build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo), reader=reader)
    assert not report.failed, report.lines()
    return report.lines()


def _mint_equations(repo: Path) -> None:
    report = equations.build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo))
    assert not report.failed, report.lines()


@pytest.fixture(scope="module")
def declared_build(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    repo = install_claimgraph_consumer(tmp_path_factory.mktemp("nodepass-declared") / "consumer", _TREE)
    _declare(repo)
    with held_unchanged(repo, name="nodepass declared"):
        yield repo


@pytest.fixture
def declared(declared_build: Path, tmp_path: Path) -> Path:
    return copy_build(declared_build, tmp_path / "consumer")


@pytest.fixture(scope="module")
def discovered_build(declared_build: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    repo = copy_build(declared_build, tmp_path_factory.mktemp("nodepass-discovered") / "consumer")
    assert _discover(repo, PhraseReader(repo)) == []
    with held_unchanged(repo, name="nodepass discovered"):
        yield repo


@pytest.fixture
def discovered(discovered_build: Path, tmp_path: Path) -> Path:
    return copy_build(discovered_build, tmp_path / "consumer")


def _read(repo: Path):
    documents = tree.read(repo / "kb-root")
    sites = inventory.scan(documents)
    return documents, sites, graph.read(documents, sites)


def _by_title(authored: graph.AuthoredGraph) -> dict[str, graph.ClaimNode]:
    return {node.title: node for node in authored.nodes.values()}


def _reading(repo: Path, path: str) -> identify.Reading:
    documents, sites, _ = _read(repo)
    return identify.reading_of(documents.documents[path], sites)


def _verdicts(repo: Path, path: str) -> dict[str, kb_pipeline.ParagraphVerdict]:
    """``path``'s recorded verdicts, by the opening words of the paragraph each judges."""
    reading = _reading(repo, path)
    entry = kb_pipeline.read_node_pass(repo).leaves[path]
    by_line = {verdict.line: verdict for verdict in entry.verdicts}
    return {
        reading.render.span_of(paragraph).excerpt[:24]: by_line[paragraph.start]
        for paragraph in reading.render.paragraphs
        if paragraph.start in by_line
    }


# ---------------------------------------------------------------------------
# 1 — which paragraphs are asked
# ---------------------------------------------------------------------------


def test_the_readable_prose_leaves_out_claim_proof_and_definition_blocks(declared: Path):
    reading = _reading(declared, "vol/alpha.md")
    (block,) = reading.blocks

    assert not any("Alpha holds for every admissible state" in sentence.text for sentence in reading.render.sentences)
    assert "Alpha holds for every admissible state" in reading.render.text, "shown, unlabelled, as context"
    assert set(range(block.start, block.end)) <= reading.excluded


def test_a_paragraph_holding_a_resolving_reference_is_obligated_and_no_other_is(declared: Path):
    alpha = _reading(declared, "vol/alpha.md")
    owed = [alpha.render.span_of(paragraph).excerpt for paragraph in alpha.obligated]

    assert [excerpt[:24] for excerpt in owed] == [
        "The alpha bound follows ",
        "This paragraph only poin",
        'Compare <a href="delta.m',
    ]
    assert _reading(declared, "vol/delta.md").obligated == ()


def test_every_obligated_paragraph_is_asked_whatever_its_words(declared: Path):
    """``Compare Lemma 1.`` is three words, which opens no claim, and it holds a reference: it is asked."""
    compare = next(
        paragraph
        for paragraph in identify.asked_paragraphs(_reading(declared, "vol/alpha.md"))
        if paragraph.span.excerpt.startswith("Compare")
    )
    assert not any(identify._opens_a_claim(sentence, ()) for sentence in compare.span.sentences)

    reader = PhraseReader(declared)
    assert _discover(declared, reader) == []
    assert any(excerpt.startswith("Compare") for _, excerpt in reader.asked)
    assert _verdicts(declared, "vol/alpha.md")['Compare <a href="delta.m'].judgement is (
        kb_pipeline.Judgement.NOT_A_CLAIM
    )


def test_a_markup_only_paragraph_holding_no_reference_is_not_asked(declared: Path):
    reading = _reading(declared, "vol/gamma.md")
    assert any(sentence.text == '<div class="center">' for sentence in reading.render.sentences)

    reader = PhraseReader(declared)
    assert _discover(declared, reader) == []
    assert [excerpt for group, excerpt in reader.asked if group == "vol/gamma.md"] == [
        "The notation below follows "
        '<a href="alpha.md#thm:alpha" data-reference-type="ref" data-reference="thm:alpha">Theorem 1</a> throughout.'
    ]
    assert list(_verdicts(declared, "vol/gamma.md")) == ["The notation below follo"]


def test_a_leaf_whose_only_readable_text_is_its_heading_is_asked_nothing(declared: Path):
    reader = PhraseReader(declared)
    assert _discover(declared, reader) == []

    assert "vol/delta.md" not in reader.groups()
    entry = kb_pipeline.read_node_pass(declared).leaves["vol/delta.md"]
    assert entry.outcome is kb_pipeline.LeafOutcome.NOTHING_TO_READ


# ---------------------------------------------------------------------------
# 2 — what an answer comes to: a claim, its title, and the defaults
# ---------------------------------------------------------------------------


def _judged(reading: identify.Reading, says: Mapping[str, bool | None]) -> identify.Identification:
    """``reading`` judged with each asked paragraph answered by the first phrase of ``says`` it holds."""
    answers = [
        (asked, next((said for phrase, said in says.items() if phrase in asked.span.excerpt), False))
        for asked in identify.asked_paragraphs(reading)
    ]
    return identify.judge(reading, answers)


def test_a_yes_s_claim_is_its_whole_paragraph(declared: Path):
    reading = _reading(declared, "vol/beta.md")
    paragraph = reading.obligated[0]

    (claim,) = _judged(reading, {"Beta relies on": True}).claims
    assert claim.excerpt == reading.render.span_of(paragraph).excerpt
    assert claim.line == paragraph.start
    assert claim.title == _BETA_TITLE
    assert "``` math" in claim.excerpt


def test_a_reply_with_no_letter_defaults_and_its_references_follow_the_unjudged_rule(declared: Path):
    """Twice unreadable, alpha's pointer paragraph is defaulted: its references count as if nobody read it."""
    reader = PhraseReader(declared, {**_ANSWERS, "only points the reader": "Maybe."})
    lines = _discover_report(declared, reader)

    pointer = _verdicts(declared, "vol/alpha.md")["This paragraph only poin"]
    assert (pointer.judgement, pointer.cause) == (kb_pipeline.Judgement.DEFAULTED, kb_pipeline.DefaultCause.NO_LETTER)
    assert sum("only points the reader" in excerpt for _, excerpt in reader.asked) == 2, "asked, and once more"
    assert any("stage-C-defaulted" in line and "no-letter=1" in line for line in lines), lines

    documents, sites, _ = _read(declared)
    to_gamma = next(anchor for anchor in sites.anchors if anchor.label == "eq:gamma")
    entry = kb_pipeline.read_node_pass(declared).leaves["vol/alpha.md"]
    assert prose.standing(to_gamma, prose.readable(documents.documents["vol/alpha.md"], sites), entry) is (
        prose.Standing.UNJUDGED
    )
    _mint_equations(declared)
    assert _minted(declared) == {"eq:beta", "eq:gamma"}, "an unjudged reference still counts toward minting"
    narrowed, nodes = _narrowed(declared)
    assert (nodes["Alpha result"].id, nodes["Equation (`eq:gamma`) — Gamma"].id) in _pairs(narrowed)


_REPEATED = "The gamma bound holds on every interior state."


def test_an_unplaceable_yes_is_recorded_defaulted_and_the_stage_continues(declared: Path):
    """Two paragraphs with the same words: neither has a slice of its own, so neither can be marked."""
    leaf = declared / "kb-root" / "vol" / "gamma.md"
    leaf.write_text(leaf.read_text(encoding="utf-8") + f"\n{_REPEATED}\n\n{_REPEATED}\n", encoding="utf-8")

    lines = _discover_report(declared, PhraseReader(declared, {**_ANSWERS, "gamma bound holds": _CLAIM}))

    entry = kb_pipeline.read_node_pass(declared).leaves["vol/gamma.md"]
    defaulted = [verdict for verdict in entry.verdicts if verdict.judgement is kb_pipeline.Judgement.DEFAULTED]
    assert [verdict.cause for verdict in defaulted] == [kb_pipeline.DefaultCause.UNPLACEABLE] * 2
    assert (entry.state, entry.outcome, entry.claims) == (
        kb_pipeline.ReadState.LANDED,
        kb_pipeline.LeafOutcome.NO_CLAIM,
        (),
    )
    assert any("stage-C-defaulted" in line and "unplaceable=2" in line and "vol/gamma.md" in line for line in lines)
    assert kb_pipeline.read_node_pass(declared).leaves["vol/beta.md"].state is kb_pipeline.ReadState.LANDED


def test_titles_are_unique_in_their_leaf_and_the_author_s_own_words():
    """A repeated opening takes its paragraph's position; markup is reduced to what the page shows; long is cut."""
    long = " ".join(["The operator is monotone on the cone"] * 6) + "."
    body = (
        "<!-- kb-frontmatter\nkind: leaf\n-->\n\n"
        "The bound holds on the cone. It is sharp.\n\n"
        "The bound holds on the cone. It is not sharp here.\n\n"
        'As <a href="b.md#lem:x" data-reference-type="ref" data-reference="lem:x">Lemma 2</a> and '
        '<span class="citation" data-cites="smith2020">Smith (2020)</span> give, the map contracts.\n\n'
        f"{long}\n"
    )
    reading = identify.Reading(document="vol/leaf.md", text=body, body=body)
    every_paragraph_says_yes = {"": True}
    titles = [claim.title for claim in _judged(reading, every_paragraph_says_yes).claims]

    assert titles[:3] == [
        "The bound holds on the cone.",
        "The bound holds on the cone. (¶2)",
        "As Lemma 2 and Smith (2020) give, the map contracts.",
    ]
    assert len(titles[3]) <= identify.TITLE_MAX_CHARS
    assert titles[3].endswith("…") and long.startswith(titles[3][:-1])
    assert long[len(titles[3]) - 1] == " ", "cut at a word boundary"
    assert titles == [claim.title for claim in _judged(reading, every_paragraph_says_yes).claims]


def test_titles_are_identical_across_two_runs(declared_build: Path, tmp_path: Path):
    runs = [copy_build(declared_build, tmp_path / name) for name in ("one", "two")]
    for repo in runs:
        assert _discover(repo, PhraseReader(repo)) == []

    first, second = (kb_pipeline.read_node_pass(repo).leaves for repo in runs)
    assert first == second
    assert {claim.title for entry in first.values() for claim in entry.claims} == {
        _P1_TITLE,
        _REMARK_TITLE,
        _BETA_TITLE,
    }
    assert _titles_in_register(runs[0]) == _titles_in_register(runs[1])


# ---------------------------------------------------------------------------
# 3 — the pass end to end: every leaf read, every paragraph judged, the KB final
# ---------------------------------------------------------------------------


def test_every_leaf_is_asked_and_every_asked_paragraph_carries_exactly_one_verdict(discovered: Path):
    """Every obligated paragraph among them, over a leaf hosting a block and a blockless one alike."""
    record = kb_pipeline.read_node_pass(discovered)
    documents, sites, _ = _read(discovered)

    for path, entry in record.leaves.items():
        reading = identify.reading_of(documents.documents[path], sites)
        judged = [verdict.line for verdict in entry.verdicts]
        assert judged == sorted({asked.paragraph.start for asked in identify.asked_paragraphs(reading)}), path
        owed = {
            paragraph.start for paragraph in prose.obligated(prose.readable(documents.documents[path], sites), sites)
        }
        assert owed <= set(judged), path
    assert [verdict.judgement for verdict in record.leaves["vol/alpha.md"].verdicts] == [
        kb_pipeline.Judgement.CLAIM,
        kb_pipeline.Judgement.NOT_A_CLAIM,
        kb_pipeline.Judgement.NOT_A_CLAIM,
        kb_pipeline.Judgement.CLAIM,
    ]
    assert len(record.leaves["vol/gamma.md"].verdicts) == 1


def test_a_hosting_leaf_keeps_its_block_claim_and_every_claim_is_marked(discovered: Path):
    """The block claim is carried forward, and marker coverage holds over the final set."""
    kb_root = discovered / "kb-root"
    text = (kb_root / "vol" / "alpha.md").read_text(encoding="utf-8")
    fields = kb_index_lib.parse_frontmatter(text)
    nodes = _by_title(_read(discovered)[2])

    assert fields["claims"][0] == nodes["Alpha result"].id
    assert {nodes[title].id for title in ("Alpha result", _P1_TITLE, _REMARK_TITLE)} == set(fields["claims"])
    assert verify_kb_metadata.check_tier2_coverage([(kb_root / "vol" / "alpha.md", fields)], set()) == []


def test_a_yes_s_marker_sits_on_its_paragraph_s_first_line(discovered: Path):
    reading = _reading(discovered, "vol/alpha.md")
    paragraph = next(p for p in reading.obligated if "The alpha bound" in reading.render.span_of(p).excerpt)
    node = _by_title(_read(discovered)[2])[_P1_TITLE]

    assert render.render_tier2_marker(node.id) in reading.text.splitlines()[paragraph.start]


def test_a_blockless_leaf_takes_its_claim_and_loses_the_declared_pass_s_reason(discovered: Path):
    fields = kb_index_lib.parse_frontmatter((discovered / "kb-root" / "vol" / "beta.md").read_text(encoding="utf-8"))
    assert len(fields["claims"]) == 1 and "no-claim" not in fields


def test_a_blockless_leaf_stating_nothing_keeps_the_declared_pass_s_reason(discovered: Path):
    """Whether a leaf was read is build record: the KB says only that it carries no claim."""
    fields = kb_index_lib.parse_frontmatter((discovered / "kb-root" / "vol" / "gamma.md").read_text(encoding="utf-8"))
    assert fields["no-claim"] == BLOCKLESS_REASON
    assert kb_pipeline.read_node_pass(discovered).leaves["vol/gamma.md"].outcome is kb_pipeline.LeafOutcome.NO_CLAIM


def test_an_attribute_the_node_pass_does_not_own_is_carried_forward(declared: Path):
    leaf = declared / "kb-root" / "vol" / "alpha.md"
    leaf.write_text(
        leaf.read_text(encoding="utf-8").replace("kind: leaf\n", 'kind: leaf\npath-stable: "alpha-stable"\n', 1),
        encoding="utf-8",
    )
    assert _discover(declared, PhraseReader(declared)) == []
    assert kb_index_lib.parse_frontmatter(leaf.read_text(encoding="utf-8"))["path-stable"] == "alpha-stable"


def test_no_file_under_kb_root_carries_build_state(discovered: Path):
    """Verdicts and read states are the record's, and no reserved literal is left to reserve."""
    texts = kb_index_lib.document_texts(discovered / "kb-root")
    state_words = [state.value for state in kb_pipeline.ReadState] + [
        kb_pipeline.Judgement.NOT_A_CLAIM.value,
        kb_pipeline.Judgement.DEFAULTED.value,
    ]

    for path, text in texts.items():
        fields = kb_index_lib.parse_frontmatter(text) or {}
        assert not any(word in str(fields) for word in state_words), path
        assert kb_pipeline.NODE_PASS_ABOUT not in text, path
    assert not hasattr(kb_index_lib, "UNSCANNED_REASON")


# ---------------------------------------------------------------------------
# 4 — the record is the checkpoint: a stopped run completes, and asks nothing twice
# ---------------------------------------------------------------------------


def _stop_once(monkeypatch, target, name: str, *, on: str) -> None:
    """Make ``target.name`` raise the first time it is called for ``on``, as a killed process would stop."""
    original = getattr(target, name)
    fired: list[bool] = []

    def once(*args, **kwargs):
        subject = kwargs.get("document") or str(kwargs.get("values_file", ""))
        if not fired and on in subject:
            fired.append(True)
            raise ClaimGraphError("stopped", f"stopped at {name} for {on}")
        return original(*args, **kwargs)

    monkeypatch.setattr(target, name, once)


def _titles_in_register(repo: Path) -> list[str]:
    register = repo / "kb-root" / "vol" / "claim-quality.md"
    return [entry.title for entry in kb_index_lib.parse_claim_quality_file(register, repo / "kb-root")]


def test_a_stop_after_leaf_k_resumes_asking_from_leaf_k_plus_1(declared: Path):
    """A call that never completes stops the stage; the leaves before it are landed and never asked again."""
    stopped = PhraseReader(declared, stop_on="vol/beta.md")
    lines = _discover(declared, stopped)
    assert any("inference-failed" in line for line in lines), lines
    assert stopped.groups() == ["vol/alpha.md"]
    leaves = kb_pipeline.read_node_pass(declared).leaves
    assert leaves["vol/alpha.md"].state is kb_pipeline.ReadState.LANDED
    assert leaves["vol/beta.md"].state is kb_pipeline.ReadState.UNREAD

    resumed = PhraseReader(declared)
    assert _discover(declared, resumed) == []
    assert resumed.groups() == ["vol/beta.md", "vol/gamma.md"]
    assert _titles_in_register(declared).count(_P1_TITLE) == 1


def test_a_run_stopped_after_a_leaf_s_record_entry_asks_it_nothing_and_mints_once(declared: Path, monkeypatch):
    """Stopped before the leaf's first KB write."""
    _stop_once(monkeypatch, write, "land_leaf", on="vol/alpha.md")
    assert _discover(declared, PhraseReader(declared)) != []
    assert kb_pipeline.read_node_pass(declared).leaves["vol/alpha.md"].state is kb_pipeline.ReadState.PLANNED

    resumed = PhraseReader(declared)
    assert _discover(declared, resumed) == []
    assert "vol/alpha.md" not in resumed.groups()
    assert _titles_in_register(declared).count(_P1_TITLE) == 1
    assert _titles_in_register(declared).count(_REMARK_TITLE) == 1


def test_a_run_stopped_between_a_leaf_s_insert_and_its_frontmatter_takes_the_ids_it_minted(declared: Path, monkeypatch):
    """Stopped mid-write: the entries it inserted are hosted by nobody, and are taken, not doubled."""
    _stop_once(monkeypatch, ops, "set_frontmatter", on="cinf-vol_alpha.md")
    assert _discover(declared, PhraseReader(declared)) != []
    assert _titles_in_register(declared).count(_P1_TITLE) == 1

    resumed = PhraseReader(declared)
    assert _discover(declared, resumed) == []
    assert "vol/alpha.md" not in resumed.groups()
    assert _titles_in_register(declared).count(_P1_TITLE) == 1
    assert _titles_in_register(declared).count(_REMARK_TITLE) == 1


# ---------------------------------------------------------------------------
# 5 — phase 2 reads the verdicts: stage D, and the equations
# ---------------------------------------------------------------------------


def _minted(repo: Path) -> set[str]:
    return {node.equation for node in _read(repo)[2].nodes.values() if node.equation is not None}


def test_an_equation_named_only_from_prose_judged_not_a_claim_is_not_minted(discovered: Path):
    """And an equation a counting reference names is."""
    _mint_equations(discovered)
    assert _minted(discovered) == {"eq:beta"}


def test_with_no_verdict_every_reference_counts(declared: Path):
    """A build spending no inference: the record judges nothing, and the equation set is the declared pass's old one."""
    _mint_equations(declared)
    assert _minted(declared) == {"eq:beta", "eq:gamma"}


def test_the_equations_stage_mints_nothing_twice(discovered: Path):
    _mint_equations(discovered)
    before = _titles_in_register(discovered)
    _mint_equations(discovered)
    assert _titles_in_register(discovered) == before


def _narrowed(repo: Path) -> tuple[attribute.Attribution, dict[str, graph.ClaimNode]]:
    documents, sites, authored = _read(repo)
    return attribute.narrow(documents, authored, sites, kb_pipeline.read_node_pass(repo)), _by_title(authored)


def _pairs(narrowed: attribute.Attribution) -> set[tuple[str, str]]:
    return {candidate.pair for candidate in narrowed.candidates}


def test_a_reference_in_prose_judged_not_a_claim_yields_no_pair(discovered: Path):
    """Alpha's pointer paragraph contributes no candidate.

    Read over one tree with and without the record, so the only thing that
    differs is the verdicts: unjudged, the pointer paragraph's references offer
    every claim alpha hosts as their source, the theorem among them.
    """
    _mint_equations(discovered)
    documents, sites, authored = _read(discovered)
    theorem = _by_title(authored)["Alpha result"].id
    pointer = next(anchor for anchor in sites.anchors if anchor.label == "eq:gamma")
    entry = kb_pipeline.read_node_pass(discovered).leaves["vol/alpha.md"]

    assert prose.standing(pointer, prose.readable(documents.documents["vol/alpha.md"], sites), entry) is (
        prose.Standing.NOT_A_CLAIM
    )
    assert any(source == theorem for source, _ in _pairs(attribute.narrow(documents, authored, sites)))
    judged, _ = _narrowed(discovered)
    assert not any(source == theorem for source, _ in _pairs(judged))


def test_a_reference_in_a_yes_paragraph_has_that_claim_alone_as_its_source(discovered: Path):
    """The lemma reference in alpha's first paragraph runs from its claim, not from the theorem."""
    _mint_equations(discovered)
    narrowed, nodes = _narrowed(discovered)
    to_lemma = {source for source, target in _pairs(narrowed) if target == nodes["Delta lemma"].id}
    to_beta_eq = {source for source, target in _pairs(narrowed) if target == nodes["Equation (`eq:beta`) — Beta"].id}

    assert to_lemma == {nodes[_P1_TITLE].id}
    assert to_beta_eq == {nodes[_P1_TITLE].id}
    assert {source for source, target in _pairs(narrowed) if target == nodes["Alpha result"].id} == {
        nodes[_BETA_TITLE].id
    }


def test_a_reference_nobody_judged_keeps_today_s_rule(declared: Path):
    """No verdict, no drop: prose never judged offers every claim its document hosts."""
    _mint_equations(declared)
    narrowed, nodes = _narrowed(declared)
    assert (nodes["Alpha result"].id, nodes["Equation (`eq:gamma`) — Gamma"].id) in _pairs(narrowed)


# ---------------------------------------------------------------------------
# 6 — the node set is fixed when equations-minted ends
# ---------------------------------------------------------------------------


def _ids(repo: Path) -> set[str]:
    return set(kb_index_lib.scan_authored_ids(repo / "kb-root"))


def test_only_the_node_pass_mints_prose_claims_and_no_later_stage_moves_the_node_set(declared: Path):
    """Driving each claim-graph stage in turn against a fixed inference."""
    after_declared = _ids(declared)
    assert _discover(declared, PhraseReader(declared)) == []
    after_discovered = _ids(declared)
    _mint_equations(declared)
    after_equations = _ids(declared)
    report = depends.build(kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), reader=None)
    assert not report.failed, report.lines()
    after_depends = _ids(declared)

    titles = {
        entry.id: entry.title
        for entry in kb_index_lib.parse_claim_quality_file(
            declared / "kb-root" / "vol" / "claim-quality.md", declared / "kb-root"
        )
    }
    prose_titles = {titles[node_id] for node_id in after_discovered - after_declared}
    assert prose_titles == {_P1_TITLE, _REMARK_TITLE, _BETA_TITLE}
    assert all(kb_schema.equation_label(titles[node_id]) for node_id in after_equations - after_discovered)
    assert after_depends == after_equations


# ---------------------------------------------------------------------------
# 7 — the record is committed at the node pass's boundary and outlives the build
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@invalid", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_the_record_lands_in_the_node_pass_boundary_commit_and_stands_after_the_last(consumer: Path):
    """Through the ledger's own sweep."""
    shutil.rmtree(consumer / ".git")
    _git(consumer, "init", "-q")
    _git(consumer, "add", "-A")
    _git(consumer, "commit", "-qm", "tree")

    _declare(consumer)
    kb_pipeline._record(consumer, kb_pipeline.stage_by_id("claims-declared"))
    assert _discover(consumer, PhraseReader(consumer)) == []
    kb_pipeline._record(consumer, kb_pipeline.stage_by_id("claims-discovered"))

    assert kb_pipeline.NODE_PASS_RELPATH in _git(consumer, "show", "--name-only", "--format=", "HEAD").split()
    for stage in kb_pipeline.STAGES[kb_pipeline.STAGE_IDS.index("claims-discovered") + 1 :]:
        kb_pipeline._record(consumer, stage)
    assert _git(consumer, "ls-files", kb_pipeline.NODE_PASS_RELPATH).strip() == kb_pipeline.NODE_PASS_RELPATH
    assert kb_pipeline.read_node_pass(consumer).leaves["vol/alpha.md"].state is kb_pipeline.ReadState.LANDED
