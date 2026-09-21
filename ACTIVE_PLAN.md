# CLAIM_GRAPH_LEGIBILITY_PLAN.md — the sheet can be read; this is what it still gets wrong

**Paths** are repository-root-relative. The renderer lives at `kb_tools/kb_graph/`.

**Seat.** **PC** python-coder. Nothing here is a contract-doc change unless a row says so.

**Bold marks a decision the row itself must make and record.** It is not emphasis.

**What travels with a dispatched row**: this header, the Standing rules, the Where the
sheet is section, the row, and the rows it is blocked on. The Order section does not
travel.

## What produced this

The plan this replaces was a width-reduction burndown. Its rows are done and its subject
is closed: `references` left the layered sheet, network simplex replaced longest-path,
and the transitive reduction of the drawn premise set landed. What it graded on no longer
exists — it required a layer-0 box count in every row's evidence, and `measure-sheet` has
since dropped that column because a layer is a ring index under the concentric placer and
`y == 0` is the bedrock row only under a linear one.

**The change that mattered was not a layout lever.** The sheet drew 851 of 949 strokes as
`references`; removing them took crossings from 64,907 to 94 and the file from 8.6 MB to
148 KB. Every width lever the old plan ranked was rearranging the 10% of strokes that are
the argument.

**The instrument changed too, and that is why this plan reads differently.** Nothing in
the toolchain could look at a sheet until rasterisation arrived. Every legibility number
taken before that has since disagreed with a human reading of the same picture — a 690×
crossing reduction that still read as illegible, a coordinate method whose figures moved
while the picture did not. **Measurement here is reliable for content questions — what is
drawn, how much, of what kind, whether a stroke passes through a box it does not end on —
and has been unreliable for "can a person read this."** Rows below grade legibility by
rendering and looking, and reserve figures for the content questions.

## Where the sheet is

Geometry constants are in `style.py` and are not transcribed here; read them there.
`LABEL_CHARS` × `TITLE_LINES` is the width lever and is settled — it is the narrowest
setting with no label collision on any measured corpus, and its curve is recorded at the
constant.

**Arrangement is selectable.** `layout.PLACEMENT_ENV` (`KB_GRAPH_PLACEMENT`) chooses
between `linear`, `ring-rectangle` and `ring-ellipse`; `layout.DEFAULT_PLACEMENT` is the
shipped default. Layering and in-layer ordering are shared — only where an occupant stands
differs. This is a development control and is not a consumer-facing surface.

**A hop is a jump.** The hopping stroke is emitted open between the arc's feet; the crossed
stroke runs through unbroken. A hop whose gap would not leave drawn stroke on both sides
within its own run is not drawn at all, because a stub with no glyph reads as a stroke
stopping in mid-air. The census states how many crossings carry a glyph so the suppression
is never silent.

Figures a row cites come from `measure-sheet` (`kb-testing/justfile`), which imports
nothing from `kb_tools`. Note `hop_glyphs` counts *drawn glyphs*, not geometric crossings —
the geometric count is not derivable from a document whose strokes carry no node identity,
and the instrument says so rather than approximating it.

## Standing rules — on every row, not restated per row

1. **Geometry is a pure function of the graph, never of record order.**
   `test_shuffling_the_loaded_records_changes_no_geometry` passes, and it is not
   "byte-identical across runs" — a sweep iterating a dict built in record order also
   passes that. Every tie is broken by a stated rule, never by a container's iteration.
2. **Layout lives in `layout.py` and nowhere else.** A swap, a barycentre or a
   try-both-and-keep-the-better found in `model.py`, `style.py`, `svg.py` or `ops.py` is a
   crossed boundary rather than an optimisation. `svg.py` computes no coordinate.
3. **`layout.py` knows no colour, no font, no tag name, no URL.** If it imports `xml`, the
   boundary has been crossed.
4. **Stdlib only.** No third-party runtime dependency, no vendored layout library, no DOT,
   no Graphviz.
5. **The golden is regenerated through `just regenerate-mini-kb-golden`, never hand-edited.**
   A row's evidence names the target, never a bare interpreter invocation.
