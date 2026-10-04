"""Read-only figures for how many one-letter asks a build would make.

Invoked through `just measure-kb-roots` (kb-testing/justfile), which hands every
staged kb-root as a leading positional argument. Each kb-root goes through
``tree.read`` → ``inventory.scan`` → ``graph.read`` → ``attribute.narrow`` with
the repository's node-pass record and the yeses its unmarked record holds
(``unmarked.found``; none where no record stands), and nothing else.

Per kb-root, one tab-separated line.

**Node pass**, over every leaf (a document with no children — the leaves the
declared pass records):

* ``readable``: paragraphs of ``prose.readable``'s render;
* ``obligated``: ``prose.obligated``;
* ``opener``: paragraphs holding a sentence ``identify._opens_a_claim`` passes;
* ``asked``: obligated or opener — one paragraph ask each — and ``asked-leaves``,
  the leaves holding at least one, which are the node pass's ask groups.

**Classification**, over the candidate records ``attribute.narrow`` returns —
one per ``(source, target)``, every harvest reaching one pair merged — each
counted by class and harvest (``ref``, ``named``, ``unmarked``, and ``both`` for
a pair more than one harvest reached). ``unmarked-yeses`` is the pairs the
unmarked record holds answered yes, ``-`` where no record stands.
The class does not travel past the narrowing, so it is read back off the
record: ``eqn`` where the target is a minted equation node; ``proof`` where it
is not and the pair is offered no *in support of* (some provenance sat in a
proof bound to a subject); ``claim`` otherwise.

``sources`` is the distinct source claims (the classify ask groups);
``draft-supported-by`` and ``draft-mention`` count the drafts; ``depends`` and
``references`` are what a build with no reader writes from them
(``classify.records``), after ring demotion over the classified set.

Writes nothing.
"""

import sys
from pathlib import Path

from kb_tools import kb_pipeline
from kb_tools.kb_claimgraph import attribute, classify, graph, identify, inventory, prose, tree, unmarked

CLASSES = ("proof", "eqn", "claim")
HARVESTS = ("ref", "named", "unmarked", "both")


def _node_pass(documents: tree.Tree, sites: inventory.Inventory) -> dict[str, int]:
    figures = dict.fromkeys(("leaves", "readable", "obligated", "opener", "asked", "asked-leaves"), 0)
    for path, document in documents.documents.items():
        if documents.children[path]:
            continue
        figures["leaves"] += 1
        leaf = prose.readable(document, sites)
        fences = [fence for fence in sites.fences if fence.document == path]
        obligated = {paragraph.index for paragraph in prose.obligated(leaf, sites)}
        opener = {sentence.paragraph for sentence in leaf.render.sentences if identify._opens_a_claim(sentence, fences)}
        asked = obligated | opener
        figures["readable"] += len(leaf.render.paragraphs)
        figures["obligated"] += len(obligated)
        figures["opener"] += len(opener)
        figures["asked"] += len(asked)
        figures["asked-leaves"] += bool(asked)
    return figures


def _classify(
    documents: tree.Tree, sites: inventory.Inventory, kb_root: Path
) -> tuple[dict[str, int | str], kb_pipeline.NodePassRecord | None]:
    authored = graph.read(documents, sites)
    record = kb_pipeline.read_node_pass(kb_root.parent)
    unmarked_record = kb_pipeline.read_unmarked(kb_root.parent)
    yeses = () if unmarked_record is None else unmarked.found(unmarked_record)
    candidates = attribute.narrow(documents, authored, sites, record, unmarked=yeses).candidates

    figures = {f"{kind}/{harvest}": 0 for kind in CLASSES for harvest in HARVESTS}
    for candidate in candidates:
        if candidate.target.equation is not None:
            kind = "eqn"
        elif attribute.Relation.IN_SUPPORT_OF not in candidate.offered:
            kind = "proof"
        else:
            kind = "claim"
        harvest = {
            frozenset({attribute.Harvest.REFERENCE}): "ref",
            frozenset({attribute.Harvest.HAND_NAMED}): "named",
            frozenset({attribute.Harvest.UNMARKED}): "unmarked",
        }.get(candidate.harvests, "both")
        figures[f"{kind}/{harvest}"] += 1
    drafts = [candidate.draft for candidate in candidates]
    depends, references, _ = classify.records(candidates, {candidate.pair: candidate.draft for candidate in candidates})
    return {
        "nodes": len(authored.nodes),
        "unmarked-yeses": "-" if unmarked_record is None else len(yeses),
        "candidates": len(candidates),
        **figures,
        "sources": len({candidate.source.id for candidate in candidates}),
        "draft-supported-by": drafts.count(attribute.Relation.SUPPORTED_BY),
        "draft-mention": drafts.count(attribute.Relation.MENTION),
        "depends": len(depends),
        "references": len(references),
    }, record


def _figures(kb_root: Path) -> dict[str, object]:
    documents = tree.read(kb_root)
    sites = inventory.scan(documents)
    classified, record = _classify(documents, sites, kb_root)
    states = (
        "-"
        if record is None
        else ",".join(
            f"{state.value}={sum(entry.state is state for entry in record.leaves.values())}"
            for state in kb_pipeline.ReadState
        )
    )
    return {"record": states, **_node_pass(documents, sites), **classified}


def main(argv: list[str]) -> None:
    tag = "-"
    roots = list(argv)
    if "--tag" in roots:
        at = roots.index("--tag")
        tag = roots[at + 1]
        del roots[at : at + 2]
    columns = None
    totals: dict[str, int] = {}
    for root in roots:
        kb_root = Path(root)
        figures = _figures(kb_root)
        if columns is None:
            columns = list(figures)
            print("\t".join(["tag", "corpus-root", *columns]))
        for name, value in figures.items():
            if isinstance(value, int):
                totals[name] = totals.get(name, 0) + value
        print("\t".join([tag, kb_root.parent.name, *(str(figures[name]) for name in columns)]))
    if columns is not None:
        print("\t".join([tag, "TOTAL", *(str(totals.get(name, "-")) for name in columns)]))


if __name__ == "__main__":
    main(sys.argv[1:])
