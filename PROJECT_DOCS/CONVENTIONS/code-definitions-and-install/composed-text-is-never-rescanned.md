### Composed text is never rescanned

Filled text is literal. A definition body gets one substitution: the body fill, `render.filled_text`,
which fills each hole once. Whatever a fill puts in is never filled again, whether it comes from a
clause constant, a harness string, a family overlay, a model name or an agents-file value. A
placeholder-shaped span inside it reaches the rendered output as written. A definition module may
call `.format` on one of its own string literals, because that literal holds no composed text. The
reason is ownership: if filled text could introduce a hole, any harness or family value could edit
any definition, and no reader of the body could tell what renders. The check is
`tests/test_adjagent.py::test_a_filled_value_carrying_a_hole_reaches_the_body_literally`. Each of its
cases fills in a value that carries a hole, and asserts that the hole survives unfilled.
