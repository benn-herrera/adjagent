### Harness agent file changes explicitly

The harness agents file changes by explicit act, in either direction. Publish by hand: edit
`adjagent/definitions/harness_agents_file.py`, then commit. Adopt with
`just install-agents-file <dir> [--harness NAME]`, which replaces only the block between the `adjagent`
marker lines and refuses while `adjagent/` has uncommitted changes. The second explicit act of
adoption is `--install-global-agents-file` on a user-level `install`; it takes the same refusals. Your own rules go outside the
markers, because inside is replaced on every install. Machine-local sections (an auth sandbox,
host-specific paths) live outside the block in the live file and are never published.
