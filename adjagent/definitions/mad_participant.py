"""mad-participant-*: the four model-pinned debate seats.

They are separate definitions because the referee dispatches by `subagent_type`, so each pin needs
its own file presenting the identical contract.
"""

from adjagent.definition import Definition
from adjagent.sections.mad import ParticipantContract
from adjagent.vocabulary import ALL, Tier

_DESCRIPTION = (
    "Independent technical participant for multi-model debate process. Produces structured initial "
    "assessments (review mode) or proposals (design mode), and responds to debate rounds. Sees only the "
    "Alignment Assessor's structured map, never another participant's full output."
)


def _participant(*, seat: str, tier: Tier, color: str) -> Definition:
    return Definition(
        name=f"mad-participant-{seat}",
        description=_DESCRIPTION,
        tools=ALL,
        tier=tier,
        color=color,
        sections=(ParticipantContract(),),
    )


DEFINITIONS = (
    _participant(seat="fable", tier="highest", color="#7C3AED"),
    _participant(seat="opus", tier="high", color="#6D28D9"),
    _participant(seat="sonnet", tier="medium", color="#5B21B6"),
    _participant(seat="haiku", tier="low", color="#4C1D95"),
)
