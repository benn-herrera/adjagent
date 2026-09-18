# ROADMAP – liaison_tools

Future intent only. Not part of the contract doc set; not handed to coding dispatches.

1. **Restore a `python`-fallback launcher if an environment turns up that needs one.** `post-openai.sh` was retired: all three tools now run off `#!/usr/bin/env python3` alone, matching SPEC.md's "a `python3` on `PATH` and nothing else". The case it covered — `python` aliased to a Python 3 interpreter with no `python3` on `PATH` — is real but unobserved here; add the launcher back for all three tools, not one, if it appears.
