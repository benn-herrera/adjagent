# ROADMAP – kb_tools

Future intent only. Not part of the contract doc set; not handed to coding dispatches.

Items are cited by title, never by number: an item closing renumbers the list.

## Policy direction

Standing constraints on how the items below get decided. These do not
retire; an item that conflicts with one of them is the defect.

- **The lowest tier is the target configuration, not a stress test.** The
  agent set must do full knowledge-base work — dissection and
  exploration/maintenance alike — driven by a bottom-tier model on a
  stock harness. Capability above that floor is headroom, never a
  requirement. A decision that works only on a frontier model has not
  solved the problem.

- **Local compute is a first-class deployment, not a fallback.** Nothing
  in the pipeline may assume network egress, a hosted endpoint, or a
  provider-specific capability.

- **The floor has two names.** The build process targets local inference
  on the **`gemma-4`** family; the shipped agent set targets **`haiku`**
  in the Claude Code context. `just render <slug> --family=gemma-4`
  renders at the `gemma-4` floor, and the tooling suite renders the whole
  set under that family on every `just test`, so "does this survive the
  target tier" is a run and not a reading.

- **No artifact crosses between producer and reviewer.** A knowledge base
  is never an interchange format: it is built locally, from a source
  document, by whoever is reading. This is why no schema-compatibility
  guarantee spans installs, and why the format stays free to change.

- **Per-node only.** Solidity and confidence exist per claim. No
  aggregate, no corpus-level score, no single number that could stand in
  for reading the map.

## Items

1. **Full-vs-incremental refresh** — revisit only if rebuild time becomes
   the constraint. Why `refresh` is always a full rebuild, and what an
   incremental path would cost the freshness gate, is in ARCHITECTURE.md's
   module inventory (`refresh_kb_metadata.py`). Nothing moves until rebuild
   time actually binds.

2. **Pre-split invariants parsing, deprecation.** A KB built before
   `kb-root/invariants.md` split off as the framework-node source still
   parses `### INVARIANT-*` headings and `- Axiom N:` bullets from
   `CLAUDE.md`. `verify_kb_metadata.py` carries a deprecation note for this
   compatibility path, live until the headings move.

3. **Generality corpus — arXiv papers, varied in construction.** The
   instrument has landed: `kb-testing/justfile`'s `ARXIV_IDS` samples by
   category, `prep-test-data-arxiv` and `stage-arxiv-corpus` fetch and stage
   the papers, and `no-inference-kb-driver-arxiv-corpus` drives the sweep.
   What the corpus is *for* is unfinished. Every design decision the pipeline
   carries was taken against a single document, so a sweep only measures the
   process where it is read against the assumptions that document seeded.

   **The one concrete blocker, still open**: `kb_survey.manifest.volume_slug`
   takes `PurePosixPath(source).stem`, discarding the directory before
   slugging. An arXiv sampling is overwhelmingly `main.tex`, so every entry
   slugs to `main`. It fails loudly rather than silently — `_volume_members`
   carries a `runlog.require` guarding "two source volumes share one slug, so
   one survey would overwrite the other" — but it refuses, and the directory
   is the only distinguishing component and is discarded by construction. The
   per-paper sweep never meets it because each paper is its own KB; a corpus
   built as one multi-volume KB does, and the slug scheme changes first.

   The other assumptions this corpus exists to stress: domain attribution by
   first path component, section-sparse documents (the badly-structured-paper
   item below), and `\input` chains — rare in the seven-volume corpus used
   for early development, normal in arXiv.

