## Package and Command

The adjagent package installs on Python 3.9 or later, with no third-party runtime dependency. It has
two install sources: a release tag's git URL,
`git+https://github.com/benn-herrera/adjagent@v<version>`, or a built wheel. No package index
publishes it.

The installed package provides the `adjagent` command. `python3 -m adjagent` is the same command:
both print the same `--help`, and the same arguments install the same product, byte for byte.
Every `adjagent` command exits 0 on success and 2 on a refusal or an operating-system failure, printing `error: <message>` on
stderr.

adjagent also runs from a checkout of this repository, as `PYTHONPATH=<clone> python3 -m adjagent
install …` (Deployed Surfaces). The install product is the same from a checkout or from an installed package.

A check that protects or assumes a checkout holds only when adjagent runs from one. A worktree and
an editable install of a clone count as one. The adjagent package installed into a Python
environment does not, wherever the environment sits, including inside another project's repository.
Run from an installed package:

- A project install of either plugin writes its runner include lines for any project (Deployed
  Surfaces, Plugins).
- Installing the agents file is not refused for uncommitted changes (Agents File).

From a checkout, every one of these checks holds; the uncommitted-changes refusal there covers only
the writes Agents File names.
