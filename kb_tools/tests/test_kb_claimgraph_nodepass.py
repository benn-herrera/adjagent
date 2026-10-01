"""The node pass: verdicts on reference-bearing prose, the record, and the node set it fixes.

**The inference is fixed at the :class:`~kb_tools.kb_claimgraph.identify.Identifier`
seam.** The fake reads the leaf the stage hands it — its render and the
paragraphs it owes a verdict — composes the answer text a seat would return, and
hands it to the production parse. So verdict completeness, every refusal, the
record-then-KB-then-landed order, completion of a stopped run, the per-leaf
write, stage D's use of the verdicts and the equation stage's are all exercised,
and none of it depends on the wording of a prompt.

The corpus puts each case on its own leaf:

* **alpha** hosts a theorem and two paragraphs holding references — one a claim,
  one not — and a third paragraph holding none, which a record may start in;
* **beta** hosts no block, and its one reference-bearing paragraph is a claim
  carrying its own equation;
* **gamma** hosts no block, states nothing, and holds the one equation that only
  alpha's not-a-claim paragraph names;
* **delta** hosts a lemma and nothing else to read but its heading.
"""

import os
import shutil
import subprocess
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
    prose,
    tree,
    write,
)
from kb_tools.kb_claimgraph.build import build
from kb_tools.kb_claimgraph.report import ClaimGraphError
from kb_tools.kb_write import ops, render

_PACKAGE_ROOT = Path(kb_util.__file__).resolve().parent

pytestmark = pytest.mark.skipif(
    shutil.which("just") is None,
    reason="every stage here ends on the consuming project's runner targets",
)

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

_P1_TITLE = "Sharpness of the alpha bound"
_BETA_TITLE = "The beta bound on interior states"
_REMARK_TITLE = "Closure of the admissible set under limits"
_GAMMA_REASON = "The section fixes the notation other sections use and states no result of its own."

#: What the seat says about each leaf. A verdict is keyed by a phrase of the
#: paragraph it judges, and a record by the opening of its sentence; the fake
#: resolves both against the leaf it is handed.
_PLAN: dict[str, dict] = {
    "vol/alpha.md": {
        "records": [("A closing remark states", _REMARK_TITLE)],
        "verdicts": {"The alpha bound follows": _P1_TITLE, "only points the reader": None},
    },
    "vol/beta.md": {"verdicts": {"Beta relies on": _BETA_TITLE}},
    "vol/gamma.md": {"verdicts": {"The notation below follows": None}, "reason": _GAMMA_REASON},
}


class VerdictIdentifier:
    """An :class:`identify.Identifier` answering from :data:`_PLAN` through the production parse.

    ``withhold`` names verdict phrases left out of a leaf's first answer, which
    is how an answer missing a verdict is expressed; ``always_withhold`` leaves
    them out of every answer.
    """

    def __init__(self, plan=None, *, withhold: frozenset[str] = frozenset(), always_withhold: bool = False):
        self._plan = _PLAN if plan is None else plan
        self._withhold = withhold
        self._always = always_withhold
        self.asks: list[tuple[str, tuple[str, ...]]] = []

    def identify(self, reading, *, report, missing=()):
        del report
        first = reading.document not in [document for document, _ in self.asks]
        self.asks.append((reading.document, tuple(missing)))
        plan = self._plan.get(reading.document, {})
        rendered = reading.render
        records = [
            identify.Record(quote=quote, label=_label_opening(rendered, quote), title=title)
            for quote, title in plan.get("records", ())
        ]
        verdicts = []
        for name, paragraph in reading.paragraph_ids().items():
            text = rendered.span_of(paragraph).excerpt
            for phrase, title in plan.get("verdicts", {}).items():
                if phrase in text and not (phrase in self._withhold and (first or self._always)):
                    verdicts.append(identify.Verdict(paragraph=name, title=title))
        says_nothing = not records and not verdicts and not reading.may_decline
        answer = ask.identify_answer_block(records, plan.get("reason", ""), verdicts, nothing_further=says_nothing)
        return ask.parse_identify_answer(answer, document=reading.document)

    def re_ask(self, reading, unresolved):
        raise AssertionError(f"{reading.document}: every record here resolves on the first ask")


def _label_opening(rendered, quote: str) -> str:
    return next(sentence.label for sentence in rendered.sentences if sentence.text.startswith(quote))


# ---------------------------------------------------------------------------
# The consuming repository, and the stages over it
# ---------------------------------------------------------------------------


@pytest.fixture
def consumer(tmp_path: Path) -> Path:
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
    return repo


def _scratch(repo: Path) -> Path:
    return repo / kb_util.scratch_dirname() / "claimgraph"


