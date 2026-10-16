"""Classification: every edge candidate is *supported by*, *in support of* or *mention*.

One letter ask per candidate (:mod:`letters`), grouped by source claim in
ascending id, so every ask of a group opens with the source and its passages
and only the candidate differs. The letters a candidate is offered are its
:attr:`~.attribute.Candidate.offered` relations and no others; a reply naming
none of them is re-asked once and then takes the candidate's draft. With no
reader, every candidate takes its draft.

**Each group lands in the classification record as it completes**
(:data:`kb_pipeline.CLASSIFICATION_RELPATH`), and a resumed run asks only the
candidates the record does not hold, so a stop mid-stage costs at most the group
in flight. A candidate recorded *drafted* was held by no reader, and a run with
one asks it.

**What each candidate writes is :func:`attribute.written`'s**, cycles included:
the stage cuts every ``depends`` edge on a cycle once it has written them
(:func:`write.demote_cycles`), and no question is asked again about a cycle.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .. import kb_pipeline
from . import ask, equation_sites, letters
from .attribute import Candidate, Relation, Written, written
from .graph import AuthoredGraph, ClaimNode
from .hand_named import bodies
from .inventory import Inventory
from .tree import Tree, strip_markers, unquote

#: The classify letters' meanings: one to one, and the only place a letter becomes a relation.
LETTER_RELATION: Mapping[ask.ClassifyLetter, Relation] = MappingProxyType(
    {
        ask.ClassifyLetter.SUPPORTED_BY: Relation.SUPPORTED_BY,
        ask.ClassifyLetter.IN_SUPPORT_OF: Relation.IN_SUPPORT_OF,
        ask.ClassifyLetter.MENTION: Relation.MENTION,
    }
)
_RELATION_LETTER: Mapping[Relation, ask.ClassifyLetter] = MappingProxyType(
    {relation: letter for letter, relation in LETTER_RELATION.items()}
)

Pair = tuple[str, str]


@dataclass(frozen=True)
class Classification:
    """What classification decided and what it writes.

    ``relations`` and ``outcomes`` are per candidate. ``edges`` and
    ``references`` are what :func:`attribute.written` makes of them, and the
    edges may close cycles. ``asks`` is this run's group records; a group the
    record already held is not among them.
    """

    relations: Mapping[Pair, Relation]
    outcomes: Mapping[Pair, kb_pipeline.ClassifyOutcome]
    edges: tuple[Pair, ...]
    references: tuple[Pair, ...]
    asks: tuple[letters.GroupRecord, ...]


def statements(tree: Tree, graph: AuthoredGraph, inventory: Inventory) -> Callable[[ClaimNode], str]:
    """Each claim's statement as an ask shows it: its block, its prose paragraph, or its equation fence.

    A claim none of the three reaches is shown by its title.
    """
    found = {node.id: body for node, _, _, body in bodies(tree, graph, inventory)}
    lines: dict[str, list[str]] = {}
    for node_id, fence in equation_sites.fences(graph, inventory).items():
        if fence.document not in lines:
            lines[fence.document] = unquote(strip_markers(tree.documents[fence.document].text)).splitlines()
        found[node_id] = "\n".join(lines[fence.document][fence.start : fence.end])
    return lambda node: found.get(node.id, node.title)


def _held(entry: kb_pipeline.CandidateEntry | None, *, asking: bool) -> bool:
    """Whether the record already answers for a candidate: a draft does not, to a run that can ask."""
    return entry is not None and not (asking and entry.outcome is kb_pipeline.ClassifyOutcome.DRAFTED)


def _relation(candidate: Candidate, entry: kb_pipeline.CandidateEntry) -> Relation:
    return candidate.draft if entry.letter is None else LETTER_RELATION[ask.ClassifyLetter(entry.letter)]


def _asked(
    source: ClaimNode,
    group: Sequence[Candidate],
    *,
    statement: Callable[[ClaimNode], str],
    reader: letters.LetterReader,
    record_dir: Path | None,
) -> tuple[letters.GroupRecord, dict[Pair, kb_pipeline.CandidateEntry]]:
    items = [
        ask.ClassifyItem(
            target=candidate.target,
            statement=statement(candidate.target),
            passages=candidate.passages,
            offered=tuple(_RELATION_LETTER[relation] for relation in candidate.offered),
        )
        for candidate in group
    ]
    asked = letters.ask_group(
        kind=letters.Kind.CLASSIFY,
        group=source.id,
        items=ask.classify_asks(ask.ClassifyGroup(source=source, statement=statement(source)), items),
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


def _drafted(group: Sequence[Candidate]) -> dict[Pair, kb_pipeline.CandidateEntry]:
    return {
        candidate.pair: kb_pipeline.CandidateEntry(
            offered=tuple(_RELATION_LETTER[relation] for relation in candidate.offered),
            letter=None,
            outcome=kb_pipeline.ClassifyOutcome.DRAFTED,
        )
        for candidate in group
    }


def records(
    candidates: Sequence[Candidate], relations: Mapping[Pair, Relation]
) -> tuple[tuple[Pair, ...], tuple[Pair, ...]]:
    """The ``depends`` edges and ``references`` records the classified candidates write, each sorted.

    Two candidates writing one record write it once. The edges may close cycles.
    """
    written_as = [written(candidate, relations[candidate.pair]) for candidate in candidates]
    depends = tuple(sorted({pair for kind, pair in written_as if kind is Written.DEPENDS}))
    references = tuple(sorted({pair for kind, pair in written_as if kind is Written.REFERENCES}))
    return depends, references


def classify(
    candidates: Sequence[Candidate],
    *,
    graph: AuthoredGraph,
    statement: Callable[[ClaimNode], str],
    reader: letters.LetterReader | None,
    repo_root: Path,
    record_dir: Path | None = None,
) -> Classification:
    """Classify every candidate, group by group, recording each group as it lands.

    ``reader`` is ``None`` for a run with no model reachable: every candidate
    the record does not hold takes its draft. An :class:`~.ask.AskError` from a
    reader stops the stage with every completed group already recorded.
    """
    record = kb_pipeline.read_classification(repo_root) or kb_pipeline.ClassificationRecord()
    by_source: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        by_source.setdefault(candidate.source.id, []).append(candidate)

    asked: list[letters.GroupRecord] = []
    for source_id in sorted(by_source):
        pending = [
            c for c in by_source[source_id] if not _held(record.candidates.get(c.pair), asking=reader is not None)
        ]
        if not pending:
            continue
        if reader is None:
            entries = _drafted(pending)
        else:
            group_record, entries = _asked(
                graph.nodes[source_id], pending, statement=statement, reader=reader, record_dir=record_dir
            )
            asked.append(group_record)
        record = record.with_entries(entries)
        kb_pipeline.write_classification(repo_root, record)

    entries = {candidate.pair: record.candidates[candidate.pair] for candidate in candidates}
    relations = {candidate.pair: _relation(candidate, entries[candidate.pair]) for candidate in candidates}
    edges, references = records(candidates, relations)
    return Classification(
        relations=MappingProxyType(relations),
        outcomes=MappingProxyType({pair: entry.outcome for pair, entry in entries.items()}),
        edges=edges,
        references=references,
        asks=tuple(asked),
    )
