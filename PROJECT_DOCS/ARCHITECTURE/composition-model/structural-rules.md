### Structural rules

Two checks over source and output fix the properties above, and both are tests in the suite
(`just test adjagent`). `render` runs neither: a syntax-tree analysis has no place on a consumer's
machine of unknown Python.

- **Substitution depth is one.** `tests/_structure.py` walks the syntax trees of the definition
  modules and `clauses.py`. A module-level constant is a string literal or an f-string over
  constants in the same module, never a call. The only calls in a definition module are
  `Definition(...)` in `DEFINITIONS`, `SkillFile(...)` as a `files=` element, and, inside a `body=`
  value or a `SkillFile` body, `clauses.<name>(...)` and `<constant>.format(...)` on a
  string-literal constant, every argument a literal or a constant. A
  `clauses.py` function takes at most three keyword-only parameters and returns one string over its
  parameters and constants, with no call. A chain of constants cannot defeat the depth, because
  nothing a call returns can be bound to a constant or passed as an argument: slot text is always
  fixed text, and filling it is the last substitution. Every `SkillFile` body is walked under the
  `body=` rule, so a reference takes shared text from `clauses` as a definition body does and cannot
  carry a call of its own — a `SkillFile` path is a string literal and nothing else. The same walk
  confirms a definition module's top level holds only imports, string constants and `DEFINITIONS`.
- **A paragraph two outputs share has one source.** `tests/test_adjagent.py` renders every
  definition twice, once as written and once with each `clauses` constant, function and private
  constant standing as a sentinel, and fails on a paragraph or list item that survives both in two
  outputs: it was written out rather than taken from a constant. A skill is swept the same way, each
  of its files walked as an output in its own right and labelled by the path it renders to, so a
  paragraph a router and a reference both carry is found as readily as one two definitions share.

