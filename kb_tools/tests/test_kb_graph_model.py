"""Assembly-level tests for ``kb_graph.model``.

One clause of the row's done-condition per section: edge dedupe and the
relation-precedence conflict, ``supported-by.jsonl`` contributing nothing, an
edge naming an absent id becoming a stub rather than an exception, and
root-hosted domain attribution. Plus the two properties those clauses rest
on — connectivity classification, and the shuffle invariance demanded of
every ordering.

Most tests hand the model its dataclasses directly; only the
``supported-by.jsonl`` clause needs bytes on disk, because the fact it asserts
is about what the loader does and does not read.
"""

import json
import random
from dataclasses import asdict
from pathlib import Path

import pytest

from kb_tools import kb_schema
from kb_tools.kb_cmd import index as kb_index
from kb_tools.kb_graph import model

# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def _claim(cid: str, *, canonical_path: str = "vol1/topic/leaf.md") -> kb_index.Claim:
    return kb_index.Claim(
        node_type="claim",
        id=cid,
        title=f"Claim {cid}",
        canonical_path=canonical_path,
        canonical_anchor=cid,
        confidence=0.8,
        solidity=0.8,
        build_status=None,
        build_band="ok-to-build",
        rationale="",
        depends_on_count=0,
        strengthen_by_count=0,
        citation_count=0,
    )


def _support(sid: str, *, canonical_path: str = "vol1/topic/sup.md") -> kb_index.SupportNode:
    return kb_index.SupportNode(
        node_type="support",
        id=sid,
        title=f"Support {sid}",
        canonical_path=canonical_path,
        canonical_anchor=sid,
        quality=0.9,
        solidity=0.9,
        build_band="ok-to-build",
    )


def _edge(source: str, target: str, relation: str = "depends", **overrides) -> kb_index.DependsOnEdge:
    fields = {
        "source": source,
        "target": target,
        "target_kind": "claim",
        "target_solidity_recorded": None,
        "context": None,
        "relation": relation,
        "strength": None,
        "fraction": None,
    }
    fields.update(overrides)
    return kb_index.DependsOnEdge(**fields)


# ---------------------------------------------------------------------------
# Dedupe — one edge per relationship, one stroke per edge
# ---------------------------------------------------------------------------


def test_two_records_for_one_pair_yield_one_edge() -> None:
    """The file's own sort key includes ``context`` because duplicates occur."""
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _claim("clm-bbbbbb")],
        edges=[
            _edge("clm-aaaaaa", "clm-bbbbbb", context="second note"),
            _edge("clm-aaaaaa", "clm-bbbbbb", context="first note"),
        ],
    )
    assert [(e.source, e.target) for e in graph.edges] == [("clm-aaaaaa", "clm-bbbbbb")]
    assert graph.edges[0].contexts == ("first note", "second note")
    assert not graph.edges[0].conflict


def test_repeated_and_empty_contexts_collapse() -> None:
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _claim("clm-bbbbbb")],
        edges=[
            _edge("clm-aaaaaa", "clm-bbbbbb", context="note"),
            _edge("clm-aaaaaa", "clm-bbbbbb", context="note"),
            _edge("clm-aaaaaa", "clm-bbbbbb", context=None),
        ],
    )
    assert len(graph.edges) == 1
    assert graph.edges[0].contexts == ("note",)


def test_two_relation_group_is_one_stroke_carrying_depends_and_the_conflict_mark() -> None:
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _support("sup-aaaaaa")],
        edges=[
            _edge("sup-aaaaaa", "clm-aaaaaa", "supports", fraction=0.5),
            _edge("sup-aaaaaa", "clm-aaaaaa", "depends"),
        ],
    )
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert edge.relation == "depends"
    assert edge.conflict
    # The stroke names every relation found, so its title can too.
    assert edge.relations == ("depends", "supports")


