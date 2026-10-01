"""The node pass — stage C-inf, the one home for claimhood in prose.

**The missing middle.** The declared pass authors the claims the author marked;
stage D attributes dependencies over an authored graph. Between them sits the
question neither asks: what does a leaf's prose state. This pipeline asks it,
once per leaf, over the prose outside the leaf's headings and its
claim-bearing, proof and definition blocks (:mod:`prose`) — whether or not the
leaf hosts blocks — and
in the same ask judges every paragraph of that prose holding a cross-reference,
a claim or not a claim.

**The node-pass record is its scope and its checkpoint** (``kb_pipeline``). The
declared pass lists every leaf ``unread``; this pass reads the unread ones and
completes the ``planned`` ones, and never asks about a leaf the record holds a
plan for. Per leaf, in this order and no other:

1. the ask, the checks and the re-asks (:mod:`identify`);
2. the leaf's whole outcome — its verdicts, and its claims by title and
   locator — into the record as ``planned``;
3. the KB writes, in one per-leaf act (:func:`write.land_leaf`), which
   completes idempotently from the plan;
4. the leaf marked ``landed``.

So a stop anywhere costs nothing already paid for: a resume lands a planned leaf
from its record without asking, and reads only what no plan covers.

**It exits on a comparison, never on an opinion.** Every leaf landed, and every
obligated paragraph of every leaf — recomputed over the tree the run just wrote
— carrying exactly one verdict in the record. Whether a paragraph *is* a claim
is never checked.

**No number is authored and no edge is.** Every entry's rigor is the pending
literal, and dependency attribution runs afterward from :mod:`depends`.
"""

from dataclasses import replace
from pathlib import Path

from .. import kb_pipeline
from ..kb_pipeline import LeafEntry, LeafOutcome, NodePassRecord, PlannedClaim, ReadState
from . import conform, gate, graph, identify, inventory, prose, tree, write
from .report import FACT, PASS, ClaimGraphError, Finding, Report


class DiscoveryError(ClaimGraphError):
    """A stage of the node pass stopped on a comparison it makes."""


def _plan(found: identify.Identification) -> LeafEntry:
    """One leaf's outcome as the record holds it, ahead of any KB write."""
    if found.claims:
        outcome = LeafOutcome.MINTED
    elif found.unanchored:
        outcome = LeafOutcome.UNANCHORED
    elif found.no_claim is not None:
        outcome = LeafOutcome.NO_CLAIM
    else:
        outcome = LeafOutcome.MINTED
    return LeafEntry(
        state=ReadState.PLANNED,
        outcome=outcome,
        reason=found.no_claim,
        claims=tuple(PlannedClaim(title=claim.title, locator=claim.excerpt) for claim in found.claims),
        verdicts=found.verdicts,
    )


def _unjudged(record: NodePassRecord, documents: tree.Tree) -> list[str]:
    """I4 over the tree the run just wrote: each leaf's obligated paragraphs against its recorded verdicts."""
    sites = inventory.scan(documents)
    wrong: list[str] = []
    for path, entry in sorted(record.leaves.items()):
        owed = {
            paragraph.start for paragraph in prose.obligated(prose.readable(documents.documents[path], sites), sites)
        }
        judged = [verdict.line for verdict in entry.verdicts]
        if sorted(judged) != sorted(owed):
            wrong.append(
                f"{path}: paragraphs owed a verdict begin on lines {sorted(line + 1 for line in owed)}, and the "
                f"record judges lines {sorted(line + 1 for line in judged)}"
            )
    return wrong


def build(*, kb_root: Path, repo_root: Path, scratch: Path, identifier: identify.Identifier) -> Report:
    """Carry every leaf the record holds to landed. The record and the tree are the inputs."""
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

        asked = minted = 0
        unanchored: list[str] = []
        for path in sorted(record.leaves):
            entry = record.leaves[path]
            if entry.state is ReadState.LANDED:
                continue
            document = documents.documents[path]
            if entry.state is ReadState.UNREAD:
                reading = identify.reading_of(document, sites)
                if not reading.render.sentences:
                    entry = LeafEntry(state=ReadState.PLANNED, outcome=LeafOutcome.NOTHING_TO_READ)
                else:
                    found = identify.infer_claims(reading, identifier)
                    asked += 1
                    report.findings.append(Finding(FACT, "stage-C-inference-cost", f"{path}: {found.telemetry.line()}"))
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
                no_claim=entry.reason if entry.outcome is LeafOutcome.NO_CLAIM else None,
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
            if entry.outcome is LeafOutcome.UNANCHORED:
                unanchored.append(path)

        if unanchored:
            report.findings.append(
                Finding(
                    FACT,
                    "stage-C-unanchored",
                    f"{len(unanchored)} leaf/leaves end this run with no claim minted after identification named "
                    f"results in them: {unanchored}. The record says so and the KB is unchanged for them; read "
                    f"the captures before treating this tree as complete",
                )
            )

        wrong = _unjudged(record, tree.read(kb_root))
        if wrong:
            raise DiscoveryError(
                "verdict-coverage",
                f"{len(wrong)} leaf/leaves do not carry exactly one verdict per paragraph owed one: {wrong[:5]}",
            )
        report.findings.append(
            Finding(
                PASS,
                "stage-C-identify",
                f"{minted} claims minted across {len(record.leaves)} leaves, {asked} of them asked this run; every "
                f"leaf landed and every paragraph owed a verdict carries one",
            )
        )
    except ClaimGraphError as error:
        report.findings.append(error.finding())
        return report

    report.findings += gate.run(repo_root)
    return report
