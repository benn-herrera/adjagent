"""The ``references-found`` stage: references made in prose with no cross-reference, found by asking.

THESIS gap 2. A mechanical shortlist (:mod:`shortlist`) is the draft: per
source claim — every node but a minted equation, which has no text of its own
to point from — its :data:`shortlist.K` best-ranked targets over the whole
node set, less every pair already an edge candidate (:func:`attribute.narrow`)
and every equation minted from inside the source's own body
(:func:`equation_sites.own_equations`). No locality bound enters the pool.
Each shortlisted ordered pair is one letter ask — does the source claim's text point at the candidate's result —
grouped by source in ascending id, every ask of a group sharing the source's
leaf and statement. ``A`` is a yes and the only answer that yields anything:
``B`` and a default (no offered letter after one re-ask) are recorded and
yield no candidate. The ask decides existence only; what a yes is — *supported
by*, *in support of* or *mention* — is classification's.

**The unmarked record is the stage's scope and its checkpoint**
(``kb_pipeline``). The shortlist is planned into it before the first ask, and
each source group's letters land in it as the group completes, so a stop
costs at most the group in flight and a resume asks only the planned pairs it
does not hold. An answer is a fact about the text, so a pair answered under an
earlier plan stays in the record and :func:`found` still reads it.

**Its exit is the ledger's comparison** (``kb_pipeline``'s coverage for the
stage): the record's planned shortlist against its outcomes, every planned
pair carrying one. It writes nothing under ``kb-root/``, so no refresh or
verify follows it.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .. import kb_pipeline
from . import ask, attribute, classify, conform, equation_sites, graph, identify, inventory, letters, shortlist, tree
from .report import FACT, PASS, ClaimGraphError, Finding, Report

Pair = tuple[str, str]

#: How near a pair's two documents sit, nearest first: a yes's locality is what the report counts it under.
LOCALITIES: tuple[str, ...] = ("same document", "same directory", "same paper", "cross paper")


@dataclass(frozen=True)
class Shortlist:
    """The pairs to ask: sources ascending, each source's targets best first.

    ``excluded`` counts the ordered pairs left out of the pools as existing candidates,
    ``own_equations`` those left out as a source's own equation (:func:`equation_sites.own_equations`).
    """

    sources: tuple[str, ...]
    pairs: tuple[Pair, ...]
    excluded: int
    own_equations: int


def plan(
    nodes: Mapping[str, graph.ClaimNode],
    statements: Mapping[str, str],
    *,
    candidate_pairs: Sequence[Pair],
    own: Collection[Pair],
) -> Shortlist:
    """The stage's shortlist over the whole node set: a pure function of the statements and the excluded pairs.

    ``statements`` holds every node's statement, keyed by id; ``candidate_pairs``
    is every pair stage D's narrowing already reaches; ``own`` is
    :func:`equation_sites.own_equations`, each source's own equations, left out of its pool.
    """
    sources = sorted(node_id for node_id, node in nodes.items() if node.equation is None)
    ranked = shortlist.rank(statements, sources=sources, candidate_pairs=candidate_pairs)
    pools = {source: [target for target in ranked[source] if (source, target) not in own] for source in sources}
    chosen = shortlist.top_k(pools, shortlist.K)
    pool = len(statements) - 1
    return Shortlist(
        sources=tuple(sources),
        pairs=tuple((source, target) for source in sources for target in chosen[source]),
        excluded=sum(pool - len(ranked[source]) for source in sources),
        own_equations=sum(len(ranked[source]) - len(pools[source]) for source in sources),
    )


def found(record: kb_pipeline.UnmarkedRecord) -> tuple[Pair, ...]:
    """Every pair the record holds answered :attr:`ask.UnmarkedLetter.POINTS`, sorted: the stage's yeses."""
    return tuple(sorted(pair for pair, entry in record.pairs.items() if entry.letter == ask.UnmarkedLetter.POINTS))


def locality(source_document: str, target_document: str) -> str:
    """The nearest of :data:`LOCALITIES` two kb-root-relative document paths share."""
    if source_document == target_document:
        return LOCALITIES[0]
    if source_document.rsplit("/", 1)[0] == target_document.rsplit("/", 1)[0]:
        return LOCALITIES[1]
    if source_document.split("/")[0] == target_document.split("/")[0]:
        return LOCALITIES[2]
    return LOCALITIES[3]


def _ask_source(
    source: graph.ClaimNode,
    targets: Sequence[graph.ClaimNode],
    *,
    body: str,
    statement: Mapping[str, str],
    reader: letters.LetterReader,
    record_dir: Path | None,
) -> tuple[letters.GroupRecord, dict[Pair, kb_pipeline.CandidateEntry]]:
    asked = letters.ask_group(
        kind=letters.Kind.UNMARKED,
        group=source.id,
        items=ask.unmarked_asks(
            ask.UnmarkedGroup(document=source.document, body=body, source=source, statement=statement[source.id]),
            [ask.UnmarkedItem(target=target, statement=statement[target.id]) for target in targets],
        ),
        reader=reader,
        record_dir=record_dir,
    )
    return asked, {
        (source.id, item.item): kb_pipeline.CandidateEntry(
            offered=item.offered,
            letter=item.letter,
            outcome=kb_pipeline.ClassifyOutcome(item.outcome.value),
            confidence=item.confidence,
        )
        for item in asked.items
    }


