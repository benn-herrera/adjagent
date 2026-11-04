"""adjagent: the skill that tells a consuming project's session how the agent set adjagent installed
there is changed, updated and inspected."""

from adjagent.definition import Definition
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="adjagent",
        kind=Kind.SKILL,
        description=(
            "Use when the user wants to change, update or inspect the agent, command and skill definitions "
            "adjagent installed in this project, or its installed version, or for global setup — "
            "the set or the agents file at user level — or when a file carrying "
            "adjagent's generated banner seems to need a change; NOT for the project's own code or documents."
        ),
        body="""**Changing the set.** Never edit an installed definition or the installed adjagent package: the
next `adjagent install` overwrites the definitions, and the next update of the package overwrites
the package, `site-packages/adjagent/` included. A behavior the project wants from its seats goes in
the project's own CONVENTIONS.md or AGENTS.md, which the seats read and no install writes. A
persistent change to the definitions themselves has two routes, because adjagent merges nothing
local into the set it generates: vendor the whole adjagent repository — a copy the user's
organization hosts — edit the definitions there and install from it, owning that copy from then on;
or fork adjagent and open a pull request. Otherwise the project uses the set as installed.

**Updating.** Raise the adjagent version where the project pins it — its dependency specification,
or the `AGENTS_VER` its justfile or Makefile sets — and install that version into the project's
environment. Preview with `adjagent install --dry-run`, then run `adjagent install`, each with the
target and flags the project already installs with.

**Running adjagent.** Where the project has a runner recipe for the install, run that recipe.
Otherwise — a user trying adjagent before writing one — install the release tag's
`git+https://github.com/benn-herrera/adjagent@<tag>` into a venv, the project's `.venv` for example.
Every other `adjagent` command runs as the `adjagent` of wherever it was installed:
`.venv/bin/adjagent …` for a venv install, `adjagent` on PATH for a pipx install. Every
`adjagent install`, the Inspecting dry run included, takes the project's target and flags.

**Global setup.** A user-level install — `adjagent install` with a harness's user directory as
TARGET — installs the definitions there and no tools; `--install-global-agents-file` also installs
the agents file there. `adjagent install-agents-file <dir>` installs the agents file alone, into a
harness's user directory for example. Both verbs take `--dry-run`.

**Inspecting** is `adjagent --version` and `adjagent install --dry-run`.

Everything else: `adjagent --help`.""",
    ),
)
