### Install entry

`just install` and `just install-with-kb` are one-line recipes over `python3 -m adjagent install
"$@"`, the second adding `--with-kb`; the installed `adjagent install` is the same verb (Packaging). The verb takes TARGET, its first non-flag argument, and
`adjagent/install_target.py` resolves it, writing nothing: `resolve_install_target` normalises the
target lexically — made absolute, `..` collapsed, symlinks not followed — and returns the harness,
the harness directory built from that path (`InstallTarget.harness_dir`), and the project root
(symlinks followed). The harness and harness directory follow
SPEC.md, Install destination; every directory name is read from the `Harness` values
(`project_harness_dir`, `user_harness_dir`, and `plugin_parent_dir` for a plugin), and the
home-directory comparison follows symlinks. A target that is a literal `~` is refused with a hint
that the shell did not expand it. The resolver decides neither ROOT nor whether the install is
user-level; `cli.py` passes the harness directory to `install`, which computes
`ROOT = harness_dir / harness.plugin_dir` and decides user-level from `user_dir_harnesses(harness_dir)`
naming the harness, whatever the route to it, and
then renders and prunes and skips the packages, resource files, guardrail and the runner include line
(the kb MCP entry is written at user level where `McpSettings.site` is `HARNESS`, below). Prune, the legacy trees and
the agents file are all in terms of the harness directory, which holds ROOT. `install.py` writes the agents file in the harness
directory for a standalone plugin whose harness directory is
not the project root, and for a user-level install given `--install-global-agents-file`, a flag a
project install ignores. Only the second is refused while `adjagent/` has uncommitted changes
(`agents_file.refuse_uncommitted`, called only when the install is user-level): no project install is,
the plugin below a project included. The verb takes no `kbase` argument: it
writes, copies, verifies and locates no `kbase` executable. It refuses, with nothing written, a
TARGET that is not an existing directory; a harness it cannot tell, or two harness directories in
the target, without `--harness`; a harness directory or ROOT that exists and is not a directory
("is not a directory"); either that is this repository (refused only when running from a clone) or inside a source it copies
from — a shipped package's, the kb toolchain's, or a harness's resource tree — and, on a project install only, a ROOT
outside the project root it is given: a user-level install skips that check, so a user directory that
is a symlink out of home is accepted. The refusals name the normalised path. So does a render or harness-resource target
holding a file without this repository's banner, or with a symlink or non-directory on its path
below ROOT; and a harness settings file the install writes into — the MCP settings file on a kb
install — that is not UTF-8 or holds the wrong type, `null` included, where the entry goes. A file a
retired entry is removed from is no refusal: removal leaves one it cannot edit alone
([Guardrail registration](guardrail-registration.md)). Every such check, the agents file's included, runs
before the first write, and ROOT itself is created after them. The target
refusal names every failing path at once; a settings or entry refusal names the one it met. A
settings path that is a symlink or not a regular file is no refusal: the merge reports it and leaves
it (below).

