"""mad-participant-*: the four model-pinned debate seats.

They are separate definitions because the referee dispatches by `subagent_type`, so each pin needs
its own file presenting the identical contract.
"""

from adjagent import text as t
from adjagent.definition import Definition
from adjagent.vocabulary import ALL

_DESCRIPTION = (
    "Independent technical participant for multi-model debate process. Produces structured initial "
    "assessments (review mode) or proposals (design mode), and responds to debate rounds. Sees only the "
    "Alignment Assessor's structured map, never another participant's full output."
)

DEFINITIONS = (
    Definition(
        name="mad-participant-fable",
        description=_DESCRIPTION,
        tools=ALL,
        tier="highest",
        color="#7C3AED",
        body=t.MAD_PARTICIPANT_CONTRACT,
    ),
    Definition(
        name="mad-participant-opus",
        description=_DESCRIPTION,
        tools=ALL,
        tier="high",
        color="#6D28D9",
        body=t.MAD_PARTICIPANT_CONTRACT,
    ),
    Definition(
        name="mad-participant-sonnet",
        description=_DESCRIPTION,
        tools=ALL,
        tier="medium",
        color="#5B21B6",
        body=t.MAD_PARTICIPANT_CONTRACT,
    ),
    Definition(
        name="mad-participant-haiku",
        description=_DESCRIPTION,
        tools=ALL,
        tier="low",
        color="#4C1D95",
        body=t.MAD_PARTICIPANT_CONTRACT,
    ),
)
