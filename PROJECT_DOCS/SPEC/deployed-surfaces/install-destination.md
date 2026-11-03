### Install destination

An install writes into the project's harness directory — `.claude/` by default, or the selected
`--harness`'s `project-harness-dir` (`.opencode/` for `opencode`; mage installs under its `adjagent`
subdirectory, so the named ROOT is the parent that `adjagent/` is created in); `just install` accepts
`--subdir=<dir>` to override it, and an empty `--subdir=` installs directly into the project path:
every definition its type carries, rendered by that same invocation, together with the packages
those definitions read (below), delivered to their own frozen destinations by explicit mapping
rather than as part of any surface, and the files the installing harness itself ships, copied into
that same directory as they stand (below). What is not part of the product does not travel: test
suites and their fixtures, caches, `.DS_Store`, backup (`.bak`) copies, and this repository's own
project documentation. That last class is a filename vocabulary — the contract
documents (`SPEC.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `THESIS.md`) and the development
apparatus (`ROADMAP.md`, `AGENTS.md`, `CLAUDE.md`) — matched at any depth in a shipped package's
source. A shipped package's contract states what it must do for someone changing it *here*; a
consuming project receives the code and not the project it came from, so no installed prose may
assume a reader who can open one. `README.md` is not in that class: it is the one such name a
package writes for its consumer, and a package that grows one ships it. The optional tuning
arguments — a model family, a replacement for the tier map it declares, and an alias map — render
the generated definitions under that tuning (see Generation System, below).
The optional harness argument names the supported harness whose values the generated definitions are
rendered with, and whose frontmatter they carry: each field in the spelling that harness reads, and
absent where that harness has no use for it (default `claude`); an unsupported name is refused
before anything is written.

An install's ROOT may be any directory prepared to receive the product. The sanctioned deployment
shape has a consuming project gitignore a subdirectory for this repository's own clone and run
install from inside it, so ROOT resolves to the project's `.claude/` with the repository sitting
underneath it as one of the sources the install reads — that containment is what the sanctioned
shape *is*, not a hazard it happens to create. ROOT may not, however, be this repository's own root:
the render would then land beside the sources that produce it, as `agents/`, `commands/` and
`skills/` materializing untracked at the repository's own top level, in a place no `.gitignore`
entry here covers. Nor may ROOT sit inside any source an install copies from — a shipped package's or
a harness's resource tree (Deployed Surfaces names both): installing there once writes the product
into the tree a later install reads from, and that later install then deletes or overwrites,
out from under itself, files its own copy still needs to read. Both refusals are decided on the tree
an invocation actually names, whatever path or symlink was written to reach it. A ROOT that sits
above the repository, rather than at or inside it, is accepted — and deliberately so: it is
indistinguishable from the sanctioned shape, being a directory the repository sits under rather than
the repository or one of its sources, and the cost of accepting it is an untracked render landing
outside this repository rather than inside it.

