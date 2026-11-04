### Version has one home

The version lives in `__version__` in `adjagent/__init__.py` alone, and `just tag` cuts `v<version>` from it. A
bump is a hand edit of that one constant, committed before the tag, since `just tag` refuses while
`adjagent/` is uncommitted. `pyproject.toml` reads it and holds no copy. No rendered file carries the version except mage's
`.claude-plugin/plugin.json`, whose whole purpose is to carry it. No reference slot is rendered for
mage, so a bump still churns nothing under `rendered/` and `just render-diff` after one shows
nothing.
