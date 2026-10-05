"""The one module that knows how a graph is drawn.

Everything the package draws goes through :func:`to_svg`, and nothing else in
it names the ``dot`` binary or builds an argv for it, so replacing the layout
engine is one module's rewrite. ``tests/test_binary_monopoly.py`` is what says
the monopoly still holds on each run.

The binary is Graphviz's, assumed present on the system. This module neither
installs nor vendors it, and an absent one is :exc:`DotMissingError` naming what
to do — never the ``FileNotFoundError`` subprocess would otherwise raise.

``dot -V`` on the dev host, verbatim (it writes to stderr, not stdout)::

    dot - graphviz version 16.1.0 (20260904.0139)

Stdlib only.
"""

import logging
import re
import shutil
import subprocess
from collections.abc import Sequence

_log = logging.getLogger(__name__)

#: The binary, spelled once for the whole package.
BINARY = "dot"

#: Where the binary comes from, named by every message about its absence.
INSTALL_URL = "https://graphviz.org/download/"

#: What a drawing stands in for when the binary is absent: the reason, then the remedy. Fixed at
#: import, so a placeholder's bytes never depend on how the binary was looked up.
ABSENT_NOTICE: tuple[str, str] = (
    f"This diagram is drawn by Graphviz {BINARY}, which was not installed when it was generated.",
    f"Install Graphviz from {INSTALL_URL} and refresh the KB to draw it.",
)

#: The version token in ``dot -V``'s banner, as the release prints it.
_VERSION_RE = re.compile(r"\bgraphviz version (\S+)")


class DotError(RuntimeError):
    """``dot`` exited nonzero; the message carries the argv, the exit code and its stderr."""


class DotMissingError(DotError):
    """The binary is not on PATH.

    Its own type because the remediation differs in kind — install a program,
    rather than fix the graph composed for it.
    """


def version() -> str:
    """The version of the binary behind this seam, e.g. ``"16.1.0"``."""
    banner = _run(["-V"], stdin="").stderr.strip()
    found = _VERSION_RE.search(banner)
    if found is None:
        raise DotError(f"unrecognized `{BINARY} -V` output: {banner!r}")
    return found.group(1)


def to_svg(dot_text: str) -> str:
    """Lay out ``dot_text`` and return the SVG ``dot -Tsvg`` writes."""
    completed = _run(["-Tsvg"], stdin=dot_text)
    complaint = completed.stderr.strip()
    if complaint:
        _log.warning("%s exited 0 but wrote to stderr: %s", BINARY, complaint)
    return completed.stdout


def _missing() -> DotMissingError:
    return DotMissingError(
        f"Graphviz `{BINARY}` is not on PATH. This toolchain draws the claim-graph sheets by invoking it and "
        f"does not install or vendor it — install Graphviz ({INSTALL_URL}) and re-run."
    )


def _run(arguments: Sequence[str], *, stdin: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``dot``; the binary absent and a nonzero exit are raised as :exc:`DotError`.

    An absent binary is found by lookup rather than by a failed spawn, so a
    host without Graphviz spawns nothing at all; the spawn's own
    ``FileNotFoundError`` still covers a binary removed between the two.
    """
    if shutil.which(BINARY) is None:
        raise _missing()
    argv = [BINARY, *arguments]
    try:
        completed = subprocess.run(argv, input=stdin, capture_output=True, text=True, encoding="utf-8", check=False)
    except FileNotFoundError as absent:
        raise _missing() from absent
    if completed.returncode != 0:
        raise DotError(
            f"`{' '.join(argv)}` exited {completed.returncode}: {completed.stderr.strip() or '<no stderr>'}"
        )
    return completed
