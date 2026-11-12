### Agents file changes explicitly

The agents file reaches the operator's global configuration by explicit act, and its content
changes by explicit act: publishing is a manual edit, never generated. Publish by hand: edit
`devpro/definitions/harness_agents_file.py`, then commit. Adopt with
`just install-agents-file <dir> [--plugin=NAME] [--harness NAME]`, which replaces only the agents-file block
between the `devpro` marker lines with that plugin's block and appends it to a file that has none. Into a harness's user harness
directory it also refuses while `devpro/` has uncommitted changes; into a project root it does not.
Machine-local sections (an auth sandbox, host-specific paths) live outside the agents-file block in
the live file and are never published.
