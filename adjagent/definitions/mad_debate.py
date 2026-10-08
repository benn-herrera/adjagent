"""mad-review and mad-design: the two commands that launch a debate, one per mode.

The modes diverge in two places beyond their nouns: design resolves its first token against a topic
library and review has none, and design's run name comes from the prose, after a topic, while
review's first token is the run name.
"""

from adjagent.definition import Definition
from adjagent.section import Prose
from adjagent.sections.mad import DebateCommand
from adjagent.vocabulary import HarnessText, Kind

_HOME = HarnessText.PROJECT_HARNESS_DIR

DEFINITIONS = (
    Definition(
        name="mad-review",
        kind=Kind.COMMAND,
        sections=(
            DebateCommand(
                mode="review",
                referee="mad-review-referee.md",
                first_token=Prose(
                    "**Review name**: the first token — a bare slug naming this review (`auth-flow`, "
                    "`installer-rewrite`). It names the output folder and the documents. Review mode has no topic "
                    "library: the first token resolves to no file, and the charter carries the whole methodology."
                ),
                target_bullet="path to the artifact under review (file or directory)",
                suggest_tail="the material rewards more independent looks",
                charter_term="charter",
            ),
        ),
    ),
    Definition(
        name="mad-design",
        kind=Kind.COMMAND,
        sections=(
            DebateCommand(
                mode="design",
                referee="mad-design-referee.md",
                first_token=Prose(
                    "**Topic name**: the first token — matches a file in `",
                    _HOME,
                    "/agents/mad/design-topics/[topic-name].md`. Load that file as the topic. If the file does not "
                    "exist, list available topics from `",
                    _HOME,
                    "/agents/mad/design-topics/` and halt.",
                ),
                target_bullet=(
                    "path to the problem statement. Either (a) an existing brief defining the open problem (file or "
                    "directory), or (b) an empty/not-yet-created output location — in case (b) the referee will "
                    "elicit the problem statement from the user interactively before dispatching participants"
                ),
                prose_name="\n  - A short design name (for output folder and document titles) — this one has no key",
                suggest_tail="the problem rewards more independent constructions",
                charter_term="brief",
            ),
        ),
    ),
)
