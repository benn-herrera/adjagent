"""kbase: the kbase skill and the definitions a knowledge-base project works with; a definition joins it
by a line here."""

from adjagent.plugin import Plugin

PLUGIN = Plugin(
    name="kbase",
    include=frozenset(
        {
            "kbase",
            "adjagent",
            "development",
            "architect",
            "python-coder",
            "prompt-engineer",
            "tech-writer",
            "shell-dsl-coder",
            "applied-mathematician",
            "economic-historian",
            "theoretical-economist",
            "prose-architect",
            "literature-scout",
        }
    ),
)
