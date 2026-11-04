## Sanctioned Invocation

A recipe body longer than three command lines is a script in `devtools/scripts/`, named for its
recipe, and the recipe is the line that runs it, handing it the variables it reads as an env
prefix; a shorter body stays in the justfile. `just install`,
`just install-with-kb`, `just install-agents-here`, `just render`, `just retake-reference`,
`just install-agents-file <dir> [--harness NAME] [--dry-run]`, `just mage-dist`, `just tag` and `just check-wheel` reach
`python3 -m adjagent`:
`install`, `install-with-kb`, `install-agents-here` and `install-agents-file` each run the verb
directly in one line; `install-agents-file` takes `dir *args` and forwards all of it as `"$@"`, so
`--harness NAME` and `--dry-run` both reach the verb; `render` and `retake-reference` go through the private
`_render-slot.sh`, which calls `python3 -m adjagent install` with `--subdir= --with-kb`, and through the
stable private `render-agents-file HARNESS OUT` script, which a later revision calls inside a
worktree of an earlier one, so its name and two arguments do not change incompatibly; and `tag`
through `--version`, which prints the version bare and nothing else, so the `v` of `v<version>` is the
recipe's; `check-wheel` through `--version` and through `install` (see the paragraph on `build` below). Scripts read a harness's five `HarnessText` values through
`python3 -m adjagent harness NAME KEY`, never from a copy of them — `_harness-value.sh` is the one
shell reader, for `_render-slot.sh` and `mage-dist.sh` — and the version through `python3 -m adjagent --version`, never restated in a recipe or a
script. `just tag` reads it there to create the signed annotated tag `v<version>`: it refuses while
`adjagent/` has uncommitted changes and again while that tag already exists, and it pushes nothing.
CONVENTIONS.md states where the version is written down, and the order a bump takes against its tag.

`just build` runs `python -m build --no-isolation` in `.venv` and runs no adjagent.
`just check-wheel` reaches `python3 -m adjagent` from the working tree for the version and for the
checkout side of its install comparison, and runs the `adjagent` console script only from its
throwaway venv. Packaging states both.

`just mage-dist` (SPEC.md, Mage Plugin Distribution) runs `mage-dist.sh` with `PROJECT_ROOT` and
`GEN` and depends on no other recipe. `resolve_names` validates before anything is removed or
written: the version's shape. It reads the agents file name and the plugin directory through
`_harness-value.sh mage`, as `_render-slot.sh` does. It then removes any stale `stage/` and the two
outputs of this version, and sets an exit trap that removes `stage/` and both outputs, so a build
that fails at any step, signing included, leaves none of them. Once signing succeeds the trap is
replaced by one that removes `stage/` alone, so only a signed tarball outlives the script. It rebuilds `dist/stage/adjagent`: `python3 -m adjagent install` with `--subdir= --harness=mage`, then the
agents file from `render-agents-file.sh mage`, never `install-agents-file`, which refuses while
generator sources are uncommitted and so would make a build depend on the tree's cleanliness. It
tars `adjagent/` from the stage with `COPYFILE_DISABLE=1` and `--no-xattrs`, so the tarball carries
neither AppleDouble entries nor extended-attribute pax headers (`test_build_layout` checks the
latter), and signs it with `gpg --yes --detach-sign --armor` and gpg's default secret key. The
tarball holds no `kbase` executable and no installer: its `kb-tools/` holds `runner-snippets/`
alone, and its `.mcp.json` command is `kbase` (`test_build_layout`). `DIST_DIR` overrides `dist/`
for tests only.

The tests run the script against the stub `gpg` of `tests/stubs/`, which answers only the signing
call and writes an `.asc` naming the tarball it signs, which `test_build_layout` checks. A signing
failure is tested with a failing `gpg` first on `PATH`: neither output and no `stage/` remains. The
real signed build is the operator's: no test or agent runs it
against real `gpg`, and no test checks a signature.

