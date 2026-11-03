### Harness resources are copied verbatim

The install stamps nothing on a file under `adjagent/harnesses/resources/`, which never takes
the package loop. `harness_resource_copies` writes each with `copyfile` and `copymode` and
nothing else, so a consumer receives what the source holds — a header the file already carries
included, as the file's own text. That header is required: a resource file carries
`!INSTALLED! … adjagent` in its first ten lines, because an install refuses to overwrite a target
without it, and the source test enforces it for every file a harness ships. The loop beside it
stamps by suffix (`STAMPED_SUFFIXES`), a package's files being this repository's emissions, so a
packet adding a resource must not reuse that loop just because the walk is already there: the
suffix says nothing about what a file already holds, and a `.py` resource would gain a banner
above its own. This tree is the master for what it ships — an installed copy is never edited,
and no other repository's copy is a source.
