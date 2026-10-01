"""Where this toolchain is installed, read off the package's own path.

kb_tools runs installed under a coding-agent harness's project directory —
``<project>/.claude/agents/kb_tools`` or ``<project>/.opencode/agents/kb_tools``
— and that directory decides every harness-named path the toolchain spells: the
PYTHONPATH entry a consumer's command line carries, the include line its runner
file holds, and the project's scratch directory. :func:`current` finds it by
walking up from this file to the nearest ancestor carrying a harness
directory's name.

Paths are taken as the import system gave them, never resolved: a tree reached
through a symlinked ``agents/`` is located at the link, which is where its
consumer named it.

The consuming repository's root is not read here; it stays cwd-anchored
(``kb_util.find_repo_root``). Stdlib only.
"""

from dataclasses import dataclass
from pathlib import Path

HARNESS_DIRNAMES = (".claude", ".opencode")


class InstallLocationError(RuntimeError):
    """kb_tools is not sitting under any harness directory."""


@dataclass(frozen=True)
class InstallLocation:
    """One installed toolchain's harness directory, and what it decides."""

    harness_dir: Path

    @property
    def project_root(self) -> Path:
        return self.harness_dir.parent

    @property
    def agents_dir(self) -> Path:
        """The PYTHONPATH entry: the directory the ``kb_tools`` package sits in."""
        return self.harness_dir / "agents"

    @property
    def agents_relpath(self) -> str:
        """:attr:`agents_dir` as a consumer spells it from the project root."""
        return self.agents_dir.relative_to(self.project_root).as_posix()

    @property
    def scratch_dir(self) -> Path:
        """The project's scratch directory: ``.claude-temp`` beside ``.claude``, and so on."""
        return self.project_root / f"{self.harness_dir.name}-temp"


def locate(start: Path) -> InstallLocation:
    """The installed location ``start`` sits in: its nearest harness-named ancestor."""
    for ancestor in start.parents:
        if ancestor.name in HARNESS_DIRNAMES:
            return InstallLocation(harness_dir=ancestor)
    raise InstallLocationError(
        f"{start} sits under no {' or '.join(HARNESS_DIRNAMES)} directory, so kb_tools cannot tell "
        f"which project it serves. Invoke the installed copy: "
        f"PYTHONPATH={' or '.join(f'<project>/{name}/agents' for name in HARNESS_DIRNAMES)}. "
        f"If the project has neither, the agent set is not installed there — installing it is the "
        f"operator's act."
    )


def current() -> InstallLocation:
    """Where this copy of kb_tools is installed. Raises :class:`InstallLocationError` when nowhere."""
    return locate(Path(__file__))
