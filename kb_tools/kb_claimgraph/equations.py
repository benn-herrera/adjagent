"""The ``equations-minted`` stage: the node set's last mechanical addition.

A referenced equation nothing else holds is minted as an ordinary ``clm-``
node (:mod:`equation` says which, :func:`assemble.equation_entries` arranges
them). It is minted here rather than in the declared pass because **a reference
counts only where the node pass did not judge its paragraph not a claim**
(:func:`prose.standing`): stage D drops such a reference, so an equation it
alone named would be a node nothing points at. Under ``--no-inference`` the node
pass judged nothing, every reference counts, and this stage mints exactly what
the declared pass once did.

Mechanical end to end, and resumable: an equation already minted is skipped,
and each leaf lands through :func:`write.land_leaf`, which completes an
interrupted write rather than repeating it. **It exits on a comparison**: the
equation nodes the tree now holds are exactly the counting set.
"""

from pathlib import Path

from .. import kb_pipeline
from . import assemble, conform, equation, gate, graph, inventory, prose, tree, write
from .report import PASS, ClaimGraphError, Finding, Report


def _counting(
    documents: tree.Tree, sites: inventory.Inventory, record: kb_pipeline.NodePassRecord
) -> list[inventory.Anchor]:
    """Every resolving reference that counts: all of them, less those in prose judged not a claim."""
    readable = {path: prose.readable(document, sites) for path, document in documents.documents.items()}
    return [
        anchor
        for anchor in sites.anchors
        if anchor.target is not None
        and prose.standing(anchor, readable[anchor.document], record.leaves.get(anchor.document))
        is not prose.Standing.NOT_A_CLAIM
    ]


def build(*, kb_root: Path, repo_root: Path, scratch: Path) -> Report:
    """Mint every counting referenced equation not yet minted, then prove the set."""
    report = Report()

    try:
        record = kb_pipeline.read_node_pass(repo_root)
        if record is None:
            raise ClaimGraphError(
                "node-pass-record",
                f"no node-pass record stands at {kb_pipeline.NODE_PASS_RELPATH}; which references count is "
                f"read off its verdicts, and the declared pass is what writes it",
            )
        documents = tree.read(kb_root)
        conform.pass_two_gate(documents)
        sites = inventory.scan(documents)
        authored = graph.read(documents, sites)

        counting = _counting(documents, sites, record)
        wanted = equation.unheld(sites, counting)
        dropped = len({(a.target, a.label) for a in sites.anchors if a.target is not None}) - len(
            {(a.target, a.label) for a in counting}
        )
        pending = [found for found in wanted if authored.equation_node(found.document, found.label) is None]
        entries = assemble.equation_entries(documents, pending)

        hosted: dict[str, set[str]] = {}
        for node in authored.nodes.values():
            hosted.setdefault(node.document, set()).add(node.id)
        by_document: dict[str, list[assemble.Entry]] = {}
        for entry in entries:
            by_document.setdefault(entry.document, []).append(entry)
        for path, found in sorted(by_document.items()):
            ids = write.land_leaf(
                document=path,
                kind=tree.document_kind(path, has_children=bool(documents.children[path])),
                claims=[write.NewClaim(title=entry.title, rationale=entry.rationale, locator=None) for entry in found],
                blocks={},
                elsewhere=frozenset(node_id for other, ids in hosted.items() if other != path for node_id in ids),
                kb_root=kb_root,
                scratch=scratch,
                stem=f"equations-{path.replace('/', '_')}",
            )
            hosted.setdefault(path, set()).update(ids)

        written = tree.read(kb_root)
        minted = {
            (node.document, node.equation)
            for node in graph.read(written, inventory.scan(written)).nodes.values()
            if node.equation is not None
        }
        expected = {(found.document, found.label) for found in wanted}
        if minted != expected:
            raise ClaimGraphError(
                "equation-set",
                f"the equation nodes the tree holds are not the counting set: minted and not counted "
                f"{sorted(minted - expected)[:5]}, counted and not minted {sorted(expected - minted)[:5]}",
            )
        report.findings.append(
            Finding(
                PASS,
                "stage-E-equations",
                f"{len(entries)} equation nodes minted this run, {len(expected)} in all across "
                f"{len({document for document, _ in expected})} documents — the referenced equations no "
                f"claim-bearing block and no proof holds, bounded by the references that count; "
                f"{dropped} referenced label(s) named only from prose judged not a claim count toward none",
            )
        )
    except ClaimGraphError as error:
        report.findings.append(error.finding())
        return report

    report.findings += gate.run(repo_root)
    return report
