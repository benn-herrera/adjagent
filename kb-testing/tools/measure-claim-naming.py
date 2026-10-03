"""Read-only figures for the two readings of a claim's printed name around a reference.

Invoked through `just measure-kb-roots` (kb-testing/justfile), which hands every
staged kb-root as a leading positional argument. Each kb-root goes through the
build's own narrowing — ``tree.read`` → ``inventory.scan`` → ``graph.read`` →
``attribute.narrow`` with the repository's node-pass record — and nothing else.

Per kb-root, one tab-separated line:

* the narrowing's output: ``depends`` edges it settles, ``references`` it
  records, the candidate pairs it would put to a model and the questions
  (source claims) they make up;
* ``word-dropped``: anchor-level candidates the word before an anchor removed —
  the pairs an anchor would have opened had its preceding word not named a kind
  no premise relation can hold;
* ``named``: hand-named candidates (a claim's printed name and number written
  with no ``\\ref``) the narrowing found beyond the pairs references already
  open or settle, and ``named-raw`` before that subtraction;
* ``named-in-proofs``: hand-named mentions inside proof bodies that join a
  claim, which the narrowing does not scan — reported so the scope is visible.

A field the code under measurement does not carry reads ``-``, so the same
script reports the tree before and after a change. Trailing ``--tag <name>``
labels the run; ``--list`` adds one line per hand-named candidate — where the
mention sits, what it says, and the two claims it joins. Writes nothing.
"""

import sys
from pathlib import Path

from kb_tools import kb_pipeline
from kb_tools.kb_claimgraph import attribute, graph, inventory, tree

try:
    from kb_tools.kb_claimgraph import hand_named
except ImportError:  # the tree before the harvest existed
    hand_named = None


#: One line per hand-named candidate, printed under ``--list``.
LISTING: list[str] = []


def _figures(kb_root: Path) -> dict[str, object]:
    documents = tree.read(kb_root)
    sites = inventory.scan(documents)
    authored = graph.read(documents, sites)
    record = kb_pipeline.read_node_pass(kb_root.parent)
    narrowed = attribute.narrow(documents, authored, sites, record)
    figures: dict[str, object] = {
        "nodes": len(authored.nodes),
        "anchors": len(sites.anchors),
        "depends": len(narrowed.edges),
        "references": len(narrowed.references),
        "candidates": sum(len(question.candidates) for question in narrowed.questions),
        "questions": len(narrowed.questions),
        "word-dropped": len(narrowed.word_dropped) if hasattr(narrowed, "word_dropped") else "-",
        "named": "-",
        "named-raw": "-",
        "named-in-proofs": "-",
    }
    named = getattr(narrowed, "hand_named", None)
    if named is not None:
        for candidate in named:
            LISTING.append(
                f"{kb_root.parent.name}\t{candidate.document}:{candidate.line + 1}\t{candidate.mention}\t"
                f"{authored.nodes[candidate.source].title[:60]}\t->\t{authored.nodes[candidate.target].title[:60]}"
            )
        figures["named"] = len(named)
        figures["named-raw"] = len(hand_named.harvest(documents, authored, sites))
        figures["named-in-proofs"] = _in_proofs(documents, authored, sites)
    return figures


def _in_proofs(documents: tree.Tree, authored: graph.AuthoredGraph, sites: inventory.Inventory) -> int:
    """Hand-written mentions inside proof bodies that join a claim — the scope the harvest leaves out."""
    names = hand_named.claim_names(sites)
    if not names:
        return 0
    vocabulary = hand_named.Vocabulary(names)
    printed = hand_named.printed_claims(authored, sites, vocabulary)
    count = 0
    for block in sites.blocks:
        if block.environment.casefold() != inventory.PROOF_ENVIRONMENT:
            continue
        lines = tree.unquote(tree.strip_markers(documents.documents[block.document].text)).splitlines()
        for _, name, numbers, _ in vocabulary.mentions("\n".join(lines[block.start : block.end])):
            count += sum(1 for number in numbers if printed.get((name, number)))
    return count


def main(argv: list[str]) -> None:
    tag = "-"
    roots = list(argv)
    listing = "--list" in roots
    if listing:
        roots.remove("--list")
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
        label = kb_root.parent.name
        print("\t".join([tag, label, *(str(figures[name]) for name in columns)]))
    if columns is not None:
        print("\t".join([tag, "TOTAL", *(str(totals.get(name, "-")) for name in columns)]))
    if listing:
        print("\n".join(["", "corpus-root\tsite\tmention\tsource\t\ttarget", *LISTING]))


if __name__ == "__main__":
    main(sys.argv[1:])
