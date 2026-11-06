### Version has one home

The version lives in `__version__` in `adjagent/__init__.py` alone, and `just tag` cuts `v<version>` from it. A
bump is a hand edit of that one constant, committed before the tag, since `just tag` refuses while
`adjagent/` is uncommitted. `pyproject.toml` reads it and holds no copy. Two rendered files carry the version, both filled from that constant: the plugin
manifest's `version` in `.claude-plugin/plugin.json` (claude and mage), and the agents file's begin
marker line (every harness). So after a bump, `just render-diff` shows the manifest line in the claude
and mage slots, the marker line in every slot, and nothing else. An installed marker is stamped
differently: it keeps the release that last changed the block's content, so a bump alone does not
change it.