4. **The badly structured paper — a finer boundary set, not a different
   mechanism.** A monolith with no useful sectioning collapses to one leaf:
   `kb_docgraph.outline` ranks the heading levels the source declares and cuts
   there, and nothing finer is reachable. The two seams reserved for the
   remedy are stubs that always accept — `kb_docgraph.judge.recut` raises
   `NotImplementedError`, and `kb_survey.skeleton.sections_needing_recut`
   returns nothing, "today: none, always."

   **The property to keep wherever the remedy lands: a boundary is picked from
   a set the tool enumerated, and authored by nobody.** That is what full
   transcription traded away — it handled the monolith at the price of
   trusting a model to move bytes faithfully.

   A finer set means paragraph breaks and `\paragraph` heads; the manifest
   schema already admits `paragraph` and `subparagraph` as levels. **What it
   does not have is a reader.** `pandoc.py` is the only one this package keeps
   (CONVENTIONS.md), and a blank line is not a boundary pandoc reports, so the
   source of the finer set is itself an open question rather than a detail.

   **Oversize sections get a mechanical split**, at a sentence break, with the
   pieces titled `(forced-split I/N)` — so a forced boundary is never mistaken
   for an authored one, in the index or in a leaf title derived from it.

   **And the judgment may be rarer than assumed.** Heuristics can take most
   leaf cuts straight from the original authoring, farming out a call only
   where a section falls outside acceptable shape properties. Inference as the
   exception path rather than as the stage is the strongest form of this
   design, and may be cheaper than the current one on a well-structured
   corpus.

   **If it injects levels, it owes the injected nodes a summary.** A node the
   author never wrote has no carved text to carry, so the stage that breaks up
   a wall of text also synthesizes navigation prose for what it created. That
   authoring runs as write / review / repair in one pass, with a
   subject-matter expert on both ends — selection automatic, or declared,
   something like `--discipline=[math|engineering|general]`; undecided. Not
   demo work.

5. **Inline-drawn figures survive the document-graph build — a source
   pre-pass.**

   Pandoc's LaTeX reader **discards `tikzpicture` at parse time**: not as a
   `RawBlock`, not as a `Div`, absent from the AST entirely, with or without
   `\usepackage{tikz}`, at exit 0 with no warning. A genuinely unknown
   environment becomes a `Div` classed with its own name; this one pandoc
   recognises and deliberately drops.

   Two consequences make this a real item rather than polish. **No downstream
   rule can recover it** — content the reader discarded is not in the AST for
   anything to select. And **the partition check cannot see the loss**: its
   reference is that same AST, so a drop upstream of it is missing from both
   sides of the comparison and reads as clean. A build over a figure-heavy
   manuscript loses every drawing and reports success. SPEC.md's Document-Tree
   Contract states both halves — point 8 the hole, point 11 the target it is
   not yet enforcing.

   The mechanism is therefore a **pre-pass over source text**, before pandoc
   parses — the same moment as `convert.strip_environment_declarations`, for
   the same reason. It rewrites drawing environments into a form pandoc
   preserves; only then can point 11's fenced-source treatment apply. What it
   keys on is the open question, and a name list is the wrong shape:
   `tikzpicture` and `circuitikz` are both known members, and a rule keyed to
   the first silently drops the second.

   Needs a corpus that contains figures; the tracked fixtures have none.

   **Tabled deliberately**: soluble but messy, and it is not the thing that
   needs proving. The claim graph built from text is — the document tree
   exists to be its sole input, and figures bear on neither.

6. **Point 7 promises what nothing checks.** SPEC.md's Document-Tree Contract
   point 7 says every internal link resolves and every rewritten anchor lands
   on the node that held its label, and it now states the rendered anchor form
   as part of the contract. Nothing checks that form. `kb_links.LINK_RE`
   matches `[text](target)` and nothing else, while a cross-reference renders
   as `<a href="…" data-reference-type="ref|eqref">` — so `verify_md_links`
   covers the Markdown-link half and the whole class point 7 is *about* goes
   unchecked on every build. They resolved when hand-verified once; nothing
   would report it if they stopped.

   This blocks nothing. It is the difference between a contract that holds
   because it is checked and one that holds because nobody has broken it yet.

