## Recipes

`just install <target> [--plugin=NAME]`, `just agents`, `just render`,
`just retake-reference`, `just install-agents-file <dir> [--plugin=NAME] [--harness NAME] [--dry-run]`,
`just tag` and `just check-wheel` reach `python3 -m devpro`: `install`,
`agents` and `install-agents-file` each run the verb directly in
one line; `install` takes `target *args` and `install-agents-file` takes `dir *args`,
and each forwards all of it as `"$@"`, so `--plugin=NAME`, `--harness NAME` and `--dry-run` all
reach the verb, which defaults the plugin to `context.DEFAULT_PLUGIN`;
`agents` installs the devpro plugin with `--plugin=devpro`; `render` and
`retake-reference` go through the private `_render-slot.sh`, which calls
`python3 -m devpro install <slot>/<plugin> --plugin=<plugin>` with
`--subdir=` once per plugin, into `<slot>/<plugin>/`, and through the private
`render-agents-file HARNESS OUT [PLUGIN]` script, which may be an
earlier revision's copy run inside that revision's worktree, where that worktree's own justfile
supplies `GEN` and the worktree holds the package `GEN` names. Its third positional, the plugin,
becomes `--plugin=<plugin>` where given and not empty; absent or empty, the script passes no
plugin and the verb's default applies, which the script does not name. A copy predating the third
positional ignores it. `tag` goes through `--version`, which
prints the version bare and nothing else, so the `v` of `v<version>` is the recipe's;
`check-wheel` through `--version` and through `install` (see the paragraph on `build` below).
Scripts read a harness's `HarnessText` values through
`python3 -m devpro harness --plugin=PLUGIN NAME KEY`
and the loaded plugins' names, one per line, through `python3 -m devpro plugins`: the maintainer
scripts' readers, both hidden from `--help` and not part of the consumer CLI. `harness` takes
`--plugin` because every plugin verb does, and the `{plugin}`-templated keys need a bound harness. `devtools/scripts/_harness-value.sh` is the one shell reader of harness
values, for `_render-slot.sh`; `devtools/scripts/_plugin-names.sh` is the one
reader of plugin names, which `_render-slot.sh` and `check-wheel.sh` loop over. The
version is read through `python3 -m devpro --version`. `just tag` reads it there to create the signed annotated tag `v<version>`: it refuses while
`devpro/` has uncommitted changes and again while that tag already exists, and it pushes nothing.
CONVENTIONS.md states where the version is written down, and the order a bump takes against its tag.

`just build` runs `python -m build --no-isolation` in `.venv` and runs no devpro.
`just check-wheel` reaches `python3 -m devpro` from the working tree for the version and for the
checkout side of its install comparison, and runs the `devpro` console script only from its
throwaway venv. Packaging states both.

**Toolchain.** This repository's justfile needs `just` 1.27.0 or later, the first release with the
`[doc]` recipe attribute, and runs its recipes under `bash`. That is not the floor a consuming
project needs, which is SPEC.md, Guide and README's 1.33.0 for the `import?` include line. The private `_venv` recipe creates `.venv`
where its python is absent. On macOS it makes it from `/usr/bin/python3` where present, the Xcode
command-line tools' Python 3.9.6, so the suite there runs on the Python 3.9 floor. It installs the
pinned tools with pip, so the first run needs the network. The suite needs `bun`, `perl` and
`kbase` (at least `KBASE_MIN_VERSION`) on `PATH`. `tests/test_guardrail.py`,
`tests/test_opencode_entry.py` and `tests/test_kbase_surface.py` fail rather than skip without
them, because a skip would hide drift.
