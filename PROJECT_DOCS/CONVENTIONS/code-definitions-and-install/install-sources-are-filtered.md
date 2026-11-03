### Install sources are filtered

Every tree an install copies from is walked through `_shipped`, and named in `_refuse_root`.
The filter is what keeps a `__pycache__`, a `.DS_Store`, a `.bak` copy and this repository's own
project documents (`SPEC.md`, `AGENTS.md` and the rest) out of a consumer; a source that skips it
ships them, and the walk is the one place they are caught. `_refuse_root` holds the same set of
trees — a shipped package's, the kb toolchain's, `adjagent/harnesses/resources/` — because a
ROOT inside one is refused rather than filled with the product it is itself copying from.
