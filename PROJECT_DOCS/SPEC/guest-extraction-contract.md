## Guest-Extraction Contract

Any definition's body — the content after its frontmatter — must be usable frontmatter-free as an
external (non-Claude) model's system prompt. The obligation attaches to definitions, not to their
outputs: every dispatchable definition must hold the property mechanically — dropping every line
through the one that closes the frontmatter block yields the body entire, losing no content and
needing no knowledge of what the block holds. The property is guaranteed where a definition is
built, not where it is read: the project's test suite, run before a change lands, refuses a
definition that would not extract, so none ships truncated. The install does not check it. The
extracted body does not carry the definition's `model:` pin, which stays in the frontmatter where
the harness render carries one: a caller that uses the body without `--agent`
carries the pin itself.

