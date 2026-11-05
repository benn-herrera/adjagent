# Harness agents file

The agent definitions assume a set of operator-level working rules, published as one definition
(`adjagent/definitions/harness_agents_file.py`) and rendered per harness. Among them: a project may
keep its contract documents diced, as trees under `PROJECT_DOCS/`. Before planning, briefing or
dispatching an agent, accepting returned work or making a checkpoint commit, the file tells the
session to load the `dev-process` skill ([Definition sets](definition-sets.md)). The file also
requires code that calls a network API to follow the usage guidelines provided for it.

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

## What it replaces

The install replaces only the block between the `adjagent` marker lines and keeps everything outside
it; put your own rules outside the markers. Edits inside the block are not preserved. An absent file
is written whole, and a file with no marker lines gets the block appended at its end after a blank
line, every existing byte kept.

- If the destination holds nothing but a single `@<path>` import, the install goes into that target
  and leaves the redirect alone. A redirect to another redirect, or to a file outside `<dir>`, is
  refused for you to merge by hand.
- A file with marker lines other than one begin line followed by one end line is refused with
  nothing written, as is any run from a clone while `adjagent/` has uncommitted changes.
- A write that changes the file keeps one rolling `backup.<name>` of what it replaced.

## Up to date and `--dry-run`

Identical output writes nothing, so installing twice changes nothing: the second run reports the
directory up to date, exits 0 and creates no backup.

`--dry-run` runs the same judgment and writes nothing. It prints whether the agents file, and any
redirect the install would create, would be created or changed, with paths relative to `<dir>`; where
nothing would change it says the directory is up to date.
