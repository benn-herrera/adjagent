### Shared text is one constant

Text two definitions share byte for byte is one constant, in `adjagent/clauses.py`, or in a
group module's private constants when only that set shares it. A definition never pastes shared
text or a paraphrase of it; `just test` fails on a paragraph two outputs write out.
- **A private constant cannot name `clauses.*`.** Shared text that holds a harness string takes a
  hole, filled at the call site in the body.
- **A paragraph added to `clauses.CODE_PRINCIPLES_CODER` goes before the constant's last one.**
  `python_coder.py` and `shell_dsl_coder.py` continue the constant on the same line with a
  sentence of their own, so a paragraph placed last is joined to that sentence under either
  harness and reads as theirs. `RECIPE_RULE` stands before `PROJECT_CONVENTIONS_OUTRANK` for
  that reason.
