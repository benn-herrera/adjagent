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

- Harnesses: claude, opencode, or mage (so far). pi and codex are doable but aren't my daily drivers
- Homebrew (macOS or Linux), to install devpro.
- `git` on `PATH`.
- `just` 1.33.0 or later, where the project's runner is a justfile: a claude or opencode install
  writes include lines into it.
- `perl` on `PATH` with core `JSON::PP`, for the claude guardrail hook. Without them the claude install
  skips the hook, says why, and installs everything else.

## Quick Start Guide

### Claude Code and opencode

Install devpro, then run its install from the project root:

```sh
brew install benn-herrera/tap/devpro
devpro install .
```

Add the installed trees to the project's `.gitignore`:

```text
.claude/
# agent scratch space
.claude-temp/
__pycache__/
```

For opencode, use `.opencode/` and `.opencode-temp/` in place of the two claude entries.

The install detects your harness by the presence of a `.claude` or `.opencode` directory. It also
adds include lines to the project's `justfile` or `Makefile` (a project with neither gets a new
`Makefile`) for the runner files it installs, and writes the project's `AGENTS.md` (under claude, also
a one-line `CLAUDE.md` redirect to it). Commit the edited `justfile` or `Makefile` and the agents
file; the installed `.claude/` or `.opencode/` tree is not committed, which is why it is in `.gitignore`.

In a project the harness has never opened, create `.claude/` (or `.opencode/`) first, or add
`--harness=claude` (or `--harness=opencode`) to the install line.

To update, run `brew upgrade devpro`, then the same install line, with the same flags.

### Mage

Install devpro, then run its install into Mage's skills directory:

```sh
brew install benn-herrera/tap/devpro
mkdir -p ~/Mage/Skills
devpro install ~/Mage/Skills --plugin=devpro --harness=mage
```

This writes `~/Mage/Skills/devpro/`. `--plugin=kbase` writes `~/Mage/Skills/kbase/`, the
knowledge-base plugin; restart Mage after installing it.

To update, run `brew upgrade devpro`, then the same `devpro install` line.

## Next: ask your agent

Start your coding harness, or, if a session was already open during the install, reload it: run
`/reload-plugins` or restart under Claude Code, restart under opencode, and, after installing the
kbase plugin, restart Mage. Then ask the session agent to load the `guide` skill: `devpro:guide` under
claude and mage, `devpro-guide` under opencode. It starts a design, explains how the development
process runs, shows the board, and installs, updates, inspects or changes what you just installed.

## Third Party Acknowledgements

- **kanban from markdown** - idea from Jason Coleman (https://github.com/sangrail)
- **pytest** (the pytest developers, MIT): runs the test suite; installed into this repository's
  `.venv` by `just test`.
- **black** (Łukasz Langa and contributors, MIT): formats the Python source; installed into `.venv`
  by `just test` and run by `just format-python`.
- **isort** (Timothy Crosley and contributors, MIT): sorts Python imports; installed and run the same
  way.
- **flake8** (Tarek Ziadé and contributors, Python Code Quality Authority, MIT): lints the Python
  source; installed and run the same way.
- **setuptools** (Python Packaging Authority, MIT): the build backend `pyproject.toml` names;
  installed into `.venv`.
- **build** (Python Packaging Authority, MIT): the frontend `just build` runs; installed into
  `.venv`.
- **docdicer** (Benn Herrera, MIT): the link and tree checks behind `just check-links`, installed into
  `.venv` from its git tag. The installed `tools/docdicer` script installs it from the same tag
  into a venv beside the script when you ask it to.
- **@opencode/plugin** (the opencode project, MIT): the module the opencode plugin
  entry, `index.ts`, imports `Plugin` from to register the plugin; opencode supplies it, and nothing
  here bundles it.
- **perl** (Larry Wall and the Perl 5 porters, Artistic License or GPL, at your choice): runs the
  claude guardrail hook at session time, and the guardrail's tests; a host program you install.
- **bun** (Oven, MIT): runs the opencode guardrail's and plugin entry's TypeScript cases in
  `just test`; a host program you install.
