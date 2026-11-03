### Kb installation is sticky

An install whose ROOT already holds a kb install installs the kb set. The signal is a file,
never the `kb-tools/` directory (ARCHITECTURE.md, Install Consumption Model, names the file). The
choice is per ROOT — the harness directory — not per project, so a later plain `just install`
into that directory refreshes the kb set rather than emptying it.
