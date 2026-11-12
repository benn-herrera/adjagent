### A skill omits its tool's offered surface

A skill's supporting file carries only what its tool's offered surface does not. A session sees the
server instructions, each tool's description and its parameter descriptions, and each resource's
text once it reads it — the listing carries a resource's uri, name and mimeType only — so a
supporting file that restates one is a second source for text the session already reads, and the two
drift the moment either moves. kbase's surface also includes the
maintained block kbase stamps into `kb-root/AGENTS.md` and `kb-root/CONVENTIONS.md`, for a
supporting file that has the session read those documents. The offered surface is the one the minimum
kbase version provides (`KBASE_MIN_VERSION` in `devpro/definitions/kbase.py`), so a change of that
minimum is the moment to re-read the supporting files. The docdicer skill's offered surface is
`docdicer --help` of the version `tools/docdicer` pins (its `VERSION`), and changing that pin is the
moment to re-read the skill. Of that surface, only the names the kbase skill cites are checked:
`tests/test_kbase_surface.py` checks those names (its docstring states how); nothing else in a
supporting file or a skill entry file, the docdicer skill included, is checked for sync. Prose only
the tool's README carries is not offered to a session, and stays in the supporting file.
