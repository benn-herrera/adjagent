"""The node pass — stage C-inf, the one home for claimhood in prose.

**The missing middle.** The declared pass authors the claims the author marked;
stage D attributes dependencies over an authored graph. Between them sits the
question neither asks: what does a leaf's prose state. This pipeline asks it of
every leaf, whether or not the leaf hosts blocks, one paragraph at a time: each
paragraph :func:`identify.asked_paragraphs` names is one letter ask, the leaf is
the group whose context those asks share (:func:`letters.ask_group`), and
:func:`identify.judge` turns the letters into verdicts and claims.

**The node-pass record is its scope and its checkpoint** (``kb_pipeline``). The
declared pass lists every leaf ``unread``; this pass reads the unread ones and
completes the ``planned`` ones, and never asks about a leaf the record holds a
plan for. Per leaf, in this order and no other:

1. the leaf's asks, every one answered or defaulted;
2. the leaf's whole outcome — its verdicts, and its claims by title and
   locator — into the record as ``planned``;
3. the KB writes, in one per-leaf act (:func:`write.land_leaf`), which
   completes idempotently from the plan;
4. the leaf marked ``landed``.

So a stop anywhere costs at most one leaf's asks: a resume lands a planned leaf
from its record without asking, and asks only what no plan covers. Only a call
that never completes stops the pass (:class:`~.ask.AskError`); a reply carrying
no offered letter is a default, recorded with its cause.

**It exits on a comparison, never on an opinion.** Every leaf landed, and every
obligated paragraph of every leaf — recomputed over the tree the run just wrote
— carrying a verdict in the record, a defaulted one included. Whether
a paragraph *is* a claim is never checked.

**No number is authored and no edge is.** Every entry's rigor is the pending
literal, and dependency attribution runs afterward from :mod:`depends`.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

from .. import kb_pipeline
from ..kb_pipeline import Judgement, LeafEntry, LeafOutcome, NodePassRecord, PlannedClaim, ReadState
from . import ask, conform, gate, graph, identify, inventory, letters, prose, tree, write
from .report import FACT, PASS, ClaimGraphError, Finding, Report


class DiscoveryError(ClaimGraphError):
    """A stage of the node pass stopped on a comparison it makes."""


#: What each paragraph letter says about its paragraph: whether it states a result.
_STATES_A_RESULT: Mapping[str, bool] = MappingProxyType(
    {ask.ParagraphLetter.CLAIM: True, ask.ParagraphLetter.NOT_A_CLAIM: False}
)


def _ask_leaf(
    reading: identify.Reading,
    asked: tuple[identify.Asked, ...],
    *,
    reader: letters.LetterReader,
    record_dir: Path | None,
) -> tuple[identify.Identification, letters.GroupRecord]:
    """One leaf's asks, as one group sharing the leaf's render, and what they come to."""
    group = letters.ask_group(
        kind=letters.Kind.PARAGRAPH,
        group=reading.document,
        items=ask.paragraph_asks(
            ask.ParagraphGroup(document=reading.document, body=reading.render.text),
            [ask.ParagraphItem(paragraph=paragraph.name, text=paragraph.text) for paragraph in asked],
        ),
        reader=reader,
        record_dir=record_dir,
    )
    answers = [
        (paragraph, None if item.letter is None else _STATES_A_RESULT[item.letter])
        for paragraph, item in zip(asked, group.items, strict=True)
    ]
    return identify.judge(reading, answers), group


def _plan(found: identify.Identification) -> LeafEntry:
    """One leaf's outcome as the record holds it, ahead of any KB write."""
    return LeafEntry(
        state=ReadState.PLANNED,
        outcome=LeafOutcome.MINTED if found.claims else LeafOutcome.NO_CLAIM,
        claims=tuple(PlannedClaim(title=claim.title, locator=claim.excerpt) for claim in found.claims),
        verdicts=found.verdicts,
    )


def _unjudged(record: NodePassRecord, documents: tree.Tree) -> list[str]:
    """Over the tree the run just wrote: each leaf's obligated paragraphs against its recorded verdicts."""
    sites = inventory.scan(documents)
    wrong: list[str] = []
    for path, entry in sorted(record.leaves.items()):
        owed = {
            paragraph.start for paragraph in prose.obligated(prose.readable(documents.documents[path], sites), sites)
        }
        missing = sorted(line + 1 for line in owed - {verdict.line for verdict in entry.verdicts})
        if missing:
            wrong.append(
                f"{path}: paragraphs owed a verdict begin on lines {missing}, and the record judges none of them"
            )
    return wrong


