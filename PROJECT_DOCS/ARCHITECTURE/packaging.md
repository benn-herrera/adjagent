## Packaging

How the package and command of SPEC.md, Package and Command are built. `pyproject.toml` at the
adjagent project root is the whole build configuration.

- **Backend.** setuptools (`setuptools.build_meta`). `[build-system] requires` is `setuptools>=77.0`, the first release that reads a PEP 639
  `license` string. The package has no runtime dependency (`dependencies = []`); `requires-python` is
  `>=3.9`.
- **Version.** `dynamic = ["version"]` with `[tool.setuptools.dynamic]` reading
  `adjagent.__version__`. `pyproject.toml` holds no version literal (CONVENTIONS.md, Version has one
  home).
- **Package data.** `[tool.setuptools.package-data]` lists five patterns, `kb-tools/**/*`,
  `harnesses/resources/**/*`, `docdicer-tools/**/*`, `docdicer-tools/**/.*` and
  `development-tools/**/*`: the trees `install.py`
  reads through `PACKAGE_ROOT` (`HARNESS_RESOURCES_SOURCE` and each `SHIPPED_PACKAGES` source,
  the kb-tools, docdicer-tools and development-tools trees). The `.*` pattern exists because
  setuptools' `**/*` skips dotfiles, and the docdicer package ships a `.gitignore`. A glob sweeps in whatever sits
  under its tree, so `just check-wheel` holds the list equal to the tree: the wheel's non-`.py`
  files under `adjagent/` must be exactly the non-`.py` files git tracks or would track there
  (`git ls-files --cached --others --exclude-standard`). A shipped tree missing from the list fails
  it, and so does a stray file the list sweeps in.
- **Console script.** `adjagent = "adjagent.cli:main"`. argparse's `prog` is `"adjagent"`, so
  `adjagent --help` and `python3 -m adjagent --help` print the same text.
- **Offline build.** `just build` runs `python -m build --no-isolation` in `.venv` and writes the
  wheel and sdist to `dist/`, so it uses the venv's own setuptools, not a downloaded one. `.venv`'s
  install line in `python.just` therefore pins `setuptools~=82.0.1` and `build~=1.4.4`, the last
  releases that run on Python 3.9. The build makes no git check, following `mage-dist`
  (Recipes). A build also
  writes `adjagent.egg-info/` at the adjagent project root, which `.gitignore` covers. The sdist is
  a byproduct of the build: SPEC.md, Package and Command names no sdist install source, and
  `check-wheel` checks only that the sdist exists.
- **Check.** `just check-wheel [python]` builds, then installs the wheel into a throwaway venv under
  `.claude-temp/` made from `python` (default `/usr/bin/python3`, the Python 3.9 floor on macOS only). With `PYTHONPATH` unset and
  `GIT_CEILING_DIRECTORIES` at that scratch directory, it checks that `adjagent` imports from the
  venv, that the console script and `python -m adjagent` print the same `--help` and the checkout's
  version, that an install of each plugin into a scratch project equals the checkout's
  byte for byte (each exercises packages the other lacks), and that a mage devpro install writes
  `devpro/CLAUDE.md`. It is the `wheel` test surface:
  `just test wheel`, and the last step of an unscoped `just test`. A change to `pyproject.toml` or
  under `adjagent/` selects it in `just test-changed`.

**The checkout premise.** adjagent runs from a checkout when `PACKAGE_ROOT.parent` holds a `.git` entry: a directory in a
clone, a file in a worktree. `install_base.checkout_root` tests for it without running a subprocess, and
`REPO_ROOT` is that parent, or `None` outside a checkout. An editable install's `PACKAGE_ROOT` is
inside the clone. A wheel's, in site-packages, is not, and `git` there would answer for the
surrounding project. `PACKAGE_ROOT` and `REPO_ROOT` are defined in `install_base.py` alone.

| check | in a checkout | outside |
|---|---|---|
| `install_kb_include_line`: no include line for the repository itself, written by an install of the kbase plugin | skips that project | stands down: writes the line for any project |
| `uncommitted_sources`, before an agents-file write into a user harness directory | refuses on uncommitted sources; a failed `git status` refuses with `InputError` | returns `()` without running git |

Only a missing premise stands a check down: in a checkout nothing changes.
