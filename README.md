# devpro

Unsupervised agent-written code rots quietly then fails suddenly. devpro installs a collaborative
AI development process into Claude Code, opencode and Mage that lets you build to last: you work with
the agents to design, plan, build, review, and deliver.

![A kanban board with the columns Roadmap, Design, Drafted, Dispatchable, In progress and Landed; each work-package card shows its rating, mechanical or expert, and its lifetime](docs/images/kanban.webp)

*Work packages from the 0.16.0 release on the board `docdicer kanban` serves: the roadmap, the
design under way, then each package by state, rated mechanical or expert.*

## What it asks of you

This process does not run itself, and it does not claim to be a 10X everyone-is-now-an-engineer super suit.
You collaborate on design, architecture, mechanisms, and standards. You have to know what good and bad look
like and you will need to exercise that judgment frequently.

## What it gets you

The installed skills, agents, tools, and AGENTS.md/CLAUDE.md have been coordinated and tuned
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

## How it works

The process is the `development` skill. The `devpro` plugin installs it with the agents that carry it
out.

1. **Design.** Your request becomes a design: requirements, decisions and the questions still open.
   You accept it before anything is planned.
2. **Plan.** The plan cuts the design into packages small enough for one agent, each with a done-line
   anyone can re-run. Routine packages run on a cheaper model; judgment calls get the strong one.
3. **Build.** Specialist agents carry out the packages, and you accept each one as it lands.
4. **Review**, at three levels:
   - Every plan, design and brief an agent works from is reviewed by a prompt-engineer agent before
     use.
   - Every plan ends with reviewers from each domain it touched, then a burndown of what they found.
   - Every few plans, a broader review catches drift no single change caused.
5. **Deliver**, as a sprint-based release process:
   - Plan the scope
   - Build the features
   - Harden the code
   - Deliver

## What it installs

- **Specialist agents**: a coder for each language, platform experts, an architect, a security
  reviewer, a tech writer and a prompt engineer ([Definition sets](docs/definition-sets.md)).
- **Working rules and a guardrail**: the operator rules every session loads
  ([Agents file](docs/agents-file.md)), and a hook that sends file changes through the edit tools
  ([Guardrail](docs/guardrail.md)).
- **One standard across handoffs.** A rule several agents carry is written once and rendered into each,
  so the architect who designs, the coder who builds and the reviewer who checks judge the work by the
  same text ([THESIS](PROJECT_DOCS/entry-point.md#what-is-new)).
- **Customizable to any harness, any model family.** The same definitions render for Claude Code, opencode and Mage, and
  per model family ([Model tuning](docs/model-tuning.md)). One runner recipe installs them.

The `kbase` plugin is separate: tooling for building and maintaining a knowledge base from a canonical
corpus ([Knowledge base](docs/knowledge-base.md)).

## Requirements and Supported Platforms

- `python3` 3.9 or later with its `venv` module, and `git` on `PATH`.
- The runner include lines either plugin's project install writes need `just` 1.33 or later, if the
  project's runner is a justfile.
- Harnesses: claude (Claude Code), opencode and mage.

The full list, optional requirements and the kbase plugin's included:
[Installing](docs/installing.md#requirements).

## Quick Start Guide

Add the recipe for your project's runner. It installs devpro, pinned to `DEVPRO_VER`, into the
project's `.venv/` (the project's existing one, or one it creates), then installs the `devpro` plugin
into the project for both harnesses ([Plugins](docs/installing.md#plugins) says what each plugin holds).

A project that uses one harness drops the other harness's `install` line.

Justfile:

```just
DEVPRO_VER := "0.17.0"
VENV := justfile_dir() / ".venv"
PYTHON := "\"" + VENV + "/bin/python" + "\""
DEVPRO := "\"" + VENV + "/bin/devpro" + "\""
agents:
  #!/usr/bin/env bash
  set -euo pipefail
  [[ -x {{PYTHON}} ]] || python3 -m venv --upgrade-deps "{{VENV}}"
  [[ -x {{DEVPRO}} && "$({{DEVPRO}} --version)" == "{{DEVPRO_VER}}" ]] || \
    {{PYTHON}} -m pip install "git+https://github.com/benn-herrera/devpro@v{{DEVPRO_VER}}"
  {{DEVPRO}} install . --harness=claude
  {{DEVPRO}} install . --harness=opencode
```

Run `just agents`. The recipe never recreates or clears an existing `.venv`, and runs pip only when
the venv's devpro is not the pinned version.

A project install also writes the docdicer include line into the project's `justfile` or `Makefile`,
creating a `Makefile` where there is neither. That runner file is tracked: commit it
([Runner include lines](docs/install-reference.md#runner-include-lines)).

Under claude, invoke the plugin's agents and skills as `devpro:<name>`, and run
`/reload-plugins` (or restart Claude Code) after an install for new definitions to register.

Add the installed trees to the project's `.gitignore`:

```text
.claude/
.opencode/
.venv/
__pycache__/
```

The ignored trees are not committed: on each clone, run the install recipe again to re-create them.

[Installing](docs/installing.md) has the rest: the Makefile recipe, the agents file the install
writes, what to commit, previewing, updating, the kbase plugin, running devpro by hand and
customizing the set. Mage installs from a release tarball
([Mage plugin release](docs/mage-release.md)).

## More documentation

- [Installing](docs/installing.md): requirements, plugins, the Makefile recipe, the agents file,
  previewing, updating, running by hand, customizing.
- [Mage plugin release](docs/mage-release.md): downloading, verifying and unpacking a mage plugin.
- [Install reference](docs/install-reference.md): target and harness resolution, the install
  directory of each plugin, user-level installs, what an install writes, refusals.
- [Guardrail](docs/guardrail.md): the hooks that block shell writes behind the edit tools.
- [Agents file](docs/agents-file.md): the operator-level working rules.
- [Model tuning](docs/model-tuning.md): families, anchors and tier maps.
- [Definition sets](docs/definition-sets.md): the agents and skills of each plugin.
- [Knowledge base](docs/knowledge-base.md): the kbase plugin and its toolchain.
- [Development](docs/development.md): building, testing, layout, releasing, authoring a family.
- [Agent sandboxing](agent-sandboxing/README.md): a checklist for running an agent harness as a
  separate, unprivileged local user. It is accident protection, not hack-proofing.
- [docs index](docs/index.md), and the project's contract documents under `PROJECT_DOCS/`:
  [THESIS](PROJECT_DOCS/entry-point.md), [SPEC](PROJECT_DOCS/SPEC/entry-point.md),
  [ARCHITECTURE](PROJECT_DOCS/ARCHITECTURE/entry-point.md),
  [CONVENTIONS](PROJECT_DOCS/CONVENTIONS/entry-point.md).

## Third Party Acknowledgements

What devpro installs into a project (`agents/`, `commands/`, `skills/`) is stdlib-only Python and
shell with no third-party dependencies. Everything below is used by this repository's development,
build and documentation checks; none is bundled.

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
