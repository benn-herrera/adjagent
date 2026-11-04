### Clause paragraphs

A sentence of the module's own that reads as its own rule stands as its own paragraph. One that
continues the clause beside it stays joined to it. These patterns stay joined:

- a predicate clause with its subject: `This` or `That` before `LOGGING_ABSTRACTION_NOTE`;
- a phrase clause inside its sentence: `DATA_FORMATS_SCOPE`;
- a label alone: `*Unit tests*:`.

After editing a definition, run `just clause-join-sites <path>` and judge each newly listed site by
the rule. It lists each paragraph or list item that joins a clause to the module's own text, as
`<path>:<line>: <clause> + <clause>`, and ends `sites: <count>`. A clause's module-constant argument
is the module's own text; a literal argument is part of the clause's sentence. A heading, table row
or fence line is not a unit, so a clause there is not listed. `just test` holds none of this.
