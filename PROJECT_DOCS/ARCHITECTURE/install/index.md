## Install

An install is a deploy step: each harness has its own layout, and the rendered definitions, the
package copies and the harness resources are written to the places and names that layout gives. It
departs from a plain copy in five places.

- It removes each file under the install directory's `agents/`, `commands/` and `skills/` that
  would ship, is ours, and was not written by this run (Renders and copies). Removing, renaming and
  relocating installed files is standard maintenance: an install removes the files of ours it no
  longer writes, so none accumulate.
- It first runs into a scratch copy and compares the result. The dry run is the install itself, run
  into a scratch copy and compared with the real paths: one code path, so the up-to-date check and
  `--dry-run` are trivial comparisons, the dry run cannot drift from the install, and there is less
  code than a separately computed plan of writes. Detail is in Renders and copies, Preflight and
  the tool install.
- It re-runs `docdicer --install` where a venv stood; the reason is in Renders and copies, The
  tool install.
- It runs a harness's guardrail script once before registering it, and skips the script and its
  registration where the run fails (Guardrail registration).
- It selects by plugin membership: it renders and ships the definitions the plugin carries, and each
  package and harness-rendered file whose owning definition ships (Plugins).

Contents:

- [Install entry](install-entry.md)
- [Plugins](plugins.md)
- [Renders and copies](renders-and-copies.md)
- [Guardrail hook](guardrail-hook.md)
- [Guardrail registration](guardrail-registration.md)
- [Opencode entry](opencode-entry.md)
- [Installing this repository](installing-this-repository.md)
