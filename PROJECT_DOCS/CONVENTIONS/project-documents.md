## Project Documents

THESIS, SPEC, ARCHITECTURE and CONVENTIONS are trees of small files under `PROJECT_DOCS/`, each
section one file. The root `THESIS.md`, `SPEC.md`, `ARCHITECTURE.md` and `CONVENTIONS.md` only
point there.

- Edit the leaf that holds the section. Never edit a root pointer file, and never regenerate the
  trees from the root files: the leaves are the source.
- A new section is a new leaf, added to the `Contents:` list of its parent `index.md` and of the
  document's `entry-point.md`. `just check-links` verifies that every relative link and `#anchor` in
  `PROJECT_DOCS/` and the top-level `*.md` files resolves, and that every `PROJECT_DOCS/` document is
  listed by its parent and reachable from its entry point; `just test` and `just test-changed` run it
  as the `docs` surface.
- Read the leaves a task needs, starting from the document's `entry-point.md`; a whole document is
  read only when the task is about the whole document.
- Citations keep their form: a document and a section title, as "SPEC.md, Write Safety". A leaf's
  file name is its title's slug.
