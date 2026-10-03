"""The consuming repository the claim-graph suites build in, and stage G run in-process over it.

A claim-graph consumer is stood up the way a consumer's is: the tree under
``kb-root/``, the package installed under ``.claude/agents/`` as a link, and the
real runner snippet imported by the line the installer writes — so stage G's
targets are the real ones wherever a test reaches them through the runner.
"""

import os
from collections.abc import Mapping
from pathlib import Path

from kb_tools import kb_util, refresh_kb_metadata
from kb_tools.kb_claimgraph.report import FAIL, PASS, Finding

_PACKAGE_ROOT = Path(kb_util.__file__).resolve().parent


def install_claimgraph_consumer(repo: Path, tree: Mapping[str, str]) -> Path:
    """A consuming repo at ``repo``: ``tree`` under ``kb-root/``, the installed package and the real runner targets.

    The runner targets resolve the repository root the way every tool in this
    toolchain does — a ``.git`` beside a ``kb-root/`` — so the marker is what
    makes this a repository to them, not a convenience of the fixture.
    """
    for relative, text in tree.items():
        target = repo / "kb-root" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / "justfile").write_text("default:\n    @true\n", encoding="utf-8")
    installed = repo / ".claude" / "agents"
    installed.mkdir(parents=True)
    os.symlink(_PACKAGE_ROOT, installed / _PACKAGE_ROOT.name)
    kb_util.install_targets(repo, "just")
    return repo


def stage_g_in_process(repo_root: Path) -> list[Finding]:
    """Stage G as :func:`kb_tools.kb_claimgraph.gate.run` reports it, refresh and verify called in-process.

    The same refresh and the same three verifiers over the same KB, green or
    stop on the return code alone. What it does not exercise is the runner
    channel — ``just`` through the installed include line — which a test keeps
    by taking the ``runner_gate`` fixture.
    """
    refresh = kb_util.refresh_cmd(repo_root)
    refreshed = refresh_kb_metadata.main(["--kb-root", str(kb_util.kb_root(repo_root))])
    if refreshed != 0:
        return [Finding(FAIL, refresh, f"exited {refreshed}")]
    verify = kb_util.verify_cmd(repo_root)
    verified = kb_util.run_kb_verify(repo_root, skip_frontmatter_presence=False)
    if verified.failed:
        return [Finding(PASS, refresh, "exited 0"), Finding(FAIL, verify, f"exited 1 ({verified.detail()})")]
    return [Finding(PASS, refresh, "exited 0"), Finding(PASS, verify, "exited 0")]