@pytest.mark.parametrize(
    ("present", "expected"),
    [
        (("supports", "strengthens"), "supports"),
        (("strengthens", "depends"), "depends"),
        (("strengthens",), "strengthens"),
        (("supports", "conjectures"), "supports"),
        (("conjectures", "zzz"), "conjectures"),
        # `references` asserts nothing about strength, so any other class on the
        # same pair is the one worth drawing — it sorts last of the declared set
        # and still ahead of an undeclared one. Where it does survive, the
        # narrowing takes the pair off the sheet.
        (("references", "rests-on"), "rests-on"),
        (("references", "conjectures"), "references"),
    ],
)
def test_relation_precedence_is_the_declared_constant(present: tuple[str, ...], expected: str) -> None:
    """Precedence is ``RELATION_PRECEDENCE``, not the order records arrived in;
    a relation outside it sorts after all of them, by name. The survivor is what
    decides whether the pair is a stroke, so a group whose survivor is
    ``references`` is not drawn."""
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _claim("clm-bbbbbb")],
        edges=[_edge("clm-aaaaaa", "clm-bbbbbb", relation) for relation in reversed(present)],
    )
    if expected == model.REFERENCE_RELATION:
        assert graph.edges == ()
    else:
        assert graph.edges[0].relation == expected
    assert model.RELATION_PRECEDENCE == ("depends", "supports", "strengthens", "rests-on", "references")


def test_surviving_scalars_come_from_the_surviving_relation() -> None:
    """A conflict's ``fraction`` must not leak in from the losing record."""
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _support("sup-aaaaaa")],
        edges=[
            _edge("sup-aaaaaa", "clm-aaaaaa", "supports", fraction=kb_schema.PENDING_LITERAL),
            _edge("sup-aaaaaa", "clm-aaaaaa", "depends", target_kind="invariant"),
        ],
    )
    assert (graph.edges[0].fraction, graph.edges[0].target_kind) == (None, "invariant")


def test_a_supports_edge_keeps_its_fraction_when_it_is_the_only_relation() -> None:
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _support("sup-aaaaaa")],
        edges=[_edge("sup-aaaaaa", "clm-aaaaaa", "supports", fraction=0.3)],
    )
    assert (graph.edges[0].relation, graph.edges[0].fraction) == ("supports", 0.3)


def test_opposite_directions_are_two_edges() -> None:
    """Edge identity is the ORDERED pair; a reciprocal pair is two facts."""
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _claim("clm-bbbbbb")],
        edges=[_edge("clm-bbbbbb", "clm-aaaaaa"), _edge("clm-aaaaaa", "clm-bbbbbb")],
    )
    assert [(e.source, e.target) for e in graph.edges] == [
        ("clm-aaaaaa", "clm-bbbbbb"),
        ("clm-bbbbbb", "clm-aaaaaa"),
    ]


# ---------------------------------------------------------------------------
# The drawn set is the premise set — `references` is not among it
# ---------------------------------------------------------------------------

_A, _B, _C, _D = "clm-aaaaaa", "clm-bbbbbb", "clm-cccccc", "clm-dddddd"


def _drawn(edges: list[kb_index.DependsOnEdge], *, ids: tuple[str, ...] = (_A, _B, _C, _D)) -> list[tuple[str, str]]:
    graph = model.build_graph(nodes=[_claim(cid) for cid in ids], edges=edges)
    return [(e.source, e.target) for e in graph.edges]


@pytest.mark.parametrize("relation", ["depends", "rests-on", "supports", "strengthens"])
def test_every_premise_relation_is_drawn(relation: str) -> None:
    """Each of the four states a premise, a lift or a standing, and each is a
    stroke — none is narrowed out by the class the sheet does not draw."""
    drawn = _drawn([_edge(*pair, relation) for pair in ((_A, _B), (_C, _D))])
    assert drawn == [(_A, _B), (_C, _D)]


def test_a_references_stroke_is_not_drawn() -> None:
    """The sheet draws what a claim rests on, and this class asserts no such
    thing — so no path, no length and no endpoint makes it a stroke."""
    assert _drawn(
        [_edge(_A, _B, "depends"), _edge(_B, _C, model.REFERENCE_RELATION), _edge(_C, _C, model.REFERENCE_RELATION)],
        ids=(_A, _B, _C),
    ) == [(_A, _B)]


def test_a_pair_recorded_as_both_a_dependency_and_a_reference_is_drawn() -> None:
    """The narrowing reads the *surviving* relation, which dedupe has already
    resolved to ``depends`` — so the reference riding with it cannot take the
    dependency off the sheet, and the stroke still names both."""
    graph = model.build_graph(
        nodes=[_claim(_A), _claim(_B)],
        edges=[_edge(_A, _B, model.REFERENCE_RELATION), _edge(_A, _B, "depends")],
    )
    assert [(e.source, e.target, e.relation) for e in graph.edges] == [(_A, _B, "depends")]
    assert graph.edges[0].relations == ("depends", model.REFERENCE_RELATION)


