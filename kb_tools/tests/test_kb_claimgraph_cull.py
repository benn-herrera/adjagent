"""The co-linearity cull: its planner, and the stage over an in-test KB.

**The planner cases are kbase's** (``internal/claimgraph/cull_test.go``): claims placed one line apart in one
document, answers given by id. **The stage's asks are answered by a fixed reader** keyed by the claim each ask
is named by, so the asks, the issue and the record are exercised with no model reachable.
"""

import random
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_pipeline, kb_util
from kb_tools.kb_claimgraph import __main__ as cli
from kb_tools.kb_claimgraph import ask, cull, discover, equations, graph, inventory, letters, order, tree
from kb_tools.kb_claimgraph.build import build
from kb_tools.kb_driver import steps
from kb_tools.tests._claimgraph_consumer import install_claimgraph_consumer
from kb_tools.tests._shared_builds import copy_build, held_unchanged

Verdict = kb_pipeline.CullVerdict
Harvest = kb_pipeline.LinkHarvest


def _read_at(*ids: str) -> dict[str, order.Position]:
    """``ids`` in reading order, one line apart in one document."""
    return {node_id: order.Position(0, line) for line, node_id in enumerate(ids)}


def _adds_nothing(culled: str, into: str) -> tuple[order.Link, Verdict]:
    link = order.link(culled, into)
    return link, Verdict.A_ADDS_NOTHING if culled == link[0] else Verdict.B_ADDS_NOTHING


def _distinct(x: str, y: str) -> tuple[order.Link, Verdict]:
    return order.link(x, y), Verdict.DISTINCT


# ---------------------------------------------------------------------------
# The letter, recorded by id
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("letter", "shown", "verdict"),
    [
        (ask.ColinearLetter.SECOND_ADDS_NOTHING, ("a", "b"), Verdict.B_ADDS_NOTHING),
        (ask.ColinearLetter.SECOND_ADDS_NOTHING, ("b", "a"), Verdict.A_ADDS_NOTHING),
        (ask.ColinearLetter.FIRST_ADDS_NOTHING, ("a", "b"), Verdict.A_ADDS_NOTHING),
        (ask.ColinearLetter.FIRST_ADDS_NOTHING, ("b", "a"), Verdict.B_ADDS_NOTHING),
        (ask.ColinearLetter.DISTINCT, ("a", "b"), Verdict.DISTINCT),
        (None, ("b", "a"), Verdict.DISTINCT),
    ],
)
def test_a_letter_names_a_claim_by_the_order_shown_and_the_verdict_by_id(
    letter: str | None, shown: tuple[str, str], verdict: Verdict
) -> None:
    assert cull.verdict_of(letter, ("a", "b"), _read_at(*shown)) is verdict


def test_claims_tied_in_reading_order_are_shown_by_id() -> None:
    assert order.shown_order(("a", "b"), {"a": order.Position(0, 3), "b": order.Position(0, 3)}) == ("a", "b")
    assert order.shown_order(("a", "b"), {"a": order.Position(1, 0), "b": order.Position(0, 9)}) == ("b", "a")


# ---------------------------------------------------------------------------
# Targets, roots, the confirming pass
# ---------------------------------------------------------------------------

_TIED = {**_read_at("p", "x"), "q": order.Position(0, 0)}


