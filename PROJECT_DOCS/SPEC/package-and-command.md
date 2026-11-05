## Package and Command

adjagent installs as a Python package on Python 3.9 or later, with no third-party runtime
dependency. Two sources install it: a release tag's git URL, `git+https://github.com/benn-herrera/adjagent@v<version>`,
or a built wheel. No package index publishes it.

The installed package provides the `adjagent` command. `python3 -m adjagent` is the same command:
both print the same `--help`, and the same arguments install the same product, byte for byte.

The other route is a clone of this repository, run through its runner (`just install`, Deployed
Surfaces). The install product is the same from either route.

A check that protects or assumes a clone holds only when adjagent runs from one. A worktree and an
editable install of a clone count as one. A wheel installed into a Python environment does not,
wherever the environment sits, including inside another project's repository. Run from an installed
wheel:

- ROOT being "this repository" is not refused, because there is no repository to protect; ROOT
  inside a source the install copies from is still refused (Install destination).
- A kb install writes the runner include line for any project, because the project cannot be this
  repository.
- Installing the harness agents file is not refused for uncommitted changes, because an installed
  package has no uncommitted state (Harness Agents File).

From a clone, every one of these checks holds as before; the uncommitted-changes refusal there
covers only the writes Harness Agents File names.
