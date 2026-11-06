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

2. **Legacy project comprehension skill**: how a session enters a brownfield project with known
   and unknown issues, builds familiarity with it, and begins repair work. The target case is
   projects whose debt accumulated through ungoverned agentic development. It follows the
   development-process skill and should not assume that skill's workflow is already in place.

3. **Rename the project to `devpro`**, its own plan: the PyPI package, the
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

4. **Split `adjagent/install.py` into modules.** It holds the JSON text editor (`_splice`,
   `_without_item` and the scanner under them), the settings merge and retired-entry removal
   (`mcp_merge`, `_retired_items`, `_remove_retired_entry`) and the runner-file line
   (`install_kb_include_line`) beside the install itself.

5. **Share the decisions `install` and `_install_managed_paths` both make.** Whether the guardrail
   registers, whether the MCP entry is written and which retired entries are retiring are decided
   twice in `adjagent/install.py`, once in `install` and once in `_install_managed_paths`. Each
   would be a helper both call.

6. **Move retired entries onto `GuardrailHook` and `McpSettings`, and delete `Replacement`.** A
   `RetiredEntry` in `Harness.retired_entries` (`adjagent/harness.py`; claude's two in
   `adjagent/harnesses/claude.py`) names the `Replacement` whose write licenses its removal, a fact
   that belongs on the hook or the MCP settings it is replaced by.

7. **State the minimum Claude Code version that loads a plugin from a project's skills directory.**
   Under claude the set is a plugin at `.claude/skills/adjagent/`. No document states the Claude Code
   version that loads one, and README.md's Requirements section names none; the version is not yet
   established from any source.

8. **Give the kbase router's not-offered branch the plugin reload remedy.** Under claude the
   plugin's `kbase` tools appear after a fresh install only once the plugins are reloaded. The "A
   path" branch of the router and `references/installing.md` (both in
   `adjagent/definitions/kbase.py`) say only to restart or reconnect the server. The `reload_rule`
   hole names agents, not tools, so reusing it there would misdirect the model; the remedy needs a
   harness hole of its own.

9. **Verify the opencode guardrail's tool names against the opencode runner.** Which tool names
   reach `execute.before` is unverified: only `patch` is matched, not `apply_patch`; a `list` tool
   taking `path` is not handled; the `shell` alias is accepted but never sent. Probe the runner,
   accept every name the hook receives, and add a case row for each (`guardrail.ts` `shellTools`
   and its tool `switch`; `tests/test_guardrail.py` `_OPENCODE_ONLY_TOOLS`).

11. **Nothing checks that the kbase names the skill cites are offered.** Every `kbase://` URI, tool
    and op `adjagent/definitions/kbase.py` names goes unchecked against kbase's surface. A test
    that runs `kbase mcp` (`initialize`, `tools/list`, `resources/list`) and asserts each cited name
    is offered would catch drift; it fails, not skips, without `kbase`.

12. **The guardrails hard-code kbase's private record names.** The Grep/Glob judgement depends on
    `nodes.yaml`, `edges.yaml` and `format.yaml` (`guardrail.pl` `@kb_records`, `guardrail.ts`
    `kbRecords`), so a record file a later kbase adds passes silently. Passing a Grep/Glob rooted in
    `kb-root/` only when its filter's last segment ends in `.md` drops both lists; it is a behaviour
    change to both scripts and the case table together.

15. **How a work contributes to strength is stated three times in the kbase reading reference.**
    `clauses.kb_orientation`, `reading.md`'s "Pending does not propagate" and its works paragraph
    (`adjagent/definitions/kbase.py`) each state the `bearing × rigor` contribution and the pending
    rule; `scoring-system.md` only links out. One statement should hold it.

18. **Claude's guardrail runs perl on every file-tool call on base installs.** The registration's
    matcher (`adjagent/harnesses/claude.py` `_guardrail_registration`) covers every file tool on
    every claude install; on a base install the script finds no kb signal and passes the call.
    Measure perl startup per call first, and narrow the matcher to `Bash` on base installs only if
    the cost matters.

19. **The guardrail's behaviour is restated in four documents:** SPEC
    `deployed-surfaces/shipped-files.md`, ARCHITECTURE `install-consumption-model/guardrail-hook.md`,
    CONVENTIONS `guardrails-change-together.md` and `docs/guardrail.md`. ARCHITECTURE should cite
    SPEC for what is blocked, CONVENTIONS keep only the process rules, and `docs/guardrail.md`
    keep the user's symptom and remedy.

22. **Mage has no guardrail.** `adjagent/harnesses/mage.py` sets `guardrail=None` and SPEC
    `shipped-files.md` says mage ships none, so a mage install's `.index/` protection rests on
    kbase's prose instruction alone. Check whether mage's plugin format carries a hook; if it does
    not, record the gap in SPEC.

26. **`just test` does not hold the own-paragraph rule for module text beside a clause.**
    `PROJECT_DOCS/CONVENTIONS/adding-definitions/clause-paragraphs.md` says `just test` holds none of
    it; `devtools/clause_join_sites.py` (`just clause-join-sites`) reports join sites, but no test
    fails on a new one.

27. **A shared sentence written out inside a longer paragraph is not checked for double delivery.**
    `tests/test_adjagent.py` `_double_paragraphs` compares whole prose units and never splits them
    into sentences.

28. **The double-delivery check fills only the claude family under the claude harness.**
    `tests/test_adjagent.py` `_prompts` fills with `_CLAUDE_RENDER`, so family overlay text and other
    harnesses' text go unchecked.

29. **The installed agents file is never part of a prompt in the double-delivery check**, though it
    sits in context beside every command and skill (`tests/test_adjagent.py` `_prompts`, `_loaded`;
    SPEC `generation-system.md` defines a prompt without it).

31. **A coder or platform expert that never carries its group's anchor is outside every group**, so
    nothing checks it: `tests/test_clause_groups.py` `check_clause_groups` flags only a carrier
    missing from its group or a member missing the anchor, and `GROUPS` is hand-listed.