def test_a_claim_only_references_reach_is_unattached() -> None:
    """Orphan-ness is measured over the premise set, so a claim that rests on
    nothing and carries nothing is unattached however many claims name it — and
    it is its own component for the same reason."""
    graph = model.build_graph(
        nodes=[_claim(cid) for cid in (_A, _B, _C)],
        edges=[_edge(_A, _B, "depends"), _edge(_A, _C, model.REFERENCE_RELATION)],
    )
    assert [node.id for node in graph.nodes if node.isolated] == [_C]
    assert graph.components == ((_A, _B), (_C,))


# ---------------------------------------------------------------------------
# The reduction — a premise another drawn route already carries is not drawn
# ---------------------------------------------------------------------------


def _routes(graph: model.ClaimGraph) -> list[tuple[str, str]]:
    """Every drawn stroke as ``(premise, dependent)`` — the direction a reader walks."""
    return [model.premise_pair(edge) for edge in graph.edges]


def _walkable(routes: list[tuple[str, str]], premise: str, dependent: str) -> bool:
    """Whether one or more drawn strokes lead from ``premise`` up to ``dependent``."""
    frontier, seen = [d for p, d in routes if p == premise], set()
    while frontier:
        current = frontier.pop()
        if current == dependent:
            return True
        if current not in seen:
            seen.add(current)
            frontier.extend(d for p, d in routes if p == current)
    return False


def test_a_premise_a_longer_route_already_carries_is_not_drawn() -> None:
    """The owner's own case: ``C`` rests on ``B``, ``B`` on ``A``, and ``C``
    cites ``A`` as well. The route is drawn and the direct stroke is not — a
    reader walks from ``C`` to ``A`` either way, and the stroke that goes is the
    one that would have spanned the layer between."""
    drawn = _drawn(
        [_edge(_B, _A, "depends"), _edge(_C, _B, "depends"), _edge(_C, _A, "depends")],
        ids=(_A, _B, _C),
    )
    assert drawn == [(_B, _A), (_C, _B)]


@pytest.mark.parametrize("relation", ["depends", "rests-on", "supports", "strengthens"])
def test_the_reduction_reads_every_premise_class_alike(relation: str) -> None:
    """The reduction is over the premise relation and not over one class of it:
    a route of ``supports`` implies a ``supports`` the same way a route of
    ``depends`` implies a ``depends``."""
    drawn = _drawn([_edge(*pair, relation) for pair in ((_A, _B), (_B, _C), (_A, _C))], ids=(_A, _B, _C))
    assert drawn == [(_A, _B), (_B, _C)]


def test_a_premise_no_route_carries_is_drawn_whatever_it_spans() -> None:
    """No alternate route, no elision: the stroke is the only thing saying these
    two claims stand in a premise relation at all."""
    drawn = _drawn(
        [_edge(_B, _A, "depends"), _edge(_C, _B, "depends"), _edge(_D, _A, "depends")],
    )
    assert drawn == [(_B, _A), (_C, _B), (_D, _A)]


def test_the_route_is_walked_in_the_premise_direction_and_not_the_records() -> None:
    """A ``supports`` record reads premise-first and a ``depends`` record reads
    the other way, so one set of records spells two different graphs.

    ``S supports C``, ``C depends B``, ``S supports B``: in record order that is
    the chain ``S → C → B`` with ``S → B`` over the top, and a reduction reading
    it would elide the support of B — a lift no route replaces, B being a
    *premise* of C rather than a dependent of it. In premise order the chain is
    ``S → B → C``, and what the route carries is the support of C. The premise
    order is what the sheet lays out and what a reader walks, so it is what the
    reduction reads: the stroke that goes is the second one.
    """
    support = "sup-aaaaaa"
    graph = model.build_graph(
        nodes=[_support(support), _claim(_B), _claim(_C)],
        edges=[
            _edge(support, _C, "supports"),
            _edge(_C, _B, "depends"),
            _edge(support, _B, "supports"),
        ],
    )
    assert [(e.source, e.target) for e in graph.edges] == [(_C, _B), (support, _B)]
    assert [(e.source, e.target) for e in graph.implied] == [(support, _C)]


