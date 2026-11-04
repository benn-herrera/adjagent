"""`python3 -m adjagent install-agents-file DIR [HARNESS]`: the harness agents file installed by
replacing its block and keeping every other byte of the live file.

The block runs from the begin marker line through the end marker line. A marker line is recognised
by its whitespace-stripped ends alone, so a block any earlier revision wrote is still found. A live
file with one ordered marker pair has that span replaced; an absent file is written whole; any other
file is refused. In the harness's user directory the file is the harness's own name; anywhere else
it is AGENTS.md, and a harness that reads another name gets that file as the redirect `@AGENTS.md`.
A destination whose only content is `@<path>` is followed one hop, within DIR. A write that changes
the file first copies it to the one rolling `backup.<name>` beside it. Every check runs before the
first write, and the install is refused, when run from a checkout, while this package has uncommitted
changes.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from adjagent.errors import InputError
from adjagent.harness import Harness
from adjagent.render import render_agents_file, write_text_verbatim

BEGIN = ("<!-- vvv-adjagent", "adjagent-vvv -->")
END = ("<!-- ^^^-adjagent", "adjagent-^^^ -->")
STANDARD_AGENTS_FILE = "AGENTS.md"
GLOBAL_SCOPE = "Global"
BACKUP_PREFIX = "backup."
REDIRECT_PREFIX = "@"


def _is_marker(line: str, marker: tuple[str, str]) -> bool:
    stripped = line.strip()
    return stripped.startswith(marker[0]) and stripped.endswith(marker[1])


def marker_span(text: str, *, where: str) -> tuple[list[str], int, int]:
    """`text` split at "\\n", with the index of its one begin marker line and its one end marker line,
    begin first; any other count or order is refused, naming `where`."""
    lines = text.split("\n")
    begins = [index for index, line in enumerate(lines) if _is_marker(line, BEGIN)]
    ends = [index for index, line in enumerate(lines) if _is_marker(line, END)]
    if len(begins) != 1 or len(ends) != 1 or begins[0] > ends[0]:
        raise InputError(
            f"{where}: found {len(begins)} begin and {len(ends)} end adjagent marker line(s) — the file needs one "
            "begin line followed by one end line around the block; nothing written"
        )
    return lines, begins[0], ends[0]


def _in_user_dir(harness: Harness, directory: Path) -> bool:
    """A relative user directory is resolved against `directory`, so mage's `.` is the destination
    itself; an absolute one is unaffected, since joining with an absolute path yields it."""
    return (directory / Path(harness.user_harness_dir).expanduser()).resolve() == directory.resolve()


def scope_name(harness: Harness, directory: Path) -> str:
    """`Global` in the harness's user directory, otherwise the directory's own name."""
    return GLOBAL_SCOPE if _in_user_dir(harness, directory) else directory.resolve().name


def _refuse_unless_regular_or_absent(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise InputError(f"{path} is a symlink or not a regular file — nothing written")


def _read(path: Path) -> str | None:
    """The file's text with line endings untranslated, or None when there is no file."""
    _refuse_unless_regular_or_absent(path)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            return stream.read()
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not UTF-8 text — nothing written") from exc


def _redirect(text: str | None) -> str | None:
    """The <path> of a text whose only non-blank line is `@<path>`, else None."""
    lines = [line.strip() for line in (text or "").split("\n") if line.strip()]
    if len(lines) != 1 or not lines[0].startswith(REDIRECT_PREFIX):
        return None
    return lines[0].removeprefix(REDIRECT_PREFIX) or None


