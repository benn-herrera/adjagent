### Install entry

`just install` wraps `python3 -m adjagent install <project>/<subdir>` (`adjagent/install.py`);
`just install-with-kb` wraps the same verb with `--with-kb`. The verb takes no `kbase` argument: it
writes, copies, verifies and locates no `kbase` executable. It refuses, with nothing written, a ROOT
that is this repository or inside a source it copies from — a shipped package's, the kb toolchain's,
or a harness's resource tree — and a ROOT outside the project root it is given. So does a render or harness-resource target
holding a file without this repository's banner, or with a symlink or non-directory on its path
below ROOT; a harness settings file that is not UTF-8 or holds the wrong type, `null` included,
where the entry goes — the MCP settings file on a kb install, and the guardrail's
`.claude/settings.json` on a claude install whose probe passes; and, on that install, a harness
directory the guardrail entry cannot name. Every such check runs before the first write. The target
refusal names every failing path at once; a settings or entry refusal names the one it met. A
settings path that is a symlink or not a regular file is no refusal: the merge reports it and leaves
it (below).

