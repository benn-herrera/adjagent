### Default exclusions go by name

A set a default install excludes is excluded by its definitions' names, held in
`NOT_BY_DEFAULT`. `install.py` holds that pattern over definition names — `excluded()`'s one
call site in the install is the `include` filter `render_all` takes, and what it passes is a
definition's name — and it names `^(kb-|kbase$)` today: a name is excluded by its shape, so a
`kb-` definition would stay out of a base install, and `kbase` is the one name it excludes.
A package destination is not a name and no destination is matched: `SHIPPED_PACKAGES` destinations
sit beside the surfaces under `adj-tools/` — the table holds no row today — and the kb toolchain's
sits inside one, in the `kbase` skill's own directory, where its files are stamped installed or
carry no banner and never a generated one, so no carve-out follows and every file under a surface
is either ours or untouched. The match is on the definition's name, not on a rendered file's stem,
so a definition that owns several files is one keep-or-drop decision and never a partial tree. A
second such set adds its own alternation there, over its output names — a name the pattern misses
is rendered and shipped by every install. A run that excludes the match renders none of the
matching definitions, and one already installed is stale: removed from the tree and named in that
run's report. A harness that renders nothing for a definition declares it on `Harness.omits`, which
`render_all` applies itself; `NOT_BY_DEFAULT` stays the invocation's filter, over names, passed by
the caller.
