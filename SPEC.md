# SPEC – Adjagent

This repository is the source of a drift-proof, model-tunable generation system that renders agent,
command and skill definitions to order; the multi-capability agent, command and skill set it ships,
consumed by other projects, is its flagship rendering. This document states the observable contract
— what the repository guarantees, independent of how the guarantee is implemented. See
ARCHITECTURE.md for mechanism.

## Deployed Surfaces

The repository exposes exactly three deployed surfaces, `agents/`, `commands/` and `skills/` — the
rendered-definition trees this repository's generation and validation mechanism governs. They are
names in the product, not directories in this repository: no render is kept here. Every definition
is produced to order into the output root an invocation names, so there is no checked-in copy for a
render to be served from, compared against, or drift away from. `agents/` and `commands/` hold one
file per definition. `skills/` holds one directory per definition of the skill kind —
`skills/<name>/SKILL.md`, then each supporting file that definition lists, beneath that directory
and nowhere else. A kb install also places its `kb-tools/` package in `kbase`'s own directory; it is
no supporting file of that skill, and the shipped-package paragraph below states what it is and
where it sits. A `SKILL.md`'s frontmatter is `name` and `description`, the two fields every
harness reads, and the description is the whole of what a session sees before it loads the skill:
it carries the conditions under which the skill applies, so discovery needs no command of its own.
A supporting file has no frontmatter. A consuming project receives the install product — the three
surfaces together with the packages delivered alongside them by explicit mapping (below), the files
the installing harness ships (below), and, under mage, one file more, `.claude-plugin/plugin.json`,
the manifest a plugin is discovered by, rendered and neither a surface nor a definition — by
**install**: one deployment shape, two types, and no other:

```sh
just install <path-to-consuming-project> [--family=NAME] [--model-tier-map=SPEC] [--model-pin-tier-alias-map=SPEC] [--harness=NAME] [--verbose]
just install-with-kb <path-to-consuming-project> [the same arguments]
```

