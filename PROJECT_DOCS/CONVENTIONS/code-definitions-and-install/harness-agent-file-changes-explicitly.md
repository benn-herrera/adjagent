### Harness agent file changes explicitly

The harness agents file reaches the operator's global configuration by explicit act, and its content
changes by explicit act: publishing is a manual edit, never generated. Publish by hand: edit
`adjagent/definitions/harness_agents_file.py`, then commit. Adopt with
`just install-agents-file <dir> [--harness NAME]`, which replaces only the block between the `adjagent`
marker lines and appends it to a file that has none. Into a harness's user-global directory it also
refuses while `adjagent/` has uncommitted changes; into a project directory it does not. The second
explicit act of adoption is `--install-global-agents-file` on a user-level `install`; it takes the
same refusal. Once the global file holds the block, every claude or opencode project install keeps it
current there and removes the project's copy; with no global block, a project install keeps it current
in the project's `AGENTS.md`. A project install never puts the block into the global file first, and
its write into the global file takes the same refusal. Your own rules go outside the
markers, because inside is replaced on every install. Machine-local sections (an auth sandbox,
host-specific paths) live outside the block in the live file and are never published.
