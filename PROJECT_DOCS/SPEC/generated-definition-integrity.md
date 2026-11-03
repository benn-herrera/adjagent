## Generated-Definition Integrity

Every definition in the deployed surfaces (`agents/`, `commands/`, `skills/`) is generated rather
than hand-authored — the partition is total, because a definition with no source here is never
rendered and so never reaches the product at all. A skill's supporting files are generated and
validated like any other render: the paragraph-sharing check (ARCHITECTURE.md, Structural rules)
covers a reference's body exactly as it covers a definition's own. The guest-extraction contract and
the rendered-line cap both govern outputs under `agents/`; neither applies to a reference, whose
reader is the session that navigated to it. For every definition and every file it produces:

- Its content is exactly what the generator renders for it from its source, deterministically; a
  rendered file whose source no longer exists is removed on the next install.
- Every banner claiming a definition is generated names the source it was rendered from and states
  that the file is not for local edit. A project that tracks the installed tree gets modification
  detection from its own git; one that does not is protected by the file being replaced whole on the
  next install, so no modification survives it.

A file without a generated banner is not a definition this repository produced, and is outside this
guarantee — Write Safety, below, is what governs meeting one at a generation target.

