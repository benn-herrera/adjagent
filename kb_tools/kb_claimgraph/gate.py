"""Stage G — refresh, then the build-time check, in-process.

Refresh rebuilds the derived index and the claim-graph sheet from what the
earlier stages authored; :func:`kb_tools.kb_util.run_build_verify` then runs the
standard check and the citation-grammar check over the result. Each verifier
prints its own report as it runs.

**This is the loop that works: it exits on return codes.** There is no fix loop
here and no seat to run one. Every check compares one mechanical product against
another — a rebuild diffed against disk, a link against the file it names, an id
against the register that mints it — so a red gate is a defect in this stage's
input or in this stage, and neither is repaired by asking.
"""

from pathlib import Path

from .. import kb_util, refresh_kb_metadata
from .report import FAIL, PASS, Finding


def run(repo_root: Path) -> list[Finding]:
    """Refresh, then the build-time check. Green or stop, on the return codes alone."""
    refreshed = refresh_kb_metadata.main(["--kb-root", str(kb_util.kb_root(repo_root))])
    if refreshed != 0:
        return [Finding(FAIL, "refresh", f"exited {refreshed}")]
    verified = kb_util.run_build_verify(repo_root)
    status = FAIL if verified.failed else PASS
    return [Finding(PASS, "refresh", "exited 0"), Finding(status, "verify", verified.detail())]