A **base install** — `just install` — delivers every definition this repository produces except the
kb set: the `kbase` skill — except a mage install, which always includes the kb set. It also
delivers each package `SHIPPED_PACKAGES` names (Deployed Surfaces, below) to its destination there,
beside the definition surfaces; the table holds no row today, so no install of this version
delivers one.
A **kb install** — `just install-with-kb`, or any install carrying `--with-kb` — adds the kb set —
the `kbase` skill with every supporting file it lists — together with the
`kb-tools/` package (the signed `kbase` executable beside its runner snippets, inside the `kbase`
skill's own directory), the harness's `kbase` MCP server entry in the harness's MCP settings file —
the project's own, or, under mage, the plugin's at ROOT — and one runner include line in the
project's own justfile or Makefile, never into this repository's own — except a plugin harness,
which is not a repo project and writes no runner include line and creates no `Makefile`.
The choice is sticky per harness directory: an install whose ROOT already
holds the installed `kbase` executable — at `skills/kbase/kb-tools/kbase` or `kbase.exe`, or in the
`agents/kb-tools/` an earlier version wrote — is a kb install, refreshing the runner snippets and
reusing the executable installed there unless the invocation carries a new one. The signal is that
executable, never the directory holding it. Exclusion is decided once per definition, on its name,
and never per rendered file: a base install keeps no kb-set definition it finds — under that type
the definition is stale, every file of it generated here is removed and named in the report, and a
skill's directory is removed once that leaves it empty, so no run leaves a *generated* router
standing beside generated references it dropped. A mage install is always a kb install, so the
exclusion never applies to it. A file under `skills/<name>/` that carries no
generated banner is its project's own and is never touched. Either type removes each tree an earlier
version installed — `agents/kb_tools/` (underscore), `agents/kb-tools/` and `agents/liaison_tools/`
— naming each it removed, and reporting the underscore tree's removal on a run that excluded kb. A
kb install with no `kbase` executable to write — none named as a distribution, none already
installed — refuses, writing nothing.

The kb set scores through the `kbase` server rather than through an agent: `score` is a tool of that
server, and the `kbase` skill drives it. Its call answers once the run's ledger and pid stand, not
when the walk ends, and the run it started is followed with `wait`, `status` and `cancel`. A run
enumerates the KB's scoring set itself, lands one value per item and records a per-item outcome, so
re-running it resumes. It never supplies two scores — a work's rigor and a `founds` edge's
bearing, both because the work lies outside the corpus. The user authors those through `set-rigor`
and `set-bearing`.

The generator and install need Python 3.11 or later on the host; the kb set's toolchain is a binary
and needs no Python. `README.md` states what that binary asks of the host.

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
file whose type takes a `#` comment carries an installed banner at its top, below its shebang where
it has one. No banner sits where it changes how the file is read. Every other copied file — and
every file a harness ships, whatever its type — is installed byte-verbatim and unstamped.

Every path written inside a definition body — a file the agent is told to `Read`, a script it
invokes — is written against the installing harness's project directory —
`<harness-dir>/agents/...` for a definition, `<harness-dir>/adj-tools/...` or
`<harness-dir>/skills/kbase/kb-tools/...` for a shipped package's script, which are
`.claude/agents/...`, `.claude/adj-tools/...` and `.claude/skills/kbase/kb-tools/...` under the
default claude harness — not against the repository's own path: that is where the installed file
actually lives, and the path it must resolve from inside a consuming session. The same holds for
the project's scratch directory, named as the harness names it. A project's agents file is named
`AGENTS.md` under claude and opencode, whose user directory is a separate scope; where the
destination is the harness's own directory — mage — the harness's name is used, so the file is
`CLAUDE.md` (Harness Agents File, below).

Every file directly under `agents/` matching `*.md` whose definition is an agent, its frontmatter
carrying dispatch keys (`name`, `description`, `model`), is a dispatchable agent definition — the
rule holds without exception, and its rendered frontmatter spells those keys as the installing
harness reads them.

The repository's fourth file class is a **shipped package**: plain code, never rendered and so never
carrying a `!GENERATED!` banner in this repository, its tests beside it where it has them, installed
by explicit mapping to a frozen destination under the install ROOT — frozen because an installed
consumer's own artifacts, such as the runner include line an install writes into the consumer's
justfile or Makefile, and the path the `kbase` MCP entry registers, name that destination directly
and cannot be asked to notice a source-side rearrangement. Its installed copy is stamped like any
other install emission whose filetype admits a comment: the `!INSTALLED!` banner, not `!GENERATED!`
— a shipped package is source taken as-is, never a render. `SHIPPED_PACKAGES` is the table of those
an install delivers by explicit mapping: each row a repository-top-level package and the destination
under the install ROOT it lands at, beside the three definition surfaces, under `adj-tools/`. It
holds no row today, so no install of this version delivers one. `kb-tools/` is a shipped package
installed at its own stated destination rather than by that table: `skills/kbase/kb-tools/`, inside
the `kbase` skill's own directory and so inside the `skills/` surface — the one package destination
outside `adj-tools/`, a skill carrying its tooling in its own directory — its runner snippets beside
the `kbase` executable an install writes, and not an importable package either, read by the consumer
through the runner include line and the `kbase` MCP server the same install writes. No package is a
definition: `adj-tools/` is outside the dispatch namespace entirely, and a package under a skill's
directory is neither its `SKILL.md` nor a supporting file it lists.

A harness's shipped files are the fifth class: copied as they stand, never rendered. A harness also
*renders* files of its own into ROOT — mage's manifest is the one — which are generated, not copied,
carry no banner, and are replaced whole.
An install copies the installing harness's set into ROOT — the harness directory itself — save a
file conditional on a run at install time (below), so a harness file lands at the path it holds
below that directory: opencode's sits at `<harness-dir>/plugins/guardrail.ts` today and claude's at
`<harness-dir>/hooks/guardrail.pl` (mage ships none), beside the surfaces and outside all three.
Each keeps its bytes and its mode: the install stamps nothing on them. Every such file carries an
`!INSTALLED! … adjagent` header in its first ten lines — the guardrail files' name this repository
and forbid edits — as the file's own text, which travels with it. A harness shipping none copies nothing, which
is not an error. A harness file may be conditional on a run at install time: claude's hook is
delivered only when one run of the script on the installing machine succeeds within a few seconds,
and is otherwise skipped, with the reason reported and the rest of the install unaffected. Both
guardrails block the same Bash commands — those that change a file behind the edit tools, such as
in-place `sed`, `perl` or `ruby` edits, redirects, `tee`, `cp` or `mv` onto an existing file, and
inline scripts that write — and allow writes into scratch. A relative target is judged against the
working directory of the call, scratch against the project directory, and a heredoc's body is not
read as shell. Claude's runs at session time and needs perl with core `JSON::PP`; an install also
registers it as a `PreToolUse` entry for Bash in the project's `.claude/settings.json`, whatever the
harness directory is, keeping every other byte of that file (Write Safety, below). The entry runs
the script only where it stands readable: where it is missing — a project that commits the settings
file but not the script — a Bash call reports the missing path on stderr and proceeds, and is not
blocked.

## Generation System

The mechanism behind every definition in the deployed surfaces guarantees three observable
properties, independent of how they are implemented (see ARCHITECTURE.md):

- **Single-sourcing.** Text shared across two or more definitions has exactly one source. Wherever
  rendered output shares text across definitions, that text is identical by construction — not by
  maintenance discipline that could silently drift apart.
- **Additive-only model tuning.** A family's tuning may extend a definition's base text at declared
  anchor points; it can never replace, suppress, or fork that text. A definition whose
  anchors the loaded family does not fill is byte-identical, below its banner, to its base render.
- **Tier-keyed tuning, with recorded provenance.** Every agent definition declares a tier —
  one of `highest`, `high`, `medium`, `low`, `lowest`, ordered by capability — and the family's tier
  map, the one model source on every harness, resolves it: the tier's family member is both what
  the definition is tuned against and the model it renders with. The tier map comes from the family,
  or whole from the tier-map argument. Each map argument covers all five tiers, naming each or
  giving one value for all and naming any exceptions; one leaving a tier unnamed is refused, with no
  fallback to the family. An optional alias map, with no
  default, renders an alias in place of each tier's member and changes nothing else, so what a
  definition is tuned for and what it dispatches on may diverge; it exists for a harness that
  resolves aliases through its own remapping, such as Claude Code's `ANTHROPIC_*` model variables,
  and any harness may use it. A tier-map value naming no tier and holding neither `=` nor `,` has a
  third reading — the whole map, that one value for every tier — on a harness whose vocabulary reads
  a bare value so; a harness whose vocabulary does not refuses it as no `tier=value` pair, and the
  alias map has no bare form anywhere. A harness declares the shape a rendered model must have — a
  model outside it fails the render before anything is written, naming the tier, the value, and the
  argument or family that supplied it — and the text each of its inherit words renders as, `inherit`
  among them; an empty rendering leaves the definition without a model line. Every generated
  definition's tuning line records the family's name, the tier map, the alias map where one was
  given, and the harness it was rendered for, so what it is tuned for and what it dispatches on are
  readable from the definition alone.
  Documents and commands declare no tier and stand outside this resolution; family-wide tuning text
  still fills their anchors. A family whose member-scoped tuning names a member no tier reaches — in
  neither its own tier map nor the effective one — is refused before anything is rendered.

An install that requests a tuning other than the default (Deployed Surfaces, above) renders the
generated definitions under it; Generated-Definition Integrity, below, holds for the tuning the
install was given exactly as it holds for the default one.

## Generated-Definition Integrity

Every definition in the deployed surfaces (`agents/`, `commands/`, `skills/`) is generated rather
than hand-authored — the partition is total, because a definition with no source here is never
rendered and so never reaches the product at all. A skill's supporting files are generated and
validated like any other render: the paragraph-sharing check (ARCHITECTURE.md, Structural rules)
covers a reference's body exactly as it covers a definition's own. The guest-extraction contract and
the rendered-line cap both govern outputs under `agents/`; neither applies to a reference, whose
reader is the session that navigated to it. For every definition and every file it produces:

- Its content is exactly what the generator renders for it from its source, deterministically; a
  rendered file whose source no longer exists is removed on the next install.
- Every banner claiming a definition is generated names the source it was rendered from and states
  that the file is not for local edit. A project that tracks the installed tree gets modification
  detection from its own git; one that does not is protected by the file being replaced whole on the
  next install, so no modification survives it.

A file without a generated banner is not a definition this repository produced, and is outside this
guarantee — Write Safety, below, is what governs meeting one at a generation target.

## Write Safety

An install overwrites every definition it renders where the target is absent or carries a generated
banner: the `!GENERATED!` line inside a frontmatter block, or the comment form a skill's supporting
file opens with. A harness-rendered file is ours when it holds the marker that file states about
itself, and any other file at that path refuses like any foreign target. Any other file at a target
— one a project wrote itself, a directory, a symlink — refuses the install with nothing written,
naming each such path. So does a symlink, or anything but
a directory, on the path from ROOT to such a target, since a write would pass through it or fail
there; what stands at or above ROOT is the operator's own and is not examined. It removes — naming each in its
report — every file under a deployed surface that it did not write and that carries a generated
banner, and with them any directory that leaves empty; a file with neither banner is never touched.
A shipped package's destination is replaced whole; the one thing a kb install leaves standing is the
`kbase` executable a previous install wrote, which it rewrites only when it carries a new one. A
file a harness ships is replaced whole on each install when the file already at its path carries
`!INSTALLED! … adjagent` in its first ten lines; any other file there refuses the install the same
way. It is never removed: the copy is one-way and no mirror, so a file this repository stops
shipping stays in the consuming project until that project removes it, outside the reach of every
prune. A harness-rendered file takes the same two rules: replaced whole on each install where it
holds the marker it states, and never removed, since prune walks the three surfaces only.
A claude install also edits a file the project owns, `.claude/settings.json`, to register the
guardrail hook: bytes outside the hook's own entry are kept, an earlier install's entry is replaced
in place, and the project's other hooks are never touched. An element is the hook's own only when
its command is exactly the one an install writes, so a hook of the project's that names some other
`guardrail.pl` stays the project's. One settings file serves the project whatever the harness
directory, so an install under a different `--subdir` replaces the entry of the first: a project
has one guardrail. A file it cannot edit safely — one with comments, more than one entry of ours, or
ours sharing an element with another command — is reported with the entry printed, and left alone.
So is a settings path that is a symlink, dangling or not, that lies behind a symlink or a
non-directory, or that is not a regular file; the report names which. A settings file that is not
UTF-8, or holds a `hooks` that is not an object (`null` included) or a `PreToolUse` that is not an
array, refuses the install with nothing written, as does a harness directory whose path holds a
`"`, `$`, backtick or `\` where the hook is to be registered, the entry being unable to name it. A
kb install's `kbase` settings file is held to the same, wherever it lives — under mage it sits at
the plugin root, inside ROOT: left alone where a symlink or non-regular file stands in the way,
refused where it is not UTF-8 or nests a non-object, `null` included, where the entry goes. A hook
skipped for a failed install-time run leaves the settings file and any script or entry an earlier
install wrote where they stand, and the report names those that are the install's own. An install's report names each
path it pruned; where the consuming project tracks the installed set, its git is the record of what an
install changed.

## Guest-Extraction Contract

Any definition's body — the content after its frontmatter — must be usable frontmatter-free as an
external (non-Claude) model's system prompt. The obligation attaches to definitions, not to their
outputs: every dispatchable definition must hold the property mechanically — dropping every line
through the one that closes the frontmatter block yields the body entire, losing no content and
needing no knowledge of what the block holds. The property is guaranteed where a definition is
built, not where it is read: the project's test suite, run before a change lands, refuses a
definition that would not extract, so none ships truncated. The install does not check it. The
extracted body does not carry the definition's `model:` pin, which stays in the frontmatter where
the harness render carries one: a caller that uses the body without `--agent`
carries the pin itself.

## Harness Agents File

The repository publishes a recommended operator agents file as one definition, rendered per
supported harness. It is installed only by explicit act, into a directory the operator names — the
harness's user-global directory or a project's own; `install` never installs it.

Agent directives live in `AGENTS.md`. Installed into the harness's user-global directory, the file
takes the name that harness reads there — `CLAUDE.md` for Claude Code and mage, `AGENTS.md` for
opencode — and nothing else is written. For mage every destination is its own directory, so it
writes `CLAUDE.md` there and never reaches the `AGENTS.md` redirect rule below. Installed anywhere
else, it is `AGENTS.md`; a harness that reads another name gets that file as the one-line redirect
`@AGENTS.md`, created when absent and left alone when already present. A file of that other name
holding anything else is refused with nothing written: moving its content into `AGENTS.md` is the
operator's act, never the install's.

The installed file carries the repository's content as **one delimited block**, from its begin
marker line through its end marker line, recognised by their fixed ends so a block any earlier
revision wrote is still found; installation replaces that span and keeps every other byte of the
file as the operator's, writes an absent file whole, and refuses with nothing written a file without
exactly one ordered marker pair. A destination whose only content is one `@<path>` import is a
redirect followed one hop, within the named directory, and never rewritten itself; a longer chain,
or a target outside that directory, is refused with nothing written.

Edits made inside the block are not preserved. A write that changes the file keeps one rolling
backup of the prior content beside it; identical output writes nothing, so installing twice changes
nothing. Installation is refused while the generator's sources carry uncommitted changes.
Publishing an improvement is a manual edit to the agents-file definition.

Neither direction is a symlink, so a write to this repository can never silently rewrite live
operator configuration. The install writes a regular file, and refuses a symlink in place of the
file or its backup.
