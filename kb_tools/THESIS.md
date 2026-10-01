# THESIS - kb_tools

*Why the KB build pipeline has the shape it has.*

---

## The thesis

**A well-structured argument inscribed in LaTeX is not raw text to be mined. It is a tree that
has already been flattened, and distillation is deserialization.**

Dump a program's tree data as JSON and you get a flat file; parse it back and you get the tree. A
LaTeX document set is that flat file. The author built a hierarchy and the format serialized it,
so the hierarchy is present in the bytes rather than latent in the prose.

Two hierarchies are encoded this way, and they are independent.

## The navigation hierarchy

Titles, parts, chapters, sections, subsections. These are hierarchy encodings and nothing else:
each one names a node and its position, and the nesting is the edge set. Breaking them into
documents with children linked under their parents is a transcription, not a judgment.

Mechanical in the testable sense: a second implementation produces the same tree.

## The argument hierarchy

The spine is also mechanically encoded, by two different constructs.

**Nodes** LaTeX environments for theorems, lemmas, definitions, propositions and
displayed equations carry auto-assigned identifiers. A claim that got an environment got an
identity, and that identity is in the file.

**Edges** A reference to one of those identifiers is written in `\ref`-family
syntax, which names the reference target explicitly. A ref can not fully determine an edge mechanically
as it may be a mention, supported by, or in support of the citation. It does indicate an edge
candidate, however.

**For an ideally transcribed paper, that captures all nodes and edge candidates.**

## Why the ideal does not hold

We don't get to choose our inputs, and authors frequently do not transcribe arguments into LaTeX 
exhaustively. Under-marking is the issue refinement via inference resolves.

## What inference is for

**Inference refines a mechanical draft. It never produces one.** Both hierarchies come out of the
mechanical pass first.

**Claim-graph refinement is the half that needs bounding**, and it closes exactly three gaps, all
nameable:

1. A claim constructed in prose without a formal delimiter — real, argued, and carrying no
   environment. (nodes)
2. A reference made in prose without `\ref` syntax — inside either a prose-defined claim or a
   properly delimited one. (additional edge candidates)
3. Edge existence and direction - mention, supported by, in support of (exactly 3 options)

In the final claim graph construction, base claims sit at the bottom, asserted de novo, or resting
on a citation to a work outside this document set. The rest of the edges connect internally, resulting
in a directed graph whose nodes and edges were drafted mechanically and refined by inference.