def _findings(
    planned: Shortlist,
    record: kb_pipeline.UnmarkedRecord,
    nodes: Mapping[str, graph.ClaimNode],
    *,
    held: int,
    groups: Sequence[letters.GroupRecord],
) -> list[Finding]:
    yeses = found(record)
    by_locality = [locality(nodes[source].document, nodes[target].document) for source, target in yeses]
    defaulted = [pair for pair in planned.pairs if record.pairs[pair].outcome is kb_pipeline.ClassifyOutcome.DEFAULTED]
    return [
        Finding(
            FACT,
            "stage-U-shortlist",
            f"{len(planned.sources)} sources, K={shortlist.K}, {len(planned.pairs)} pairs planned, "
            f"{planned.excluded} pairs excluded as existing candidates, {planned.own_equations} as a source's "
            f"own equation; {held} held by the record already, "
            f"{len(planned.pairs) - held} asked this run",
        ),
        Finding(FACT, "stage-U-asks", f"sources={len(groups)} {letters.AskTotals.of(groups).detail()}"),
        Finding(
            FACT,
            "stage-U-yeses",
            f"{len(yeses)} pairs answered {ask.UnmarkedLetter.POINTS}; by locality: "
            + ", ".join(f"{name} {by_locality.count(name)}" for name in LOCALITIES),
        ),
        Finding(
            FACT,
            "stage-U-defaulted",
            (
                "no pair defaulted"
                if not defaulted
                else f"{len(defaulted)} pairs carried no offered letter after one re-ask and yield no candidate: "
                + ", ".join(f"{source} -> {target}" for source, target in defaulted)
            ),
        ),
    ]


def build(
    *,
    kb_root: Path,
    repo_root: Path,
    reader: letters.LetterReader,
    record_dir: Path | None = None,
) -> Report:
    """Plan the shortlist into the unmarked record and ask every planned pair the record does not hold.

    ``reader`` puts each ask; ``record_dir`` is where each source group's ask
    record lands, and none is kept where it is ``None``.
    """
    report = Report()

    try:
        node_pass = kb_pipeline.read_node_pass(repo_root)
        if node_pass is None:
            raise ClaimGraphError(
                "node-pass-record",
                f"no node-pass record stands at {kb_pipeline.NODE_PASS_RELPATH}; the pairs already candidates are "
                f"read off its verdicts, and the declared pass is what writes it",
            )
        record = kb_pipeline.read_unmarked(repo_root)
        if record is None:
            raise ClaimGraphError(
                "unmarked-record",
                f"no unmarked record stands at {kb_pipeline.UNMARKED_RELPATH}. The declared pass writes one empty, "
                f"and this stage resumes from nothing else",
            )
        documents = tree.read(kb_root)
        conform.pass_two_gate(documents)
        sites = inventory.scan(documents)
        authored = graph.read(documents, sites)
        statement_of = classify.statements(documents, authored, sites)
        statement = {node_id: statement_of(node) for node_id, node in authored.nodes.items()}
        narrowed = attribute.narrow(documents, authored, sites, node_pass)
        planned = plan(
            authored.nodes,
            statement,
            candidate_pairs=[candidate.pair for candidate in narrowed.candidates],
            own=equation_sites.own_equations(documents, authored, sites),
        )

        record = record.with_plan(planned.pairs)
        kb_pipeline.write_unmarked(repo_root, record)
        pending: dict[str, list[str]] = {}
        for source, target in record.unanswered():
            pending.setdefault(source, []).append(target)
        held = len(planned.pairs) - sum(len(targets) for targets in pending.values())

        bodies: dict[str, str] = {}
        groups: list[letters.GroupRecord] = []
        for source_id, target_ids in pending.items():
            source = authored.nodes[source_id]
            if source.document not in bodies:
                bodies[source.document] = identify.reading_of(documents.documents[source.document], sites).render.text
            group, entries = _ask_source(
                source,
                [authored.nodes[target_id] for target_id in target_ids],
                body=bodies[source.document],
                statement=statement,
                reader=reader,
                record_dir=record_dir,
            )
            groups.append(group)
            record = record.with_entries(entries)
            kb_pipeline.write_unmarked(repo_root, record)

        report.findings += _findings(planned, record, authored.nodes, held=held, groups=groups)
        report.findings.append(
            Finding(
                PASS,
                "stage-U-found",
                f"{len(found(record))} unmarked references found; every one of the {len(planned.pairs)} "
                f"shortlisted pairs carries a recorded outcome",
            )
        )
    except ClaimGraphError as error:
        report.findings.append(error.finding())
    return report
