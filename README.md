# devpro

Unsupervised agent-written code rots quietly then fails suddenly. devpro installs a collaborative
AI development process into Claude Code, opencode, or mage that lets you build to last: you work with
the agents to design, plan, build, review, and deliver.

![kanban screenshot](images/kanban.webp)

*Work packages on the board `docdicer kanban` serves*

## What it asks of you

This process does not run itself, and it does not claim to be a 10X everyone-is-now-an-engineer super suit.
You collaborate on design, architecture, mechanisms, and standards. You have to know what good and bad look
like and you will need to exercise that judgment frequently.

## What it gets you

The installed skills, agents, tools, and AGENTS.md have been coordinated and tuned
to maximize leverage for your attention, minimize decision fatigue, and provide visibility of and
correction steps for the stepwise drift that is unavoidable in agentic coding processes.

My ballpark estimate is a 3X gain over unassisted engineering. It's not the much-hyped 10X of the
ad campaigns, but it is dead real and the output is production-grade. For evidence, look at the git
history of not only this project, but also:

- [linux-kernel-driver-sandbox](https://github.com/benn-herrera/linux-kernel-driver-sandbox)
- [go-inference-lab-bench](https://github.com/benn-herrera/go-inference-lab-bench)
- [kbase](https://github.com/benn-herrera/kbase)
- [docdicer](https://github.com/benn-herrera/docdicer)

I was able to stand up the kernel driver sandbox in a day to learn how to hand-code Linux
kernel device drivers. And the sandbox's learning harness was not sloppy garbage. It was designed
to be efficient, reusable, and transferable. The go-inference-lab-bench project went from a cold
start to a scratch inference engine in Go with proven llama.cpp equivalence and data-driven support
for multiple architectures and multiple loading formats in a little over a month. It does all of that
in just over 16K lines of runtime code, including vision tower support and an OpenAI-compatible HTTP server.

## Requirements and Supported Platforms

- Harness: claude, opencode, or mage; `--harness` takes these three names.
- Homebrew (macOS or Linux), to install devpro.

## Quick Start Guide

### Claude Code and opencode

Install devpro, then run its install from the project root:

```sh
brew install benn-herrera/tap/devpro
devpro install .
```

The install takes the harness from the `.claude/` or `.opencode/` directory inside the target.
Where the project holds neither, or holds both, it refuses and writes nothing; `--harness=claude`
or `--harness=opencode` on the install line settles either case.

Add the installed tree, the agent scratch space and the agents file's backup to the project's
`.gitignore`:

```text
.claude/
# agent scratch space
.claude-temp/
# the agents file's rolling backup
backup.AGENTS.md
```

For opencode, use `.opencode/` and `.opencode-temp/` in place of `.claude/` and `.claude-temp/`.

The install also adds include lines to the project's `justfile` or `Makefile` (a project with
neither gets a new `Makefile`) for the runner files it installs, and settles the project's agents
file in one of three ways:

- `AGENTS.md`, holding the devpro block;
- under claude, `AGENTS.md` and the one-line `CLAUDE.md` redirect to it;
- nothing, where the global agents file already holds the block, or where a hand-written
  `CLAUDE.md` stands where the redirect would go.

A hand-written `CLAUDE.md` refuses the install with exit 2 and nothing written: moving its content
into `AGENTS.md` is yours to do.

### Mage

Install devpro, then run its install into Mage's skills directory:

```sh
brew install benn-herrera/tap/devpro
mkdir -p ~/Mage/Skills
devpro install ~/Mage/Skills --plugin=devpro --harness=mage
```

This writes `~/Mage/Skills/devpro/`. `--plugin=kbase` writes `~/Mage/Skills/kbase/`, the
knowledge-base plugin. That plugin drives the `kbase` executable, which no devpro install provides
or checks: on macOS and Linux, install it with `brew install benn-herrera/tap/kbase` (0.11.1 or
later); native Windows is unsupported for the plugin. Restart Mage after installing it.

## Next: ask your agent

Start your coding harness, or, if a session was already open during the install, reload it: run
`/reload-plugins` or restart under Claude Code, restart under opencode, and, after installing the
kbase plugin, restart Mage. Then ask the session agent to load the `guide` skill: `devpro:guide` under
claude and mage, `devpro-guide` under opencode. It starts a design, explains how the development
process runs, tells you where your work stands, and shows the board. It also installs, updates,
inspects or changes what you just installed, and covers a file carrying devpro's generated banner
that seems to need a change.

## Updating

To update, run `brew upgrade devpro`, then the same install line with `--dry-run` added to preview
it, then without to apply it.

## Third Party Acknowledgements

Credit to Jason Coleman (https://github.com/sangrail) for the kanban-from-markdown idea

- **pytest** (the pytest developers, MIT): Python test runner
- **black** (Łukasz Langa and contributors, MIT): Python formatter
- **isort** (Timothy Crosley and contributors, MIT): Python import sorter
- **flake8** (Tarek Ziadé and contributors, Python Code Quality Authority, MIT): Python linter
- **docdicer** (Benn Herrera, MIT): context-saving reformatter and kanban server
- **kbase** (Benn Herrera, MIT): the knowledge-base program and MCP server the `kbase` plugin drives
