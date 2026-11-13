### Installed tree

An installed tree is not for local edit: a re-install overwrites the files that carry this
repository's banner and removes what this repository no longer produces, and over any other file at
a rendered-definition or harness-resource destination it refuses and writes nothing (SPEC.md,
Write Safety). A package destination belongs to this repository entire, and no file there is for local
edit.

An installed tree needs no devpro installation: removing the devpro package, or replacing it with
another version, changes nothing any installed file does, and only the next `devpro install` needs
the package. The devpro plugin adds no machine-level dependency: beyond the harness, it runs only
what installing the devpro package already requires. What a plugin needs beyond that is the
operator's to install, as Plugins states for each.

A rendered definition, a copied script or build file, and a harness resource each states its origin
in banner lines; a harness-rendered file states it in its ownership marker; no other installed file
carries a banner. A rendered definition carries two banner lines inside its frontmatter: the
generated banner (Generated files), which says where the file was rendered from and that it is not
for local edit, and the tuning line (Rendering). A skill's supporting file has no frontmatter, so it
carries the same two lines as HTML comments — its first two lines, above a blank line and the body
— and nothing about how the file is read depends on them. Under opencode every rendered file is
written without frontmatter and carries the two lines as those comments. A copied package file of a script or
build-file type (`.py`, `.sh`, `.mk`, `.just`), and the extensionless launcher `tools/docdicer`,
carries an installed banner at its top, below its shebang where it has one. Both banners say to
request changes from the devpro project and that local needs belong in the consuming project's
CONVENTIONS.md. An installed banner names the source file it was copied from. A copied package
file keeps its source's mode. A harness resource
(Shipped files) carries its own installed banner, a `!INSTALLED! … devpro` line in its first ten
lines, as shipped: the install adds nothing to it. A harness-rendered file — the plugin manifest and
`.mcp.json` under claude and mage, `registry.json` under opencode, and under claude the guardrail
registration — carries no banner; its **ownership marker**, a fixed string in its content, states
its origin: `"name": "<plugin>"` in the plugin manifest, `"command": "kbase"` in `.mcp.json`,
`"plugin": "<plugin>"` in `registry.json`, and `guardrail hook: no readable script at` in
`hooks/hooks.json`. No banner sits where it changes how
the file is read. Every other copied file — `tools/.gitignore` among them — and every harness
resource is installed byte-verbatim.

A definition body names no installed path below the harness directory. A script inside a skill's own
directory is named relative to that directory (`tools/docdicer`). The project's scratch directory is
named as the harness names it. A cross-definition reference renders with the plugin's namespace —
under claude and mage `<plugin>:<name>` for an agent, a command or a skill, and under opencode
`<plugin>-<name>`, the id the registry registers it under; a `kbase` MCP tool is named
`mcp__plugin_kbase_kbase__<tool>` under claude, `mcp_kbase_<tool>` under mage and `kbase_<tool>`
under opencode. A project's agents file is named `AGENTS.md` under claude and opencode, and `CLAUDE.md` under mage
(SPEC.md, Agents File).

Under claude and mage every file directly under `agents/` matching `*.md` whose definition is an
agent is a dispatchable agent definition, without exception. Its frontmatter carries the dispatch
fields the harness reads, each in that harness's spelling: `name`, `description` and, unless its
model renders empty, `model`. A document's frontmatter carries no field. A command's frontmatter
holds its banner lines alone. Under opencode a file has no frontmatter, and the registry
holds a record for every such file whose definition is an agent: its id, `<plugin>-<name>`, its
`description`, `mode: subagent` and, unless its model renders empty, the `model`. A document's
record is `hidden`.

