### Base and kb installs

The two install types differ by one filter and three emissions. The filter is `NOT_BY_DEFAULT`,
`^(kb-|kbase$)`, applied to the definition's name — its declared name, not a rendered file's stem —
before anything about it is rendered: a base install drops every match whole, so no file of a
dropped definition is written, and the skill's directory is never created by a run that excludes
it. A harness whose `user_harness_dir` is `.` is always a kb install, so the filter never applies
to it. A kb install is named by `--with-kb`, the flag `install-with-kb` passes, or is sticky, per
ROOT rather than per project, so a later base-typed invocation refreshes the kb set instead of
dropping it. The predicate, at `kb_included` in `install`, is `with_kb`, or `Harness.is_standalone_plugin`
(`user_harness_dir == "."`), or `_is_ours` (the generated-banner test) of the router, `KBASE_ROUTER` —
`skills/kbase/SKILL.md` — at ROOT or at the harness directory. The two differ only under claude, where the
harness directory holds an earlier flat install's router, so the first install after upgrade stays kb. The
router is the whole of the sticky signal, because no release installed a `kbase` executable without
also installing the generated router beside it. The test reads the router's banner and nothing
else: the mode is never read, and the runner snippets are never inspected, so a destination holding
a `kb-tools/` directory and no router — or an empty one — is a base install. A `SKILL.md` without
the generated banner is its project's own and signals nothing. No legacy tree is a signal.

A kb install writes three things beyond the renders — two under a harness whose
`user_harness_dir` is `.`, with no runner include line and no `Makefile`:

- **The kb-tools package**: every file of `adjagent/kb-tools/` — the `runner-snippets/` fragments — taking the
  package copy below. The destination is `KB_TOOLS_PACKAGE` — `skills/kbase/kb-tools/`, its own
  directory inside the `kbase` skill's, within the `skills/` surface — and is removed whole before
  the copy, so an executable and `.asc` an earlier version installed there go, while the skill's
  `SKILL.md` and references beside it are not touched. Package destinations come from one list,
  `_packages`, which `package_copies`, the clearing before the copy and `_refuse_root` all read:
  the `SHIPPED_PACKAGES` table, whose one row is the docdicer tools package at
  `DOCDICER_TOOLS_PACKAGE` (`skills/docdicer/tools/`) and so in the list whether or not kb is included (a user-level install copies none); and `kb-tools/` at
  `KB_TOOLS_PACKAGE` when kb is included. kbase itself reaches the host by the
  user's own install (`docs/knowledge-base.md`); the skill's `references/installing.md` walks a session through it.
- **The `kbase` server entry**, merged into the harness's own settings file (`Harness.mcp`): `.mcp.json`
  at the plugin root under claude and mage — `McpSettings.site` names the directory, `HARNESS`
  there and `PROJECT` for opencode — or for opencode the first discovered of
  `.opencode/opencode.json`, `opencode.jsonc`, `opencode.json`, else `.opencode/opencode.jsonc`
  created. Under every harness the entry's command is `KBASE_NAME`, the bare `kbase`, which the
  host resolves from `PATH`, so the settings file names no machine-specific path and a project can
  track it. Each harness's entry builder takes the command and nothing else. Its argument
  list is `mcp` alone and names no KB path: the server locates the KB from the working directory it
  is started in, so it has to be started in the project root. Mage, an application harness started
  outside any one project, adds `--project-dir-required` (`harnesses/mage.py`), under which every
  tool call names its project with `project-dir` and the server locates none of its own. An existing settings file is edited in
  place: the entry's own slot is spliced into the text as it stands, so every other byte — other
  entries, key order, indentation, line endings — is kept, while a file this install creates is
  written whole.
  One that is not plain JSON — JSONC comments a splice would destroy — or that the splice cannot
  place with certainty, or whose path `_settings_obstacle` names, is reported with the entry
  printed, and left as it stands. A project install that writes the entry also removes the `kbase`
  member an earlier version registered in the project's own `.mcp.json`, as the retired entries of
  [Guardrail registration](guardrail-registration.md) are removed.
- **The runner include line**, appended to the project's justfile or Makefile — or to a `Makefile`
  created carrying it, where the project has neither: the non-fatal `import?` or `-include` form
  naming the installed snippets at `<harness-relpath>/skills/kbase/kb-tools/runner-snippets/<snippet>`,
  `harness_relpath` being ROOT relative to the project root, so under claude
  `.claude/skills/adjagent/skills/kbase/kb-tools/…`. Written only for a harness whose user directory is not `.`:
  a plugin is not a repo project, so mage gets no line and no `Makefile`. One line only: a line
  naming another harness directory — its first path segment differing from `harness_relpath`'s — is reported and left alone, and one
  naming this harness's directory is this install's, its whole path token rewritten in place to
  the canonical one, so a line an earlier version wrote at the flat path is moved into the plugin.

On a user-level install only the server entry is written, and only where the settings file's
`McpSettings.site` is `HARNESS` (claude's `.mcp.json` inside the user-level plugin, with no user
settings file touched): the kb-tools package and the include line are project-only, and `install`
otherwise renders the kb set's definitions and stops there.

