"""dupe_sweep — the corpus, read from git: tracked plus untracked non-ignored files, or a revision's tree.

Never a directory walk: the tree holds gitignored byte-copies of the swept sources (``rendered/``,
the installed surface under ``.claude/``, install targets under ``kb-testing/``), and a walk would
report every copy as a duplicate.
"""

import logging
import subprocess
from collections.abc import Sequence

from gen_defs.paths import REPO_ROOT

log = logging.getLogger(__name__)


class SweepError(Exception):
    """The sweep could not run at all — a bad revision, or git unavailable."""


def _git(*args: str) -> str:
    try:
        done = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=True
        )
    except FileNotFoundError as exc:  # git itself absent
        raise SweepError(
            "git is not on PATH — this sweep reads its corpus from git, not from a directory walk"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SweepError(f"git {' '.join(args)} failed: {exc.stderr.strip()}") from exc
    return done.stdout


def corpus(*, rev: str | None, prefixes: Sequence[str], suffix: str) -> dict[str, str]:
    """Repo-relative path -> text, for the tracked-or-untracked files under `prefixes`.

    `rev` None reads the working tree; otherwise the tree at that revision.
    """
    if rev is None:
        listing = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *prefixes)
    else:
        listing = _git("ls-tree", "-r", "-z", "--name-only", rev, "--", *prefixes)
    texts: dict[str, str] = {}
    for path in sorted(entry for entry in listing.split("\0") if entry.endswith(suffix)):
        if rev is not None:
            texts[path] = _git("show", f"{rev}:{path}")
            continue
        file = REPO_ROOT / path
        if not file.is_file():  # tracked, deleted in the working tree, not yet staged
            log.warning("%s is tracked but absent from the working tree — skipped", path)
            continue
        texts[path] = file.read_text(encoding="utf-8")
    if not texts:
        log.warning("no %s files under %s — the pass has nothing to compare", suffix, ", ".join(prefixes))
    return texts
