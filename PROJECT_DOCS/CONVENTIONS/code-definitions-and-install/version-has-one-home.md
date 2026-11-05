### Version has one home

The version lives in `__version__` in `adjagent/__init__.py` alone, and `just tag` cuts `v<version>` from it. A
bump is a hand edit of that one constant, committed before the tag, since `just tag` refuses while
`adjagent/` is uncommitted. `pyproject.toml` reads it and holds no copy. No rendered file carries the version except the plugin manifest,
`.claude-plugin/plugin.json`, whose whole purpose is to carry it; claude and mage render the one
manifest value. So after a bump, `just render-diff` against `reference-claude` and against
`reference-mage` each show exactly that file's version line, and every other slot shows nothing.
