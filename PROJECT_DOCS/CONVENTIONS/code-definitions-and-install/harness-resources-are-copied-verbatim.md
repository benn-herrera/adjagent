### Harness resources are copied verbatim

The install stamps nothing on a file under `devpro/harnesses/resources/`, which never takes
the package loop. A consuming project receives what the source holds, an installed banner the file
already carries included, as the file's own text. That installed banner is required (SPEC.md, Write
Safety), and the source test enforces it for every file a harness ships. The loop beside it
stamps a file whose suffix is in `STAMPED_SUFFIXES` or whose name is in `STAMPED_NAMES`, a package's
files being this repository's own, so a change adding a resource must not reuse that loop just
because the walk is already there: the suffix or name says nothing about what a file already holds,
and a `.py` resource would gain a banner above its own. This tree is the master for what it ships — an installed copy is never edited,
and no other repository's copy is a source.
