# ROADMAP – Adjagent

Future intent only. Not part of the contract doc set; not handed to coding dispatches.

**See also**, for work scoped to a shipped package: `kb_tools/ROADMAP.md`,
`liaison_tools/ROADMAP.md`.

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
   `tests/test_gen_defs.py` (ARCHITECTURE.md, Verification, and Why There Is No Verification Verb);
   behavioral ones do not yet.

2. **Claude Code release reconciliation.** The generator authors agent definitions and slash
   commands against the harness's definition format and its dispatch behavior, so a release that
   moves either moves this repository's templates with it. The binary moved `2.1.220` → `2.1.272`,
   fifty-two releases. The definition surface was surveyed against the new build; what follows is
   what that established.

    **Verified and requiring no change:**

    - **Tool declaration.** Eight definitions name tools, and between them they name five: `Read`,
      `Grep`, `Glob`, `WebFetch`, `WebSearch`. None was renamed or removed, and a definition naming
      a tool that does not resolve fails to launch rather than degrading — so this surface is safe
      or loudly broken, never quietly wrong. The other definitions omit `tools`, which still means
      inherit.
    - **`model`.** Every rendered value is in the accepted vocabulary (`opus` 23, `sonnet` 11,
      `haiku` 1, `fable` 1). **This is the one behavior that moved under us**: releases
      `.259`–`.261` fixed frontmatter `model:` being ignored in some contexts, so the tier map
      begins taking effect where it may have been inert. The floor and stock tunings are worth
      re-rendering under the new binary for that reason — each is a `just render <slug>` with the
      tuning flags that name it, diffed against a default slot by `just render-diff`.
    - **`omitClaudeMd`** (new at `.271`) — **deliberately not set.** Both the operator baseline and
      the project's own conventions reaching every dispatched seat is the design, and the field's
      only use is to switch that off.

    **Settled as nonexistent. Do not re-open, and do not add either field to a definition:**

    - `type` / `type: custom` — no such key. It entered this item from a model's invention rather
      than from documentation.
    - `stripParentContext` — no such key. Subagents already start without the parent's conversation;
      there is no field governing it.

    **The method that settled them, which is reusable against any future release**: grep the installed binary for the key name *alongside positive controls*. At `2.1.272`, `stripParentContext` returns 0 while `permissionMode` returns 157, `disallowedTools` 59, `maxTurns` 42 and `omitClaudeMd` 15. The controls are what make a zero mean absent rather than unsearchable, and this reads what is actually running rather than what is documented.

    **The one open question: `permissionMode`.** The key exists. What it defaults to when absent is not documented, and `templates/` states it nowhere — so that default is this repository's behavior on every dispatch, unexamined. Settling it wants a behavioral probe rather than a search.

    **Fields available and not used**, each an adopt-or-decline decision rather than a repair: `disallowedTools`, `maxTurns`, `skills`, `memory`, `background`, `effort`, `isolation`, `mcpServers`, `hooks`, `experimental`.

    **Closed by a live-inference walk, not a mechanical one.** The `--no-inference` recipes spend no model call by construction, so they exercise the build pipeline and dispatch nothing — a moved dispatch default passes straight through them. What settles this is `kb-driver-arxiv-corpus` over `ARXIV_LIVE_IDS`, and it was run: both papers reached `claims-discovered` and `depends-attributed`, so seats launch, receive briefs, and return parseable answers under the new build. Re-render and re-install were no-ops, the templates being unchanged.

    **The pins were verified honored, at the output side.** `runs/<id>/<ts>/calls/*.stream.jsonl` carries the model id per session, and a floor-tuned run (every tier tuned for and pinned to haiku) reported `claude-haiku-4-5-20251001` throughout. That is the direct check: the definition states the pin, and the stream says what served the call. Neither `/usage` nor the console log breaks usage down by model, so this is the only instrument for it.

3. **Atomic install** (dry-run-then-live, git-style): the install first runs a full dry pass and
   halts before writing anything if any target would be a collision — where collision = target
   exists, differs from the bytes this run would write, and is not provably this generator's output
   (the differs clause covers the unbannerable `.tmpl` and `.tmpl.md` payload files). Reports all
   collisions at once; only a clean dry pass proceeds to the live run. Doing the work twice is
   trivial against the whole-install runtime. **What is left here is the dry pass alone.** Pruning
   landed outside this item and without its gate: a deployed surface is swept per file against the
   banner, and a shipped package's destination is replaced whole (SPEC.md, Write Safety). Neither
   needs a dry run, so the collision pass is the remainder rather than the prerequisite it was
   written as.

4. **Unified install with owner-safe config integration.** `just install <project>` gains a binary
   flag that runs the agents-file install at *project* scope, inside the atomic dry run.
   `install-agents-file`'s DIR already reaches a project root; what remains is the flag and its
   place in the dry run.

   - README documents the integration target as the *project* `CLAUDE.md` primarily, `~/.claude/`
     optionally.
   - Policy: the target project's `CLAUDE.md` is NEVER touched by default. Config integration
     happens only via the binary flag on `just install`, or via
     `just install-agents-file <harness> <dir>` whose directory target is required and may be `~/.claude`
     or a project root.
   - Atomicity covers config integration: when specified, the agents-file install participates in
     the dry-run pass, and its refusal aborts the entire installation with nothing changed.

