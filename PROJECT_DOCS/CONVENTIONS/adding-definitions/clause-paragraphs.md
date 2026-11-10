### Clause paragraphs

A sentence of the module's own that reads as its own rule stands as its own paragraph. One that
continues the clause beside it stays joined to it. These patterns stay joined:

- a predicate clause with its subject: `This` or `That` before `LOGGING_ABSTRACTION_NOTE`;
- a phrase clause inside its sentence: `DATA_FORMATS_SCOPE`;
- a label alone: `*Unit tests*:`.

After editing a definition, run `just clause-join-sites <path>` and judge each newly listed site by
the rule. `just test` holds none of this.
