### Plugins

An install delivers one **plugin**, a named selection of definitions: `adjagent install devpro` or
`adjagent install kbase`. The plugin argument has no default. A harness may carry fewer than every
definition of its plugin: mage does not carry `adjagent`.

- **devpro** delivers every definition but `kbase`: the coding, platform and specialist agents, the
  `development`, `docdicer` and `adjagent` skills and the rest.
- **kbase** delivers thirteen definitions: the `kbase` skill, which drives kbase, a separately
  installed knowledge-base program and MCP server, with its supporting files, and `adjagent`,
  `development`, `architect`, `python-coder`, `prompt-engineer`, `tech-writer`, `shell-dsl-coder`,
  `applied-mathematician`, `economic-historian`, `theoretical-economist`, `prose-architect` and
  `literature-scout`.

A plugin naming a definition that does not exist refuses every render, `render` and `install`
alike, naming the plugin and the names. Each plugin installs into its own install directory (Install
destination), so installing one never changes the other's.

A supporting artifact is delivered with the definition that uses it, and only where that definition
ships. The docdicer tools package (SPEC.md, Deployed Surfaces, Shipped files) goes to its destination
inside the `docdicer` skill's own directory, and the development scripts package inside the
`development` skill's. The docdicer tools ship with devpro; the development scripts ship with both
plugins. The kbase plugin delivers the kb-tools package (runner
snippets: `justfile` and `Makefile` fragments a project includes, inside the `kbase` skill's own
directory), the harness's `kbase` MCP entry and one runner include line. The MCP entry is the
`.mcp.json` in the install directory under claude and mage (Install destination), and a
record in the registry `registry.json` under opencode (Write Safety states which settings files no
install writes). A user-level install delivers no package.

The runner include line is the line that includes the kb-tools snippets in the project's **runner
file**, its `justfile` or `Makefile`, never into this repository's own. It names the snippets inside
the installed tree (under claude, `.claude/skills/kbase/skills/kbase/kb-tools/runner-snippets/`;
under opencode, `.opencode/plugins/kbase/skills/kbase/kb-tools/runner-snippets/`). A mage install
writes no runner include line and creates no `Makefile`. The line does nothing where the snippets
are absent: `import? '<path>'` in a justfile, `-include <path>` in a Makefile. A project with
neither runner file gets a `Makefile` created to hold it. A runner file keeps at most one such line.
A line already naming snippets under this install's top-level directory is updated in place. Updating it changes
only the snippets path it names: the rest of the line, and every line ending in the file, stay as
written. A line whose first non-blank character is `#` is not such a line. A line naming another
top-level directory's snippets, or more than one such line, is reported, and the runner file is left
unwritten. A user-level install of the kbase plugin (SPEC.md, Deployed Surfaces, Install
destination) writes its definitions and the `kbase` MCP entry, `.mcp.json` under claude and the registry's record
under opencode. It writes no kb-tools package, no runner include line and no runner file (Write
Safety states which settings files no install writes).

Installing both plugins in one place gives duplicate agents under different names.

No install reads, rewrites or removes a file outside its own managed set.

No install writes, copies, verifies or locates a `kbase` executable. The operator installs kbase
themselves (docs/knowledge-base.md, Requirements), and every harness's `kbase` MCP entry names the
bare command `kbase`, resolved from `PATH`, with the argument `mcp` and no KB path; under mage the
entry keeps its `--project-dir-required` argument. Version 0.11.0 is the minimum kbase this product is written for, and nothing checks it.
The kbase plugin is supported on macOS and Linux, where Homebrew provides kbase as
`benn-herrera/tap/kbase`; native Windows is unsupported for it, and no install refuses or warns on
Windows.

adjagent, the generator, needs Python 3.9 or later on the host; the kbase plugin's toolchain is the
`kbase` executable the operator installs, which needs no Python. `tools/docdicer --install` also
needs `python3`'s `venv` module, and installing the package from its git URL needs `git` on `PATH`.
Everything else the kbase plugin needs (pandoc 3.12, git, a way to reach a model) is kbase's own
requirement, which the operator meets.
