### Cross-references are holes

Definition text names another definition only through `clauses.ref(name="python-coder")`, which
spells the reference hole `@!ref-python-coder!@`. The renderer fills it with the harness's
`reference_prefix` and the name (Composition Model, Holes), so one source names an agent, command or
skill the way each harness addresses it. Write the call inside the body's or description's f-string,
as any clause is composed; a description that holds one is an f-string.
- **An overlay cannot carry one.** Filled text is never rescanned (Composed text is never rescanned),
  so an overlay names no definition at all.
- **A role noun stays bare.** "Hand that to the architect" names a role, not a definition.
- **A program stays bare.** `adjagent`, `docdicer` and `kbase` name an executable, a tool or a CLI
  when written as one ("every other `adjagent` command"). Written as the definition (the `docdicer`
  skill), the name is a reference.

`tests/test_cross_references.py` fails on a definition name spelled outside a hole in a body,
description, skill supporting file, the agents file or a family overlay: a hyphenated name as a whole
word outside a path, any other name in backticks, and `adjagent`, `docdicer` or `kbase` in backticks
followed by ` skill`. A reference to a name no definition has is refused at render, naming the
definition. A new definition is covered by the guard from the commit that adds it.
