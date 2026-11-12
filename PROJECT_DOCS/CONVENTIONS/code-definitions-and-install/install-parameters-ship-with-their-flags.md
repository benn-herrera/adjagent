### Install parameters ship with their flags

An install parameter and its CLI flag are one change. `just install` reaches the verb only
through the flags `devpro/cli.py` declares in `build_parser`, so a parameter added to
`install()` alone ships a capability no recipe can ask for. The flag lands in the same change. The
parameter's own tests do not catch the gap: a test calling `install(...)` proves the parameter
works, never that anything can supply it — only a call through `main([...])` proves the flag
reaches it, the shape the plugin argument has.
