### Base and kb installs

A **base install** — `just install` — delivers every definition this repository produces except the
kb set: the `kbase` skill — except a mage install, which always includes the kb set. It also
delivers each package `SHIPPED_PACKAGES` names (Deployed Surfaces, below) to its destination there,
beside the definition surfaces; the table holds no row today, so no install of this version
delivers one.
A **kb install** — `just install-with-kb`, or any install carrying `--with-kb` — adds the kb set —
the `kbase` skill with every supporting file it lists — together with the
`kb-tools/` package (the runner snippets, inside the `kbase` skill's own directory), the harness's
`kbase` MCP server entry in the harness's MCP settings file — the project's own, or, under mage, the
plugin's at ROOT — and one runner include line in the
project's own justfile or Makefile, never into this repository's own — except a plugin harness,
which is not a repo project and writes no runner include line and creates no `Makefile`.
The choice is sticky per harness directory: an install whose ROOT already
holds a kb install is a kb install. The signal is a file, never the `kb-tools/` directory
(ARCHITECTURE.md, Install Consumption Model, names it). Exclusion is decided once per definition, on its name,
and never per rendered file: a base install keeps no kb-set definition it finds — under that type
the definition is stale, every file of it generated here is removed and named in the report, and a
skill's directory is removed once that leaves it empty, so no run leaves a *generated* router
standing beside generated references it dropped. A mage install is always a kb install, so the
exclusion never applies to it. A file under `skills/<name>/` that carries no
generated banner is its project's own and is never touched. Either type removes each tree an earlier
version installed under a harness directory, naming each it removed (ARCHITECTURE.md lists them),
and a run that excluded kb reports the removal of the pre-1.0 kb helper tree. A
kb install replaces `skills/kbase/kb-tools/` whole, so a `kbase` executable and `.asc` an earlier
version installed there are removed.

No install writes, copies, verifies or locates a `kbase` executable. The user installs kbase
themselves (README.md, Usage, Install), and every harness's `kbase` MCP entry
names the bare command `kbase`, resolved from `PATH`; under mage the entry keeps its
`--project-dir-required` argument. Version 0.10.0 is the minimum kbase this product is written for,
and nothing checks it. The kb set is supported on macOS and Linux, where kbase installs through
Homebrew as `benn-herrera/kbase/kbase`; native Windows is unsupported for it, and no code detects Windows.

The kb set scores through the `kbase` server rather than through an agent: `score` is a tool of that
server, and the `kbase` skill drives it. Its call answers once the run has started, not when the
walk ends. A run enumerates the KB's scoring set itself, so an interrupted run is resumed rather
than repeated. It never supplies two scores — a work's rigor and a `founds` edge's bearing, both
because the work lies outside the corpus; the user authors those.

The generator and install need Python 3.11 or later on the host; the kb set's toolchain is the
`kbase` executable the user installs, which needs no Python. `README.md` states what it asks of the
host.

