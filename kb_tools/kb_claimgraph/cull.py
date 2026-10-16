"""The ``claims-culled`` stage: prose claims that state no step a linked claim does not, removed.

**The candidates are the links**: every marked pair (:func:`attribute.narrow`), every pair the
unmarked-reference ask answered yes in either direction (:func:`unmarked.found`) and every adjacency link
(:func:`order.adjacent_links`), each unordered, with at least one end a prose claim
(:func:`hand_named.prose_claims`). Each is one colinear ask (:func:`ask.colinear_asks`), its two claims shown
in reading order (:mod:`order`), grouped by the earlier claim and named by the later. The letters name the
claims by the order shown and the record names them by id, so a letter becomes a verdict through
:func:`verdict_of`.

**The pure planner** follows the first pass: each culled claim's target (:func:`cull_targets`) and root
(:func:`cull_roots`). A claim whose root is not its target is asked once more, against its root — grouped by
the root, named by the claim — and kept unless that answer names it as adding nothing (:func:`final_culls`);
no claim is asked a third time. A defaulted ask is ``distinct`` and both claims keep.

**The culled claims are removed and no edge is added.** :func:`write.issue_culls` lands the removals; every
inferred link that survives, one with a culled end re-pointed onto that end's root, goes undirected to the cull
record (:func:`plan_cull`), which is written once, after the issue, for dependency attribution to read. The
node set is fixed at this stage's boundary.
"""

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from .. import kb_pipeline
from . import (
    ask,
    attribute,
    classify,
    conform,
    gate,
    graph,
    hand_named,
    inventory,
    letters,
    order,
    tree,
    unmarked,
    write,
)
from .report import FACT, PASS, ClaimGraphError, Finding, Report

Link = order.Link
Verdict = kb_pipeline.CullVerdict
Harvest = kb_pipeline.LinkHarvest

#: The no-claim reason a leaf takes when the cull removes the one claim it hosted.
CULLED_NO_CLAIM = (
    "This document's claim states nothing that another claim in the KB does not already state; that claim "
    "stands for both in the claim graph."
)

#: A link's inferred harvests, the earlier taking precedence where two find one link. A marked pair outranks
#: them all.
_HARVEST_PRECEDENCE: tuple[Harvest, ...] = (Harvest.UNMARKED, Harvest.ADJACENT, Harvest.CULLED)


def _adds_nothing(link: Link, node_id: str) -> Verdict:
    return Verdict.A_ADDS_NOTHING if node_id == link[0] else Verdict.B_ADDS_NOTHING


def verdict_of(letter: str | None, link: Link, positions: Mapping[str, order.Position]) -> Verdict:
    """The verdict, by id, a colinear letter over ``link`` records; ``None`` — a defaulted ask — is distinct."""
    first, second = order.shown_order(link, positions)
    if letter == ask.ColinearLetter.SECOND_ADDS_NOTHING:
        return _adds_nothing(link, second)
    if letter == ask.ColinearLetter.FIRST_ADDS_NOTHING:
        return _adds_nothing(link, first)
    return Verdict.DISTINCT


def named(link: Link, verdict: Verdict) -> tuple[str, str] | None:
    """The claim ``verdict`` names as adding nothing, and its partner; ``None`` for distinct."""
    if verdict is Verdict.A_ADDS_NOTHING:
        return link
    if verdict is Verdict.B_ADDS_NOTHING:
        return link[1], link[0]
    return None


def cull_targets(
    answers: Iterable[tuple[Link, Verdict]], prose: Collection[str], positions: Mapping[str, order.Position]
) -> dict[str, str]:
    """Each culled prose claim's target.

    An answer naming a claim culls it into its partner, except that a claim outside ``prose`` is never culled:
    the prose claim of the pair goes into it instead, and a pair with no prose claim culls nothing. A claim
    several answers cull targets the earliest of their partners in reading order, a tie by id. A cycle among
    targets is broken by removing the target of the cycle's earliest claim in reading order.
    """
    earlier = order.reading_key(positions)
    targets: dict[str, str] = {}
    for link, verdict in answers:
        pair = named(link, verdict)
        if pair is None:
            continue
        culled, into = pair
        if culled not in prose:
            culled, into = into, culled
        if culled not in prose:
            continue
        if culled not in targets or earlier(into) < earlier(targets[culled]):
            targets[culled] = into

    breaks = []
    done: set[str] = set()
    for start in sorted(targets):
        path: list[str] = []
        at = start
        while at not in done and at not in path and at in targets:
            path.append(at)
            at = targets[at]
        if at in path:
            breaks.append(min(path[path.index(at) :], key=earlier))
        done.update(path)
    for node_id in breaks:
        del targets[node_id]
    return targets


def cull_roots(targets: Mapping[str, str]) -> dict[str, str]:
    """Each culled claim's root: its targets followed to a claim with none. ``targets`` holds no cycle."""
    roots = {}
    for culled, root in targets.items():
        while root in targets:
            root = targets[root]
        roots[culled] = root
    return roots


