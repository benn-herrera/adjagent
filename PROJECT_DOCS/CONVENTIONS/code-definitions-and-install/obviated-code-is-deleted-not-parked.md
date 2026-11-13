### Obviated code is deleted, not parked

When a change makes code unnecessary, it goes in the
same change — not commented out, not left unreferenced behind a "maybe someday", not kept as a
second implementation nobody calls. Git holds it, and a commit message naming what replaced it is
a better record than a dead module. The cost of keeping it is paid by everyone after: a reader
can't tell live from vestigial, an agent reads it as current, and whoever reads the module next
inherits the job of classifying a name nothing refers to. A plan for rebuilding it later is cheap
and belongs in `ROADMAP_DESIGNS/`; the code itself is not.