def _declare(repo: Path) -> None:
    report = build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo))
    assert not report.failed, report.lines()


def _discover(repo: Path, identifier) -> list[str]:
    report = discover.build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo), identifier=identifier)
    return report.lines() if report.failed else []


def _mint_equations(repo: Path) -> None:
    report = equations.build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo))
    assert not report.failed, report.lines()


@pytest.fixture
def declared(consumer: Path) -> Path:
    _declare(consumer)
    return consumer


@pytest.fixture
def discovered(declared: Path) -> Path:
    assert _discover(declared, VerdictIdentifier()) == []
    return declared


def _read(repo: Path):
    documents = tree.read(repo / "kb-root")
    sites = inventory.scan(documents)
    return documents, sites, graph.read(documents, sites)


def _by_title(authored: graph.AuthoredGraph) -> dict[str, graph.ClaimNode]:
    return {node.title: node for node in authored.nodes.values()}


def _reading(repo: Path, path: str) -> identify.Reading:
    documents, sites, _ = _read(repo)
    return identify.reading_of(documents.documents[path], sites)


def _paragraph(reading: identify.Reading, phrase: str) -> str:
    rendered = reading.render
    return next(
        name for name, paragraph in reading.paragraph_ids().items() if phrase in rendered.span_of(paragraph).excerpt
    )


# ---------------------------------------------------------------------------
# 1 — what is owed a verdict
# ---------------------------------------------------------------------------


def test_the_readable_prose_leaves_out_claim_proof_and_definition_blocks(declared: Path):
    reading = _reading(declared, "vol/alpha.md")
    (block,) = reading.blocks

    assert not any("Alpha holds for every admissible state" in sentence.text for sentence in reading.render.sentences)
    assert "Alpha holds for every admissible state" in reading.render.text, "shown, unlabelled, as context"
    assert set(range(block.start, block.end)) <= reading.excluded


def test_a_paragraph_holding_a_resolving_reference_is_owed_a_verdict_and_no_other_is(declared: Path):
    alpha = _reading(declared, "vol/alpha.md")
    owed = [alpha.render.span_of(paragraph).excerpt for paragraph in alpha.obligated]

    assert len(owed) == 2
    assert owed[0].startswith("The alpha bound follows") and owed[1].startswith("This paragraph only points")
    assert _reading(declared, "vol/delta.md").obligated == ()


def test_a_leaf_hosting_a_block_may_not_decline_and_a_blockless_one_may(declared: Path):
    assert not _reading(declared, "vol/alpha.md").may_decline
    assert _reading(declared, "vol/gamma.md").may_decline


# ---------------------------------------------------------------------------
# 2 — the checks over an answer's verdicts
# ---------------------------------------------------------------------------


def _answer(reading, *, verdicts=(), records=(), reason="", nothing_further=False) -> identify.Checked:
    return identify.check_answer(
        identify.Answer(
            claims=tuple(records), verdicts=tuple(verdicts), no_claim=reason, nothing_further=nothing_further
        ),
        reading,
    )


def test_a_verdict_naming_no_paragraph_owed_one_is_refused_and_leaves_that_paragraph_missing(declared: Path):
    reading = _reading(declared, "vol/alpha.md")
    kept = _paragraph(reading, "only points the reader")
    checked = _answer(reading, verdicts=[identify.Verdict("S99", "A title"), identify.Verdict(kept, None)])

    assert any("'S99'" in refusal for refusal in checked.refusals)
    assert checked.missing == (_paragraph(reading, "The alpha bound follows"),)


def test_a_second_verdict_for_one_paragraph_is_refused(declared: Path):
    reading = _reading(declared, "vol/alpha.md")
    one = _paragraph(reading, "The alpha bound follows")
    checked = _answer(reading, verdicts=[identify.Verdict(one, _P1_TITLE), identify.Verdict(one, None)])

    assert any("second verdict" in refusal for refusal in checked.refusals)
    assert [claim.title for claim in checked.claims] == [_P1_TITLE]


def test_a_claim_verdict_titled_as_the_leaf_s_block_is_refused(declared: Path):
    """I8: a register entry is bound back to its site by title, so no two of one document's claims share one."""
    reading = _reading(declared, "vol/alpha.md")
    one = _paragraph(reading, "The alpha bound follows")
    checked = _answer(reading, verdicts=[identify.Verdict(one, "Alpha result")])

    assert one in checked.missing
    assert checked.claims == ()