def confirm_pairs(targets: Mapping[str, str], roots: Mapping[str, str]) -> list[Link]:
    """The link of each culled claim and its root, where the root is not its target; sorted."""
    return sorted(order.link(culled, roots[culled]) for culled, target in targets.items() if roots[culled] != target)


def confirmed_culls(answers: Iterable[tuple[Link, Verdict]], roots: Mapping[str, str]) -> set[Link]:
    """The confirming links whose answer names the culled claim, not its root, as adding nothing."""
    confirmed = set()
    for link, verdict in answers:
        pair = named(link, verdict)
        if pair is not None and roots.get(pair[0]) == pair[1]:
            confirmed.add(link)
    return confirmed


def final_culls(targets: Mapping[str, str], roots: Mapping[str, str], confirmed: Collection[Link]) -> dict[str, str]:
    """Each claim the cull drops, mapped to its root: one whose root is its target, and one whose confirming link
    is confirmed. Every other claim is kept."""
    return {
        culled: roots[culled]
        for culled, target in targets.items()
        if roots[culled] == target or order.link(culled, roots[culled]) in confirmed
    }


@dataclass(frozen=True)
class CullPlan:
    """The culled claims in id order, and every inferred link that survives the cull, by pair."""

    culls: tuple[str, ...]
    links: tuple[kb_pipeline.CullLink, ...]


def plan_cull(
    *, marked: Collection[Link], inferred: Iterable[tuple[Link, Harvest]], into: Mapping[str, str]
) -> CullPlan:
    """Every link re-pointed through ``into`` — each culled claim mapped to its root — on both ends.

    Links coinciding on one pair keep the harvest of higher precedence, a marked pair the highest. A self-link
    is dropped; an untouched marked pair is withheld, as is a re-pointed link equal to one; an untouched inferred
    link keeps its harvest; every other re-pointed link, a marked one included, is inferred with harvest
    :attr:`~kb_tools.kb_pipeline.LinkHarvest.CULLED`.
    """
    best: dict[Link, Harvest | None] = dict.fromkeys(marked)
    for link, harvest in inferred:
        if link not in best:
            best[link] = harvest
        else:
            held = best[link]
            if held is not None and _HARVEST_PRECEDENCE.index(harvest) < _HARVEST_PRECEDENCE.index(held):
                best[link] = harvest

    kept_marked: set[Link] = set()
    kept: dict[Link, Harvest] = {}
    repointed: set[Link] = set()
    for link, harvest in best.items():
        moved = order.link(into.get(link[0], link[0]), into.get(link[1], link[1]))
        if moved[0] == moved[1]:
            continue
        if moved != link:
            repointed.add(moved)
        elif harvest is None:
            kept_marked.add(link)
        else:
            kept[link] = harvest
    for link in repointed - kept_marked:
        kept.setdefault(link, Harvest.CULLED)
    return CullPlan(
        culls=tuple(sorted(into)),
        links=tuple(kb_pipeline.CullLink(a=a, b=b, harvest=harvest) for (a, b), harvest in sorted(kept.items())),
    )


@dataclass(frozen=True)
class _Pass:
    """One pass of colinear asks: each answer by its link, the record's entries, and the groups as asked."""

    answers: tuple[tuple[Link, Verdict], ...]
    entries: tuple[kb_pipeline.CullEntry, ...]
    groups: tuple[letters.GroupRecord, ...]


def _ask_pass(
    pass_number: int,
    groups: Mapping[str, Sequence[tuple[Link, str]]],
    *,
    nodes: Mapping[str, graph.ClaimNode],
    statement: Mapping[str, str],
    positions: Mapping[str, order.Position],
    reader: letters.LetterReader,
    record_dir: Path | None,
) -> _Pass:
    """One group per key of ``groups`` in ascending order, named ``p<pass>-<key>``, each ask named by its claim."""
    answers: list[tuple[Link, Verdict]] = []
    entries: list[kb_pipeline.CullEntry] = []
    asked_groups: list[letters.GroupRecord] = []
    for key in sorted(groups):
        items = []
        for link, item in groups[key]:
            first, second = order.shown_order(link, positions)
            items.append(
                ask.ColinearItem(
                    key=item,
                    first=nodes[first],
                    first_statement=statement[first],
                    second=nodes[second],
                    second_statement=statement[second],
                )
            )
        asked = letters.ask_group(
            kind=letters.Kind.COLINEAR,
            group=f"p{pass_number}-{key}",
            items=ask.colinear_asks(items),
            reader=reader,
            record_dir=record_dir,
        )
        asked_groups.append(asked)
        for (link, _), record in zip(groups[key], asked.items, strict=True):
            verdict = verdict_of(record.letter, link, positions)
            answers.append((link, verdict))
            entries.append(
                kb_pipeline.CullEntry(
                    a=link[0],
                    b=link[1],
                    pass_number=pass_number,
                    verdict=verdict,
                    outcome=kb_pipeline.ClassifyOutcome(record.outcome.value),
                )
            )
    return _Pass(answers=tuple(answers), entries=tuple(entries), groups=tuple(asked_groups))


