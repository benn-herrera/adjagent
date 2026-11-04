### Install entry

`just install` and `just install-with-kb` are one-line recipes over `python3 -m adjagent install
"$@"`, the second adding `--with-kb`; the installed `adjagent install` is the same verb (Packaging). The verb takes TARGET, its first non-flag argument, and
`adjagent/install_target.py` resolves it, writing nothing: `resolve_install_target` normalises the
target lexically — made absolute, `..` collapsed, symlinks not followed — and returns the harness,
ROOT built from that path, and the project root (symlinks followed). The harness and ROOT follow
SPEC.md, Install destination; every directory name is read from the `Harness` values
(`project_harness_dir`, `user_harness_dir`, and `plugin_parent_dir` for a plugin), and the
home-directory comparison follows symlinks. A target that is a literal `~` is refused with a hint
that the shell did not expand it. The resolver does not decide whether the install is user-level:
`install` does, from `user_dir_harnesses(ROOT)` naming the harness, whatever the route to ROOT, and
then renders and prunes and skips the packages, resource files, guardrail and kb emissions. `install.py` writes the agents file at ROOT for a plugin whose ROOT is
not the project root, and for a user-level install given `--install-global-agents-file`, a flag a
project install ignores. The verb takes no `kbase` argument: it
writes, copies, verifies and locates no `kbase` executable. It refuses, with nothing written, a
TARGET that is not an existing directory; a harness it cannot tell, or two harness directories in
the target, without `--harness`; a ROOT that exists and is not a directory ("is not a
directory"); a ROOT that is this repository (refused only when running from a clone) or inside a source it copies
from — a shipped package's, the kb toolchain's, or a harness's resource tree — and, on a project install only, a ROOT
outside the project root it is given: a user-level install skips that check, so a user directory that
is a symlink out of home is accepted. The refusals name the normalised path. So does a render or harness-resource target
holding a file without this repository's banner, or with a symlink or non-directory on its path
below ROOT; a harness settings file that is not UTF-8 or holds the wrong type, `null` included,
where the entry goes — the MCP settings file on a kb install, and the guardrail's
`.claude/settings.json` on a claude install whose probe passes; and, on that install, a harness
directory the guardrail entry cannot name. Every such check, the agents file's included, runs
before the first write, and ROOT itself is created after them. The target
refusal names every failing path at once; a settings or entry refusal names the one it met. A
settings path that is a symlink or not a regular file is no refusal: the merge reports it and leaves
it (below).

