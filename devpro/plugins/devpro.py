"""devpro: every definition but the kbase skill, so a new definition joins it by existing."""

from devpro.plugin import Plugin

PLUGIN = Plugin(name="devpro", exclude=frozenset({"kbase"}))
