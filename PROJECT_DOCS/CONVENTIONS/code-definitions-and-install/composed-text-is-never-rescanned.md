### Composed text is never rescanned

Outside `adjagent/definitions/`, no module of the package
calls `str.replace`, `format` or `format_map` (`dataclasses.replace` is not one), and the only
pattern substitution is the body fill in `render.filled_text`. A definition module's `.format` on
one of its own string literals is the permitted call, and that literal holds no composed text.
What a constant or a harness string fills in is literal: a placeholder-shaped span it introduces
is never filled again. Only `tests/test_adjagent.py::test_no_composed_text_is_rescanned` stated
the rule, which is why it is written here.
