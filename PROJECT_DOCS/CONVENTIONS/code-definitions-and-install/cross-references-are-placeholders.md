### Cross-references are placeholders

Definition text names another definition only through `clauses.ref(name="python-coder")`, which
spells the reference placeholder `@!ref-python-coder!@` (ARCHITECTURE.md, Rendering, Placeholders).
Write the call inside the body's or description's f-string, as any clause is composed; a description
that holds one is an f-string.
- **A plain reference must resolve in every plugin that ships its citing definition.** References
  close within the shipped set, so a plain reference to a definition outside a plugin refuses that
  plugin's render. Where the text does not need the out-of-plugin name, state the role instead of the
  name ("a security review's findings"), so the text holds in both plugins.
- **An optional reference** is `clauses.optional_ref(name="development")`. It fills as a plain one
  does where the referent ships and drops its whole paragraph where it does not, so it stands in a
  paragraph of its own: a sentence or bullet that must go with the reference, never one that shares
  its paragraph with a heading or text the other plugin keeps.
- **Tuning text cannot carry one.** Filled text is never rescanned (Composed text is never
  rescanned), so tuning text names no definition at all.

`tests/test_cross_references.py` fails on a definition name spelled outside a placeholder; its
docstring lists what counts as a reference and what stays bare. A new definition is covered from the
commit that adds it.