7. **One source per rating ladder, read by every consumer.** Two ladders are
   hand-copied today, and neither is pinned. `kb_schema.BUILD_BAND_LADDER` —
   five thresholds over computed solidity, with the status phrases a reader
   acts on — is transcribed as a markdown table in `[chunks.kb-solidity]` in
   `templates/shared-chunks.toml`, thresholds and phrases both. That chunk is
   the one statement every seat that explains a score expands, so a drift
   reaches all of them at once. The rigor grades — seven discrete values a
   person assigns to a derivation — exist **only** as prose, in
   `[chunks.rigor-scale]`, with no code-side definition at all:
   `values.check_rigor` accepts any number in `[0, 1]`.

   **The duplication stands for the prototype and a test carries the alarm —
   and that test does not exist yet.** It asserts that the two statements of
   the band ladder are identical, `[chunks.kb-solidity]`'s table against
   `kb_schema.BUILD_BAND_LADDER`, thresholds and phrases both. It is not
   single-sourcing and does not pretend to be; it converts silent drift into a
   failing test, which is the property that is actually missing.

   **Why pinning rather than single-sourcing.** True single-sourcing needs one
   side to read the other, and neither direction is affordable. `kb_tools`
   cannot read `shared-chunks.toml`: `gen-defs.py` is project space and never
   installs, so an installed `kb_tools` would import something absent. The
   inverse is architecturally sound — a generator may read its inputs — but
   `gen-defs.py` is stdlib-only and renders the whole definition set, most of
   it unrelated to this toolchain; importing a shipped package to render it
   would make the agent set's build depend on this one importing cleanly,
   which is the coupling the surface boundary exists to keep out.
   `shared-chunks.toml` already handles unreachable-by-chunk duplication with
   a maintainer comment saying *check by hand*; where the other side is a
   constant rather than prose, a test is strictly stronger than the comment
   and costs little more. Templates own the text; code asserts agreement.

   **Not a consumer of this ladder:** `applied-mathematician`. That seat
   judges argument strength for any formal system, kb or not, so a grade scale
   is its own to own. The two aligning is fortunate rather than structural,
   and if they ever diverge the kb-side dispatch tells the mathematician to
   use the kb ladder instead of its own.

   **Open, and decide it first: one ladder or two.** They share a range and
   are different quantities. Rigor's `0.9` means *derived end-to-end* — how
   the argument was made. A band's `0.85–1.00` means *ok to build on* — what
   to do with the result. A claim with no dependencies has solidity equal to
   its rigor, which is why they look mergeable; merging picks one vocabulary
   and loses the other.

   **Not gating.** `[chunks.rigor-scale]` stays as it is, with its one
   consumer, as the seam this builds on.

8. **A re-launch over a finished build still exits 0 rather than stopping
   loudly.** The destructive half of this item has landed: there is no
   build-mode setting, an invocation that finds `start` unrecorded is opening
   a build, and `pre.kb-root` refuses one over a populated `kb-root/`. What is
   left is the case an empty ledger cannot describe — a build whose ledger is
   *complete*, re-launched. `Runner.run` skips every recorded stage and
   returns `EXIT_OK`, which is right for a repeat invocation and wrong for
   someone who meant to rebuild. Nothing records whether a KB has gained
   hand-authored leaves since its build — SPEC.md makes that a per-leaf origin
   rather than a state the tree carries — so the driver cannot tell a safe
   rebuild from a destructive one, and refusing while naming an explicit
   override is the only honest answer.

9. **One-hop cross-volume links.** A multi-volume corpus cites its own
   siblings by citation key. Today that reaches the KB as author-year prose
   where a bibliography resolves it and as nothing where one does not, so a
   reader resolving "Part 2" goes key → `references.md` → author-year entry →
   title → match a volume title by eye. The standing quality eval measured the
   consequence on the mechanical baseline: **zero cross-domain links
   anywhere** in a mutually-citing corpus, with that textual route recorded as
   the only path that works.

   **The key is enough, and it costs no bibliography.**
   `authored_blocks.lua`'s `Cite` handler carries every `citation.id` through
   to the `data-cites` span whether the corpus ships a `.bib`, a `.bbl`, or
   neither. So recognition is available on exactly the corpora where a
   bibliography is least likely to be — the arXiv population the generality
   corpus samples.

   **Which keys name sibling volumes is a corpus declaration, not a toolchain
   guess** — the same posture as the claim-bearing environment vocabulary and
   the label-prefix taxonomy. A `.bib`'s `title` field makes auto-detection
   possible as a convenience; a `.bbl` degrades it to a substring match
   against formatted prose; neither is required where the corpus states which
   keys are its own.

   What it delivers is better than what a resolving bibliography gives today:
   a direct link to the cited volume in place of a hop a reader performs by
   hand. The **external** half of the same split has already landed, as the
   off-graph `work-` endcap; this item is the **internal** half.

