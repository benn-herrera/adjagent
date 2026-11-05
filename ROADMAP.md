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

5. **Rename the project to `devpro`**, its own plan after item 4 lands: the PyPI package, the
   `adjagent` CLI and Python package, the plugin namespace (`devpro:<name>` under claude and mage),
   the agents-file fence markers, the `!GENERATED!` banner, the repository, its docs, and the
   references in sibling projects that install it.
   - The `dev-process` skill becomes `development`: `devpro:development` under claude and mage.
     Every text that names it moves with it, the agents-file pointer sentence and sibling
     projects' CONVENTIONS included.
   - The `adjagent` skill needs a new name that is not `devpro`.
   - opencode has no namespacing, so its names carry the `devpro-` prefix: the reference holes
     fill `devpro-<name>`, and the serialized file and directory names are prefixed to match
     (`devpro-architect.md`, `skills/devpro-development/`). This keeps the set from colliding
     with an existing fleet's generic names under every harness.