6. **A row that changes how the sheet looks delivers sheets, not only numbers.** SVG paths,
   because the reader sets their own zoom and the tooltips and hyperlinks are live there
   (`kb_tools/CONVENTIONS.md`). Rasterise to read it yourself and say which crops you read.
   Both arrangements, at least two corpora, before and after.
7. **Figures accompany the command that produced them**, before and after. From
   `measure-sheet`: `viewBox`, `hop_glyphs`, `edge_len`, the widest layer's occupants split
   into boxes and placeholders, and file size. **Strokes drawn through a claim box that is
   not one of their endpoints** is a sixth figure and is layout-neutral — a false edge is
   bad in any arrangement. `measure-sheet` does not report it yet; **L0 is what makes this
   clause satisfiable**, and until it lands a row says the figure is unavailable rather than
   substituting one of its own.
8. **An option under evaluation is rendered at every value under test, not at the one
   expected to win.** The comparison is the deliverable. Where the pictures separate the
   options, land the winner and say what separated them; where they do not, keep the
   current value and say the evidence did not separate them.
9. **An accepted approximation records the condition that makes it acceptable.** The arc
   feet sitting off the drawn cubic was accepted and documented as accepted — with no note
   that what made it invisible was the stroke running continuous underneath. Gapping the
   stroke removed that condition and turned it into a visible defect nothing flagged.
10. **The method, its parameters, its round cap and its convergence condition are recorded
    in `layout.py`'s own docstring**, not here.
11. `just test` green at handoff, and `integration-test` (`kb-testing/justfile`) too when a
    row touches the instrument. Scratch under `.claude-temp/`. Never `/tmp`.
    `kb-testing/test-data/transient/` is read-only — render a copy.

## Rows

| Row | What | Blocked on | Done when |
|---|---|---|---|
| **L0** | **`measure-sheet` gains a `through_box` column** — strokes drawn through a claim box that is not one of their endpoints. Standing rule 7 already calls this the figure that matters and no instrument produces it, so every ring comparison run so far is missing the column that would settle it. It is readable straight off the document from box rectangles and edge path vertices, so it meets `kb_tools/CONVENTIONS.md`'s own test and imports nothing from `kb_tools`. Note a stroke is now emitted open across its hop gaps: the pieces of one `path` element are one stroke, and a gap is not an exit from a box | — | The column reports on every sheet in both arrangements; a hand-built sheet with a known count verifies it; every other figure unmoved |
| **L1** | **Linear is the shipped default again; rings stay reachable for R&D.** `layout.DEFAULT_PLACEMENT` back to `linear`. Nothing else about the concentric placer changes — it keeps its forms, its constant and its tests, and stays selectable through `KB_GRAPH_PLACEMENT`. **`SPEC.md` is the larger half of this row, not a footnote to it**: it currently opens the sheet's description with the concentric arrangement as a consumer-facing outcome, and carries a paragraph conceding that a stroke may cross a claim box that is neither of its ends — a loss the linear arrangement does not have, since every stroke there runs between adjacent layers through a placeholder holding a space of its own. Both go back. The census clause stating how many crossings carry a glyph stays: it is true of any arrangement. `ARCHITECTURE.md`'s statement of the default follows | — | Default renders linear; each of the three names still renders its own arrangement; `SPEC.md` describes the arrangement that ships and concedes no loss the shipped arrangement does not have |
| **L2** | **Vertical spacing sweep.** `style.LAYER_GAP` is 44px between one row's boxes and the next, and every stroke travelling between two layers fans through that band — on a rendered sheet it carries six or seven near-parallel strokes with hop glyphs wedged among them. Sweep it upward. Height is the axis these sheets have slack on; width is the scarce one and this does not touch it | L1 | Sheets at every value tried, per rule 8. Whether the inter-layer band separates its strokes is judged by looking. `edge_len` and `viewBox` reported because they move; `hop_glyphs` because a wider band may admit glyphs the suppression rule was refusing |
| **L3** | **Ordering objective becomes per-arrangement.** In-layer ordering is barycentre + transpose, minimising crossings, and the ring placer wraps that order around a perimeter — so once the order turns a corner, adjacent-in-order stops meaning adjacent-in-space and a short edge becomes a diameter. On the same 43-node graph, `edge_len` is 12144 linear against 35552 ring-rectangle. **Make the objective a property of the arrangement** rather than of the module: `_exchange_gain` is already the one function the transpose loop asks "does swapping this adjacent pair improve things", and `_Placement` is already the per-arrangement policy object. **Median edge length, not mean** — a few unavoidable long edges must not drag the objective. **Measure the index-space approximation first**: scoring in placed coordinates makes ordering depend on placement, which consumes ordering, and resolving that needs a bounded order-place-rescore loop. If approximating length by index distance gets most of the gain, the loop is not bought | L1 | `edge_len` and the through-a-box count on both ring forms, before and after. Linear must not regress on crossings. Sheets per rule 8. **Records whether the bounded loop was bought and what the cheap version measured** |
| **L4** | **The orphan block.** On `2609.09855v1` the unattached claims are roughly 60% of the sheet's height — four columns of boxes carrying no strokes, and the largest single object on the page. 73 of 156 claims participate in no dependency edge. `style.py` says the block exists so its height reads as how much of the KB is unattached, which is a real job it is doing at a cost nothing has weighed against it. **Decide what it is for and size it to that** | L2 | A rendered sheet where the hierarchy is the dominant object, or a recorded finding that the block's current size is the honest reading and the cost is accepted |

