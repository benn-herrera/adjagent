"""Dependency attribution: the edges between the claims the graph already holds.

**The passes are separate because inference is the part that needs repeating.**
A failed or improved inferential pass must not cost the mechanical work, and
must be re-runnable against a different model or a better ask without rebuilding
the tree. That is an operational property, and it is why this is a second
entry point over the first's output rather than a branch inside it.

**It runs after claim discovery** (:mod:`discover`), over a graph that by then
includes the claims nobody marked. Nothing here mints a node, and nothing there
authors an edge.

Stages, in order:

* **A′, :mod:`conform`** — the same structural checks the declared pass makes,
  and in place of its cleanliness check the per-document entry condition:
  :func:`conform.pass_two_gate`.
* **B, :mod:`inventory`** — the same scan. The tree gained metadata and no
  prose, so every claim site it found before is where it was.
* **:mod:`graph`** — the authored claim graph, read back off the tree's own
  declarations and registers.
* **D, :mod:`attribute`** — the narrowing: every edge candidate, from a
  reference, a hand-written name, or a pair the unmarked record holds answered
  yes (:func:`unmarked.found`, read and never recomputed), classed and
  drafted, with the drafts that
  lie on a containment ring drafted *mention*. Its harvest completes for the
  whole corpus before the first ask.
* **:mod:`classify`** — one letter ask per candidate, grouped by source, each
  group recorded as it lands; then every ``depends`` edge on a cycle of the
  classified set is cut, and every cut — those and the ring pairs that kept
  their drafted *mention* — lands as a ``demoted`` record carrying its origin
  (:func:`classify.cuts`). Inference reaches it through an
  injected :class:`~.letters.LetterReader`, which is why this pipeline takes a
  reader rather than building one.
* **F′, :func:`write.write_edges`** — pass 3 of the write path, one
  ``add-build-edges`` batch.
* **G, :mod:`gate`** — refresh, then the build-time check, in-process. Exits
  on the return codes.

**Nothing here exits on a model's opinion.** Every stage ends on a comparison
between two artifacts or on a return code; a reply carrying no offered letter
takes the candidate's draft, and only a call that never completes stops it.

**Only the asking is conditional.** ``reader=None`` is a run with no model
reachable, and every stage above still runs: such a run writes every
candidate's draft — *supported by* where containment directed the pair and no
ring refused it, *mention* everywhere else — so no relationship the corpus
states goes unrecorded. The report says which run it was, because a candidate
drafted and one a model answered write the same record.
"""

from pathlib import Path

from .. import kb_pipeline
from . import attribute, classify, conform, gate, graph, inventory, letters, tree, unmarked, write
from .report import FACT, PASS, ClaimGraphError, Finding, Report


def _census_findings(
    state: conform.PassTwoState, authored: graph.AuthoredGraph, sites: inventory.Inventory
) -> list[Finding]:
    return [
        Finding(
            FACT,
            "stage-A-determinations",
            f"{len(state.hosting)} leaves host claims, {len(state.determined)} carry a no-claim reason, "
            f"{len(state.undeclared)} declare neither",
        ),
        Finding(
            FACT,
            "authored-graph",
            f"{len(authored.nodes)} claims across {len(authored.documents())} hosting documents",
        ),
        Finding(
            FACT,
            "stage-D-anchors",
            f"{len(sites.anchors)} cross-reference anchors, "
            f"{sum(1 for a in sites.anchors if a.target is not None)} resolving to a document, "
            f"{sum(1 for a in sites.anchors if (a.hosting_environment or '').casefold() == attribute.PROOF_ENVIRONMENT)}"
            f" sitting inside a proof",
        ),
    ]


def _counts(values: list[str]) -> str:
    """``name n`` per distinct value, sorted, or ``none``."""
    return ", ".join(f"{value} {values.count(value)}" for value in sorted(set(values))) or "none"


