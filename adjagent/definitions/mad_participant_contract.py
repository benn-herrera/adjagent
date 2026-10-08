"""mad/participant-contract: the participant contract as a document, extracted and relayed as a guest
model's system prompt."""

from adjagent.definition import Definition
from adjagent.sections.mad import ParticipantContract
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(name="participant-contract", kind=Kind.DOCUMENT, folder="mad", sections=(ParticipantContract(),)),
)
