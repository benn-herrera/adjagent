### Plugins

An install delivers one **plugin**, a named selection of definitions: `devpro install TARGET` or
`devpro install TARGET --plugin=kbase`. Every command that takes a plugin takes it as
`--plugin=NAME`, default `devpro`. The first positional is the target, so a plugin name there is
read as a target directory (a lone `devpro install kbase` is refused where no directory `kbase`
exists: "install target 'kbase' is not an existing directory"), and a second positional is refused
before anything is written. A harness may carry fewer than every definition of its plugin: mage does
not carry `install`.

- **devpro** delivers every definition but `kbase`: the coding, platform and specialist agents, the
  `development`, `docdicer` and `install` skills and the rest.
- **kbase** delivers fourteen definitions: the `kbase` skill, which drives kbase, a separately
  installed knowledge-base program and MCP server, with its supporting files, and `install`,
  `development`, `docdicer`, `architect`, `python-coder`, `prompt-engineer`, `tech-writer`, `shell-dsl-coder`,
  `applied-mathematician`, `economic-historian`, `theoretical-economist`, `prose-architect` and
  `literature-scout`.

A plugin naming a definition that does not exist refuses every render, `render` and `install`
alike, naming the plugin and the names. Each plugin installs into its own install directory (Install
destination), so installing one never changes the other's.

A supporting artifact is delivered with the definition that uses it, and only where that definition
ships. The docdicer tools package (SPEC.md, Deployed Surfaces, Shipped files) goes to its destination
inside the `docdicer` skill's own directory, and the development scripts package inside the
`development` skill's. The docdicer tools and the development scripts ship with both plugins, so a
kbase project has the `kanban` board, `check-plan` and plan dicing. The kbase plugin also delivers
the kb-tools package (runner snippets: `justfile` and `Makefile` fragments a project includes,
inside the `kbase` skill's own directory) and the harness's `kbase` MCP entry. The MCP entry is the
`.mcp.json` in the install directory under claude and mage (Install destination), and a
record in the registry `registry.json` under opencode (Write Safety states which settings files no
install writes). A user-level install delivers no package.

Where the `kbase` skill ships, the `docdicer` skill states that `kb-root/` and everything under it
belongs to kbase, and that docdicer does not dice, undice or link-check it unless the user directs
that for it specifically. Where it does not ship, the skill carries no such statement.

A **runner include line** is the line that includes one package's runner snippets in the project's
**runner file**, its `justfile` or `Makefile`. Two packages carry snippets: the docdicer tools, a
snippet set called `docdicer`, and the kb-tools, a set called `kb`. A project install of either
plugin writes the line of every set whose package it ships: both plugins write the `docdicer` line,
and the kbase plugin also writes the `kb` line. Only a project install under a harness whose plugin
nests in the project (claude, opencode) writes one; a mage install writes no runner include line and
creates no `Makefile`, and nothing is written into this repository's own runner file. A line names
the snippets inside the installed tree (under claude,
`.claude/skills/<plugin>/skills/docdicer/tools/runner-snippets/` or
`.claude/skills/kbase/skills/kbase/kb-tools/runner-snippets/`; under opencode, the same below
`.opencode/plugins/<plugin>/`). The line does nothing where the snippets are absent: `import? '<path>'`
in a justfile, `-include <path>` in a Makefile. A project with neither runner file gets a `Makefile`
created to hold every line the install writes, whichever plugin it installs.

Each set is judged on its own: one set's line never counts as another's. A runner file keeps at
most one line per set. A line already naming a set's snippets under this install's top-level
directory is updated in place. Updating it changes only the snippets path it names: the rest of the
line, and every line ending in the file, stay as written. A line whose first non-blank character is
`#` is not such a line. A line naming another top-level directory's snippets, or more than one line
for the same set, is reported and left, and the other sets' lines are still written. A user-level
install of the kbase plugin (SPEC.md, Deployed Surfaces, Install destination) writes its
definitions and the `kbase` MCP entry, `.mcp.json` under claude and the registry's record under
opencode. It writes no package, no runner include line and no runner file (Write Safety states
which settings files no install writes).

Installing both plugins in one place gives duplicate agents under different names.

No install reads, rewrites or removes a file outside its own managed set.

No install writes, copies, verifies or locates a `kbase` executable. The operator installs kbase
themselves (docs/knowledge-base.md, Requirements), and every harness's `kbase` MCP entry names the
bare command `kbase`, resolved from `PATH`, with the argument `mcp` and no KB path; under mage the
entry keeps its `--project-dir-required` argument. Version 0.11.1 is the minimum kbase this product is written for, and nothing checks it.
The kbase plugin is supported on macOS and Linux, where Homebrew provides kbase as
`benn-herrera/tap/kbase`; native Windows is unsupported for it, and no install refuses or warns on
Windows.

devpro, the generator, needs Python 3.9 or later on the host; the kbase plugin's toolchain is the
`kbase` executable the operator installs, which needs no Python. The docdicer launcher needs `python3` 3.9 or later with its `venv` module,
and installing the package from its git URL needs `git` on `PATH`.
Everything else the kbase plugin needs (pandoc 3.12, git, a way to reach a model) is kbase's own
requirement, which the operator meets.