def _candidate_findings(narrowed: attribute.Attribution) -> list[Finding]:
    candidates = narrowed.candidates
    return [
        Finding(
            FACT,
            "stage-D-candidates",
            f"{len(candidates)} candidates over {len({c.source.id for c in candidates})} source claims; by harvest: "
            f"{_counts(['+'.join(sorted(c.harvests)) for c in candidates])}; by letters offered: "
            f"{_counts([','.join(c.offered) for c in candidates])}; "
            f"{len(narrowed.own_equations)} pairs dropped as a claim's own equation",
        ),
        Finding(
            FACT,
            "stage-D-drafts",
            f"{_counts([c.draft for c in candidates])}; the drafts containment directed, by the rule that "
            f"resolved the referenced claim: "
            f"{', '.join(f'{route} {count}' for route, count in sorted(narrowed.routes.items())) or 'none'}",
        ),
        Finding(
            FACT,
            "stage-D-word-filtered",
            f"{len(narrowed.word_dropped)} candidate pairs never opened: the word before the anchor names a "
            f"section, a figure or another kind no premise relation can hold, and nothing else reaches them",
        ),
        Finding(
            FACT,
            "stage-D-containment-ring",
            (
                "no pair containment directed lay on a cycle"
                if not narrowed.demoted
                else f"{len(narrowed.demoted)} pairs containment directed lay on a cycle and are drafted mention, "
                f"landing as demoted where they keep that draft: "
                + ", ".join(f"{source} -> {target}" for source, target in narrowed.demoted)
            ),
        ),
    ]


def _classification_findings(classified: classify.Classification, *, asked: bool) -> list[Finding]:
    """What the candidates were classified as, how each answer was reached, and what a cycle cost.

    Every figure is stated in the zero form, and every defaulted candidate and
    every demoted edge is named, a defaulted candidate and a demoted edge being
    indistinguishable from any other record once written.
    """
    outcomes = classified.outcomes
    defaulted = sorted(pair for pair, outcome in outcomes.items() if outcome is kb_pipeline.ClassifyOutcome.DEFAULTED)
    findings = [
        Finding(
            FACT,
            "stage-D-classified",
            f"by relation: {_counts(list(classified.relations.values()))}; by outcome: "
            f"{_counts(list(outcomes.values()))}"
            + ("" if asked else "; no model was asked, so every candidate this run decided took its draft"),
        ),
        Finding(
            FACT,
            "stage-D-defaulted",
            (
                "no candidate defaulted"
                if not defaulted
                else f"{len(defaulted)} candidates carried no offered letter after one re-ask and took their draft: "
                + ", ".join(f"{source} -> {target}" for source, target in defaulted)
            ),
        ),
        Finding(FACT, "stage-D-asks", letters.AskTotals.of(classified.asks).detail()),
    ]
    findings.append(
        Finding(
            PASS,
            "stage-D-classify",
            f"{len(classified.edges)} dependency edges and {len(classified.references)} references, acyclic "
            f"before the write; "
            + (
                "no classified edge lay on a cycle, so none was demoted"
                if not classified.demoted
                else f"{len(classified.demoted)} classified edges lay on a cycle and are recorded as demoted "
                f"instead: " + ", ".join(f"{source} -> {target}" for source, target in classified.demoted)
            ),
        )
    )
    return findings


def build(
    *,
    kb_root: Path,
    repo_root: Path,
    scratch: Path,
    reader: letters.LetterReader | None,
    asks: Path | None = None,
) -> Report:
    """Run the discovered pass's dependency attribution over ``kb_root``.

    ``reader`` is ``None`` for a run with no model reachable: every candidate
    takes its draft. ``asks`` is where each classify group's ask record lands.
    """
    report = Report()

    try:
        record = kb_pipeline.read_node_pass(repo_root)
        if record is None:
            raise ClaimGraphError(
                "node-pass-record",
                f"no node-pass record stands at {kb_pipeline.NODE_PASS_RELPATH}; the source end of a reference "
                f"in prose is read off its verdicts, and the declared pass is what writes it",
            )
        unmarked_record = kb_pipeline.read_unmarked(repo_root)
        yeses = () if unmarked_record is None else unmarked.found(unmarked_record)
        documents = tree.read(kb_root)
        state = conform.pass_two_gate(documents)
        report.findings.append(
            Finding(PASS, "stage-A-conformance", f"{len(documents.documents)} documents conform and admit this pass")
        )

        sites = inventory.scan(documents)
        authored = graph.read(documents, sites)
        report.findings += _census_findings(state, authored, sites)

        narrowed = attribute.narrow(documents, authored, sites, record, unmarked=yeses)
        report.findings += _candidate_findings(narrowed)

        classified = classify.classify(
            narrowed.candidates,
            graph=authored,
            statement=classify.statements(documents, authored, sites),
            reader=reader,
            repo_root=repo_root,
            record_dir=asks,
        )
        report.findings += _classification_findings(classified, asked=reader is not None)

        report.findings += write.write_edges(
            classified.edges,
            kb_root=kb_root,
            scratch=scratch,
            references=classified.references,
            demoted=classify.cuts(narrowed.demoted, classified, yeses),
        )
    except ClaimGraphError as error:
        report.findings.append(error.finding())
        return report

    report.findings += gate.run(repo_root)
    return report