def _findings(
    *, candidates: int, first: _Pass, second: _Pass, confirm: int, plan: CullPlan, into: Mapping[str, str]
) -> list[Finding]:
    defaulted = [
        entry for entry in first.entries + second.entries if entry.outcome is kb_pipeline.ClassifyOutcome.DEFAULTED
    ]
    one_step = sum(1 for link, verdict in first.answers if named(link, verdict) is not None)
    roots = [into[node_id] for node_id in plan.culls]
    return [
        Finding(FACT, "stage-cull-asks-1", f"groups={len(first.groups)} {letters.AskTotals.of(first.groups).detail()}"),
        Finding(
            FACT, "stage-cull-asks-2", f"groups={len(second.groups)} {letters.AskTotals.of(second.groups).detail()}"
        ),
        Finding(
            FACT,
            "stage-cull-defaulted",
            (
                "no co-linearity ask defaulted"
                if not defaulted
                else f"{len(defaulted)} co-linearity asks carried no offered letter after one re-ask, are recorded "
                f"distinct and keep both claims: "
                + ", ".join(f"p{entry.pass_number} {entry.a} {entry.b}" for entry in defaulted)
            ),
        ),
        Finding(
            PASS,
            "stage-cull",
            f"candidates={candidates} one-step={one_step} confirm-asked={confirm} culled={len(plan.culls)} "
            f"by-root={', '.join(f'{root} {roots.count(root)}' for root in sorted(set(roots))) or 'none'} "
            f"links={len(plan.links)}",
        ),
    ]


def build(
    *,
    kb_root: Path,
    repo_root: Path,
    scratch: Path,
    reader: letters.LetterReader,
    record_dir: Path | None = None,
) -> Report:
    """Ask every candidate, confirm every claim whose root is not its target, issue the culls, then write the
    cull record and run the gate.

    ``reader`` puts each ask; ``record_dir`` is where each group's ask record lands, and none is kept where it
    is ``None``.
    """
    report = Report()

    try:
        node_pass = kb_pipeline.read_node_pass(repo_root)
        if node_pass is None:
            raise ClaimGraphError(
                "node-pass-record",
                f"no node-pass record stands at {kb_pipeline.NODE_PASS_RELPATH}; the marked pairs are read off "
                f"its verdicts, and the declared pass is what writes it",
            )
        unmarked_record = kb_pipeline.read_unmarked(repo_root)
        documents = tree.read(kb_root)
        conform.pass_two_gate(documents)
        sites = inventory.scan(documents)
        authored = graph.read(documents, sites)
        positions = order.claim_positions(documents, authored, sites)
        prose = hand_named.prose_claims(authored, sites)
        statement_of = classify.statements(documents, authored, sites)
        statement = {node_id: statement_of(node) for node_id, node in authored.nodes.items()}

        marked = {
            order.link(*candidate.pair)
            for candidate in attribute.narrow(documents, authored, sites, node_pass).candidates
        }
        # A yes the record holds over a claim no longer in the graph — one an interrupted run of this stage
        # already removed — links nothing.
        yeses = () if unmarked_record is None else unmarked.found(unmarked_record)
        inferred = [
            (order.link(source, target), Harvest.UNMARKED)
            for source, target in yeses
            if source in authored.nodes and target in authored.nodes
        ]
        inferred += [(link, Harvest.ADJACENT) for link in order.adjacent_links(authored, positions, marked)]

        candidates = sorted({link for link in marked | {link for link, _ in inferred} if prose & set(link)})
        first_groups: dict[str, list[tuple[Link, str]]] = {}
        for link in candidates:
            earlier, later = order.shown_order(link, positions)
            first_groups.setdefault(earlier, []).append((link, later))
        ask_pass = partial(
            _ask_pass,
            nodes=authored.nodes,
            statement=statement,
            positions=positions,
            reader=reader,
            record_dir=record_dir,
        )
        first = ask_pass(1, first_groups)

        targets = cull_targets(first.answers, prose, positions)
        roots = cull_roots(targets)
        confirm = confirm_pairs(targets, roots)
        second_groups: dict[str, list[tuple[Link, str]]] = {}
        for link in confirm:
            culled, root = link if roots.get(link[0]) == link[1] else (link[1], link[0])
            second_groups.setdefault(root, []).append((link, culled))
        second = ask_pass(2, second_groups)

        into = final_culls(targets, roots, confirmed_culls(second.answers, roots))
        plan = plan_cull(marked=marked, inferred=inferred, into=into)
        report.findings += write.issue_culls(plan.culls, reason=CULLED_NO_CLAIM, kb_root=kb_root, scratch=scratch)
        kb_pipeline.write_cull(
            repo_root,
            kb_pipeline.CullRecord(
                entries=first.entries + second.entries,
                culls=tuple(kb_pipeline.Cull(culled=node_id, into=into[node_id]) for node_id in plan.culls),
                links=plan.links,
            ),
        )
        report.findings += _findings(
            candidates=len(candidates), first=first, second=second, confirm=len(confirm), plan=plan, into=into
        )
    except ClaimGraphError as error:
        report.findings.append(error.finding())
        return report

    report.findings += gate.run(repo_root)
    return report
