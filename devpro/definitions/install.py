"""install: the skill that tells a consuming project's session how the agent set the `devpro` installer put
there is changed, updated and inspected."""

from devpro import clauses
from devpro.definition import Definition
from devpro.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="install",
        kind=Kind.SKILL,
        description=(
            "Use when the user wants to change, update or inspect the agent, command and skill definitions "
            "the `devpro` installer put in this project, or the installed devpro version, or for global setup — "
            "the set or the agents file at user level — or when a file carrying "
            "the devpro project's generated banner seems to need a change; NOT for the project's own code or documents."
        ),
        body=f"""**Changing the set.** Never edit a file carrying the devpro project's generated banner, or the
installed devpro Python package: the next `devpro install --plugin=<plugin>` for that file's plugin overwrites the
file, and the next update of the package overwrites the package, `site-packages/devpro/` included. A
behavior the project wants from its seats goes in the project's own CONVENTIONS.md or AGENTS.md, which
the seats read and no install writes. A
persistent change to the definitions themselves has two routes, because the devpro project merges nothing
local into the set it generates: vendor the whole devpro project's repository — a copy the user's
organization hosts — edit the definitions there and install from it, owning that copy from then on;
or fork the devpro project and open a pull request. Otherwise the project uses the set as installed.

**Updating.** Raise the devpro version where the project pins it — its dependency specification,
or the `DEVPRO_VER` its justfile or Makefile sets — and install that version into the project's
environment. Preview with `devpro install --plugin={clauses.PLUGIN_NAME} … --dry-run`, then run
`devpro install --plugin={clauses.PLUGIN_NAME} …`, each with the target and flags the project already
installs with.

{clauses.RELOAD_RULE}

{clauses.SIDE_BY_SIDE_RULE}

**Running `devpro`.** Where the project has a runner recipe for the install, run that recipe.
Otherwise — a user trying `devpro` before writing one — install the release tag's
`git+{clauses.REPOSITORY_URL}@<tag>` into a venv, the project's `.venv` for example.
Every other `devpro` command runs as the `devpro` of wherever it was installed:
`.venv/bin/devpro …` for a venv install, `devpro` on PATH for a pipx install. Every
`devpro install --plugin={clauses.PLUGIN_NAME}`, the Inspecting dry run included, takes the project's
target and flags.

**Global setup.** A user-level install — `devpro install --plugin={clauses.PLUGIN_NAME}` with a
harness's user directory as TARGET — installs the definitions there and no tools.
`devpro install-agents-file --plugin={clauses.PLUGIN_NAME} <dir>` installs the agents file, into a
harness's user directory for example. Both verbs take `--dry-run`.

**Inspecting** is `devpro --version` and `devpro install --plugin={clauses.PLUGIN_NAME} --dry-run`.

Everything else: `devpro --help`.""",
    ),
)
