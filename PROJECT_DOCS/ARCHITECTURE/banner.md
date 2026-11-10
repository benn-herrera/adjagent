## Banner

Under claude and mage a rendered definition other than a supporting file carries two banner lines in
its frontmatter, the generated banner and `# !TUNING!`, the tuning line (SPEC.md, Rendering). `render.GENERATED_MARK`
and `GENERATED_NOTICE` spell the generated banner, and `install.stamped` writes the installed one.
Those lines are YAML comments inside the frontmatter, so the opening `---` is still the file's
first line — the one thing a harness requires to read a frontmatter at all — and the frontmatter's
field lines follow the banner. A supporting file carries the pair as `<!-- !GENERATED! … -->` and
`<!-- !TUNING! … -->` followed by a blank line, and the `!GENERATED!` line alone marks it as ours for
removal (`_is_ours`). Under opencode every rendered file takes that comment carrier
(`render._comment_banner`), a definition's own included, because the body file holds no
frontmatter; the entry strips the leading comment lines and the blank line after them when it
registers the body. A harness-rendered file carries no banner: `registry.json` carries its marker,
`"plugin": "<plugin>"`, as the plugin manifest carries `"name": "<plugin>"` and `.mcp.json` the command
`"command": "kbase"`; `index.ts` and `guardrail.ts` carry their own `!INSTALLED!` header.

