"""`python3 -m adjagent install-agents-file PLUGIN DIR [--harness NAME] [--dry-run]`: the harness agents
file of one plugin installed by replacing its block and keeping every other byte of the live file.

The block runs from the begin marker line through the end marker line. A marker line is recognised
by its whitespace-stripped ends alone, so a block any earlier revision wrote is still found. A live
file with one ordered marker pair has that span replaced; one with no marker line has the block
appended after a blank line; an absent file is written whole; any other file is refused. In the
harness's user directory the file is the harness's own name; anywhere else it is AGENTS.md, and a
harness that reads another name gets that file as the redirect `@AGENTS.md`. A destination whose only
content is `@<path>` is followed one hop, within DIR. A write that changes the file first copies it
to the one rolling `backup.<name>` beside it. Every check runs before the first write, and an
install into a harness's user directory is refused, when run from a checkout, while this package has
uncommitted changes; an install into a project directory is not.

The begin marker line carries the plugin whose block it is and the version that wrote it; a begin line
whose first word is no plugin's name is a block of no plugin, stamped with no release. A block of the
installing plugin whose lines between the markers already match is left as it stands, whatever its
stamp; any other is replaced unless its stamp is a later release than this one, which is reported
and left.

A project install keeps the block in one place (`checked_followed_agents_file`): in the harness's
user-global agents file where that already holds a marker line, as the plugin its begin line names
(the installing plugin's, for a block of no plugin), removing the project's AGENTS.md copy of the
span; and otherwise in the project's AGENTS.md, as the installing plugin's.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from adjagent.context import plugins
from adjagent.errors import InputError
from adjagent.harness import Harness
from adjagent.install_base import untranslated_text
from adjagent.install_target import user_dir_harnesses
from adjagent.plugin import Plugin
from adjagent.preflight import run_preflighted
from adjagent.render import appended_paragraph, render_agents_file, write_text_verbatim

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


def _has_no_marker_line(text: str) -> bool:
    return not any(_is_marker(line, BEGIN) or _is_marker(line, END) for line in text.split("\n"))


def _stamp_words(begin_line: str) -> list[str]:
    """The words of a begin marker line after the marker's opening."""
    return begin_line.strip().removeprefix(BEGIN[0]).split()


def _block_plugin(begin_line: str) -> Plugin | None:
    """The plugin a begin marker line names — its first word after the marker's opening, where that is a
    plugin's name — or None for a block of no plugin."""
    words = _stamp_words(begin_line)
    return plugins().get(words[0]) if words else None


def _release(begin_line: str) -> tuple[int, ...] | None:
    """The release version a begin marker line is stamped with — the word after its plugin's name,
    dot-separated digits — or None for a block of no plugin, or where that word is no such version."""
    words = _stamp_words(begin_line)
    if _block_plugin(begin_line) is None or len(words) < 2 or not re.fullmatch(r"\d+(?:\.\d+)*", words[1]):
        return None
    return tuple(int(part) for part in words[1].split("."))


def _stamp(release: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in release)


def _in_user_dir(harness: Harness, directory: Path) -> bool:
    """A relative user directory is resolved against `directory`, so mage's `.` is the destination
    itself; an absolute one is unaffected, since joining with an absolute path yields it."""
    return (directory / harness.user_dir).resolve() == directory.resolve()


def scope_name(harness: Harness, directory: Path) -> str:
    """`Global` in the harness's user directory, otherwise the directory's own name."""
    return GLOBAL_SCOPE if _in_user_dir(harness, directory) else Path(os.path.normpath(directory.absolute())).name


def _read(path: Path) -> str | None:
    """The file's text with line endings untranslated, or None when there is no file."""
    if not path.exists():
        return None
    try:
        return untranslated_text(path)
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
    if not Path(os.path.normpath(target.absolute())).is_relative_to(os.path.normpath(directory.absolute())):
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
    the harness's native file that takes the redirect, where one does, and why a differing block is
    left as it stands, where it is."""

    path: Path
    existing: str | None
    text: str
    destination: Path
    backup: Path
    native: Path | None
    left: str | None = None

    @property
    def paths(self) -> tuple[Path, ...]:
        """Every path the write reads or writes."""
        return (self.path, self.destination, self.backup, *(() if self.native is None else (self.native,)))


def _refuse_unless_directory(directory: Path) -> None:
    if not directory.is_dir():
        raise InputError(f"'{directory}' is not an existing directory")


def refuse_uncommitted(uncommitted: tuple[str, ...]) -> None:
    """Refuse while `uncommitted` (uncommitted_sources) names any change: an install into live operator
    configuration would publish sources nobody has committed."""
    if uncommitted:
        raise InputError(
            f"{__package__}/ has uncommitted changes ({', '.join(uncommitted)}) — commit them before "
            "installing; nothing written"
        )


def _refuse_uncommitted_in_user_dir(directory: Path, uncommitted: Callable[[], tuple[str, ...]]) -> None:
    """`refuse_uncommitted` where `directory` is a harness's absolute user directory; a project directory,
    mage's relative user directory included, is never refused and `uncommitted` is not called."""
    if user_dir_harnesses(directory):
        refuse_uncommitted(uncommitted())


