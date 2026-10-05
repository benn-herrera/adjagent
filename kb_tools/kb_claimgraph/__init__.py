"""The claim graph: a conforming document tree in, the metadata spine authored into it.

**The tree is the sole input.** No LaTeX, no pandoc AST, no source document, no
bibliography file. Any stage producing a tree that conforms to SPEC.md's
Document-Tree Contract can replace the current front end without this package
noticing, and reaching behind that contract for a fact the tree does not carry
would destroy that property for one build's convenience.

**Four pipelines, and they are separate because inference is the part that
needs repeating.** :mod:`build` is the declared graph — what the author marked
explicitly, mechanical end to end and always correct. :mod:`discover` is the
node pass, minting the claims every leaf's prose states and judging each
paragraph of it that holds a reference; :mod:`equations` mints the referenced
equations the references that still count name; :mod:`depends` attributes the
dependencies between them. Each extends its predecessor's output additively
rather than rebuilding it, and the node set is fixed once :mod:`equations` ends.
A failed or improved inferential pass must not cost the mechanical work.

The stages, in order:

* **A, :mod:`conform`** — the conformance gate. Writes nothing, stops on the
  first failed assertion naming the contract point. Its cleanliness check is
  the declared pass's double-run guard; the node pass's guard is the read state
  the node-pass record holds for each leaf.
* **B, :mod:`inventory`** — the claim-site inventory: labelled blockquotes,
  display-maths fences, cross-reference anchors, rendered citations. A block is
  read by the display name its author gave it, and a name the table classifies
  neither way stops nothing — it is not claim-bearing, and the census reports
  it, so an unfamiliar corpus says what it was read as rather than refusing to
  build.
* **C, :mod:`identify`** — claim identification. The block-hosted half is
  mechanical; the half that reads each leaf's prose (:mod:`prose`) asks
  through :mod:`ask` and is bounded by single occurrence against the document
  itself and by verdict completeness against its obligated paragraphs.
* **D, :mod:`attribute`** — dependency attribution over the graph
  :mod:`graph` reads back. Its narrowing settles an edge wherever containment
  directs one and asks nobody, so that half runs and is recorded even where no
  model is reachable (``--no-inference``); the pairs it leaves open are what is
  asked through :mod:`ask`, bounded by set membership and acyclicity, and what
  a run with nobody to ask leaves open and unrecorded.
* **E, :mod:`assemble`** — arrangement. No new fact enters.
* **F, :mod:`write`** — the write passes, through the write API and nothing
  else.
* **G, :mod:`gate`** — refresh, then the build-time check, in-process. Exits
  on the return codes.

**Every metadata byte goes through the write API.** Nothing here composes a
frontmatter block, a register entry or a marker as text. **No number is authored
anywhere**: every register entry's rigor is the pending literal, and solidity,
bands and roll-ups are refresh's.

The spine this package writes into — the derived-index directory and the runner
include line — is ``graph-init``'s, and a run refuses when it is absent rather
than seeding it.
"""

from .build import build
from .depends import build as build_dependencies
from .discover import build as discover_claims
from .report import Report

__all__ = ["Report", "build", "build_dependencies", "discover_claims"]