## Out of scope

**Anything that changes what `.index/` records.** The claim graph is never reduced in
service of a rendering limitation — a reference the corpus states is true whether or not a
picture can hold it. Render-only suppression is the renderer's business and is how both the
reference class and the transitive reduction already work; no row here touches
`kb_claimgraph/`.

**A replacement rendering for references** — a tooltip listing, an adjacency matrix, a
second sheet. Its own row when someone wants it. Omission was the change under test and it
measured well.

**Dummy-column pricing** — charging a dummy less than a full `COLUMN_PITCH`. Real headroom,
but it moves width while L2 and L3 are moving other things, and it wants their sheets first.

## Order

**L0 first**, and it is independent of everything else. Standing rule 7 names a figure no
instrument reports, so every row after it is graded with that column blank.

**L1 next** — it is one constant and every other row is graded on sheets whose default
arrangement should already be settled.

**L2 next**, because the owner's reading is that a little more vertical spacing may be
enough for a usable v0.5, and that is the cheapest way to find out.

**L3 and L4 are independent of each other.** L3 is the larger change and the one whose
cheap version should be measured before its expensive version is built.

**L3 decides the ring family's fate; no ring row does.** Rings stay selectable
until a layout that reads well exists. If the per-arrangement ordering objective
makes the linear sheet read well, they go. Having rings was never the goal — a
ring arrangement is worth keeping because it could be strongly communicative for
data shaped to suit it, and nothing has established that this corpus is or is
not that data.

**Retired, kept only so nobody re-proposes them.** Brandes–Köpf coordinate assignment was
implemented, measured and reverted — it widened `ModernCorpPristine` 68%, lengthened its
edges 27% and raised crossings, having been asked to close a spread that measurement showed
was 0px on most sheets. Concentric layout was rejected twice on arithmetic before being
built and measured; built, it costs area and draws far more strokes through claim boxes
than linear, which is structural rather than incidental — on a ring, the space between ring
k and ring k+1 is ring k's own boxes. It survives as an R&D option because the owner wants
to keep exploring it, not because those figures improved.

**`style.RING_STEP` is a closed lever, and only that.** Every candidate position
a ring form offers is the step times its step-1 position, so the step is a
uniform scale and changes no relationship between occupants. That is arithmetic
about the placer and holds for any corpus, which is why sweeping it further is
not worth a run.

**It settles nothing about whether a ring arrangement can read.** Whether
boundaries form depends on how a corpus's layer sizes meet its rings, and no
corpus rendered here was chosen to test that. The ring forms stay selectable.

Two untried levers, neither tested and neither ruled out: **marking the rings**
rather than spacing them, and **bounding a ring's occupancy** so a layer
overflows outward instead of stretching around its own circumference. The second
changes what a ring means and is the larger call. Whether this corpus's layer
sizes leave any gap against ring circumference is arithmetic over the layer
profile, answerable without a render.
