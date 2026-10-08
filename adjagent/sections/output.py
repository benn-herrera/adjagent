"""Report formats: what a coder seat's finished or stopped report holds."""

STOPPING_EARLY = r"""When stopping early (file conflict or scope expansion), use this format:
- **Discovered**: what was found — the conflict, the expansion, the design gap
- **Completed**: work finished before stopping, with files touched and a one-line summary of each change
- **Not started**: what was not yet attempted
- **Recommendation**: your assessment of how to proceed"""

# The pair is disjoint by quantifier: `Not changed` says IN SCOPE (deliberate
# non-action inside the assignment), `Seen and not acted on` says OUTSIDE. Keep
# both quantifiers if either bullet is reworded — without them the two collapse.
DONE_FORMAT = r"""When done:
- **Changed**: list files modified and a one-line summary of each change
- **Behavior deltas**: observable behavior your change altered that nobody asked for — including a side effect riding along with a change that was asked for, which is the half that goes unwritten. "None" is the expected entry; anything else is scope you are reporting, not a bonus you are delivering.
- **Not changed**: briefly note anything in scope you explicitly chose not to touch and why, if non-obvious
- **Verification**: the runner targets or commands you ran, and what they returned
- **Seen and not acted on**: what you noticed *outside* your assigned files and left alone — a capability already implemented where the task never pointed you, a second definition of a rule or a constant, a statement in another owner's document your change made false. Name each and where it lives. Include what looks like somebody else's obvious problem: whoever stands in the other half of a duplicate cannot see it either.
- **Contract gaps**: a rule you had to be told — by your brief, or mid-task — that this definition should already have carried, and any project trap you hit that the project's own conventions document does not state. Name the rule and the document that should hold it, and propose the wording. Editing this definition is never part of the assignment that found the gap.
- **Blockers**: any issues that prevent completing the task or that require human/coordinator decision"""

# This chunk owns the `## Output Format` heading, and nothing appends to the
# section: a template adding a field or a closing sentence under it is a second
# answer to what a finished report holds.
CODER_OUTPUT_FORMAT = f"## Output Format\n\n{DONE_FORMAT}\n\n{STOPPING_EARLY}"
