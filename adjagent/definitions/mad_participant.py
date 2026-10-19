"""mad-participant-*: the four model-pinned debate seats.

They are separate definitions because the referee dispatches by `subagent_type`, so each pin needs
its own file presenting the identical contract.
"""

from adjagent import clauses
from adjagent.definition import Definition
from adjagent.vocabulary import ALL, Kind

_DESCRIPTION = (
    "Independent technical participant in a multi-model debate, review or design: produces the initial "
    "assessment or proposal and responds to debate rounds. Sees only the Alignment Assessor's structured "
    "map, never another participant's full output."
)

DEFINITIONS = (
    Definition(
        name="mad-participant-a",
        kind=Kind.AGENT,
        description=_DESCRIPTION,
        tools=ALL,
        tier="highest",
        color="#7C3AED",
        body=clauses.MAD_PARTICIPANT_CONTRACT,
    ),
    Definition(
        name="mad-participant-b",
        kind=Kind.AGENT,
        description=_DESCRIPTION,
        tools=ALL,
        tier="high",
        color="#6D28D9",
        body=clauses.MAD_PARTICIPANT_CONTRACT,
    ),
    Definition(
        name="mad-participant-c",
        kind=Kind.AGENT,
        description=_DESCRIPTION,
        tools=ALL,
        tier="medium",
        color="#5B21B6",
        body=clauses.MAD_PARTICIPANT_CONTRACT,
    ),
    Definition(
        name="mad-participant-d",
        kind=Kind.AGENT,
        description=_DESCRIPTION,
        tools=ALL,
        tier="low",
        color="#4C1D95",
        body=clauses.MAD_PARTICIPANT_CONTRACT,
    ),
)