def test_every_elided_premise_is_still_walkable_through_the_drawn_edges() -> None:
    """The property the ruling rests on, and the whole of what is preserved:
    reachability. Every premise relation the records state is still walkable on
    the sheet — what a reader can no longer tell is whether the claim stated it
    directly."""
    ids = (_A, _B, _C, _D)
    records = [_edge(a, b, "depends") for a in ids for b in ids if a != b]
    graph = model.build_graph(nodes=[_claim(cid) for cid in ids], edges=records)
    routes = _routes(graph)

    assert graph.implied, "a fully connected graph has premises to spare"
    # A ``depends`` record reads dependent-first, so its premise is its target.
    for record in records:
        assert _walkable(routes, record.target, record.source), f"{record.target} no longer reaches {record.source}"


def test_a_premise_cycle_keeps_every_member_attached() -> None:
    """Nothing about the sheet is gated on acyclicity, so the premise relation
    may hold a ring — and every member of one has an alternate route in the
    *unreduced* graph, so a snapshot-based reduction drops the whole ring and
    strands its claims. The reduction reads the edges still standing, so the
    last stroke holding the ring together finds no route and stays."""
    ring = [_edge(_A, _B, "depends"), _edge(_B, _C, "depends"), _edge(_C, _A, "depends")]
    graph = model.build_graph(nodes=[_claim(cid) for cid in (_A, _B, _C)], edges=ring)

    assert [(e.source, e.target) for e in graph.edges] == [(_A, _B), (_B, _C), (_C, _A)]
    assert graph.implied == ()
    assert [node.id for node in graph.nodes if node.isolated] == []


def test_an_elision_never_makes_an_orphan_or_a_component() -> None:
    """The hard invariant. Degree and connectivity are measured over the drawn
    set, and that is safe rather than lucky: an elided stroke's premise still
    reaches its dependent, so both ends keep an incident stroke, no claim drops
    into the orphan block and no component splits."""
    ids = (_A, _B, _C, _D)
    graph = model.build_graph(
        nodes=[_claim(cid) for cid in ids],
        edges=[_edge(a, b, "depends") for a in ids for b in ids if a < b],
    )

    assert graph.implied
    assert [node.id for node in graph.nodes if node.isolated] == []
    assert graph.components == (ids,)


def test_a_claim_standing_as_its_own_premise_survives_where_nothing_returns_to_it() -> None:
    """Reaching a claim from itself takes a stroke; a reflexive reading would
    elide every self-premise, and one whose claim has no other stroke would take
    the claim out of the hierarchy with it."""
    assert _drawn([_edge(_A, _A, "depends")], ids=(_A,)) == [(_A, _A)]


def test_the_elided_strokes_are_carried_so_the_census_can_count_them() -> None:
    """The sheet says nothing about what it elided, so the count is reported
    instead — and the graph carries the strokes it left out for the op to
    count, never for a second drawing of them."""
    graph = model.build_graph(
        nodes=[_claim(cid) for cid in (_A, _B, _C)],
        edges=[_edge(_B, _A, "depends"), _edge(_C, _B, "depends"), _edge(_C, _A, "depends")],
    )
    assert [(e.source, e.target) for e in graph.implied] == [(_C, _A)]


# ---------------------------------------------------------------------------
# ``supported-by.jsonl`` contributes nothing
# ---------------------------------------------------------------------------


def _write_index(index_dir: Path, *, claims: list[dict], depends_on: list[dict], extra: dict[str, list[dict]]) -> Path:
    index_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, list[dict]] = {
        "claims.jsonl": claims,
        "depends-on.jsonl": depends_on,
        "strengthen-by.jsonl": [],
        "cites.jsonl": [],
        "subtree-aggregates.jsonl": [],
        **extra,
    }
    for name, records in files.items():
        (index_dir / name).write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return index_dir


def _loaded_edges(idx: kb_index.Index) -> list[kb_index.DependsOnEdge]:
    """Every edge the index loaded.

    ``Index`` exposes no accessor for the whole edge list, only the per-source
    ``depends_on_edges``; this walk over known node ids is exact for a fixture
    with no ghost source, which is the case here.
    """
    return [edge for node in idx.all_nodes for edge in idx.depends_on_edges(node.id)]