def install_agents_file(
    directory: Path,
    harness: Harness,
    plugin: Plugin,
    *,
    uncommitted: Callable[[], tuple[str, ...]],
    real_directory: Path | None = None,
) -> None:
    """Install `harness`'s agents file for `plugin` into `directory`, refusing while `uncommitted`
    (uncommitted_sources) names any change and the directory is a harness's user directory; nothing is
    written until every check has passed. `real_directory` is as `checked_agents_file` takes it."""
    _refuse_unless_directory(directory)
    _refuse_uncommitted_in_user_dir(directory if real_directory is None else real_directory, uncommitted)
    write_agents_file(checked_agents_file(directory, harness, plugin, real_directory=real_directory))


def preflighted_agents_file_install(
    directory: Path, harness: Harness, plugin: Plugin, *, uncommitted: Callable[[], tuple[str, ...]], dry_run: bool
) -> None:
    """`install_agents_file` behind the preflight: run first into a scratch copy of the files it would
    read or write — the agents file, the destination it is reached through, the backup and the native
    redirect — then, where that changed nothing, `directory` is reported up to date and nothing is
    written; with `dry_run`, what would be created or changed is printed relative to `directory` and
    nothing is written; otherwise the install runs. Every refusal names `directory`, never the copy.
    `uncommitted` is called at most once, and only where `directory` is a harness's user directory."""
    _refuse_unless_directory(directory)
    commit_state = uncommitted() if user_dir_harnesses(directory) else ()
    _refuse_uncommitted_in_user_dir(directory, lambda: commit_state)
    write = checked_agents_file(directory, harness, plugin)
    run_preflighted(
        [(directory, [str(path.relative_to(directory)) for path in write.paths])],
        install=lambda bases: install_agents_file(
            bases[0], harness, plugin, uncommitted=lambda: commit_state, real_directory=directory
        ),
        dry_run=dry_run,
        target=directory,
        report_root=directory,
    )


def checked_agents_file(
    directory: Path, harness: Harness, plugin: Plugin, *, real_directory: Path | None = None
) -> AgentsFileWrite:
    """Every check of installing `harness`'s agents file for `plugin` into `directory`, writing nothing; the commit
    state of the sources is its callers' to check. An absent `directory` reads as an empty one.
    `real_directory` is the directory the file is for, where `directory` is a scratch copy of it:
    whether it is the harness's user directory, and the scope the file is titled with, are read from it.
    It defaults to `directory`."""
    identity = directory if real_directory is None else real_directory
    native = None
    destination = directory / harness.agents_file
    if not _in_user_dir(harness, identity) and harness.agents_file != STANDARD_AGENTS_FILE:
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
    rendered = render_agents_file(harness, plugin, scope=scope_name(harness, identity))
    left = None
    if existing is None:
        text = rendered
    else:
        new, begin, end = marker_span(rendered, where="the harness agents-file definition")
        block = new[begin : end + 1]
        if _has_no_marker_line(existing):
            text = appended_paragraph(existing, "\n".join(block))
        else:
            old, first, last = marker_span(existing, where=str(path))
            held, installing = _release(old[first]), _release(block[0])
            held_plugin = _block_plugin(old[first])
            if old[first + 1 : last] == block[1:-1] and held_plugin is not None and held_plugin.name == plugin.name:
                text = existing
            elif held is not None and installing is not None and installing < held:
                text = existing
                left = (
                    f"not downgraded: {path} holds the block from adjagent {_stamp(held)}, newer than this "
                    f"{_stamp(installing)} — left as it stands"
                )
            else:
                text = "\n".join([*old[:first], *block, *old[last + 1 :]])
    return AgentsFileWrite(
        path=path, existing=existing, text=text, destination=destination, backup=backup, native=native, left=left
    )


def _backed_up_write(path: Path, *, backup: Path, text: str) -> None:
    """Copy `path` to `backup`, then write `text` to `path`."""
    shutil.copyfile(path, backup)
    write_text_verbatim(path, text)


def write_agents_file(write: AgentsFileWrite) -> None:
    """Write what `checked_agents_file` passed, backing up a file it changes."""
    path = write.path
    via = "" if path == write.destination else f" (redirect {write.destination.name} followed)"
    if write.left is not None:
        print(write.left, file=sys.stderr)
    if write.text == write.existing:
        print(f"unchanged {path}{via}")
    else:
        if write.existing is None:
            write_text_verbatim(path, write.text)
            note = " — no prior file, no backup"
        else:
            _backed_up_write(path, backup=write.backup, text=write.text)
            note = f" — prior content backed up to {write.backup}"
        print(f"wrote {path}{via}{note}")
    if write.native is not None and not write.native.exists():
        write.native.write_text(f"{REDIRECT_PREFIX}{STANDARD_AGENTS_FILE}\n", encoding="utf-8")
        print(f"wrote {write.native} — redirect to {STANDARD_AGENTS_FILE}")