@pytest.mark.parametrize(
    ("answers", "prose", "positions", "targets", "roots"),
    [
        pytest.param(
            [_adds_nothing("x", "q"), _adds_nothing("x", "p")],
            {"p", "q", "x"},
            _read_at("p", "q", "x"),
            {"x": "p"},
            {"x": "p"},
            id="the earliest partner in reading order is the target",
        ),
        pytest.param(
            [_adds_nothing("x", "q"), _adds_nothing("x", "p")],
            {"p", "q", "x"},
            _TIED,
            {"x": "p"},
            {"x": "p"},
            id="partners tied in reading order go by id",
        ),
        pytest.param(
            [_adds_nothing("k", "x")],
            {"x"},
            _read_at("k", "x"),
            {"x": "k"},
            {"x": "k"},
            id="a block claim named as adding nothing culls the prose claim into it",
        ),
        pytest.param(
            [_adds_nothing("x", "e")],
            {"x"},
            _read_at("x", "e"),
            {"x": "e"},
            {"x": "e"},
            id="a prose claim named culls into its non-prose partner",
        ),
        pytest.param(
            [_adds_nothing("k", "e")], set(), _read_at("k", "e"), {}, {}, id="two non-prose claims cull nothing"
        ),
        pytest.param([_distinct("x", "y")], {"x", "y"}, _read_at("x", "y"), {}, {}, id="distinct culls nothing"),
        pytest.param(
            [_adds_nothing("x", "r"), _adds_nothing("y", "r"), _adds_nothing("z", "x")],
            {"r", "x", "y", "z"},
            _read_at("r", "x", "y", "z"),
            {"x": "r", "y": "r", "z": "x"},
            {"x": "r", "y": "r", "z": "r"},
            id="fan-in: many claims share a root",
        ),
        pytest.param(
            [_adds_nothing("x", "y"), _adds_nothing("y", "z"), _adds_nothing("z", "x")],
            {"x", "y", "z"},
            _read_at("x", "y", "z"),
            {"y": "z", "z": "x"},
            {"y": "x", "z": "x"},
            id="a cycle among targets is broken at its earliest claim, which roots the rest",
        ),
    ],
)
def test_the_survivor_rule(
    answers: list[tuple[order.Link, Verdict]],
    prose: set[str],
    positions: dict[str, order.Position],
    targets: dict[str, str],
    roots: dict[str, str],
) -> None:
    got = cull.cull_targets(answers, prose, positions)

    assert got == targets
    assert cull.cull_roots(got) == roots


def test_in_a_chain_only_the_claim_whose_root_is_not_its_target_is_confirmed() -> None:
    """In the chain c → b → a one pair is confirmed, and a yes there culls both into a."""
    targets = cull.cull_targets(
        [_adds_nothing("b", "a"), _adds_nothing("c", "b")], {"a", "b", "c"}, _read_at("a", "b", "c")
    )
    roots = cull.cull_roots(targets)

    assert cull.confirm_pairs(targets, roots) == [("a", "c")]
    assert cull.final_culls(targets, roots, cull.confirmed_culls([_adds_nothing("c", "a")], roots)) == {
        "b": "a",
        "c": "a",
    }


@pytest.mark.parametrize(
    ("second", "final"),
    [
        pytest.param(
            [_distinct("c", "a"), _adds_nothing("d", "a")],
            {"b": "a", "d": "a"},
            id="a claim past a kept claim still culls into the root",
        ),
        pytest.param(
            [_adds_nothing("c", "a"), _distinct("d", "a")],
            {"b": "a", "c": "a"},
            id="a no to the root keeps a claim that said yes to its partner",
        ),
        pytest.param(
            [_adds_nothing("a", "c"), _adds_nothing("a", "d")],
            {"b": "a"},
            id="naming the root as adding nothing keeps the claim and the root",
        ),
        pytest.param([], {"b": "a"}, id="an unanswered pair keeps its claim"),
    ],
)
def test_each_confirmed_claim_is_judged_against_its_root_alone(
    second: list[tuple[order.Link, Verdict]], final: dict[str, str]
) -> None:
    """The chain d → c → b → a: c and d are each asked against a, and no claim is asked a third time."""
    targets = cull.cull_targets(
        [_adds_nothing("b", "a"), _adds_nothing("c", "b"), _adds_nothing("d", "c")],
        {"a", "b", "c", "d"},
        _read_at("a", "b", "c", "d"),
    )
    roots = cull.cull_roots(targets)

    assert cull.confirm_pairs(targets, roots) == [("a", "c"), ("a", "d")]
    assert cull.final_culls(targets, roots, cull.confirmed_culls(second, roots)) == final


# ---------------------------------------------------------------------------
# Re-pointing and harvests
# ---------------------------------------------------------------------------


def _link(x: str, y: str, harvest: Harvest) -> kb_pipeline.CullLink:
    a, b = order.link(x, y)
    return kb_pipeline.CullLink(a=a, b=b, harvest=harvest)


