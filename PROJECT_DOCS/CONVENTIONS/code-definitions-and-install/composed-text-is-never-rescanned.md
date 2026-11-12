### Composed text is never rescanned

No value a fill supplies — a clause's harness string, tuning text, a model name, an agents-file
value — is filled again, so none can carry a placeholder that is meant to fill (ARCHITECTURE.md,
Rendering, Placeholders).
`tests/test_devpro.py::test_a_filled_value_carrying_a_hole_reaches_the_body_literally` holds it.