def test_a_record_starting_in_a_paragraph_owed_a_verdict_costs_that_record(declared: Path):
    reading = _reading(declared, "vol/alpha.md")
    label = _label_opening(reading.render, "The alpha bound follows")
    checked = _answer(reading, records=[identify.Record("The alpha bound follows from", label, "A record")])

    assert checked.claims == ()
    assert any("owed a verdict" in refusal for refusal in checked.refusals)


def test_a_no_claim_sentence_from_a_leaf_hosting_a_block_is_refused(declared: Path):
    checked = _answer(_reading(declared, "vol/delta.md"), reason="Delta states nothing more.")

    assert checked.no_claim == ""
    assert any("hosting claims" in refusal for refusal in checked.refusals)


def test_a_yes_verdict_s_claim_is_its_whole_paragraph(declared: Path):
    reading = _reading(declared, "vol/beta.md")
    paragraph = reading.obligated[0]
    checked = _answer(reading, verdicts=[identify.Verdict(_paragraph(reading, "Beta relies on"), _BETA_TITLE)])

    (claim,) = checked.claims
    assert claim.excerpt == reading.render.span_of(paragraph).excerpt
    assert claim.line == paragraph.start
    assert "``` math" in claim.excerpt


def test_a_malformed_verdict_block_costs_that_block_and_the_blocks_beside_it_still_read():
    good = ask.identify_answer_block(verdicts=[identify.Verdict("S3-S4", None)])
    titled = f"{ask.PARAGRAPH_NOT_A_CLAIM_OPEN}\nparagraph: S9\ntitle: A title\n{ask.PARAGRAPH_NOT_A_CLAIM_CLOSE}\n"
    untitled = f"{ask.PARAGRAPH_CLAIM_OPEN}\nparagraph: S12\n{ask.PARAGRAPH_CLAIM_CLOSE}\n"

    answer = ask.parse_identify_answer(good + titled + untitled, document="d.md")

    assert answer.verdicts == (identify.Verdict("S3-S4", None),)
    assert len(answer.refusals) == 2
    assert any("unknown field 'title'" in refusal for refusal in answer.refusals)
    assert any("missing required field(s): title" in refusal for refusal in answer.refusals)


def test_an_answer_carrying_no_block_is_unreadable_for_every_leaf():
    """The format is ours and its parser stays strict: every answer says something positive."""
    with pytest.raises(identify.AnswerFormatError):
        ask.parse_identify_answer("nothing here\n", document="d.md")
    assert ask.parse_identify_answer(ask.identify_answer_block(nothing_further=True), document="d.md") == (
        identify.Answer(nothing_further=True)
    )


def test_nothing_further_carrying_text_costs_that_block():
    text = f"{ask.NOTHING_FURTHER_OPEN}\nA sentence.\n{ask.NOTHING_FURTHER_CLOSE}\n"
    answer = ask.parse_identify_answer(text, document="d.md")

    assert not answer.nothing_further and len(answer.refusals) == 1


def test_nothing_further_from_a_leaf_hosting_no_block_is_refused(declared: Path):
    """A blockless leaf says it states nothing with its own sentence, which is written into its frontmatter."""
    reading = _reading(declared, "vol/gamma.md")
    checked = _answer(
        reading, verdicts=[identify.Verdict(_paragraph(reading, "The notation below"), None)], nothing_further=True
    )

    assert any("nothing further" in refusal for refusal in checked.refusals)
    assert checked.reason_failures


def test_a_leaf_whose_only_readable_text_is_its_heading_is_asked_nothing(declared: Path):
    identifier = VerdictIdentifier()
    assert _discover(declared, identifier) == []

    assert "vol/delta.md" not in [document for document, _ in identifier.asks]
    entry = kb_pipeline.read_node_pass(declared).leaves["vol/delta.md"]
    assert entry.outcome is kb_pipeline.LeafOutcome.NOTHING_TO_READ


# ---------------------------------------------------------------------------
# 3 — the budgets: a missing verdict earns its own re-ask, and a second miss stops
# ---------------------------------------------------------------------------


def test_a_missing_verdict_earns_a_re_ask_naming_it(declared: Path):
    identifier = VerdictIdentifier(withhold=frozenset({"only points the reader"}))
    found = identify.infer_claims(_reading(declared, "vol/alpha.md"), identifier)

    missed = _paragraph(_reading(declared, "vol/alpha.md"), "only points the reader")
    assert identifier.asks == [("vol/alpha.md", ()), ("vol/alpha.md", (missed,))]
    assert len(found.verdicts) == 2