@pytest.mark.parametrize(
    ("marked", "inferred", "into", "plan"),
    [
        pytest.param(
            [],
            [(("x", "y"), Harvest.UNMARKED)],
            {"x": "p", "y": "q"},
            cull.CullPlan(culls=("x", "y"), links=(_link("p", "q", Harvest.CULLED),)),
            id="a link is re-pointed on both ends",
        ),
        pytest.param(
            [],
            [(("p", "x"), Harvest.ADJACENT)],
            {"x": "p"},
            cull.CullPlan(culls=("x",), links=()),
            id="a self-link is dropped",
        ),
        pytest.param(
            [],
            [(("r", "x"), Harvest.UNMARKED), (("r", "y"), Harvest.ADJACENT)],
            {"x": "p", "y": "p"},
            cull.CullPlan(culls=("x", "y"), links=(_link("p", "r", Harvest.CULLED),)),
            id="re-pointed links meeting on one pair are one link",
        ),
        pytest.param(
            [],
            [(("r", "x"), Harvest.UNMARKED), (("p", "r"), Harvest.ADJACENT)],
            {"x": "p"},
            cull.CullPlan(culls=("x",), links=(_link("p", "r", Harvest.ADJACENT),)),
            id="an untouched link keeps its harvest over a re-pointed one",
        ),
        pytest.param(
            [("p", "r")],
            [(("r", "x"), Harvest.UNMARKED)],
            {"x": "p"},
            cull.CullPlan(culls=("x",), links=()),
            id="an untouched marked pair stands and a link re-pointed onto it is dropped",
        ),
        pytest.param(
            [("r", "x")],
            [],
            {"x": "p"},
            cull.CullPlan(culls=("x",), links=(_link("p", "r", Harvest.CULLED),)),
            id="a marked link with a culled end comes out inferred, harvest culled",
        ),
        pytest.param(
            [],
            [(("a", "b"), Harvest.ADJACENT), (("a", "b"), Harvest.UNMARKED)],
            {},
            cull.CullPlan(culls=(), links=(_link("a", "b", Harvest.UNMARKED),)),
            id="unmarked takes precedence over adjacent on a coinciding pair",
        ),
        pytest.param(
            [("a", "b")],
            [(("a", "b"), Harvest.UNMARKED)],
            {},
            cull.CullPlan(culls=(), links=()),
            id="marked takes precedence over unmarked on a coinciding pair",
        ),
    ],
)
def test_the_plan(
    marked: list[order.Link],
    inferred: list[tuple[order.Link, Harvest]],
    into: dict[str, str],
    plan: cull.CullPlan,
) -> None:
    assert cull.plan_cull(marked=marked, inferred=inferred, into=into) == plan


def test_the_pure_cull_is_one_outcome_over_every_order_of_its_inputs() -> None:
    positions = _read_at("k", "a", "b", "c", "d", "x", "y", "z", "e", "f")
    prose = {"a", "b", "c", "d", "x", "y", "z", "f"}
    first = [
        _adds_nothing("b", "a"),
        _adds_nothing("c", "b"),
        _adds_nothing("d", "c"),
        _adds_nothing("c", "a"),
        _adds_nothing("k", "f"),
        _adds_nothing("x", "y"),
        _adds_nothing("y", "z"),
        _adds_nothing("z", "x"),
        _distinct("a", "k"),
        _adds_nothing("e", "d"),
    ]
    second = [_distinct("d", "a"), _adds_nothing("y", "x"), _adds_nothing("a", "z")]
    marked = [("a", "c"), ("x", "z")]
    inferred = [
        (order.link(x, y), harvest)
        for x, y, harvest in (
            ("a", "b", Harvest.UNMARKED),
            ("b", "c", Harvest.ADJACENT),
            ("c", "d", Harvest.UNMARKED),
            ("k", "f", Harvest.ADJACENT),
            ("x", "y", Harvest.UNMARKED),
            ("y", "z", Harvest.ADJACENT),
            ("a", "k", Harvest.UNMARKED),
            ("d", "e", Harvest.UNMARKED),
            ("b", "e", Harvest.ADJACENT),
            ("d", "b", Harvest.UNMARKED),
            ("b", "e", Harvest.UNMARKED),
        )
    ]

    def run(first, second, marked, inferred) -> tuple[dict[str, str], cull.CullPlan]:
        targets = cull.cull_targets(first, prose, positions)
        roots = cull.cull_roots(targets)
        final = cull.final_culls(targets, roots, cull.confirmed_culls(second, roots))
        return final, cull.plan_cull(marked=marked, inferred=inferred, into=final)

    want = run(first, second, marked, inferred)
    assert want[0] and want[1].links
    shuffle = random.Random(12).shuffle
    for _ in range(50):
        orders = [list(first), list(second), list(marked), list(inferred)]
        for listed in orders:
            shuffle(listed)
        assert run(*orders) == want


