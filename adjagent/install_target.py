"""Where an install lands: the harness, ROOT and the project root, resolved from the target an
operator names, without writing anything. Whether ROOT is user-level is not decided here: `install`
derives it from ROOT and the harness.

The harness is, in order: the one `--harness` names; the one whose harness directory sits inside the
target — its project harness directory, or, in the home directory, its user harness directory; the
one the target itself is a harness directory of, matched on the target's trailing path elements;
otherwise none, and the install is refused. Every directory name is read from the harnesses' own
values, so none is spelled here. The target is normalised lexically, for that matching; symlinks are
followed only for the home-directory comparison and the project root.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from adjagent.context import harness_named, harnesses
from adjagent.errors import InputError
from adjagent.harness import Harness

_HOME_PREFIX = "~/"


@dataclass(frozen=True)
class InstallTarget:
    """A resolved install: the harness's name; ROOT, built from the target normalised without following
    symlinks; and the project root, symlinks followed."""

    harness: str
    root: Path
    project_root: Path


def _user_dir_in_home(harness: Harness) -> str | None:
    """`harness`'s user harness directory relative to the home directory, None where it is not one."""
    home = harness.user_harness_dir
    return home.removeprefix(_HOME_PREFIX) if home.startswith(_HOME_PREFIX) else None


def _dir_inside(harness: Harness, *, at_home: bool) -> str | None:
    """The directory whose presence inside a target selects `harness`: its user harness directory in
    the home directory, its project harness directory anywhere else, and never a plugin's."""
    if at_home:
        return _user_dir_in_home(harness)
    return None if harness.is_plugin else harness.project_harness_dir


def _own_dir_names(harness: Harness) -> tuple[str, ...]:
    """The trailing paths a directory that is itself `harness`'s harness directory ends in. A plugin's
    project harness directory is the plugin's own name, which a clone of this repository also bears, so
    a plugin is known only by the directory its plugins sit in."""
    if harness.is_plugin:
        return (harness.plugin_parent_dir,) if harness.plugin_parent_dir else ()
    in_home = _user_dir_in_home(harness)
    return (harness.project_harness_dir, *(() if in_home is None else (in_home,)))


def _is_own_dir(target: Path, harness: Harness) -> bool:
    """Whether the normalised `target` ends in one of `harness`'s own directory names."""
    return any(
        target.parts[-len(trailing) :] == trailing
        for trailing in (PurePosixPath(name).parts for name in _own_dir_names(harness))
    )


def _only(target: Path, matches: dict[str, str]) -> str | None:
    """The one harness `matches` names (harness → what matched), None for none; several are refused."""
    if len(matches) > 1:
        found = " and ".join(f"'{what}' ({name})" for name, what in matches.items())
        raise InputError(f"'{target}' matches {found} — pass --harness=NAME to choose one; nothing written")
    return next(iter(matches), None)


def _detected_harness(target: Path, *, at_home: bool) -> str:
    known = harnesses()
    inside = {
        name: directory
        for name, harness in known.items()
        if (directory := _dir_inside(harness, at_home=at_home)) is not None and (target / directory).is_dir()
    }
    found = _only(target, inside)
    if found is None:
        found = _only(target, {name: str(target) for name, harness in known.items() if _is_own_dir(target, harness)})
    if found is None:
        raise InputError(
            f"cannot tell the harness for '{target}': it holds no harness directory and is not one — "
            f"pass --harness=NAME, one of {', '.join(known)}; nothing written"
        )
    return found


def resolve_install_target(target: Path, *, harness: str | None, subdir: str | None) -> InstallTarget:
    """The harness, ROOT and project root for installing into `target`. With `subdir` given, ROOT is
    `<target>/<subdir>` (`""`: the target itself). Otherwise, in the home directory, ROOT is the
    harness's user harness directory there; a target that is itself the non-plugin harness's directory
    is ROOT, under its parent as the project root; any other target holds ROOT at
    `<target>/<project harness directory>`. A target that is not an existing directory is refused."""
    if not target.is_dir():
        cause = (
            "'~' was not expanded; pass an absolute path" if target.parts[:1] == ("~",) else "create the project first"
        )
        raise InputError(f"install target '{target}' is not an existing directory — {cause}")
    target = Path(os.path.normpath(target.absolute()))
    at_home = target.resolve() == Path.home().resolve()
    name = _detected_harness(target, at_home=at_home) if harness is None else harness
    selected = harness_named(name)
    in_home = _user_dir_in_home(selected) if at_home else None
    project_root = target.resolve()
    if subdir is not None:
        root = target / subdir
    elif in_home is not None:
        root = target / in_home
    elif not selected.is_plugin and _is_own_dir(target, selected):
        root = target
        project_root = target.parent.resolve()
    else:
        root = target / selected.project_harness_dir
    return InstallTarget(harness=name, root=root, project_root=project_root)


def _absolute_user_dir(harness: Harness) -> Path | None:
    """`harness`'s user harness directory, `~` expanded, or None where it is relative: a relative one
    names no directory of its own."""
    path = Path(harness.user_harness_dir).expanduser()
    return path if path.is_absolute() else None


def user_dir_harnesses(directory: Path) -> list[str]:
    """Every harness whose absolute user harness directory is `directory`, symlinks followed on both
    sides."""
    resolved = directory.resolve()
    return [
        name
        for name, harness in harnesses().items()
        if (user_dir := _absolute_user_dir(harness)) is not None and user_dir.resolve() == resolved
    ]


def agents_file_harness(directory: Path, harness: str | None) -> str:
    """`harness`, or — when it is None or "" — the one harness whose user harness directory is
    `directory`; none or several are refused, naming the harnesses inference covers."""
    if harness:
        return harness
    matches = user_dir_harnesses(directory)
    if len(matches) == 1:
        return matches[0]
    inferable = ", ".join(name for name, entry in harnesses().items() if _absolute_user_dir(entry) is not None)
    if matches:
        cause = f"it is the user directory of {' and '.join(matches)}"
    else:
        cause = "it is no harness's user directory"
    raise InputError(f"cannot infer the harness for '{directory}': {cause} — pass HARNESS, one of {inferable}")
