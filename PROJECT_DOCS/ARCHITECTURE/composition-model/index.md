## Composition Model

A definition is its rendered text with holes. A module under `adjagent/definitions/` reads top to
bottom as the file it renders and defines `DEFINITIONS`, a tuple of `Definition` records
(`adjagent/definition.py`): `name`, `body`, `kind`, `folder`, and for an agent `description`,
`tools`, `tier` and optionally `color`; a skill adds `files`, its supporting files as `SkillFile`
values of a path below the skill's directory and a body. `body` is a string built at import: an
f-string over the module's own triple-quoted text, its own constants, and the constants and text
functions of `adjagent/clauses.py` (imported as `from adjagent import clauses`, written
`{clauses.NAME}`). A module with several definitions has a longer tuple, and one definition may own
several output paths: a skill's own `SKILL.md`, then one per supporting file. A module is registered
by existing in the package (`definitions.discover`); an output path produced by two modules — a
supporting file's included — is refused, naming both, and one definition naming the same
supporting-file path twice is refused. Where a module goes and what it is called are in
CONVENTIONS.md, "Adding Definitions".

SPEC.md's single-sourcing property holds because of how text is shared, in three cases:

- **Identical in two definitions** is one constant: in `clauses.py` when the definitions are in
  different modules, in the module's private constants when they ship as a set.
- **Identical but for a few words** is a slot constant, a string with `{name}` holes filled by
  `.format` where each definition uses it in its body. Across modules the same shape is a function
  in `clauses.py` taking at most three keyword-only parameters, such as `clauses.kb_orientation`.
- **Different in structure** is written out in each definition. A sentence that belongs to one
  definition and sits among shared text is written inline in that paragraph around the constant;
  no field, class or profile carries it.

Definitions that ship as a set live in one group module, and the text only that set shares is the
module's private constants, so a reader of the module needs nothing behind an import; no group
module is defined today. `clauses.py` holds only text shared across sets. A private constant cannot
name `clauses.*`; shared text that holds a harness string takes a hole filled at the call site.

Contents:

- [Holes](holes.md)
- [Kinds](kinds.md)
- [Harnesses and families](harnesses-and-families.md)
- [Structural rules](structural-rules.md)
- [History](history.md)
