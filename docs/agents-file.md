# Harness agents file

The agent definitions assume a set of operator-level working rules, published as one definition
(`adjagent/definitions/harness_agents_file.py`) and rendered per harness. Among them: a project may
keep its contract documents diced, as trees under `PROJECT_DOCS/`. Before planning, briefing or
dispatching an agent, accepting returned work or making a checkpoint commit, the file tells the
session to load the `dev-process` skill ([Definition sets](definition-sets.md)). The file also
requires code that calls a network API to follow the usage guidelines provided for it.

The global file names `adjagent:` definitions, which resolve only where the adjagent plugin loads. In
a project or session where it does not (see [Plugin does not load](install-reference.md#plugin-does-not-load)),
those names point at nothing.

## Installing it

```sh
adjagent install-agents-file <dir> [--harness NAME] [--dry-run]
```

In a clone, `just install-agents-file <dir> [--harness NAME] [--dry-run]` does the same. `<dir>` is
`~/.claude`, `~/.config/opencode`, a project root, or a plugin directory under mage.

- The harness is inferred when `<dir>` is a harness's user-global directory. For a project root, or
  anything else, name it: `adjagent install-agents-file ~/projects/foo --harness=opencode`.
- Inference covers only a harness whose user directory is absolute, so mage is always named:
  `adjagent install-agents-file <dir> --harness=mage`.

The directives live in `AGENTS.md`. Into the harness's user-global directory the install writes the
file that harness reads there (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`). Anywhere else
it writes `<dir>/AGENTS.md`, and for a harness that reads another name it creates that file as the
one-line redirect `@AGENTS.md` (Claude Code's `CLAUDE.md`), leaving an existing one alone. A
`CLAUDE.md` there holding anything else is refused with nothing written: move its content into
`AGENTS.md` and replace it with `@AGENTS.md` yourself.

Under mage the destination is the plugin's own directory, so `adjagent install-agents-file <dir> --harness=mage`
takes `<plugins-parent>/adjagent` and writes `<dir>/CLAUDE.md` directly, never an `AGENTS.md`
redirect. `adjagent install <plugins-parent> --harness=mage` writes it too, so a normal install needs
no second step. For claude and opencode, `adjagent install ~ --harness=NAME
--install-global-agents-file` installs the agents file into the user-global directory as part of a
user-level install, with the same refusals.

## Where a project install puts it

`adjagent install` into a claude or opencode project keeps the block in exactly one place. The block
first reaches your global file by `install-agents-file` or `--install-global-agents-file` (above);
a project install never puts it there first.

- Your global agents file (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`) already holds the
  block: the install keeps it current there and removes any copy from the project's `AGENTS.md`. It
  removes only the block, backs the file up and keeps the file even if it is left empty, and says
  what it removed.
- It holds none: the install keeps the block in the project's `AGENTS.md`, creating the file if
  absent. Under claude it also creates `CLAUDE.md` as the one-line `@AGENTS.md` redirect where absent,
  and refuses, with nothing written, a `CLAUDE.md` holding anything else. With the block in your global
  file the install neither reads nor writes the project's `CLAUDE.md`.

Run from a clone while `adjagent/` has uncommitted changes, the write into your global file is
refused; the project's `AGENTS.md` and redirect are not.

Each block's begin marker line carries the adjagent version that last changed its content. The block
is rewritten when its content differs; an install older than the stamped version leaves it and prints
"not downgraded" with both versions. The full rule is in
[SPEC](../PROJECT_DOCS/SPEC/harness-agents-file.md).

### A project with several contributors

Symptom: a tracked `AGENTS.md` flips between contributors. Whether the block sits in the project file
depends on whether each contributor's global agents file holds it, so one contributor's install adds
the block and another's removes it.

Remedy: each contributor runs this in their own clone, so their copy may differ without showing as a
change:

```sh
git update-index --skip-worktree AGENTS.md
```

The flag lives in the clone's index, so it is not shared; every contributor sets it themselves.

Limit: git avoids touching a file with the flag set, so a pull that brings an upstream change to
`AGENTS.md` stops with "Your local changes to the following files would be overwritten by merge".
With the flag cleared, git sees the install's difference as a local change to `AGENTS.md`, so
discard or commit that difference first. Then clear the flag, pull, re-run the install and set the
flag again:

```sh
# first discard or commit the install's difference to AGENTS.md
git update-index --no-skip-worktree AGENTS.md
git pull
# re-run your install recipe, which rewrites the block
git update-index --skip-worktree AGENTS.md
```

### Symlinks

A symlink on any of these paths (your global agents file, a project's `AGENTS.md`, `CLAUDE.md`, or
the backup) is the file it names. The install reads and writes through it and keeps the link; where
the link dangles, it creates the file it names.

## What it replaces

The install replaces only the block between the `adjagent` marker lines and keeps everything outside
it; put your own rules outside the markers. Edits inside the block are not preserved. An absent file
is written whole, and a file with no marker lines gets the block appended at its end after a blank
line, every existing byte kept.

- If the destination holds nothing but a single `@<path>` import, the install goes into that target
  and leaves the redirect alone. A redirect to another redirect, or to a file outside `<dir>`, is
  refused for you to merge by hand.
- A file with marker lines other than one begin line followed by one end line is refused with
  nothing written. Run from a clone while `adjagent/` has uncommitted changes, an install into a
  harness's user-global directory is refused too; one into a project directory is not.
- A write that changes the file keeps one rolling `backup.<name>` of what it replaced.

## Up to date and `--dry-run`

Identical output writes nothing, so installing twice changes nothing: the second run reports the
directory up to date, exits 0 and creates no backup.

`--dry-run` runs the same judgment and writes nothing. It prints whether the agents file, and any
redirect the install would create, would be created or changed, with paths relative to `<dir>`; where
nothing would change it says the directory is up to date.
