### Installed artifacts

An installed tree is an **artifact**, and not for local edit: a re-install overwrites the files that
carry this repository's banner and removes what this repository no longer produces, and over any
other file at a render or harness-resource target it refuses and writes nothing (Write Safety,
below). A change request
comes to this repository. Whether the consuming project tracks it in git is that project's own
decision; where it does not, a local edit is replaced on the next install with no diff to show it. A
shipped package's destination belongs to this repository entire, and no file there is for local
edit.

Every installed file states its own origin in banner lines, except the files a harness ships, which
carry their own header, and the manifest a harness renders, which carries none because its format
admits no comment — its `name` field states its origin; the install adds none (below). A definition's
own output carries two inside its frontmatter: the generated banner (Generated-Definition Integrity),
which says where the file was generated from and that it is not for local edit, and the tuning line
(Generation System). A skill's
supporting file has no frontmatter, so it carries the same two lines as HTML comments — its first two lines, above a
blank line and the body — and nothing about how the file is read depends on them. A copied package
file of a script or build-file type (`.py`, `.sh`, `.mk`, `.just`), and the extensionless launcher
`tools/docdicer`, carries an installed banner at its top, below its shebang where it has one. No
banner sits where it changes how the file is read. Every other copied file — `tools/.gitignore`
among them — and every file a harness ships, whatever its type, is installed byte-verbatim and
unstamped.

Every path written inside a definition body — a file the agent is told to `Read`, a script it
invokes — is written against the installing harness's project directory —
`<harness-dir>/agents/...` for a definition, `<harness-dir>/adj-tools/...` or
`<harness-dir>/skills/kbase/kb-tools/...` for a shipped package's script, which are
`.claude/agents/...`, `.claude/adj-tools/...` and `.claude/skills/kbase/kb-tools/...` under
claude — not against the repository's own path: that is where the installed file
actually lives, and the path it must resolve from inside a consuming session. The exception is a
script inside a skill's own directory, which that skill's body may name relative to that directory
(`tools/docdicer`), because the skill's directory differs by harness (under mage,
`~/Mage/Skills/adjagent/skills/docdicer/`). The same holds for
the project's scratch directory, named as the harness names it. A project's agents file is named
`AGENTS.md` under claude and opencode, whose user directory is a separate scope; where the
destination is the harness's own directory — mage — the harness's name is used, so the file is
`CLAUDE.md` (Harness Agents File, below).

Every file directly under `agents/` matching `*.md` whose definition is an agent, its frontmatter
carrying dispatch keys (`name`, `description`, `model`), is a dispatchable agent definition — the
rule holds without exception, and its rendered frontmatter spells those keys as the installing
harness reads them.

