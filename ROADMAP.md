# ROADMAP – Adjagent

Future intent only. Not part of the contract doc set; not handed to coding dispatches.

## List conventions

- **A finished item leaves nothing.** An item that is done or dropped is deleted outright and the
  list renumbers behind it, so a reference by number is verified against this file rather than
  trusted. A `(KEEP LAST)` item is last in this file, not merely last to execute: a new item is
  appended above it, and the `(KEEP LAST)` entry takes the new highest number.

## Items

1. **(STICKY) Periodic load-bearing-ness pruning pass** over definition clauses, across model
   generations: apply strip-first-observe-patch (README.md, "Variants and platform compatibility")
   on a cadence, using behavioral probe sets as the instrument. Byte-level instruments exist today —
   `just render-diff` between two render slots, and the render-property assertions in
   `tests/test_adjagent.py` (ARCHITECTURE.md, Verification, and Why There Is No Verification Verb);
   behavioral ones do not yet.

2. **One rule arriving several times in one prompt — the duplication class no instrument sees.**
   Distinct from the cross-output duplication the suite's identical-paragraph test refuses: a seat
   is told the same thing twice inside its own definition, through a clause and an inline
   restatement, or through two clauses that both land in it. Single-sourcing does not prevent it —
   a clause guarantees one *definition*, not one *delivery*. **Roughly 60 instances across 24
   files, found by reading; about 22 resolved.** The residue splits by cost: where one statement
   is a clean superset of the other the fix is a deletion, and where neither is, it needs a
   composition ruling per pair — which clause a definition stops carrying.

   **The instrument's limits are measured rather than assumed.** The retired prose sweep found
   exact runs of eight or more shared words across texts (guaranteed at fifteen), whatever the
   sentence boundaries, so a paragraph duplicated verbatim was reported even when its sentences
   were short; the identical-paragraph test that replaced it compares whole paragraphs across
   outputs. Neither sees a rule restated in different words, inside one file or across two: a
   lexical intra-file detector over all 46 templates at a 7-token floor recovered **zero** of the
   findings above, because they are semantic paraphrases — a rule stated once where it is *defined*
   and again where it is *applied*, drifting apart in wording as it goes. Reading finds them; a
   lexical instrument does not. It also refuses the fourth comparative question, one word with two
   meanings, and names what it would need: a glossary binding each project term to the one thing it
   may refer to.

   **A command's prompt can be a union, and no file-unit instrument sees it.** A command body that
   opens with an `@`-load of another definition renders as one prompt: the body plus the loaded
   definition in full. A rule stated in the body and again in the loaded text reaches the model
   twice, and neither a per-file tool nor a reading of either file alone sees the pair. Many of the
   intra-prompt findings above lived only in such a union, in command definitions since retired;
   one of those was an outright **conflict** rather than duplication — the command telling a referee
   the charter `MUST` be passed verbatim to every seat where the clause beside it forbade pasting
   the charter inline. The class retires with nothing: any command that opens with an `@`-load
   recreates it, so the instrument this item asks for has to see the rendered prompt, not the
   source files.

   **Sections meant to stay in sync are held in sync by nobody.** A section that is the same
   across a family is a run of clauses each definition lists in its own body, so the run drifts:
   go and rust carry no coverage rule by design, and nothing distinguishes a deliberate omission
   from a forgotten one. The 1.0 shape makes the run visible in each body and `render-diff` shows
   a repair exactly; what it does not do is name which omissions are deliberate. First: enumerate
   every deviation across the coders and platform experts and classify it.

3. **The content pass the 1.0 port deferred.** The port changed no prose; these change what a
   seat reads and each is a `render-diff` the owner reads before `retake-reference`. Unify the two
   debate referees' vocabulary on one set of words (gate, seat, outcome, the run and file names),
   after which their slot constants lose their holes and the two bodies converge. Drop the
   referees' "in Steps … above" cross-reference, which the sentence already names.
   The 74 sites where a clause and a definition's own sentence share a paragraph: each a judgment
   whether the sentence is its own paragraph, to be read site by site, not swept.

4. **(KEEP LAST) Definition namespace prefix** (`just install --name-prefix=aa- <project>`):
   installs the agent and command definitions under a prefixed namespace so the set coexists with
   an existing fleet — generic names (`python-coder.md`) are the collision surface; the tool
   packages are self-namespaced and stay bare. Default empty renders today's bytes. Requires a
   render pass substituting every cross-reference site (dispatch names, slash-command names in
   prose) with a lint against bare fleet names. Nothing outside the definition text
   names an agent, so the rendered prose is the whole substitution set and no runtime route has to
   carry the prefix. The harness agents file (`adjagent/definitions/harness_agents_file.py`) is in
   it, so agent references inside that file — the prompt-engineer review rule, any seat named by
   the working preferences — render with the prefix applied at install.