def test_supported_by_on_disk_contributes_nothing(tmp_path: Path) -> None:
    """``supported-by.jsonl`` is a derived reverse view of the same ``supports``
    records; drawing from it would double-stroke a fact recorded once."""
    claims = [asdict(_claim("clm-aaaaaa")), asdict(_support("sup-aaaaaa"))]
    depends_on = [asdict(_edge("sup-aaaaaa", "clm-aaaaaa", "supports", fraction=0.5))]
    # The reverse view of that same fact, plus a second pair no depends-on line
    # backs — if either were read, the graph would carry an extra stroke.
    supported_by = [
        {"claim_id": "clm-aaaaaa", "support_id": "sup-aaaaaa", "fraction": 0.5},
        {"claim_id": "clm-aaaaaa", "support_id": "sup-bbbbbb", "fraction": 1.0},
    ]
    index_dir = _write_index(
        tmp_path / ".index",
        claims=claims,
        depends_on=depends_on,
        extra={"supported-by.jsonl": supported_by},
    )
    assert (index_dir / "supported-by.jsonl").is_file()

    idx = kb_index.load(index_dir)
    assert idx.stats["depends_on_edges"] == 1
    graph = model.build_graph(nodes=idx.all_nodes, edges=_loaded_edges(idx))
    assert [(e.source, e.target) for e in graph.edges] == [("sup-aaaaaa", "clm-aaaaaa")]
    assert graph.node("sup-bbbbbb") is None


# ---------------------------------------------------------------------------
# Defects decidable without geometry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ghost_end", ["source", "target"])
def test_an_edge_naming_an_absent_id_yields_a_stub_node(ghost_end: str) -> None:
    """A defective graph is the picture's subject, never an error."""
    known, ghost = "clm-aaaaaa", "clm-ghostx"
    edge = _edge(ghost, known) if ghost_end == "source" else _edge(known, ghost)
    graph = model.build_graph(nodes=[_claim(known)], edges=[edge])

    stub = graph.node(ghost)
    assert stub is not None and stub.is_stub
    assert (stub.title, stub.node_type, stub.domain) == ("", None, None)
    assert not stub.isolated  # it exists because an edge named it
    assert graph.node(known).is_stub is False
    assert len(graph.edges) == 1


def test_a_rests_on_target_drawn_off_the_loader_is_a_node_and_not_a_ghost(tmp_path: Path) -> None:
    """The whole path a renderer takes: ``.index/`` bytes, ``all_nodes``, the
    assembly. A work node reached that way must draw as itself — the loader's
    node list omitting it is what turned every ``rests-on`` target into a stub
    while ``claims.jsonl`` carried the record all along."""
    work = "work-khalil2002"
    claims = [
        asdict(_claim("clm-aaaaaa")),
        {
            "node_type": "work",
            "id": work,
            "title": "Khalil, Hassan K. 2002. Nonlinear Systems.",
            "canonical_path": "claim-quality.md",
            "canonical_anchor": "khalil-2002",
            "strength": None,
        },
    ]
    depends_on = [asdict(_edge("clm-aaaaaa", work, "rests-on", target_kind="work", fraction=kb_schema.PENDING_LITERAL))]
    idx = kb_index.load(_write_index(tmp_path / ".index", claims=claims, depends_on=depends_on, extra={}))

    graph = model.build_graph(nodes=idx.all_nodes, edges=_loaded_edges(idx))

    node = graph.node(work)
    assert node is not None and not node.is_stub
    assert (node.node_type, node.title) == ("work", "Khalil, Hassan K. 2002. Nonlinear Systems.")
    assert [(e.source, e.target, e.relation) for e in graph.edges] == [("clm-aaaaaa", work, "rests-on")]


def test_isolated_node_carries_no_incident_edge() -> None:
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _claim("clm-bbbbbb"), _claim("clm-cccccc")],
        edges=[_edge("clm-aaaaaa", "clm-bbbbbb")],
    )
    assert [n.id for n in graph.nodes if n.isolated] == ["clm-cccccc"]


def test_disconnected_components_are_partitioned_deterministically() -> None:
    graph = model.build_graph(
        nodes=[_claim(cid) for cid in ("clm-aaaaaa", "clm-bbbbbb", "clm-cccccc", "clm-dddddd", "clm-eeeeee")],
        edges=[
            _edge("clm-dddddd", "clm-cccccc"),
            _edge("clm-bbbbbb", "clm-aaaaaa"),
        ],
    )
    assert graph.components == (
        ("clm-aaaaaa", "clm-bbbbbb"),
        ("clm-cccccc", "clm-dddddd"),
        ("clm-eeeeee",),
    )


