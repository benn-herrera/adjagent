### Plugins

What each plugin delivers is SPEC.md, Deployed Surfaces,
[Plugins](../../SPEC/deployed-surfaces/plugins.md); this leaf is how an install selects and ships it.

**Membership.** A plugin is a `Plugin` (`devpro/plugin.py`), one module in `devpro/plugins/` defining
`PLUGIN`: the devpro plugin states what it leaves out (`kbase`), kbase what it ships. By
`Plugin.ships(name)` (Rendering, Harnesses and families), `render.rendered_definitions` keeps
exactly the definitions it admits, so a definition the plugin does not carry is never rendered, and
the skill's directory is never created by a run that omits it. `discover()` is the closed set
every plugin's names are checked against (`context.plugin_named`). The install filters nothing of its
own and reads no plugin's name: everything below is keyed on a definition's name, the owner.

**Owners.** A supporting artifact ships iff the definition that uses it ships. Each package is a row
of `SHIPPED_PACKAGES` (`devpro/install.py`), a `ShippedPackage` of source, destination, owner and `snippets` (a `runner_file.SnippetSet`, or none):

| source in `devpro/` | destination below the install directory | owner |
|---|---|---|
| `docdicer-tools` | `skills/docdicer/tools` | `docdicer` |
| `development-tools` | `skills/development/scripts` | `development` |
| `kb-tools` | `skills/kbase/kb-tools` | `kbase` |

`install` takes the rows whose owner `Plugin.ships(name)` admits, and none on a user-level install. Those rows are
what `package_copies` copies and `_clear_package_destination` empties before the copy, so the
destination is emptied in place while the skill's `SKILL.md` and supporting files beside it are not
touched. A harness-rendered file is owned the same way: `HarnessFile.owner` names a definition, and
`shipped_harness_files` drops the file where that definition does not ship. The `kbase` owner name is
one constant, `harness.KBASE_OWNER`, read by the kb-tools row and by every harness's `.mcp.json` and
registry record.

**The MCP entry** is rendered whole, never merged into a file the project owns. Claude and mage
render `.mcp.json` (`harness.mcp_json`, a `HarnessFile` owned by `kbase`) at the install directory,
the `kbase` server alone under `mcpServers`, its entry from the harness's builder; opencode's
`registry.json` holds the same server as a record (Rendering, Harnesses and families). The install
directory is the plugin's own, so no project bytes need preserving. Under every harness the entry's
command is `KBASE_NAME`, the bare `kbase`, which the host resolves from `PATH`, so the file names
no machine-specific path and a project can track it. Each builder takes the command and nothing
else and writes the arguments SPEC.md states; the server locates the KB from the working directory
it is started in, so it has to be started in the project root. Mage, a harness-directory plugin started
outside any one project, adds `--project-dir-required` (`harnesses/mage.py`), under which every
tool call names its project with `project-dir` and the server locates none of its own. The file's
marker is the command, `"command": "kbase"`, since JSON admits no comment. A user-level install
renders it like any other harness-rendered file.

**The runner include lines**, appended to the project's justfile or Makefile, follow the shipped
packages that carry snippets: a `ShippedPackage` row's `snippets` field is a `runner_file.SnippetSet`
(label, snippets directory below the package's destination, snippet name per runner), set on the
docdicer tools row (`docdicer`) and the kb-tools row (`kb`). The lines are written where the install
ships at least one such row and is a project install of a nested plugin
(`_is_project_install_of_a_nested_plugin`), so both plugins write the docdicer line and kbase also
the kb line. `ShippedPackage.installed_snippets()` joins the destination to the set's directory, and a line names the
installed snippets at `<harness-relpath>/<destination>/<set directory>/<snippet>`, `harness_relpath` being the install directory
relative to the project root, so under claude
`.claude/skills/<plugin>/skills/docdicer/tools/runner-snippets/docdicer.just` and
`.claude/skills/kbase/skills/kbase/kb-tools/runner-snippets/kb.just`, and under opencode the same
below `.opencode/plugins/<plugin>/`. `runner_file.install_include_lines` writes them, in the
table's order, judging each set alone (`_with_include_line`) and writing the runner file once when
any text changed. Mage gets no line and no `Makefile`. A line is this install's when its first path
segment equals `harness_relpath`'s, and its path token is then spliced in place. A set's line is
recognized by the path's shape, ending `<snippets directory name>/<snippet>`, so the `docdicer` and
`kb` sets never match each other's line. A set whose line is reported and left does not stop the
others. Where the project has no runner file, one `Makefile` is created holding every line.
`runner_file` reads the runner file through `install_base.untranslated_text` (`newline=""`), so a
rewrite keeps each line's ending, and skips a line whose first non-blank character is `#`
(`_named_harnesses`).
