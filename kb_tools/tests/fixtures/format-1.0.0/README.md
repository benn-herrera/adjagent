# format-1.0.0 — kbase's golden pairs for KB metadata format 1.0.0

Byte copies of kbase's `internal/migrate/testdata/`, same tree, at kbase commit
`70aff06a7905693def31a77c2c82643a9737a7c2`.

Synthetic test data, not a KB. Never edit these files here: a change to them comes from kbase as
a handoff, and is copied in whole.

Each `0.9.0/` file is paired with its `1.0.0/` counterpart at the same path, the extension changed
where the format renamed it (`.json` to `.yaml`, `.jsonl` to `.yaml`). The pairs pin:

- **Reader**: every `1.0.0` file, the documents' frontmatter included, reads to the values its
  `0.9.0` twin holds.
- **Writer**: writing those values reproduces the `1.0.0` bytes exactly.
- **Migration**: converting the `0.9.0` tree gives the `1.0.0` tree byte for byte. The obsolete
  set is the three `.json` records and the six `.jsonl` index files.
