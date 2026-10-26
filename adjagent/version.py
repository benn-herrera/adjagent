"""The one place adjagent's version is written down.

`VERSION` is bare `X.Y.Z`: the `version` verb prints it for the tag recipes to read. No rendered
file carries it except mage's `.claude-plugin/plugin.json`, whose purpose is to; no reference slot
is rendered for mage, so a bump still churns nothing under `rendered/`.
"""

VERSION = "0.12.3"
