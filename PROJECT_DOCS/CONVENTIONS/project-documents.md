## Project Documents

SPEC, ARCHITECTURE and CONVENTIONS are trees of small files under `PROJECT_DOCS/`, each section one
file; THESIS is the one file `PROJECT_DOCS/entry-point.md`, whose `Volumes:` list links them. The
root `THESIS.md`, `SPEC.md`, `ARCHITECTURE.md` and `CONVENTIONS.md` only point there.

- Never edit a root pointer file, and never regenerate the trees from the root files: the leaves are
  the source.
- A new section is a new leaf, added to the `Contents:` list of its parent `index.md` and of the
  document's `entry-point.md`. `just check-links` verifies that every relative link and `#anchor` in
  `PROJECT_DOCS/` and the top-level `*.md` files resolves, and that every `PROJECT_DOCS/` document is
  listed by its parent and reachable from its entry point; `just test` and `just test-changed` run it
  as the `docs` surface.
- Citations keep their form: a document and a section title, as "SPEC.md, Write Safety". A leaf's
  file name is its title's slug.