def test_a_whole_graph_is_one_component() -> None:
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _claim("clm-bbbbbb"), _claim("clm-cccccc")],
        edges=[_edge("clm-aaaaaa", "clm-bbbbbb"), _edge("clm-bbbbbb", "clm-cccccc")],
    )
    assert graph.components == (("clm-aaaaaa", "clm-bbbbbb", "clm-cccccc"),)


def test_a_cycle_assembles_without_raising() -> None:
    """Cycle members and their back edges are the layering pass's marks;
    assembly must simply not choke on the shape."""
    graph = model.build_graph(
        nodes=[_claim("clm-aaaaaa"), _claim("clm-bbbbbb")],
        edges=[_edge("clm-aaaaaa", "clm-bbbbbb"), _edge("clm-bbbbbb", "clm-aaaaaa")],
    )
    assert len(graph.edges) == 2
    assert graph.components == (("clm-aaaaaa", "clm-bbbbbb"),)


def test_an_empty_index_assembles_to_an_empty_graph() -> None:
    graph = model.build_graph(nodes=[], edges=[])
    assert (graph.nodes, graph.edges, graph.components, graph.domains) == ((), (), (), ())


# ---------------------------------------------------------------------------
# Domain attribution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("canonical_path", "expected"),
    [
        ("claim-quality.md", model.DOMAIN_ROOT),
        ("invariants.md", model.DOMAIN_ROOT),
        ("./entry-point.md", model.DOMAIN_ROOT),
        ("", model.DOMAIN_ROOT),
        ("vol1/index.md", "vol1"),
        ("vol1/topic/leaf.md", "vol1"),
    ],
)
def test_domain_is_the_first_path_component_with_a_root_sentinel(canonical_path: str, expected: str) -> None:
    graph = model.build_graph(nodes=[_claim("clm-aaaaaa", canonical_path=canonical_path)], edges=[])
    assert graph.node("clm-aaaaaa").domain == expected


def test_domains_are_the_ascending_attributed_set() -> None:
    graph = model.build_graph(
        nodes=[
            _claim("clm-aaaaaa", canonical_path="vol2/leaf.md"),
            _claim("clm-bbbbbb", canonical_path="vol1/leaf.md"),
            _claim("clm-cccccc", canonical_path="vol1/other/leaf.md"),
            _claim("clm-dddddd", canonical_path="claim-quality.md"),
        ],
        edges=[_edge("clm-aaaaaa", "clm-ghostx")],
    )
    assert graph.domains == (model.DOMAIN_ROOT, "vol1", "vol2")


# ---------------------------------------------------------------------------
# The assembly is a function of the record set, not of its order
# ---------------------------------------------------------------------------


def test_shuffling_the_records_changes_nothing() -> None:
    nodes = [
        _claim("clm-aaaaaa", canonical_path="vol1/leaf.md"),
        _claim("clm-bbbbbb", canonical_path="vol2/leaf.md"),
        _claim("clm-cccccc", canonical_path="claim-quality.md"),
        _support("sup-aaaaaa"),
    ]
    edges = [
        _edge("clm-aaaaaa", "clm-bbbbbb", context="beta"),
        _edge("clm-aaaaaa", "clm-bbbbbb", context="alpha"),
        _edge("sup-aaaaaa", "clm-aaaaaa", "supports", fraction=0.5),
        _edge("sup-aaaaaa", "clm-aaaaaa", "strengthens", strength=0.2),
        _edge("clm-cccccc", "clm-ghostx"),
        # `references` records, narrowed out of the drawn set: a narrowing that
        # read the record order rather than the surviving relation would come
        # back with a different edge set on a shuffled list.
        _edge("clm-bbbbbb", "clm-cccccc", model.REFERENCE_RELATION),
        _edge("clm-cccccc", "clm-dddddd", model.REFERENCE_RELATION),
        _edge("clm-bbbbbb", "clm-dddddd", model.REFERENCE_RELATION),
    ]
    reference = model.build_graph(nodes=nodes, edges=edges)

    rng = random.Random(20260904)
    for _ in range(20):
        rng.shuffle(nodes)
        rng.shuffle(edges)
        assert model.build_graph(nodes=nodes, edges=edges) == reference
