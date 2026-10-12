"""kb-start and kb-next: the two commands that open a KB reading session with the docent, one for the
first question and one for the question a topic switch left behind.

Both locate the KB the same way, or one of them is wrong. Each body's first line is what the harness
lists the command by, so it reads as the description.
"""

from adjagent import text as t
from adjagent.definition import Definition
from adjagent.vocabulary import Kind

_LOCATE_THEN_LOAD_DOCENT = """## Locate the KB

Before reading anything, establish where the KB is. Probe in order:

1. `./kb-root/entry-point.md` **and** `./kb-root/.index/` both exist → **KB root** `./kb-root`, **project root** `.`
2. otherwise `./entry-point.md` **and** `./.index/` both exist → **KB root** `.`, **project root** `..`
3. otherwise **stop and ask.** Name both probes you ran, and say that this command runs from the project root (the directory holding `kb-root/`) or from `kb-root/` itself. Do not search the tree for a KB — section directories carry their own `entry-point.md`, and a search finds the wrong one.

The `.index/` sibling is what the probes turn on: it is what makes a directory a viable KB root rather than a section inside one.

From here, every file path resolves against the located **KB root**, and every tool invocation anchors to the located **project root** — `PYTHONPATH=<project-root>/{harness_dir}/agents`.

Then, in order:

1. Read `<project-root>/{harness_dir}/agents/kb-docent.md` — that definition is who
   you are for this session."""

DEFINITIONS = (
    Definition(
        name="kb-start",
        kind=Kind.COMMAND,
        body=f"""Open a knowledge-base reading session: locate the KB, load the docent, and take the user's first
question.

{_LOCATE_THEN_LOAD_DOCENT.format(harness_dir=t.PROJECT_HARNESS_DIR)}
2. Read `entry-point.md` from the KB root, and `session/covered-topics-index.md` if it exists.

You are the docent. Wait for the first question.""",
    ),
    Definition(
        name="kb-next",
        kind=Kind.COMMAND,
        body=f"""Continue a knowledge-base reading session on a new topic: locate the KB, load the docent, and answer
the question left in the handoff.

{_LOCATE_THEN_LOAD_DOCENT.format(harness_dir=t.PROJECT_HARNESS_DIR)}
2. Read `session/new-topic.md` from the KB root.

You are the docent. Respond to the question at the end.""",
    ),
)
