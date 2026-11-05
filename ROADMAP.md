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
   `tests/test_adjagent.py` (ARCHITECTURE.md, Why There Is No Verification Verb);
   behavioral ones do not yet.

2. **Follow-ups from the 0.12.7 review**, unscheduled — `ROADMAP_PLANS/review-0.12.7-followups.md`.

3. **Legacy project comprehension skill**: how a session enters a brownfield project with known
   and unknown issues, builds familiarity with it, and begins repair work. The target case is
   projects whose debt accumulated through ungoverned agentic development. It follows the
   development-process skill and should not assume that skill's workflow is already in place.

4. **Render the claude set in plugin form**: the install renders into one adjagent-owned plugin
   directory under `.claude/skills/adjagent/` — agents, commands, skills and a
   `.claude-plugin/plugin.json` manifest, as the mage harness does — and registers it in
   `.claude/settings.json`, the file the guardrail already registers in, so Claude Code loads it.
   Tuning is unaffected: the plugin is rendered per install like today's output. Namespaced
   definition names (`adjagent:<name>`) need every cross-reference in definition text rewritten at
   render time, which covers item 5's purpose under claude. To settle against current Claude Code
   documentation first: how a plugin at a project path is discovered and enabled; whether Claude
   Code copies it into a cache, which would strand the writable state kept beside skills (the
   docdicer venv, the kb runner include line's path); whether the plugin's own hooks and `.mcp.json`
   replace the guardrail and kbase settings edits.

5. **(KEEP LAST) Definition namespace prefix** (`just install --name-prefix=aa- <project>`):
   installs the agent and command definitions under a prefixed namespace so the set coexists with
   an existing fleet — generic names (`python-coder.md`) are the collision surface; the tool
   packages are self-namespaced and stay bare. Default empty renders today's bytes. Requires a
   render pass substituting every cross-reference site (dispatch names, slash-command names in
   prose) with a lint against bare fleet names. Nothing outside the definition text
   names an agent, so the rendered prose is the whole substitution set and no runtime route has to
   carry the prefix. The harness agents file (`adjagent/definitions/harness_agents_file.py`) is in
   it, so agent references inside that file — the prompt-engineer review rule, any seat named by
   the working preferences — render with the prefix applied at install.