def _followed(destination: Path, *, directory: Path) -> tuple[Path, str | None]:
    """The file an install into `destination` writes and its text: `destination` itself, or the one
    file a redirect there names, refused unless that is inside `directory`, in an existing directory,
    and not a redirect itself."""
    existing = _read(destination)
    reference = _redirect(existing)
    if reference is None:
        return destination, existing
    target = destination.parent / reference
    refusal = f"{destination} redirects to {target}"
    if not target.resolve().is_relative_to(directory.resolve()):
        raise InputError(f"{refusal}, which is outside {directory} — nothing written")
    if not target.parent.is_dir():
        raise InputError(f"{refusal}, whose directory does not exist — nothing written")
    existing = _read(target)
    if _redirect(existing) is not None:
        raise InputError(f"{refusal}, which is itself a redirect — one hop only; nothing written")
    return target, existing


@dataclass(frozen=True)
class AgentsFileWrite:
    """An agents-file install whose every check has passed: the file it writes and that file's present
    text, the text it writes there, the destination it reached that file through, the rolling backup,
    and the harness's native file that takes the redirect, where one does."""

    path: Path
    existing: str | None
    text: str
    destination: Path
    backup: Path
    native: Path | None


def install_agents_file(directory: Path, harness: Harness, *, uncommitted: tuple[str, ...]) -> None:
    """Install `harness`'s agents file into `directory`, refusing while `uncommitted`
    (uncommitted_sources) names any change; nothing is written until every check has passed."""
    if not directory.is_dir():
        raise InputError(f"'{directory}' is not an existing directory")
    write_agents_file(checked_agents_file(directory, harness, uncommitted=uncommitted))


def checked_agents_file(directory: Path, harness: Harness, *, uncommitted: tuple[str, ...]) -> AgentsFileWrite:
    """Every check of installing `harness`'s agents file into `directory`, writing nothing. An absent
    `directory` reads as an empty one."""
    if uncommitted:
        raise InputError(
            f"{__package__}/ has uncommitted changes ({', '.join(uncommitted)}) — commit them before "
            "installing; nothing written"
        )
    native = None
    destination = directory / harness.agents_file
    if not _in_user_dir(harness, directory) and harness.agents_file != STANDARD_AGENTS_FILE:
        native, destination = destination, directory / STANDARD_AGENTS_FILE
        native_text = _read(native)
        if native_text is not None and _redirect(native_text) != STANDARD_AGENTS_FILE:
            raise InputError(
                f"{native} holds its own content; outside {harness.user_harness_dir} the agents file is "
                f"{STANDARD_AGENTS_FILE} and {native.name} holds only '{REDIRECT_PREFIX}{STANDARD_AGENTS_FILE}' — "
                f"move its content into {destination} and leave that one line; nothing written"
            )
    path, existing = _followed(destination, directory=directory)
    if path == native:
        raise InputError(f"{destination} redirects to {native}, which may hold only the redirect — nothing written")
    backup = path.with_name(BACKUP_PREFIX + path.name)
    _refuse_unless_regular_or_absent(backup)
    rendered = render_agents_file(harness, scope=scope_name(harness, directory))
    if existing is None:
        text = rendered
    else:
        old, first, last = marker_span(existing, where=str(path))
        new, begin, end = marker_span(rendered, where="the harness agents-file definition")
        text = "\n".join([*old[:first], *new[begin : end + 1], *old[last + 1 :]])
    return AgentsFileWrite(
        path=path, existing=existing, text=text, destination=destination, backup=backup, native=native
    )


def write_agents_file(write: AgentsFileWrite) -> None:
    """Write what `checked_agents_file` passed, backing up a file it changes."""
    path = write.path
    via = "" if path == write.destination else f" (redirect {write.destination.name} followed)"
    if write.text == write.existing:
        print(f"unchanged {path}{via}")
    else:
        if write.existing is None:
            note = " — no prior file, no backup"
        else:
            shutil.copyfile(path, write.backup)
            note = f" — prior content backed up to {write.backup}"
        write_text_verbatim(path, write.text)
        print(f"wrote {path}{via}{note}")
    if write.native is not None and not write.native.exists():
        write.native.write_text(f"{REDIRECT_PREFIX}{STANDARD_AGENTS_FILE}\n", encoding="utf-8")
        print(f"wrote {write.native} — redirect to {STANDARD_AGENTS_FILE}")
