### Shared text is one constant

Text two definitions share byte for byte is one constant, in `devpro/clauses.py`, or in a
group module's private constants when only that group shares it. A definition never pastes shared
text or a paraphrase of it; `just test` fails on a paragraph two rendered definitions carry.
- **A private constant cannot name `clauses.*`.** Shared text that holds a harness string takes a
  placeholder, filled at the call site in the body.
