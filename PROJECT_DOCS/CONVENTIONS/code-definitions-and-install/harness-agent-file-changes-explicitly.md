### Harness agent file changes explicitly

The harness agents file changes by explicit act, in either direction. Publish by hand: edit
`adjagent/definitions/harness_agents_file.py`, then commit. Adopt with
`just install-agents-file <dir> [--harness NAME]`, which replaces only the block between the `adjagent`
marker lines and appends it to a file that has none. Into a harness's user-global directory it also
refuses while `adjagent/` has uncommitted changes; into a project directory it does not. The second
explicit act of adoption is `--install-global-agents-file` on a user-level `install`; it takes the
same refusal, and no project install does. Your own rules go outside the
markers, because inside is replaced on every install. Machine-local sections (an auth sandbox,
host-specific paths) live outside the block in the live file and are never published.
