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

**What each candidate writes is :func:`attribute.written`'s**, and only then is
the set checked: every ``depends`` edge lying on a cycle of the classified set
is cut (:func:`attribute.cycle_edges`), keeping the relationship and giving up
only the direction the cycle disproves. No question is asked again about a
cycle. Every cut lands as a ``demoted`` record carrying its origin
(:func:`cuts`).
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .. import kb_pipeline, kb_schema
from . import ask, equation_sites, letters
from .attribute import Candidate, Relation, Written, cycle_edges, written
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
    ``references`` are what :func:`attribute.written` makes of them, less the
    ``depends`` edges a cycle cut, which are ``demoted`` and among
    ``references``; :func:`cuts` says which of ``references`` land as
    ``demoted`` records. ``asks`` is this run's group records; a group the
    record already held is not among them.
    """

    relations: Mapping[Pair, Relation]
    outcomes: Mapping[Pair, kb_pipeline.ClassifyOutcome]
    edges: tuple[Pair, ...]
    references: tuple[Pair, ...]
    demoted: tuple[Pair, ...]
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
) -> tuple[tuple[Pair, ...], tuple[Pair, ...], tuple[Pair, ...]]:
    """The ``depends`` edges, ``references`` records and cycle-demoted edges the classified candidates write.

    Two candidates writing one record write it once. Every ``depends`` edge on
    a cycle of the set is demoted, so what remains is acyclic by construction.
    """
    written_as = [written(candidate, relations[candidate.pair]) for candidate in candidates]
    depends = sorted({pair for kind, pair in written_as if kind is Written.DEPENDS})
    demoted = cycle_edges(depends)
    on_ring = set(demoted)
    edges = tuple(pair for pair in depends if pair not in on_ring)
    references = tuple(sorted({pair for kind, pair in written_as if kind is Written.REFERENCES} | on_ring))
    return edges, references, demoted


def cuts(ring: Sequence[Pair], classification: Classification, unmarked_yes: Iterable[Pair]) -> Mapping[Pair, str]:
    """Every ``references`` record the build's cycle breaking cut from ``depends``, with its origin.

    A cut is a ``depends`` edge a cycle of the classified set demoted, or a
    pair of the containment ring (``ring``, :attr:`attribute.Attribution.demoted`)
    that kept its drafted *mention* — drafted with no reader, or defaulted after
    the re-ask. A ring pair a model answered is that answer's record and no cut.
    The origin is ``inferred`` where the pair, in the direction written, is a
    yes in the unmarked record (``unmarked_yes``), and ``cited`` otherwise.
    """
    cited, inferred = kb_schema.DEMOTED_ORIGINS
    yes = set(unmarked_yes)
    took_its_draft = (kb_pipeline.ClassifyOutcome.DRAFTED, kb_pipeline.ClassifyOutcome.DEFAULTED)
    cut = [
        *classification.demoted,
        *(
            pair
            for pair in ring
            if classification.relations.get(pair) is Relation.MENTION
            and classification.outcomes.get(pair) in took_its_draft
        ),
    ]
    return MappingProxyType({pair: inferred if pair in yes else cited for pair in cut})


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
    edges, references, demoted = records(candidates, relations)
    return Classification(
        relations=MappingProxyType(relations),
        outcomes=MappingProxyType({pair: entry.outcome for pair, entry in entries.items()}),
        edges=edges,
        references=references,
        demoted=demoted,
        asks=tuple(asked),
    )