# ---------------------------------------------------------------------------
# The stage, over an in-test KB
# ---------------------------------------------------------------------------


def _leaf(title: str, body: str) -> str:
    return f"[↑ Vol](index.md)\n\n# {title}\n\n{body}"


#: Alpha's leaf states A, then B restating it, then theorem D; echo's leaf states E alone.
_TREE = {
    "entry-point.md": "# Knowledge Base\n\n- [Vol](vol/index.md)\n",
    "vol/index.md": "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n- [Alpha](alpha.md)\n- [Echo](echo.md)\n",
    "vol/alpha.md": _leaf(
        "Alpha",
        "The escape rate falls as the barrier rises in every regime.\n\n"
        "Said again, the escape rate falls whenever the barrier rises.\n\n"
        '> <span id="thm:delta">**theorem**</span>\n>\n> **Theorem 1** (Delta). *The delta bound holds here.*\n',
    ),
    "vol/echo.md": _leaf("Echo", "The delta bound holds once more for every barrier height.\n"),
}

_PROSE_LEAVES = {"vol/alpha.md", "vol/echo.md"}


@pytest.fixture(scope="module")
def discovered_build(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """The declared pass, a node pass judging every prose paragraph a claim, and the equations stage."""
    repo = install_claimgraph_consumer(tmp_path_factory.mktemp("cull") / "consumer", _TREE)
    kb_root, scratch = repo / "kb-root", repo / kb_util.scratch_dirname() / "claimgraph"

    def every_paragraph_a_claim(question: letters.LetterQuestion) -> letters.Reply:
        return letters.Reply(ask.ParagraphLetter.CLAIM if question.group in _PROSE_LEAVES else "B")

    for report in (
        build(kb_root=kb_root, repo_root=repo, scratch=scratch),
        discover.build(kb_root=kb_root, repo_root=repo, scratch=scratch, reader=every_paragraph_a_claim),
        equations.build(kb_root=kb_root, repo_root=repo, scratch=scratch),
    ):
        assert not report.failed, report.lines()
    with held_unchanged(repo, name="cull discovered"):
        yield repo


def _claims(repo: Path) -> dict[str, str]:
    """A, B and D by alpha's reading order, and E: each name's claim id."""
    documents = tree.read(repo / "kb-root")
    sites = inventory.scan(documents)
    authored = graph.read(documents, sites)
    positions = order.claim_positions(documents, authored, sites)
    alpha = sorted(authored.hosted_by("vol/alpha.md"), key=lambda node: positions[node.id])
    (echo,) = authored.hosted_by("vol/echo.md")
    return dict(zip("ABDE", [node.id for node in alpha] + [echo.id], strict=True))


@pytest.fixture
def staged(discovered_build: Path, tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """The build with the unmarked record answering E → D yes."""
    repo = copy_build(discovered_build, tmp_path / "consumer")
    claims = _claims(repo)
    pair = (claims["E"], claims["D"])
    kb_pipeline.write_unmarked(
        repo,
        kb_pipeline.UnmarkedRecord()
        .with_plan((pair,))
        .with_entries(
            {
                pair: kb_pipeline.CandidateEntry(
                    tuple(ask.UnmarkedLetter), ask.UnmarkedLetter.POINTS, kb_pipeline.ClassifyOutcome.ANSWERED
                )
            }
        ),
    )
    return repo, claims


class ItemReader:
    """Answers each colinear ask by the claim it is named by, ``C`` where none is scripted; records each ask."""

    def __init__(self, replies: Mapping[str, str]):
        self._replies = dict(replies)
        self.asked: list[tuple[str, str]] = []

    def __call__(self, question: letters.LetterQuestion) -> letters.Reply:
        assert question.kind is letters.Kind.COLINEAR
        self.asked.append((question.group, question.item))
        return letters.Reply(self._replies.get(question.item, ask.ColinearLetter.DISTINCT))


def _run(repo: Path, reader: letters.LetterReader) -> list[str]:
    report = cull.build(
        kb_root=repo / "kb-root", repo_root=repo, scratch=repo / kb_util.scratch_dirname() / "claimgraph", reader=reader
    )
    assert not report.failed, report.lines()
    return report.lines()


def test_the_cull_removes_what_adds_nothing_and_re_points_its_links(staged: tuple[Path, dict[str, str]]) -> None:
    """B adds nothing to A and E nothing to D: both removed, echo restated no-claim, B's link to D onto A."""
    repo, c = staged
    reader = ItemReader(
        {c["B"]: ask.ColinearLetter.SECOND_ADDS_NOTHING, c["E"]: ask.ColinearLetter.SECOND_ADDS_NOTHING}
    )

    _run(repo, reader)

    assert sorted(reader.asked) == sorted(
        [(f"p1-{c['A']}", c["B"]), (f"p1-{c['B']}", c["D"]), (f"p1-{c['D']}", c["E"])]
    )
    authored = kb_index_lib.scan_authored_ids(repo / "kb-root")
    assert {c["A"], c["D"]} <= set(authored) and not {c["B"], c["E"]} & set(authored)
    kb_text = "".join(kb_index_lib.document_texts(repo / "kb-root").values())
    assert c["B"] not in kb_text and c["E"] not in kb_text
    echo = kb_index_lib.parse_frontmatter((repo / "kb-root" / "vol" / "echo.md").read_text(encoding="utf-8"))
    assert echo is not None and not echo.get("claims") and echo["no-claim"] == cull.CULLED_NO_CLAIM

    record = kb_pipeline.read_cull(repo)
    assert record is not None
    assert set(record.culls) == {
        kb_pipeline.Cull(culled=c["B"], into=c["A"]),
        kb_pipeline.Cull(culled=c["E"], into=c["D"]),
    }
    assert record.links == (_link(c["A"], c["D"], Harvest.CULLED),)
    assert {(entry.a, entry.b): entry.verdict for entry in record.entries} == dict(
        [_adds_nothing(c["B"], c["A"]), _distinct(c["B"], c["D"]), _adds_nothing(c["E"], c["D"])]
    )
    assert {entry.pass_number for entry in record.entries} == {1}
    assert kb_pipeline.stage_by_id("claims-culled").coverage(kb_pipeline.CheckContext(repo)).units[0].satisfied


def test_a_defaulted_ask_keeps_both_claims(staged: tuple[Path, dict[str, str]]) -> None:
    repo, c = staged

    lines = _run(repo, ItemReader({c["B"]: "?"}))

    assert c["B"] in kb_index_lib.scan_authored_ids(repo / "kb-root")
    record = kb_pipeline.read_cull(repo)
    assert record is not None and record.culls == ()
    (entry,) = [entry for entry in record.entries if {entry.a, entry.b} == {c["A"], c["B"]}]
    assert (entry.verdict, entry.outcome) == (Verdict.DISTINCT, kb_pipeline.ClassifyOutcome.DEFAULTED)
    assert any("stage-cull-defaulted 1 co-linearity asks" in line for line in lines), lines


def test_with_no_inference_the_row_drops_and_the_record_stands_as_declared(
    staged: tuple[Path, dict[str, str]], monkeypatch, capsys
) -> None:
    repo, _ = staged
    stage = kb_pipeline.stage_by_id("claims-culled")
    (row,) = [step for step in steps.steps_for(stage.id) if step.spends_inference]
    before = set(kb_index_lib.scan_authored_ids(repo / "kb-root"))
    monkeypatch.chdir(repo)

    assert row.id == "cull.build" and not steps.applies(row, spend_inference=False)
    assert cli.main(["--pass", "2", "--scope", "cull", kb_util.NO_INFERENCE_FLAG]) == cli.EXIT_USAGE
    assert kb_util.NO_INFERENCE_FLAG in capsys.readouterr().err
    assert kb_pipeline.read_cull(repo) == kb_pipeline.CullRecord()
    assert set(kb_index_lib.scan_authored_ids(repo / "kb-root")) == before
    ctx = kb_pipeline.CheckContext(repo, no_inference=True)
    assert [unit.satisfied for unit in kb_pipeline._excused(stage.coverage(ctx), stage, ctx).units] == [True]