def test_a_second_miss_stops_the_stage_naming_the_document_and_the_paragraph(declared: Path):
    identifier = VerdictIdentifier(withhold=frozenset({"only points the reader"}), always_withhold=True)
    with pytest.raises(identify.IdentificationError) as refusal:
        identify.infer_claims(_reading(declared, "vol/alpha.md"), identifier)

    missed = _paragraph(_reading(declared, "vol/alpha.md"), "only points the reader")
    assert refusal.value.check == "verdict-coverage"
    assert "vol/alpha.md" in refusal.value.detail and missed in refusal.value.detail
    assert len(identifier.asks) == 1 + identify.VERDICT_RETRY_BUDGET


# ---------------------------------------------------------------------------
# 4 — the pass end to end: every leaf read, every paragraph judged, the KB final
# ---------------------------------------------------------------------------


def test_every_leaf_is_asked_and_every_obligated_paragraph_carries_exactly_one_verdict(discovered: Path):
    """Acceptance 2, over a leaf hosting a block and a blockless one holding an equation alike."""
    record = kb_pipeline.read_node_pass(discovered)
    documents, sites, _ = _read(discovered)

    for path, entry in record.leaves.items():
        owed = sorted(
            paragraph.start for paragraph in prose.obligated(prose.readable(documents.documents[path], sites), sites)
        )
        assert sorted(verdict.line for verdict in entry.verdicts) == owed, path
    assert len(record.leaves["vol/alpha.md"].verdicts) == 2
    assert len(record.leaves["vol/gamma.md"].verdicts) == 1


def test_a_hosting_leaf_keeps_its_block_claim_and_every_claim_is_marked(discovered: Path):
    """I7: the block claim is carried forward, and marker coverage holds over the final set."""
    kb_root = discovered / "kb-root"
    text = (kb_root / "vol" / "alpha.md").read_text(encoding="utf-8")
    fields = kb_index_lib.parse_frontmatter(text)
    nodes = _by_title(_read(discovered)[2])

    assert fields["claims"][0] == nodes["Alpha result"].id
    assert {nodes[title].id for title in ("Alpha result", _P1_TITLE, _REMARK_TITLE)} == set(fields["claims"])
    assert verify_kb_metadata.check_tier2_coverage([(kb_root / "vol" / "alpha.md", fields)], set()) == []


def test_a_yes_verdict_s_marker_sits_on_its_paragraph_s_first_line(discovered: Path):
    reading = _reading(discovered, "vol/alpha.md")
    paragraph = next(p for p in reading.obligated if "The alpha bound" in reading.render.span_of(p).excerpt)
    node = _by_title(_read(discovered)[2])[_P1_TITLE]

    assert render.render_tier2_marker(node.id) in reading.text.splitlines()[paragraph.start]


def test_a_blockless_leaf_takes_its_claim_and_loses_the_declared_pass_s_reason(discovered: Path):
    fields = kb_index_lib.parse_frontmatter((discovered / "kb-root" / "vol" / "beta.md").read_text(encoding="utf-8"))
    assert len(fields["claims"]) == 1 and "no-claim" not in fields


def test_a_blockless_leaf_stating_nothing_carries_its_own_reason(discovered: Path):
    fields = kb_index_lib.parse_frontmatter((discovered / "kb-root" / "vol" / "gamma.md").read_text(encoding="utf-8"))
    assert fields["no-claim"] == _GAMMA_REASON


def test_an_attribute_the_node_pass_does_not_own_is_carried_forward(declared: Path):
    leaf = declared / "kb-root" / "vol" / "alpha.md"
    leaf.write_text(
        leaf.read_text(encoding="utf-8").replace("kind: leaf\n", 'kind: leaf\npath-stable: "alpha-stable"\n', 1),
        encoding="utf-8",
    )
    assert _discover(declared, VerdictIdentifier()) == []
    assert kb_index_lib.parse_frontmatter(leaf.read_text(encoding="utf-8"))["path-stable"] == "alpha-stable"


def test_no_file_under_kb_root_carries_build_state(discovered: Path):
    """Acceptance 3: verdicts and read states are the record's, and no reserved literal is left to reserve."""
    texts = kb_index_lib.document_texts(discovered / "kb-root")
    state_words = [state.value for state in kb_pipeline.ReadState] + [kb_pipeline.Judgement.NOT_A_CLAIM.value]

    for path, text in texts.items():
        fields = kb_index_lib.parse_frontmatter(text) or {}
        assert not any(word in str(fields) for word in state_words), path
        assert kb_pipeline.NODE_PASS_ABOUT not in text, path
    assert not hasattr(kb_index_lib, "UNSCANNED_REASON")


# ---------------------------------------------------------------------------
# 5 — the record is the checkpoint: a stopped run completes, and asks nothing twice
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


