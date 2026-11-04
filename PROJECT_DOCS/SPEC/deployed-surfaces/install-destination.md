### Install destination

An install names a **target**, its first argument that is not a flag. A target that is not an
existing directory is refused with nothing written. The **harness** is, in order: the one
`--harness` names; otherwise the one whose harness directory sits inside the target — its
`project-harness-dir` (`.claude/`, `.opencode/`) or, in the user's home directory, its
`user-harness-dir` (`.claude/`, `.config/opencode/`); otherwise the one the target itself is the
directory of, matched on the target's trailing path elements (`.claude`, `.opencode`,
`.config/opencode`, and `Mage/Skills` for mage); otherwise the install is refused, naming
`--harness`. More than one harness directory inside the target is refused the same way. No other
part of a path selects a harness.

The install's **ROOT** is where it writes, and the **project root** is the directory the MCP entry
and the runner include line belong to:

| target | ROOT | project root |
|---|---|---|
| any, with `--subdir=<dir>` | `<target>/<dir>`; an empty `--subdir=` is the target itself | the target |
| a harness's own directory (mage: `Mage/Skills`) | the target (mage: `<target>/adjagent`) | the target's parent (mage: the target) |
| the user's home directory | the harness's `user-harness-dir` inside it | the home directory |
| any other | `<target>/<project-harness-dir>` | the target |

The project-harness-dir is `.claude/` by default, `.opencode/` for `opencode`, and `adjagent/` for
mage. A home-directory target with `--harness=mage` takes the last row, mage having no absolute
user directory. The project root is resolved through symlinks. ROOT may be absent and is created
once every check has passed; one that exists and is not a directory is refused, "is not a
directory".

An install is **user-level** when its ROOT is the installing harness's `user-harness-dir`, however
the target reached it. A user-level install renders the definitions its type carries, prunes and
removes the legacy trees as any install does, and writes nothing else: no shipped harness file, no
guardrail probe or registration, no shipped package (neither `kb-tools/` nor the docdicer tools
package) and so no `--install` re-run, no MCP entry, no runner include line and no runner file.
`--install-global-agents-file` is its one opt-in: it also installs the harness agents file at ROOT
(Harness Agents File, below). On a project install the flag is ignored, with no error and no write.

An install writes into ROOT: every definition its type carries, rendered by that same invocation, together with the packages
those definitions read (below), delivered to their own frozen destinations by explicit mapping
rather than as part of any surface, and the files the installing harness itself ships, copied into
that same directory as they stand (below). What is not part of the product does not travel: test
suites and their fixtures, caches, `.DS_Store`, backup (`.bak`) copies, a `.venv` directory, and this repository's own
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
absent where that harness has no use for it; an unsupported name is refused before anything is
written. Render defaults it to `claude`; install has no default, and resolves its harness as
described at the top of this page.

An install's ROOT may be any directory prepared to receive the product. The sanctioned deployment
has two shapes. One has a consuming project gitignore a subdirectory for this repository's own clone
and run install from inside it, so ROOT resolves to the project's `.claude/` with the repository
sitting underneath it as one of the sources the install reads — that containment is what that shape
*is*, not a hazard it happens to create. The other runs the installed package (Package and Command),
which has no repository around it. Run from a clone, the install refuses a ROOT that is this
repository's own root, since the render would then land beside the sources that produce it, as `agents/`, `commands/` and
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

