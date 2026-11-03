### Harness agent file changes explicitly

The harness agents file changes by explicit act, in either direction. Publish by hand: edit
`adjagent/definitions/harness_agents_file.py`, then commit. Adopt with
`just install-agents-file <dir> [harness]`, which replaces only the block between the `adjagent`
marker lines and refuses while `adjagent/` has uncommitted changes. Your own rules go outside the
markers, because inside is replaced on every install. Machine-local sections (an auth sandbox,
host-specific paths) live outside the block in the live file and are never published.