10. **Recover a bibliography from biblatex's `.bbl`.** arXiv guarantees a
    paper carries one of the two forms — submission is blocked when the `.bbl`
    is absent and a needed `.bib` is missing — but the two `.bbl` flavours are
    not the same artifact. **bibtex** emits `\begin{thebibliography}` with
    `\bibitem` entries: plain LaTeX, which pandoc renders wherever the source
    `\input`s it and `authored_blocks.lua` classifies as apparatus.
    **biblatex** emits its own internal format — `\entry{key}{type}{}` blocks
    of `\field{name}{value}` pairs — which nothing but biblatex renders, so
    splicing it produces macro soup rather than a reference list. Neither
    flavour is scraped today, and bibliography discovery is `.bib`-only
    (`run.BIBLIOGRAPHY_SUFFIX`).

    **The recovery is easier than the case that already works, not harder.** A
    biblatex `.bbl` is *more* machine-readable than bibtex's:
    `\field{title}{…}` is an explicit field where bibtex's output is prose
    already formatted to a style. A scraper collecting `\entry` / `\field`
    pairs reconstructs either a `.bib` or a plain `thebibliography` for the
    same string substitution. Names are the fiddly part — nested, with hashes
    and initials — but title and year, which is what the cross-volume-link
    item needs, are flat.

    **Deferred rather than dismissed, for one reason:** that format
    description has not been checked against real biblatex output.
    `kb-testing/test-data/fixtures/arxiv-survey.py` now classifies a sampled
    tarball's flavour by regex, which establishes the population but reads no
    field, so the cheapest possible confirmation is available and unspent.

    Until then a biblatex `.bbl` degrades rather than fails: the citation
    filter carries the keys and no reference list is produced — which SPEC.md
    point 10 already admits, a volume the processor emits no reference list
    for getting no such document. Note the population skews old: since
    November 2025 arXiv processes `.bib` files itself, so recent submissions
    increasingly carry the form that needs none of this.

11. **Stage rewind as a first-class driver operation**
    (`--resume-from-phase <name>`). The build is resumable after an
    *interruption* — pick up at the first unrecorded stage — but there is no
    way to say "that stage's output is wrong, I have fixed the cause, run it
    again." Clearing one means rebuilding from scratch or rewinding the ledger
    by hand.

    Git already supplies the mechanism: the ledger *is* one commit per stage,
    so `reset --hard` un-records a stage and reverts its tracked output
    atomically. Because a rewind is contiguous from HEAD it cannot leave a
    stage recorded whose predecessor is not — the downstream invalidation the
    ledger's ordering does not otherwise model becomes unrepresentable rather
    than handled. What is missing is the safe front end.

    - **Correlate stages to commits by tag, not by parsing the commit
      message.** The driver writes `kb-build: <stage> | <title>`; parsing it
      back makes a human-facing message into a machine format, and a reword
      then breaks the rewind silently. A tag written in the same operation
      (`kb-build/<stage>`) is a machine reference that declares itself.
    - **The untracked half is the real work, and it is a schema question.**
      `git reset` covers what is committed; the operation is only correct if
      it also clears each rewound stage's scratch, and nothing declares that
      today. A `scratch=` field on the `Stage` rows in `kb_pipeline.STAGES`
      makes the rewind complete by construction rather than by recall, and
      makes "what does this stage keep outside its commit" an answerable
      question.
    - Guards: refuse on a dirty worktree, and refuse a stage that is not
      recorded.

    **The stronger reason for that field is not rewind.** Control-flow state
    lives in a directory whose entire contract is that it can be deleted: the
    repository concurrency lock is anchored by `runlog.repo_lock_path` inside
    `.claude-temp/` — the directory a routine restage wipes — so a restage
    landing mid-run removes the lock and a second driver can start against the
    same repository and ledger. That instance turned up in an unrelated
    investigation rather than by looking for the class, and nothing in the
    system can report how many more there are. The rule worth landing with the
    field: **state that decides control flow either goes in the commit or is
    declared.** Scratch that survives a reset is scratch that can lie about
    what has already happened.

    Until it exists the manual path is two steps, and the second is the one
    that gets forgotten: `git reset --hard <stage-commit>^`, then remove that
    stage's scratch by hand.

