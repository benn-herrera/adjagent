## Banner

A rendered definition's own output carries two banner lines in its frontmatter: `# !GENERATED! from
adjagent/definitions/<module>.py`, with the edit rule and where change requests go, and
`# !TUNING!`, which records the family, the definition's seat and member, the tier map, the alias
map where one was given, the tiers the family tunes nothing for (`stock`), and the harness. Those
lines are YAML comments inside the block, so the opening `---` is still the file's first line — the
one thing a harness requires to read a frontmatter at all — and the block's field lines follow the
banner. A skill's supporting file has no frontmatter to hold them, so it carries the same two
payloads as HTML comment lines, `<!-- !GENERATED! … -->` and `<!-- !TUNING! … -->`, from its first
line, a blank line and the body after them; nothing about how the file reads depends on them, and
the same pair is what marks it as ours for removal. A copied package file of a `#`-comment type
carries one `# !INSTALLED! from <source>` line with the same edit rule, below its shebang where it
has one. Nothing carries a hash, and the only backup is the agents file's rolling `backup.<name>`.

