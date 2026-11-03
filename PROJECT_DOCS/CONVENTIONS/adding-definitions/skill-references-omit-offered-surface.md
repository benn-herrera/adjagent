### Skill references omit offered surface

A skill's reference carries only what its tool's offered surface does not. A session sees the
server instructions, each tool's description and its parameter descriptions, and each resource's
text once it reads it — the listing carries a resource's uri, name and mimeType only — so a
reference that restates one is a second source for text its consumer already reads, and the two
drift the moment either moves. kbase's surface also includes the
maintained block kbase stamps into `kb-root/AGENTS.md` and `kb-root/CONVENTIONS.md`, for a
reference that has the session read those documents. The offered surface is the one the minimum kbase version provides
(`KBASE_MIN_VERSION` in `adjagent/definitions/kbase.py`), so a change of that minimum is the
moment to re-read the references. Nothing checks a reference for sync with that surface. Prose
only the tool's README carries is not offered to a session, and stays in the reference.
