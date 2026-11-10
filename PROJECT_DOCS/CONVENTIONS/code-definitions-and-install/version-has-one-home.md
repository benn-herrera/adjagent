### Version has one home

The version lives in `__version__` in `adjagent/__init__.py` alone, and `just tag` cuts `v<version>` from it. A
bump is a hand edit of that one constant, committed before the tag, since `just tag` refuses while
`adjagent/` is uncommitted. `pyproject.toml` reads it and holds no copy. Two rendered files carry the version, both filled from that constant: the plugin
manifest's `version` in `.claude-plugin/plugin.json` (claude and mage), and the agents file's begin
marker line (every harness). So after a bump, `just render-diff` shows the manifest line in the claude
and mage slots, the marker line in every slot, and nothing else. A recipe or script reads the
version from `python3 -m adjagent --version` and a harness's values through
`devtools/scripts/_harness-value.sh`, and writes neither down.

The mage release is cut by hand from the tagged version: `just mage-dist` signs with the
maintainer's default `gpg` secret key, so no agent runs it. The maintainer publishes the tarball and
its `.asc` to release `v<V>` of `benn-herrera/adjagent`.