def build(
    *,
    kb_root: Path,
    repo_root: Path,
    scratch: Path,
    reader: letters.LetterReader,
    record_dir: Path | None = None,
) -> Report:
    """Carry every leaf the record holds to landed. The record and the tree are the inputs.

    ``reader`` puts each paragraph's ask; ``record_dir`` is where each leaf's
    ask record lands, and none is kept where it is ``None``.
    """
    report = Report()

    try:
        record = kb_pipeline.read_node_pass(repo_root)
        if record is None:
            raise DiscoveryError(
                "node-pass-record",
                f"no node-pass record stands at {kb_pipeline.NODE_PASS_RELPATH}. The declared pass writes one "
                f"listing every leaf it stamped, and this pass reads its scope from nothing else",
            )
        documents = tree.read(kb_root)
        conform.pass_two_gate(documents)
        sites = inventory.scan(documents)
        authored = graph.read(documents, sites)
        states = [entry.state for entry in record.leaves.values()]
        report.findings.append(
            Finding(
                FACT,
                "stage-C-scope",
                f"{states.count(ReadState.UNREAD)} leaves unread, {states.count(ReadState.PLANNED)} planned and "
                f"completed from the record without an ask, {states.count(ReadState.LANDED)} landed already",
            )
        )

        hosted: dict[str, set[str]] = {}
        for node in authored.nodes.values():
            hosted.setdefault(node.document, set()).add(node.id)

        groups: list[letters.GroupRecord] = []
        defaulted: list[tuple[str, kb_pipeline.ParagraphVerdict]] = []
        minted = 0
        for path in sorted(record.leaves):
            entry = record.leaves[path]
            if entry.state is ReadState.LANDED:
                continue
            document = documents.documents[path]
            if entry.state is ReadState.UNREAD:
                reading = identify.reading_of(document, sites)
                asked = identify.asked_paragraphs(reading)
                if not asked:
                    entry = LeafEntry(state=ReadState.PLANNED, outcome=LeafOutcome.NOTHING_TO_READ)
                else:
                    found, group = _ask_leaf(reading, asked, reader=reader, record_dir=record_dir)
                    groups.append(group)
                    defaulted += [
                        (path, verdict) for verdict in found.verdicts if verdict.judgement is Judgement.DEFAULTED
                    ]
                    entry = _plan(found)
                record = record.with_leaf(path, entry)
                kb_pipeline.write_node_pass(repo_root, record)

            elsewhere = frozenset(node_id for other, ids in hosted.items() if other != path for node_id in ids)
            ids = write.land_leaf(
                document=path,
                kind=tree.document_kind(path, has_children=bool(documents.children[path])),
                claims=[
                    write.NewClaim(title=claim.title, rationale=write.prose_rationale(path), locator=claim.locator)
                    for claim in entry.claims
                ],
                blocks={node.id: node.locator for node in authored.hosted_by(path) if node.locator is not None},
                elsewhere=elsewhere,
                kb_root=kb_root,
                scratch=scratch,
                stem=f"cinf-{path.replace('/', '_')}",
            )
            hosted.setdefault(path, set()).update(ids)
            record = record.with_leaf(path, replace(entry, state=ReadState.LANDED))
            kb_pipeline.write_node_pass(repo_root, record)
            minted += len(ids)

        report.findings.append(
            Finding(FACT, "stage-C-asks", f"leaves={len(groups)} {letters.AskTotals.of(groups).detail()}")
        )
        causes = Counter(verdict.cause for _, verdict in defaulted)
        named = [f"{path} line {verdict.line + 1} ({verdict.cause})" for path, verdict in defaulted]
        report.findings.append(
            Finding(
                FACT,
                "stage-C-defaulted",
                " ".join(f"{cause}={causes[cause]}" for cause in kb_pipeline.DefaultCause)
                + (f": {', '.join(named)}" if named else ""),
            )
        )

        wrong = _unjudged(record, tree.read(kb_root))
        if wrong:
            raise DiscoveryError(
                "verdict-coverage",
                f"{len(wrong)} leaf/leaves leave a paragraph owed a verdict without one: {wrong[:5]}",
            )
        report.findings.append(
            Finding(
                PASS,
                "stage-C-identify",
                f"{minted} prose claims minted across {len(record.leaves)} leaves, {len(groups)} of them asked this "
                f"run; every leaf landed and every paragraph owed a verdict carries one",
            )
        )
    except ClaimGraphError as error:
        report.findings.append(error.finding())
        return report

    report.findings += gate.run(repo_root)
    return report
