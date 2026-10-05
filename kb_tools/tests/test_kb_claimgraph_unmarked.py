"""The unmarked-reference stage: its shortlist, its asks, its record and resume, and its generation.

**Every ask here is answered by a fixed reader** keyed by the pair it names, so
the shortlist, the record, the resume and the defaults are all exercised with
no model reachable. The corpus is two volumes: a theorem in the second restates
one in the first without a cross-reference, and the same leaf cross-references
a lemma in the first, which makes that pair a candidate the shortlist must
leave alone.
"""

import random
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from kb_tools import kb_pipeline, kb_util
from kb_tools.kb_claimgraph import __main__ as cli
from kb_tools.kb_claimgraph import (
    ask,
    attribute,
    classify,
    discover,
    equation_sites,
    equations,
    graph,
    inventory,
    letters,
    shortlist,
    tree,
    unmarked,
)
from kb_tools.kb_claimgraph.build import build
from kb_tools.kb_driver import prompt_templates, steps
from kb_tools.tests._claimgraph_consumer import install_claimgraph_consumer
from kb_tools.tests._fixture_templates import compose_from_fixture_templates
from kb_tools.tests._shared_builds import copy_build, held_unchanged

_ENTRY_POINT = "# Knowledge Base\n\n- [Alpha](alpha/index.md)\n- [Beta](beta/index.md)\n"


def _volume(title: str, leaves: Sequence[tuple[str, str]]) -> str:
    links = "".join(f"- [{name}]({path})\n" for name, path in leaves)
    return f"[↑ Knowledge Base](../entry-point.md)\n\n# {title}\n\n{links}"


def _leaf(volume: str, title: str, body: str) -> str:
    return f"[↑ {volume}](index.md)\n\n# {title}\n\n{body}"


def _block(identifier: str, environment: str, display: str, statement: str) -> str:
    return f'> <span id="{identifier}">**{environment}**</span>\n>\n> {display} *{statement}*\n'


_TREE = {
    "entry-point.md": _ENTRY_POINT,
    "alpha/index.md": _volume("Alpha", [("Escape", "escape.md"), ("Growth", "growth.md")]),
    "alpha/escape.md": _leaf(
        "Alpha",
        "Escape",
        _block(
            "thm:escape",
            "theorem",
            "**Theorem 1** (Escape rate).",
            "The escape rate $`\\lambda_c`$ falls as the barrier rises.",
        ),
    ),
    "alpha/growth.md": _leaf(
        "Alpha",
        "Growth",
        _block("lem:growth", "lemma", "**Lemma 2** (Firm growth).", "Firm growth is monotone in capital."),
    ),
    "beta/index.md": _volume("Beta", [("Zombie", "zombie.md"), ("Capital", "capital.md")]),
    "beta/zombie.md": _leaf(
        "Beta",
        "Zombie",
        _block(
            "thm:zombie",
            "theorem",
            "**Theorem 3** (Zombie escape).",
            "The zombie escape rate $`\\lambda_c`$ falls as the barrier height rises.",
        )
        + "\nZombie firms are read beside\n"
        '<a href="../alpha/growth.md#lem:growth" data-reference-type="ref" data-reference="lem:growth">Lemma 2</a>.\n',
    ),
    "beta/capital.md": _leaf(
        "Beta",
        "Capital",
        _block("lem:capital", "lemma", "**Lemma 4** (Capital).", "Capital accumulation drives investment."),
    ),
}

_ESCAPE, _GROWTH, _ZOMBIE, _CAPITAL = "Escape rate", "Firm growth", "Zombie escape", "Capital"


