## Recipes

`just install <plugin> <target>`, `just install-agents-here`, `just render`,
`just retake-reference`, `just install-agents-file <plugin> <dir> [--harness NAME] [--dry-run]`,
`just mage-dist`, `just tag` and `just check-wheel` reach `python3 -m adjagent`: `install`,
`install-agents-here` and `install-agents-file` each run the verb directly in
one line; `install` takes `plugin target *args` and `install-agents-file` takes `plugin dir *args`,
and each forwards all of it as `"$@"`, so `--harness NAME` and `--dry-run` both reach the verb;
`install-agents-here` installs devpro; `render` and `retake-reference` go through
the private `_render-slot.sh`, which calls `python3 -m adjagent install <plugin>` with
`--subdir=` once per plugin, into `<slot>/<plugin>/`, and through the private
`render-agents-file HARNESS OUT [PLUGIN]` script, which may be an
earlier revision's copy run inside that revision's worktree. Its third positional, the plugin,
defaults to `devpro` in the script and not in `cli.py`; a copy passing only `"$1" "$2"` to `cli.py`
ignores it. `tag` goes through `--version`, which
prints the version bare and nothing else, so the `v` of `v<version>` is the recipe's;
`check-wheel` through `--version` and through `install` (see the paragraph on `build` below).
Scripts read a harness's `HarnessText` values through `python3 -m adjagent harness PLUGIN NAME KEY`
and the loaded plugins' names, one per line, through `python3 -m adjagent plugins`: the maintainer
scripts' readers, both hidden from `--help` and not part of the consumer CLI. The plugin is passed
to `harness` because a value such as mage's project harness directory is a `{plugin}` template that
needs a bound harness. `devtools/scripts/_harness-value.sh` is the one shell reader of harness
values, for `_render-slot.sh` and `mage-dist.sh`; `devtools/scripts/_plugin-names.sh` is the one
reader of plugin names, which `_render-slot.sh`, `mage-dist.sh` and `check-wheel.sh` loop over. The
version is read through `python3 -m adjagent --version`. `just tag` reads it there to create the signed annotated tag `v<version>`: it refuses while
`adjagent/` has uncommitted changes and again while that tag already exists, and it pushes nothing.
CONVENTIONS.md states where the version is written down, and the order a bump takes against its tag.

`just build` runs `python -m build --no-isolation` in `.venv` and runs no adjagent.
`just check-wheel` reaches `python3 -m adjagent` from the working tree for the version and for the
checkout side of its install comparison, and runs the `adjagent` console script only from its
throwaway venv. Packaging states both.

`just mage-dist` (SPEC.md, Mage Release) runs `mage-dist.sh` with `PROJECT_ROOT` and `GEN` and
depends on no other recipe. It builds from the working tree as it stands and makes no git check.
`resolve_names` validates before anything is removed or written: the version's shape. It reads the
agents file name through `_harness-value.sh <plugin> mage` and, per plugin, the plugin directory the
same way, as `_render-slot.sh` does; mage's project harness directory is a `{plugin}` template, so the
value needs the bound harness. It then removes any stale `stage/` and the four outputs of this
version, and sets an exit trap that removes `stage/` and all four outputs, so a build that fails at
any step, signing included, leaves none of them, for either plugin. Once signing succeeds the trap
is replaced by one that removes `stage/` alone, so only signed tarballs outlive the script. For each
plugin it rebuilds `dist/stage/<plugin>`: `python3 -m adjagent install <plugin>` with
`--subdir= --harness=mage`, then the agents file from `render-agents-file.sh mage <out> <plugin>`,
never `install-agents-file`. It tars `<plugin>/` from the stage with `COPYFILE_DISABLE=1` and
`--no-xattrs` (`test_build_layout` checks the latter), and signs each tarball with
`gpg --yes --detach-sign --armor` and gpg's default secret key. `test_build_layout` checks that the
kbase tarball's `kb-tools/` holds `runner-snippets/` alone and that its `.mcp.json` command is
`kbase`, and that the devpro tarball holds neither. `DIST_DIR` overrides `dist/` for tests only.

The tests run the script against the stub `gpg` of `tests/stubs/`, which answers only the signing
call and writes an `.asc` naming the tarball it signs, which `test_build_layout` checks. A signing
failure is tested with a failing `gpg` first on `PATH`: neither output and no `stage/` remains. No
test runs it against real `gpg`, and no test checks a signature.