5. **Family-skeleton inversion — the kb agent set becomes small-model-followable** The common
   template skeleton becomes the imperative core a small local model can follow — short
   declaratives, one instruction per sentence, explicit sequencing, no conditionals beyond stop
   rules — and the Claude-grade prose (interference armor, nuanced conditionals, long contracts)
   moves into `family/claude.toml`, layered on top: capability-additive, not capability-assumed.
   **Mechanism prerequisite, already landed.** Additive-only stays — it is what keeps the template
   set trackable for maintainers instead of untrackable spaghetti — and overrides stay scoped to a
   family file and kept to a minimum; SPEC's additive-only clause is therefore untouched by this
   entry. The hard-coded rendering form this pass would otherwise have had to remove is already
   gone: family text now renders verbatim in place, with no lead-in and no wrapper, so a family file
   can restore a passage of contract prose exactly as readily as it can add a corrective note — an
   author wanting a `**NB**: ` lead writes one into their own text. Anchor placement was never
   order-dependent either: an anchor expands wherever it sits, so this pass's content work starts
   unblocked. Note the starting position: of the nine kb templates, eight hold **zero** overlay
   anchors today — the ninth, `kb-claim-scorer.tmpl.md`, carries `family.gap-aversion`, the other of
   the two anchors that exist across the entire template tree (`family.ask-vs-stipulate` in
   `applied-mathematician.tmpl.md` is the first) — so this pass authors the seams for the remaining
   eight as well as the text. The provenance doctrine is not in conflict here (owner-ruled
   2026-09-04): strip-first-observe-patch is satisfied, because these anchors answer observed
   failures from the stall catalog rather than speculation. What the hard rule failed to anticipate
   is a second legitimate motivation — holding extra content a capable family can use, to improve
   functionality, as distinct from correcting a failure. Provenance discipline itself stands
   unchanged: every entry still records the behavior, the model, and the date that motivated it. The
   render/install report is in scope too: it names each filled anchor and its scope but never which
   definitions received it, and its per-tier `stock` notice reads as contradicting the anchor list
   printed beside it. Evidence base: the 2026-09-03 paired-run stall catalog — gemma-4-31B ignored
   the long system-prompt contract but followed a short absolute one perfectly (the BANANA probe:
   the cheap instruction-following differential, seconds per hypothesis); stalled waiting at the
   confirmation barrier; then narrated "I will now continue" and ended its turn instead of acting.
   Each failure class names skeleton text needing demotion to a claude-chunk. The binding principle
   (owner): **the imperative core must stay sufficient, not just simple** — the week's mechanization
   is what makes this winnable, since format/exhaustiveness direction left the prose for tools and
   only judgment direction remains; where prose sufficiency still runs out for a seat, the answer is
   relay-pattern decomposition (code owns the loop, the model gets one bounded question), not more
   prose. Input: the gemma failure catalog mined via the resume path from the current paired runs.

6. **Multi-harness portability** - the `hrn.` namespace and the per-harness files
   (`templates/harness/<name>.toml`) have landed. What remains is moving CLAUDE.md to AGENTS.md in
   all projects and subprojects, with a redirect CLAUDE.md (just has `@AGENTS.md`, which is the
   Anthropic-specified technique).

7. **(LOW) A shipped package's contract docs stay out of the install.** Each shipped package now
   carries the full four-document set — `SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`,
   `ROADMAP.md`. The install copies a package recursively minus `INSTALL_EXCLUDED_DIRS` / `_NAMES` /
   `_SUFFIX`, so all four land in a consumer's `.claude/agents/<package>/`. `CONVENTIONS.md`
   shipping is correct — it is the package's operating contract, and a session working in an
   installed tree is exactly its reader. `ROADMAP.md` shipping is not: this repository's own roadmap
   is project space, deliberately outside the precedence chain and never handed to a coding
   dispatch, and a package's copy has no better claim on a consumer's session context. `SPEC.md` and
   `ARCHITECTURE.md` are the undecided middle — an installed consumer reading a package's observable
   contract is defensible; reading its internal mechanism is closer to the generator internals the
   surface boundary already keeps out. Smallest fix is a name in `INSTALL_EXCLUDED_NAMES`.
   Templating the installed Markdown did not subsume this: that work reached `mad/` only, so
   `kb_tools/` and `liaison_tools/` still install by the exception-driven walk, and this stays open
   on its own.