def test_a_run_stopped_after_a_leaf_s_record_entry_asks_it_nothing_and_mints_once(declared: Path, monkeypatch):
    """Acceptance 8, stopped before the leaf's first KB write."""
    _stop_once(monkeypatch, write, "land_leaf", on="vol/alpha.md")
    assert _discover(declared, VerdictIdentifier()) != []
    assert kb_pipeline.read_node_pass(declared).leaves["vol/alpha.md"].state is kb_pipeline.ReadState.PLANNED

    resumed = VerdictIdentifier()
    assert _discover(declared, resumed) == []
    assert "vol/alpha.md" not in [document for document, _ in resumed.asks]
    assert _titles_in_register(declared).count(_P1_TITLE) == 1
    assert _titles_in_register(declared).count(_REMARK_TITLE) == 1


def test_a_run_stopped_between_a_leaf_s_insert_and_its_frontmatter_takes_the_ids_it_minted(declared: Path, monkeypatch):
    """Acceptance 8, stopped mid-write: the entries it inserted are hosted by nobody, and are taken, not doubled."""
    _stop_once(monkeypatch, ops, "set_frontmatter", on="cinf-vol_alpha.md")
    assert _discover(declared, VerdictIdentifier()) != []
    assert _titles_in_register(declared).count(_P1_TITLE) == 1

    resumed = VerdictIdentifier()
    assert _discover(declared, resumed) == []
    assert "vol/alpha.md" not in [document for document, _ in resumed.asks]
    assert _titles_in_register(declared).count(_P1_TITLE) == 1
    assert _titles_in_register(declared).count(_REMARK_TITLE) == 1


# ---------------------------------------------------------------------------
# 6 — phase 2 reads the verdicts: stage D, and the equations
# ---------------------------------------------------------------------------


def _minted(repo: Path) -> set[str]:
    return {node.equation for node in _read(repo)[2].nodes.values() if node.equation is not None}


def test_an_equation_named_only_from_prose_judged_not_a_claim_is_not_minted(discovered: Path):
    """Acceptance 5, and I6's other half: an equation a counting reference names is."""
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
    offered = {
        (question.source.id, candidate.id) for question in narrowed.questions for candidate in question.candidates
    }
    return set(narrowed.edges) | set(narrowed.references) | offered


def test_a_reference_in_prose_judged_not_a_claim_yields_no_pair(discovered: Path):
    """Acceptance 6: alpha's pointer paragraph contributes no candidate and no references edge.

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
    """Acceptance 6: the lemma reference in alpha's first paragraph runs from its claim, not from the theorem."""
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
# 7 — the node set is fixed when equations-minted ends
# ---------------------------------------------------------------------------


class _SelectsNothing:
    """A stage-D selector answering every question with the empty selection."""

    def select(self, question, *, report, cycle=None):
        return ()


def _ids(repo: Path) -> set[str]:
    return set(kb_index_lib.scan_authored_ids(repo / "kb-root"))


def test_only_the_node_pass_mints_prose_claims_and_no_later_stage_moves_the_node_set(declared: Path):
    """Acceptances 1 and 4, driving each claim-graph stage in turn against a fixed inference."""
    after_declared = _ids(declared)
    assert _discover(declared, VerdictIdentifier()) == []
    after_discovered = _ids(declared)
    _mint_equations(declared)
    after_equations = _ids(declared)
    report = depends.build(
        kb_root=declared / "kb-root", repo_root=declared, scratch=_scratch(declared), selector=_SelectsNothing()
    )
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
# 8 — the record is committed at the node pass's boundary and outlives the build
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
    """Acceptance 9, through the ledger's own sweep."""
    shutil.rmtree(consumer / ".git")
    _git(consumer, "init", "-q")
    _git(consumer, "add", "-A")
    _git(consumer, "commit", "-qm", "tree")

    _declare(consumer)
    kb_pipeline._record(consumer, kb_pipeline.stage_by_id("claims-declared"))
    assert _discover(consumer, VerdictIdentifier()) == []
    kb_pipeline._record(consumer, kb_pipeline.stage_by_id("claims-discovered"))

    assert kb_pipeline.NODE_PASS_RELPATH in _git(consumer, "show", "--name-only", "--format=", "HEAD").split()
    for stage in kb_pipeline.STAGES[kb_pipeline.STAGE_IDS.index("claims-discovered") + 1 :]:
        kb_pipeline._record(consumer, stage)
    assert _git(consumer, "ls-files", kb_pipeline.NODE_PASS_RELPATH).strip() == kb_pipeline.NODE_PASS_RELPATH
    assert kb_pipeline.read_node_pass(consumer).leaves["vol/alpha.md"].state is kb_pipeline.ReadState.LANDED
