# THESIS - liaison_tools

*Why this tool set has the shape it has.*

---

## The thesis

**A guest model is a participant, not an endpoint.**

This tool set exists so an arbitrary model reached over an OpenAI-compatible API
can take part in a session or a debate. A person addressing it directly in the
main session is one of those; a seat in a multi-model debate is another; both
are the same thing, and what the guest needs does not change between them.

What a participant needs is what the channel carries: the behaviour foundation
it is working from, the prompts a person addresses to it, the prompts other
models address to it, and a way to ask for what it does not have. A guest can
request file contents and tool executions, and the liaison services those
requests and returns the answers into the same conversation. That last
capability is not an extra — a participant that cannot ask for anything is
reduced to whatever it was handed.

## Friction is the constraint

The guest is *arbitrary*. Whatever it is, it did not adopt this project, and
nothing about it can be assumed — so every requirement placed between a model
and the conversation is a model that cannot join.

That is what the design spends itself on: the lowest-friction channel that still
carries the four things above. A requirement dropped is a participant gained,
and a convenience added at the cost of a precondition is a bad trade even when
the convenience is real.

A guest is also a guest. It participates without being given the run of the
place — its requests are answered within a stated boundary rather than executed
as written, and the credential reaching the endpoint is never part of the
conversation it is having.

## The record is per instance, and it is the point

**A guest session's interaction history is auditable, and each usage instance
holds its own durable record.**

Both halves are load-bearing. Auditable, because everything relayed leaves this
machine and reaches a third party — so the history is a disclosure record, not a
debugging convenience. Per instance, because a shared history answers the wrong
question: what was said in *this* debate, to *this* guest, is what a reader
needs, and a merged log cannot be separated back into that afterwards.

Which is why the record is not a log the tooling writes alongside the work. It
is the state the work is conducted from — there is no second place to look,
because there is nothing anywhere else.

## What this rules out

A guest whose contributions cannot be reconstructed from its own session's
record. A convenience that puts part of a conversation somewhere the record does
not reach. A precondition on the guest beyond speaking the API — an SDK, a
runtime, an adoption of anything here.
