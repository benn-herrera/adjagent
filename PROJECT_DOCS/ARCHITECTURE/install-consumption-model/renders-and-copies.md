### Renders and copies

An install renders every included definition — its own output, then each supporting file a skill
lists — and every file the harness itself renders (mage's manifest), bar a definition the harness
declares it renders nothing for (`Harness.omits`), replaces each destination `_packages` names
whole with a copy, copies each file the installing harness ships into ROOT as it stands
— bar a guardrail script whose probe fails (below) — writes the renders over what is there, and
removes each file under `agents/`, `commands/` or `skills/` that this run did not write, that would
ship, and that is ours by its own carrier: a frontmatter block holding a `!GENERATED!` line, or a
comment line opening with it, which is how a skill's supporting file holds its banner. It then
removes each directory that leaves empty, up to its surface. That walk needs no carve-out for a
package destination: the table's destinations sit beside the surfaces, under `adj-tools/`, and the
kb toolchain's sits inside one — `skills/kbase/kb-tools/`, in the
`kbase` skill's own directory — where every file it holds is stamped installed or left unstamped,
never generated, so every file under a surface is still either ours or untouched. A kb-set name is
inside that would-ship vocabulary, so under a base install one this run did not write is stale and
goes — every one of its files, a skill's included. Every install also removes each tree in
`LEGACY_TREES`, naming each it removed: `agents/kb_tools/` (the pre-1.0 kb helper tree),
`adj-tools/kb-tools/` (where v0.11.x installed the kb toolchain), `agents/kb-tools/` (written only
by an unreleased build) and `agents/liaison_tools/`. A run that excludes kb reports the removal of
`agents/kb_tools/` with the advice to install with kb. A render that fails writes nothing. There is no hash or backup of a modified
file: a local edit that keeps the banner lives only until the next install, which rewrites the file
it touched or prunes it, while a file at a render target that has lost the banner, or is a directory
or symlink, refuses the install; where the consuming project tracks the installed set, its git is
the record of what an install changed.

The package copy skips a vocabulary of names matched at any depth (test directories, caches,
`.DS_Store`, `.bak` files, the project documents) and carries the executable bit. A copied file of a
`#`-comment type (`.py`, `.sh`, `.mk`, `.just`) takes the installed banner; any other file
is copied byte-verbatim.

The harness resource copy borrows that vocabulary and nothing else from the package path:
`harness_resource_copies` reads `resources/<harness>/` and writes each file into ROOT with
`copyfile` and `copymode`, so it lands as the harness ships it — no suffix is stamped, whatever the
file's type, and a header a file already holds travels with it as the file's own text. A guardrail
script is the exception to copying every file: it joins the copies only when the probe below
passes. Before the first write, a target that exists must be a regular file, not a symlink, with a
line matching `!INSTALLED! .* adjagent` among its first ten; one unreadable or without it refuses
the install. No component between ROOT and any render or resource target may be a symlink or a
non-directory (`_blocked_component`); one that is refuses the install in the same refusal, and
components at or above ROOT are not examined. Package destinations are exempt from both checks:
this repository owns those entire and replaces them whole. The resource
files join the same `copies` list as the packages', so the prune's `keep` holds them and the report
counts them: a harness file never reads as a stale render, and the report line says `copied files`
for the lot. The copy is one-way, not a mirror — `prune` owns the three rendered surfaces and nothing
outside them — so a resource this repository stops shipping stays in a consumer until that project
removes it. A harness-rendered file is a third target class beside those two: recognised by the
marker it states about itself, and refused where a file at its path does not hold it.