12. **A definition is a node, and a claim that uses a defined term is a
    candidate for depending on it.** Two halves of one defect, and they land
    together or not at all. Measured on `2609.09855v1`: stage D-inf names a
    definition as the antecedent for at least **9** orphaned claims — *"derives
    from one thing only: the definition of calibration … which is not a"*
    candidate — and there is no node for that answer to be. Separately, **15 of
    129** claims reach `narrow` with an empty candidate set and are therefore
    never asked about at all.

    **The node half needs no new kind, no new prefix and no new id grammar.** A
    definition *is* what a framework node already models: bedrock, solidity 1.0
    by construction, terminal, carrying no scoring fields.
    `kb_index_lib.parse_framework_nodes` mints them today from `invariants.md`'s
    `### INVARIANT-XX` headings and `- Axiom N:` bullets; it gains a third
    source, the `definition` blocks `kb_claimgraph.inventory` already
    classifies in the tree. SPEC.md's out-of-scope note concerns AVE-KB's
    `def-`/`ilk-` **vocabulary import** and states its own admission condition
    — *"added only against a demonstrated need arising in a corpus this
    toolchain serves"* — which the 9 orphans are. Minting an existing kind from
    a new source is not the import SPEC declined. Two existing rules move with
    it: `inventory.NOT_CLAIM_BEARING` classifies `definition`, and the
    `NOT_A_CLAIM_TARGET` derived from it ends a reference naming a definition
    block with no pair at all.

    **Answer the terminal objection in place**: SPEC says a definition node
    *"carries no scoring fields and emits no edges — so it contributes nothing
    to either graph."* True of emitting, irrelevant to receiving. `work-` is
    already terminal and receive-only, and exists precisely to be pointed at.

    **The candidate half is scoped by region, which is the whole discriminator
    and is why it is not a proximity heuristic.** A claim resting on a
    definition carries no `\ref` to it, because definitions are not labelled the
    way claims are. The rule: a claim whose **statement block** uses a defined
    term becomes a candidate for depending on it. A theorem statement is terse —
    authors do not pad a proposition with decorative vocabulary, so every term
    in one is load-bearing — where the same word scattered through surrounding
    prose carries no signal at all: searching a paper *about* calibration for
    "calibration" finds it everywhere and discriminates nothing. Scope the match
    to the claim's own statement block and nothing else. A second discriminator
    comes free and needs no constant: a term appearing in most claim statements
    is a topic word, one appearing in three of forty is a dependency signal, so
    rarity *within this corpus's claim statements* weights the match.

    **Out of scope**: matching on any word of a definition's body; matching
    outside the claim statement; any proximity or same-document rule; and any
    rule that authors a `depends` edge directly. A match produces a
    **candidate**, never an edge — it feeds `attribute.narrow`'s existing
    settle-or-ask path, and `_source_end`'s rule is not relaxed. **The node half
    alone is worthless** and makes the orphan picture worse, adding nodes
    nothing points at.

    **Separately, in the same stage: `depends.tmpl` and
    `depends-cycle-reask.tmpl` duplicate their body, and nothing checks that
    they agree.** An edit one needs is an edit the other will not get.

    **Also in the same stage: the dependency ask hands the seat its evidence
    passages unlabelled** (`ask.py`, the reference-lines slot). They are sorted
    and deduplicated, so nothing says which candidate a passage bears on and
    position carries no answer; the seat can only recover the pairing by finding
    the anchor inside the prose. Keying each passage to its candidates would
    make it readable.
