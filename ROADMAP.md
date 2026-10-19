# ROADMAP – Adjagent

Future intent only. Not part of the contract doc set; not handed to coding dispatches.

**See also**, for work scoped to a shipped package: `liaison_tools/ROADMAP.md`.

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

    **A command's prompt is a union, and no file-unit instrument sees it.** Four of the seven
    command definitions open with `@`-loads: `/mad-review` assembles a command body plus
    three full definitions, `/guest-start` a command body plus the liaison. Roughly half the
    intra-prompt findings live only in that union — invisible to any per-file tool and to reading
    either file alone. Two are outright **conflicts** rather than duplication: the command telling a
    referee the charter `MUST` be passed verbatim to every seat where the clause beside it forbids
    pasting the charter inline, and the guest commands telling the session to decide
    resume-versus-new by inspecting `messages.json` where the liaison says to decide it with
    `validate` and never by inspecting the file.

   **Sections meant to stay in sync are held in sync by nobody.** A section that is the same
   across a family is a run of clauses each definition lists in its own body, so the run drifts:
   go and rust carry no coverage rule by design, and nothing distinguishes a deliberate omission
   from a forgotten one. The 1.0 shape makes the run visible in each body and `render-diff` shows
   a repair exactly; what it does not do is name which omissions are deliberate. First: enumerate
   every deviation across the coders and platform experts and classify it.

3. **Re-examine the MAD agent set against what the harness now does.** That design predates several
   harness capabilities and may be replicating orchestration the harness performs more reliably.

   Decide whether the agent set and process actually earns its keep any more. MAD process usage
   has fallen off sharply in general practice due to increasing capability of frontier models.

   **Explore at the start of the next MAD process rather than as standalone work** — the protocol is
   best examined against a live run.

   **Two invariants constrain any change, and neither is negotiable**: participants are deliberately
   isolated from one another, seeing only the alignment assessor's structured map and never another
   participant's output; and the run leaves an audit trail.

   Agent-to-agent messaging is **not** the opportunity here — it is the thing the isolation exists
   to prevent, and it is newly possible, so the design may now need to forbid explicitly what it
   previously achieved by the absence of a mechanism.

   The two candidates:

   - **Deterministic orchestration.** The referee is an agent running a four-phase protocol with a
     round cap and a retirement gate. Running the loop as a script would make isolation a property
     of the code rather than a behaviour the referee maintains — a script controls exactly what
     reaches each participant's prompt, where an agent must keep choosing not to pass something
     along. The gate is a judgment and stays an agent call inside the loop.
   - **Participant resumption.** An agent can be resumed with its transcript intact. If participants
     are re-dispatched fresh each round, resuming them instead would preserve each one's own
     reasoning across rounds while still showing it only the assessor's map — isolation untouched,
     and each participant becomes one continuous record rather than a chain of contexts.

   **Read first**: Phase 3's round mechanics, and whether participants are currently fresh or
   carried. Both candidates turn on that answer and neither has been checked against the protocol as
   written.

   - **The content pass the 1.0 port deferred.** The port changed no prose; these change what a
     seat reads and each is a `render-diff` the owner reads before `retake-reference`. Unify the two
     debate referees' vocabulary on one set of words (gate, seat, outcome, the run and file names),
     after which their slot constants lose their holes and the two bodies converge. Drop the
     referees' "in Steps … above" cross-reference, which the sentence already names. Give the two
     liaison definitions one spelling of the `liaison_tools` path instead of one per command line.
     The 74 sites where a clause and a definition's own sentence share a paragraph: each a judgment
     whether the sentence is its own paragraph, to be read site by site, not swept.

4. **(KEEP LAST) Definition namespace prefix** (`just install --name-prefix=aa- <project>`):
   installs the agent and command definitions under a prefixed namespace so the set coexists with
   an existing fleet — generic names (`python-coder.md`) are the collision surface; the tool
   packages are self-namespaced and stay bare. Default empty renders today's bytes. Requires a
   render pass substituting every cross-reference site (dispatch names, slash-command names in
   prose, the MAD roster) with a lint against bare fleet names. Nothing outside the definition text
   names an agent, so the rendered prose is the whole substitution set and no runtime route has to
   carry the prefix. The harness agents file (`adjagent/definitions/harness_agents_file.py`) is in
   it, so agent references inside that file — the prompt-engineer review rule, any seat named by
   the working preferences — render with the prefix applied at install.
