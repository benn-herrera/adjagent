# DESCRIPTION_TRIM_PLAN.md — shorten every agent description

**Status: queued; starts after TYPESCRIPT_CODER_PLAN.md lands. Serial dispatch — one agent at a
time.** One commit; it deletes this plan.

## The rule a description follows

A description is the dispatcher's only routing input, and every session loads all of them. It
carries:

1. what the seat is, in one phrase;
2. when to choose it over its nearest neighbours (e.g. typescript-coder against web-app-expert,
   kb-maintainer against kb-docent);
3. a hard limit that changes dispatch (review only, modifies nothing; one write-enabled instance).

It drops capability inventories ("Covers X, Y, Z"), quality claims ("idiomatic, minimal"), and
operating style the body states ("stays strictly within assigned scope"). Target 25–40 words; a
seat whose routing needs more keeps it.

## Steps

1. **prompt-engineer rewrites** the `description=` value of every agent-kind definition under
   `adjagent/definitions/`. It writes the old and new text, with word counts, to
   `.claude-temp/description-trim/proposal.md` and edits no repo file. Every "prefer X over Y" pair
   between seats survives on at least one side.
2. **python-coder at `sonnet` applies** the proposal verbatim to the definition modules, keeping
   each module's string-literal splitting style.
3. **prompt-engineer reviews** the applied set as a dispatcher would read it: for each seat, could a
   task meant for it be routed elsewhere?

## Proof

`just test adjagent` passes. `just render` then `just render-diff` shows only `description:` lines
changing, in agent outputs only. Total description words, before and after, are reported.
