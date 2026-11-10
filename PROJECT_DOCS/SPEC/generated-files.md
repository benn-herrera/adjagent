## Generated files

Every rendered definition in the deployed surfaces (`agents/`, `commands/`, `skills/`) is rendered
rather than hand-authored; a definition with no source here is never rendered and never installed.
A skill's supporting files are rendered and validated like any other rendered definition.
Single-sourcing (Rendering) holds for a supporting file's body as for a definition's own: a
paragraph or list item that two rendered files carry, supporting files included, has one source.
The rule that bodies are usable without frontmatter governs every rendered definition under
`agents/`, and the rendered-line cap, at most 500 lines after the banner, every rendered
definition; neither applies to a supporting file. For every definition and every file it produces:

- Its content is exactly what the generator renders for it from its source, deterministically; a
  rendered file whose source no longer exists is pruned on the next install.
- Every banner claiming a definition is generated names the source it was rendered from and states
  that the file is not for local edit.

- Under opencode a rendered definition carries its banner as the comment lines a supporting file
  opens with and has no frontmatter; its metadata is in the registry `registry.json`, a harness-rendered
  file that carries its marker, `"plugin": "<plugin>"`, rather than a banner (Installed tree).

A definition that fails to render refuses the install with nothing written.

A file without a generated banner is not a rendered definition this repository produced, and is
outside this guarantee — Write Safety, below, is what governs meeting one at a destination.