8. **One rule arriving several times in one prompt — the duplication class the sweep cannot see.**
   Distinct from the cross-file duplication `devtools/dupe_sweep` finds and `PROSE_DEDUPE_PLAN.md`
   cleared: a seat is told the same thing twice inside its own definition, through a chunk and an
   inline restatement, or through two different chunks that both land in it. Single-sourcing does
   not prevent it — a chunk guarantees one *definition*, not one *delivery*. **Roughly 60 instances
   across 24 files, found by reading; about 22 resolved.** The residue splits by cost: where one
   statement is a clean superset of the other the fix is a deletion, and where neither is, it needs
   a composition ruling per pair — which chunk a template stops expanding.

   **The instrument's limits are measured rather than assumed.** `devtools/dupe_sweep`'s prose pass
   finds exact runs of eight or more shared words across texts (guaranteed at fifteen), whatever the
   sentence boundaries, so a paragraph duplicated verbatim is reported even when its sentences are
   short. It still cannot see a rule restated in different words, inside one file or across two: a
   lexical intra-file detector over all 46 templates at a 7-token floor recovered **zero** of the
   findings above, because they are semantic paraphrases — a rule stated once where it is *defined*
   and again where it is *applied*, drifting apart in wording as it goes. Reading finds them; a
   lexical instrument does not. It also refuses the fourth comparative question, one word with two
   meanings, and names what it would need: a glossary binding each project term to the one thing it
   may refer to.

    **A command's prompt is a union, and no file-unit instrument sees it.** Four of the seven
    `templates/commands/*.tmpl.md` open with `@`-loads: `/mad-review` assembles a command body plus
    three full definitions, `/guest-start` a command body plus the liaison. Roughly half the
    intra-prompt findings live only in that union — invisible to any per-file tool and to reading
    either file alone. Two are outright **conflicts** rather than duplication: the command telling a
    referee the charter `MUST` be passed verbatim to every seat where the chunk beside it forbids
    pasting the charter inline, and the guest commands telling the session to decide
    resume-versus-new by inspecting `messages.json` where the liaison says to decide it with
    `validate` and never by inspecting the file.

   **Sections meant to stay in sync are held in sync by nobody.** A template section that is the
   same across a family — a heading and a sequence of chunk markers — is copied per template, so
   the sequence drifts: among the seven language coders, Core Principles' marker block is
   identical in four and Parallel Execution's in five; among the seven platform experts, Code
   Standards' is identical in two and Testing's in one. Some deviations are deliberate (go and
   rust carry no coverage rule by design), and nothing distinguishes those from drift. The fix
   is one nested chunk per family per sync-intended section, heading included, with a template
   argument where a value legitimately differs; `render-diff` then shows exactly the drift
   repairs. First: enumerate every deviation and classify it from the chunk file's own comments
   and the line's history. Next dev branch's first task.

9. **Re-examine the MAD agent set against what the harness now does.** That design predates several
   harness capabilities and may be replicating orchestration the harness performs more reliably.
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

10. **Architect probes its own design assumptions.** The architect has no shell
    (`templates/agents/architect.tmpl.md`, `tools: read, grep, glob, write, edit`), so a design call
    that only execution settles — an import graph, a rendered byte, a CLI's output — reaches
    approval unverified and surfaces mid-run. It needs a way to run probes without gaining a way to
    change code. Candidates: per-agent Bash command patterns, if the harness honours them in agent
    frontmatter (unverified), limited to running scripts under `.claude-temp/`; or a defined handoff
    where the architect writes probe scripts there and a coder runs them and returns the output.

11. **Does Claude Code honour a hex `color`?** Every agent template authors `color` as a hex value,
    and Claude Code's subagent documentation lists eight color names. The claude render passes the
    hex value through unchanged. Settling it wants a behavioral probe.

12. **Does opencode load `agents/` recursively?** The shipped packages' markdown under
    `agents/kb_tools/` and `agents/liaison_tools/` — READMEs and `.tmpl.md` prompt templates —
    carries no frontmatter and sits at destinations SPEC.md freezes (Deployed Surfaces). If opencode
    loads `agents/**/*.md`, it reads those files as agents or fails its config validation, which no
    frontmatter rendering can fix. Settled by starting opencode in a project installed with
    `--harness=opencode` and listing its agents.

13. **The harness agents file names a Claude pin under every harness.**
    `templates/harness/AGENTS.tmpl.md` renders "dispatch at `model: sonnet`" for opencode too,
    because the agents-file render binds its tier tokens to the default family's members whatever
    the harness. Rewording it changes agent-visible text, so it goes through prompt-engineer review.

14. **(KEEP LAST) Definition namespace prefix** (`just install --name-prefix=aa- <project>`):
    installs the agent and command definitions under a prefixed namespace so the set coexists with
    an existing fleet — generic names (`python-coder.md`) are the collision surface; the tool
    packages are self-namespaced and stay bare. Default empty renders today's bytes. Requires a
    template pass tokenizing every cross-reference site (dispatch names, slash-command names in
    prose, the MAD roster) with a lint against bare fleet names, and a decision on how the prefix
    reaches runtime callers that name agents from code (the driver's `--agent <seat>` invocations):
    driver-config key vs. install-time stamp into the installed `kb_tools`. The harness agents file
    (`templates/harness/AGENTS.tmpl.md`) is in the prefix substitution set, so agent references
    inside it — the prompt-engineer review rule, any seat named by the working preferences — render
    with the prefix applied at install.
