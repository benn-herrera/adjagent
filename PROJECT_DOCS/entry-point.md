# THESIS - adjagent

*Why this project has the shape it has*

---

## The thesis

**An agent set is a system that must agree with itself, and in static files you cannot check that it
does.**

Agents in a set share text because they must share behaviour. A rule stated to one seat and not its
neighbor is not an inconsistency of style; it is two seats that will act differently in the same
situation.

Agreement is not a property of any one file, so there is nothing to inspect and nothing to raise.
Multiply by the model dimension and the question stops being tedious and becomes intractable. **And
the failure is silent** — a clause that reached ten seats and not the eleventh is discovered later,
by its consequences, in work unrelated to the edit that caused it.

**An agent set should be useful in more than one harness context**

The ability to specify model-family-specific tuning and harness-specific shaping falls naturally
from the basic capability and multiplies the utility.

## What follows

Agreement that cannot be verified must be made unrepresentable. A span shared by many definitions
exists once and every definition is produced from it, so two copies cannot disagree because there is
only one.

Everything else is downstream of that.

Volumes:

- [SPEC](SPEC/entry-point.md): This repository is the source of a drift-proof, model-tunable generation system that renders agent, command and skill definitions to order; the multi-capability agent, command and skill set it ships, consumed by other projects, is its flagship rendering.
- [ARCHITECTURE](ARCHITECTURE/entry-point.md): How the generation system, and the agent, command and skill set it ships, are built to satisfy SPEC.md.
- [CONVENTIONS](CONVENTIONS/entry-point.md): House rules and project-specific traps only.
