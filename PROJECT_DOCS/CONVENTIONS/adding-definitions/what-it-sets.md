### What it sets

`kind` is agent, document, command, skill or agents file; it decides the output
root, the frontmatter and the required fields. `folder` is the path below the root for a nested
output and empty otherwise; a skill refuses it, its directory being its name. A skill's
`description` is required and is all the model sees before it loads the skill; its `files` are the
supporting files, each a kebab path ending `.md` below the skill's directory, opened by the comment
banner. A definition's output paths are unique — its own, and each supporting file's.