@pytest.fixture(scope="module")
def declared_build(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    repo = install_claimgraph_consumer(tmp_path_factory.mktemp("unmarked-declared") / "consumer", _TREE)
    report = build(kb_root=repo / "kb-root", repo_root=repo, scratch=repo / kb_util.scratch_dirname() / "claimgraph")
    assert not report.failed, report.lines()
    with held_unchanged(repo, name="unmarked declared"):
        yield repo


@pytest.fixture
def declared(declared_build: Path, tmp_path: Path) -> Path:
    return copy_build(declared_build, tmp_path / "consumer")


@dataclass(frozen=True)
class _Inputs:
    """What the shortlist is a function of: the node set, every node's statement, and the pairs left out of it."""

    authored: graph.AuthoredGraph
    statements: dict[str, str]
    candidates: list[tuple[str, str]]
    own: frozenset[tuple[str, str]]

    def plan(self) -> unmarked.Shortlist:
        return unmarked.plan(self.authored.nodes, self.statements, candidate_pairs=self.candidates, own=self.own)


def _read(repo: Path) -> _Inputs:
    documents = tree.read(repo / "kb-root")
    sites = inventory.scan(documents)
    authored = graph.read(documents, sites)
    statement = classify.statements(documents, authored, sites)
    narrowed = attribute.narrow(documents, authored, sites, kb_pipeline.read_node_pass(repo))
    return _Inputs(
        authored=authored,
        statements={node_id: statement(node) for node_id, node in authored.nodes.items()},
        candidates=[candidate.pair for candidate in narrowed.candidates],
        own=equation_sites.own_equations(documents, authored, sites),
    )


def _ids(repo: Path) -> dict[str, str]:
    return {node.title: node.id for node in _read(repo).authored.nodes.values()}


class PairReader:
    """Answers each ask from a script keyed by (source id, target id), ``B`` where none is scripted.

    ``stop_at`` names a source whose first ask raises :class:`ask.AskError`, as a call that never completed would.
    """

    def __init__(self, replies: Mapping[tuple[str, str], Sequence[str]] | None = None, *, stop_at: str | None = None):
        self._replies = {pair: list(script) for pair, script in (replies or {}).items()}
        self._stop_at = stop_at
        self.asked: list[tuple[str, str]] = []

    def __call__(self, question: letters.LetterQuestion) -> letters.Reply:
        assert question.kind is letters.Kind.UNMARKED
        if question.group == self._stop_at:
            raise ask.AskError("inference-failed", f"{question.group}: the call never completed")
        pair = (question.group, question.item)
        self.asked.append(pair)
        script = self._replies.get(pair)
        return letters.Reply(script.pop(0) if script else "B")


def _run(repo: Path, reader: letters.LetterReader) -> list[str]:
    return unmarked.build(kb_root=repo / "kb-root", repo_root=repo, reader=reader).lines()


# ---------------------------------------------------------------------------
# The shortlist
# ---------------------------------------------------------------------------


def test_the_shortlist_is_the_same_twice_and_over_a_permuted_node_order(declared: Path) -> None:
    """I13: a pure function of the tree and the fixed node set, ties on target id."""
    inputs = _read(declared)
    first = inputs.plan()

    order = list(inputs.authored.nodes)
    random.Random(7).shuffle(order)
    permuted = unmarked.plan(
        {node_id: inputs.authored.nodes[node_id] for node_id in reversed(order)},
        {node_id: inputs.statements[node_id] for node_id in order},
        candidate_pairs=list(reversed(inputs.candidates)),
        own=inputs.own,
    )

    assert inputs.plan() == first
    assert permuted == first
    assert first.pairs


def test_a_cross_volume_target_earlier_in_reading_order_is_shortlisted(
    declared: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """I14: no locality bound enters the pool — at K = 1 the zombie theorem's one target is in the other volume."""
    monkeypatch.setattr(shortlist, "K", 1)
    ids = _ids(declared)
    inputs = _read(declared)

    planned = inputs.plan()

    assert (ids[_ZOMBIE], ids[_ESCAPE]) in planned.pairs
    assert inputs.authored.nodes[ids[_ESCAPE]].document.startswith("alpha/")
    assert len(planned.pairs) == len(planned.sources)


def test_a_pair_already_a_candidate_is_shortlisted_neither_way_round(declared: Path) -> None:
    ids = _ids(declared)
    inputs = _read(declared)
    assert (ids[_ZOMBIE], ids[_GROWTH]) in inputs.candidates

    planned = inputs.plan()

    assert (ids[_ZOMBIE], ids[_GROWTH]) not in planned.pairs
    assert (ids[_GROWTH], ids[_ZOMBIE]) not in planned.pairs
    assert planned.excluded == 2
    # Four claims, each pool every other node: twelve ordered pairs less the two excluded.
    assert len(planned.pairs) == 10


_FORMULA = "T_{esc} \\approx \\frac{c}{\\lambda_+} \\ln \\frac{L}{\\sigma_{eff}}"


def _fence(label: str) -> str:
    return f"``` math\n\\begin{{equation}}\n\\label{{{label}}}\n{_FORMULA}\n\\end{{equation}}\n```\n"


def _eqref(path: str, label: str) -> str:
    return f'<a href="{path}" data-reference-type="eqref" data-reference="{label}">({label})</a>'


#: One prose claim states ``eq:own`` inside its own paragraph and cross-references it
#: there; ``eq:other`` is the same formula standing free in another leaf, which a second
#: prose claim cross-references. A theorem cites both, so both are minted.
_EQUATION_TREE = {
    "entry-point.md": "# Knowledge Base\n\n- [Vol](vol/index.md)\n",
    "vol/index.md": _volume(
        "Vol", [("Growth", "growth.md"), ("Estimate", "estimate.md"), ("Bound", "bound.md"), ("Decay", "decay.md")]
    ),
    "vol/growth.md": _leaf(
        "Vol",
        "Growth",
        "Once noise delivers the trajectory into the saddle region, the unstable mode grows until\n"
        + _fence("eq:own")
        + f"with only a weak logarithmic dependence on the noise, as {_eqref('growth.md', 'eq:own')} shows.\n",
    ),
    "vol/estimate.md": _leaf("Vol", "Estimate", "The estimate used above is\n\n" + _fence("eq:other")),
    "vol/decay.md": _leaf(
        "Vol", "Decay", f"Decay of the healthy state follows {_eqref('estimate.md', 'eq:other')} in every regime.\n"
    ),
    "vol/bound.md": _leaf(
        "Vol",
        "Bound",
        '> <span id="thm:bound">**theorem**</span>\n>\n> **Theorem 1** (Escape bound). *The escape time is bounded.*\n'
        f">\n> It rests on {_eqref('growth.md', 'eq:own')} and {_eqref('estimate.md', 'eq:other')}.\n",
    ),
}


@pytest.fixture(scope="module")
def equations_build(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The declared pass, a node pass finding growth's and decay's paragraphs claims and nothing else, and the
    equations stage."""
    repo = install_claimgraph_consumer(tmp_path_factory.mktemp("unmarked-equations") / "consumer", _EQUATION_TREE)
    kb_root, scratch = repo / "kb-root", repo / kb_util.scratch_dirname() / "claimgraph"

    def growth_states_a_result(question: letters.LetterQuestion) -> letters.Reply:
        return letters.Reply(ask.ParagraphLetter.CLAIM if question.group in {"vol/growth.md", "vol/decay.md"} else "B")

    for report in (
        build(kb_root=kb_root, repo_root=repo, scratch=scratch),
        discover.build(kb_root=kb_root, repo_root=repo, scratch=scratch, reader=growth_states_a_result),
        equations.build(kb_root=kb_root, repo_root=repo, scratch=scratch),
    ):
        assert not report.failed, report.lines()
    with held_unchanged(repo, name="unmarked equations"):
        yield repo


def test_a_source_s_own_equation_leaves_its_pool_and_one_minted_elsewhere_stays(
    equations_build: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim states ``eq:own`` rather than pointing at it; ``eq:other`` matches it as strongly and stays."""
    monkeypatch.setattr(shortlist, "K", 2)
    inputs = _read(equations_build)
    (claim,) = [node.id for node in inputs.authored.hosted_by("vol/growth.md")]
    own_equation = inputs.authored.equation_node("vol/growth.md", "eq:own")
    other_equation = inputs.authored.equation_node("vol/estimate.md", "eq:other")
    assert own_equation is not None and other_equation is not None
    own, other = (claim, own_equation.id), (claim, other_equation.id)

    unexcluded = unmarked.plan(
        inputs.authored.nodes, inputs.statements, candidate_pairs=inputs.candidates, own=frozenset()
    )
    planned = inputs.plan()

    assert inputs.own == {own}
    assert {own, other} <= set(unexcluded.pairs)
    assert other in planned.pairs and own not in planned.pairs
    assert planned.own_equations == 1 and len(planned.pairs) == len(unexcluded.pairs)


def _equation_candidates(repo: Path) -> tuple[attribute.Attribution, dict[str, str]]:
    """The narrowing over ``repo``, and each prose claim's and each equation node's id by its leaf or label."""
    documents = tree.read(repo / "kb-root")
    sites = inventory.scan(documents)
    authored = graph.read(documents, sites)
    ids = {path: node.id for path in ("vol/growth.md", "vol/decay.md") for node in authored.hosted_by(path)}
    for path, label in (("vol/growth.md", "eq:own"), ("vol/estimate.md", "eq:other")):
        node = authored.equation_node(path, label)
        assert node is not None
        ids[label] = node.id
    return attribute.narrow(documents, authored, sites, kb_pipeline.read_node_pass(repo)), ids


def test_a_prose_claim_cross_referencing_its_own_equation_is_no_candidate(equations_build: Path) -> None:
    """The claim states ``eq:own``; its own reference to it neither depends on nor references it."""
    narrowed, ids = _equation_candidates(equations_build)
    own = (ids["vol/growth.md"], ids["eq:own"])

    assert own not in {candidate.pair for candidate in narrowed.candidates}
    assert narrowed.own_equations == (own,)


def test_a_prose_claim_cross_referencing_an_equation_stated_elsewhere_is_a_candidate(equations_build: Path) -> None:
    narrowed, ids = _equation_candidates(equations_build)

    (candidate,) = [c for c in narrowed.candidates if c.pair == (ids["vol/decay.md"], ids["eq:other"])]

    assert candidate.harvests == {attribute.Harvest.REFERENCE}
    assert set(candidate.offered) == attribute.OFFERED[attribute.CandidateClass.EQUATION_TARGET]


# ---------------------------------------------------------------------------
# The asks and the record
# ---------------------------------------------------------------------------


def test_only_a_points_letter_yields_and_b_and_defaulted_pairs_are_recorded(declared: Path) -> None:
    """I16: ``B`` and a default each end with a recorded outcome and neither is found."""
    ids = _ids(declared)
    yes, no, unread = (ids[_ZOMBIE], ids[_ESCAPE]), (ids[_ESCAPE], ids[_ZOMBIE]), (ids[_CAPITAL], ids[_GROWTH])
    reader = PairReader({yes: ["A"], no: ["B"], unread: ["probably A", "I think it does"]})

    lines = _run(declared, reader)

    record = kb_pipeline.read_unmarked(declared)
    assert record is not None and record.planned is not None and not record.unanswered()
    assert set(record.pairs) == set(record.planned) and set(reader.asked) >= set(record.planned)
    assert record.pairs[yes].letter == "A"
    assert (record.pairs[no].letter, record.pairs[no].outcome) == ("B", kb_pipeline.ClassifyOutcome.ANSWERED)
    assert (record.pairs[unread].letter, record.pairs[unread].outcome) == (None, kb_pipeline.ClassifyOutcome.DEFAULTED)
    assert unmarked.found(record) == (yes,)
    assert any("stage-U-yeses 1 pairs answered A" in line and "cross paper 1" in line for line in lines), lines
    assert any("stage-U-defaulted 1 pairs" in line and f"{unread[0]} -> {unread[1]}" in line for line in lines), lines
    assert not any(" FAIL " in line for line in lines), lines


def test_a_stop_after_group_k_resumes_asking_from_group_k_plus_one(declared: Path) -> None:
    """A stop costs at most the group in flight: the groups before it are recorded and never asked again."""
    _run(declared, PairReader())
    planned = kb_pipeline.read_unmarked(declared).planned  # type: ignore[union-attr]
    sources = list(dict.fromkeys(source for source, _ in planned))
    kb_pipeline.write_unmarked(declared, kb_pipeline.UnmarkedRecord())

    stopped = _run(declared, PairReader(stop_at=sources[2]))

    assert any(" FAIL inference-failed " in line for line in stopped), stopped
    after_stop = kb_pipeline.read_unmarked(declared)
    assert after_stop is not None and after_stop.planned == planned
    assert {source for source, _ in after_stop.pairs} == set(sources[:2])

    resumed = PairReader()
    lines = _run(declared, resumed)

    assert [source for source in dict.fromkeys(source for source, _ in resumed.asked)] == sources[2:]
    assert not kb_pipeline.read_unmarked(declared).unanswered()  # type: ignore[union-attr]
    held = sum(1 for pair in planned if pair[0] in sources[:2])
    assert any(f"{held} held by the record already" in line for line in lines), lines


def test_an_answer_from_an_earlier_plan_stays_in_the_record(declared: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An answer is a fact about the text: a pair the current plan does not hold keeps its letter."""
    ids = _ids(declared)
    earlier = (ids[_ZOMBIE], ids[_CAPITAL])
    kb_pipeline.write_unmarked(
        declared,
        kb_pipeline.UnmarkedRecord().with_entries(
            {earlier: kb_pipeline.CandidateEntry(("A", "B"), "A", kb_pipeline.ClassifyOutcome.ANSWERED)}
        ),
    )
    monkeypatch.setattr(shortlist, "K", 1)

    _run(declared, PairReader())

    record = kb_pipeline.read_unmarked(declared)
    assert record is not None and earlier not in record.planned  # type: ignore[operator]
    assert unmarked.found(record) == (earlier,)


# ---------------------------------------------------------------------------
# A build spending no inference
# ---------------------------------------------------------------------------


def test_with_no_inference_the_row_drops_and_the_record_stays_empty(declared: Path) -> None:
    """The declared pass writes the record empty, nothing writes it again, and the boundary is excused."""
    stage = kb_pipeline.stage_by_id("references-found")
    (row,) = [step for step in steps.steps_for(stage.id) if step.spends_inference]

    assert row.id == "unmarked.build" and not steps.applies(row, spend_inference=False)
    assert kb_pipeline.read_unmarked(declared) == kb_pipeline.UnmarkedRecord()
    ctx = kb_pipeline.CheckContext(declared, no_inference=True)
    assert [unit.satisfied for unit in stage.coverage(ctx).units] == [False]
    assert [unit.vacuous for unit in kb_pipeline._excused(stage.coverage(ctx), stage, ctx).units] == [True]


def test_the_unmarked_asks_have_no_run_that_asks_nobody(declared: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(declared)

    assert cli.main(["--pass", "2", "--scope", "unmarked", kb_util.NO_INFERENCE_FLAG]) == cli.EXIT_USAGE

    assert kb_util.NO_INFERENCE_FLAG in capsys.readouterr().err
    assert kb_pipeline.read_unmarked(declared) == kb_pipeline.UnmarkedRecord()


def test_a_scope_no_stage_of_pass_two_declares_is_refused(declared: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(declared)

    assert cli.main(["--pass", "2", "--scope", "full"]) == cli.EXIT_USAGE

    assert "is no stage of the build" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Generation, against fixture templates
# ---------------------------------------------------------------------------

#: Fixture templates for the unmarked ask, standing in for the working one so
#: the goldens below pin the composer and move with nothing a wording edit
#: touches: every group slot, the composer-filled letters, the per-item slots
#: last, and the ``correction`` alternative ending without a newline.
_FIXTURE_TEMPLATES = {
    ask.LETTER_TEMPLATES[letters.Kind.UNMARKED]: (
        "Leaf @!dyn.document!@\n"
        "@!dyn.body!@\n"
        "Source @!dyn.claim-line!@\n"
        "@!dyn.claim-text!@\n"
        "Candidate @!dyn.candidate-line!@\n"
        "@!dyn.candidate-text!@\n"
        "Answer @!letter-points!@ or @!letter-does-not-point!@.@!correction!@\n"
    ),
    prompt_templates.ALTERNATIVES[ask.LETTER_CORRECTION]: "\n\nAgain; it read:\n@!dyn.returned!@\nOne letter.",
}

_GOLDEN_GROUP = ask.UnmarkedGroup(
    document="beta/zombie.md",
    body="S1: Zombie firms are read beside Lemma 2.\n",
    source=graph.ClaimNode("clm-zzzzzz", "beta/zombie.md", "Zombie escape", "**Theorem 3** (Zombie escape).", None),
    statement="**Theorem 3** (Zombie escape). The zombie escape rate falls.\n",
)
_GOLDEN_ITEMS = (
    ask.UnmarkedItem(
        graph.ClaimNode("clm-eeeeee", "alpha/escape.md", "Escape rate", "**Theorem 1** (Escape rate).", None),
        "**Theorem 1** (Escape rate). The escape rate falls.\n",
    ),
    ask.UnmarkedItem(
        graph.ClaimNode("clm-qqqqqq", "alpha/escape.md", "Equation (2)", None, None, equation="eq:two"),
        "$$ \\lambda_c = e^{-\\Delta} $$",
    ),
)

#: Every ask of the group opens with these bytes: the leaf, then the source claim.
_GOLDEN_PREFIX = """\
Leaf beta/zombie.md
S1: Zombie firms are read beside Lemma 2.
Source - `clm-zzzzzz` — Zombie escape (stated in `beta/zombie.md`: **Theorem 3** (Zombie escape).)
**Theorem 3** (Zombie escape). The zombie escape rate falls.
Candidate """

_GOLDEN_TAILS = (
    """\
- `clm-eeeeee` — Escape rate (stated in `alpha/escape.md`: **Theorem 1** (Escape rate).)
**Theorem 1** (Escape rate). The escape rate falls.
Answer A or B.""",
    """\
- `clm-qqqqqq` — Equation (2) (stated in `alpha/escape.md`)
$$ \\lambda_c = e^{-\\Delta} $$
Answer A or B.""",
)

_GOLDEN_CORRECTION = """

Again; it read:
It does, A.
One letter."""


@pytest.mark.parametrize("returned", [None, "  It does, A.\n"], ids=["first-ask", "re-ask"])
@pytest.mark.parametrize("item", [0, 1], ids=["claim-target", "equation-target"])
def test_the_unmarked_ask_composes_byte_for_byte_from_fixture_templates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, item: int, returned: str | None
) -> None:
    compose_from_fixture_templates(monkeypatch, tmp_path, _FIXTURE_TEMPLATES)
    entry = ask.unmarked_asks(_GOLDEN_GROUP, _GOLDEN_ITEMS)[item]

    correction = "" if returned is None else _GOLDEN_CORRECTION
    assert entry.compose(returned) == _GOLDEN_PREFIX + _GOLDEN_TAILS[item] + correction + "\n"
