"""The one parse of ``show-status``'s checklist block.

``kb_pipeline`` writes the block (``checklist_lines``); the driver reads the
render back across a process boundary, through the ``kb_util show-status``
subprocess adapter (``ledger.show_status``). So the format travels as text and
is parsed here, once — a second regex over the same render is how two readings
of one format start to disagree.

Stdlib only.
"""

import re

from . import runlog

# The checklist block is the only thing in a render matching `^\[[x* ]\] `
# (kb_pipeline._print_report), which is what makes it liftable without knowing
# about the rest of the render. `[x]` is recorded; `[*]` and `[ ]` are not.
_CHECKLIST_RE = re.compile(r"^\[([x* ])\] (\S+)", re.MULTILINE)


def recorded_stages(render: str) -> frozenset[str]:
    """The recorded stage ids in a ``show-status`` render — a format, not prose."""
    markers = _CHECKLIST_RE.findall(render)
    # A render with no checklist at all would read as a build with nothing
    # recorded, which is a resumable position the walk would act on. That is
    # drift in the tool's output shape, not a pipeline outcome: exit 15.
    runlog.require(markers, "show-status printed no checklist block")
    return frozenset(stage for marker, stage in markers if marker == "x")