def _lenient_text(path: Path) -> str:
    """The file's text, undecodable bytes replaced; empty where there is no file. For deciding where the
    block lives, never for writing."""
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _followed_lenient_text(destination: Path) -> str:
    """`_lenient_text` of `destination`, or of the file a redirect there names."""
    text = _lenient_text(destination)
    reference = _redirect(text)
    return text if reference is None else _lenient_text(destination.parent / reference)


def _held_plugin(text: str) -> Plugin | None:
    """The plugin `text`'s one begin marker line names; None where it holds no such line, or more than
    one, or a block of no plugin."""
    begins = [line for line in text.split("\n") if _is_marker(line, BEGIN)]
    return _block_plugin(begins[0]) if len(begins) == 1 else None


@dataclass(frozen=True)
class ProjectCopyRemoval:
    """A project's copy of the block whose removal every check has passed: the file holding it and that
    file's present text, the text left once the span is gone, the destination it was reached through,
    and the rolling backup."""

    path: Path
    existing: str
    text: str
    destination: Path
    backup: Path

    @property
    def paths(self) -> tuple[Path, ...]:
        return (self.path, self.destination, self.backup)


def _checked_project_copy_removal(project: Path) -> ProjectCopyRemoval | None:
    """The removal of the block from `project`'s AGENTS.md, a redirect there followed; None where it
    holds no marker line, so a file without one is not read for writing."""
    destination = project / STANDARD_AGENTS_FILE
    if _has_no_marker_line(_followed_lenient_text(destination)):
        return None
    path, existing = _followed(destination, directory=project)
    lines, first, last = marker_span(existing or "", where=str(path))
    backup = path.with_name(BACKUP_PREFIX + path.name)
    return ProjectCopyRemoval(
        path=path,
        existing=existing or "",
        text="\n".join([*lines[:first], *lines[last + 1 :]]),
        destination=destination,
        backup=backup,
    )


@dataclass(frozen=True)
class FollowedAgentsFile:
    """Where a project install keeps the block current: the write that does it, and, where that write is
    into the user-global agents file, the removal of the project's own copy."""

    write: AgentsFileWrite
    removal: ProjectCopyRemoval | None

    @property
    def paths(self) -> tuple[Path, ...]:
        """Every path the install reads or writes for it."""
        return (*self.write.paths, *(() if self.removal is None else self.removal.paths))


def checked_followed_agents_file(
    project: Path,
    harness: Harness,
    plugin: Plugin,
    *,
    global_dir: Path,
    uncommitted: Callable[[], tuple[str, ...]],
    real_project: Path | None = None,
) -> FollowedAgentsFile:
    """Every check of keeping `harness`'s block current for a project install of `plugin`, writing nothing. Where
    the user-global agents file in `global_dir` holds a marker line, the block is kept there as the plugin
    its begin line names, or as `plugin`'s where that names none, refused while `uncommitted`
    (uncommitted_sources) names any change, and the project's AGENTS.md loses its copy of the span; the
    project's native file is not read. Otherwise `plugin`'s block is kept in the project's AGENTS.md as
    `checked_agents_file` keeps it, the native redirect included, whatever the commit state.
    `global_dir` may be a scratch copy of the harness's user harness directory, and `real_project` is
    as `checked_agents_file` takes `real_directory`."""
    global_text = _followed_lenient_text(global_dir / harness.agents_file)
    if _has_no_marker_line(global_text):
        return FollowedAgentsFile(
            write=checked_agents_file(project, harness, plugin, real_directory=real_project), removal=None
        )
    refuse_uncommitted(uncommitted())
    held = _held_plugin(global_text) or plugin
    write = checked_agents_file(global_dir, harness, held, real_directory=harness.user_dir)
    return FollowedAgentsFile(write=write, removal=_checked_project_copy_removal(project))


def write_followed_agents_file(followed: FollowedAgentsFile) -> None:
    """Write what `checked_followed_agents_file` passed: the block, then the removal of the project's copy,
    backed up and reported with why. The project's file stays, empty or not."""
    write_agents_file(followed.write)
    removal = followed.removal
    if removal is None:
        return
    _backed_up_write(removal.path, backup=removal.backup, text=removal.text)
    print(
        f"removed the adjagent block from {removal.path} — the user-global agents file {followed.write.path} "
        f"holds it — prior content backed up to {removal.backup}"
    )
