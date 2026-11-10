"""Where an install lands: the harness, the harness directory and the project root, resolved from the
target an operator names, without writing anything. ROOT, where the set is written, is not decided
here, nor whether the install is user-level: `install` derives both from the harness directory and the
harness.

The harness is, in order: the one `--harness` names; the one whose harness directory sits inside the
target — its project harness directory, or, in the home directory, its user harness directory; the
one the target itself is a harness directory of, matched on the target's trailing path elements;
otherwise none, and the install is refused. Every directory name is read from the harnesses' own
values, so none is spelled here. The target is normalised lexically, for that matching and for the
harness directory and project root built from it; it is resolved only where it is compared with the
home directory, so two spellings of home compare equal.
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
    """A resolved install: the harness's name; and the harness directory and the project root, each
    built from the target normalised."""

    harness: str
    harness_dir: Path
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
    return None if harness.is_harness_dir_plugin else harness.project_harness_dir


def _own_dir_names(harness: Harness) -> tuple[str, ...]:
    """The trailing paths a directory that is itself `harness`'s harness directory ends in. A harness-directory
    plugin's project harness directory is its own name, which a clone of this repository also bears, so
    such a plugin is known only by the directory its plugins sit in."""
    if harness.is_harness_dir_plugin:
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


def resolve_install_target(target: Path, *, harness: str | None, plugin: str, subdir: str | None) -> InstallTarget:
    """The harness, harness directory and project root for installing the plugin `plugin` into `target`.
    The harness is detected from values no plugin changes; the directories are then resolved with it
    bound to `plugin`. With `subdir` given, the harness directory is `<target>/<subdir>` (`""`: the
    target itself). Otherwise, in the home directory, it is the harness's user harness directory there;
    a target that is itself the nested-plugin harness's directory is the harness directory, under its
    parent as the project root; any other target holds it at `<target>/<project harness directory>`. A
    target that is not an existing directory is refused."""
    if not target.is_dir():
        cause = (
            "'~' was not expanded; pass an absolute path" if target.parts[:1] == ("~",) else "create the project first"
        )
        raise InputError(f"install target '{target}' is not an existing directory — {cause}")
    target = Path(os.path.normpath(target.absolute()))
    at_home = target.resolve() == Path.home().resolve()
    name = _detected_harness(target, at_home=at_home) if harness is None else harness
    selected = harness_named(name).bound(plugin)
    in_home = _user_dir_in_home(selected) if at_home else None
    project_root = target
    if subdir is not None:
        normalized = os.path.normpath(subdir)
        if os.path.isabs(subdir) or normalized == ".." or normalized.startswith("../"):
            raise InputError(f"--subdir '{subdir}' must name a directory inside the target — nothing written")
        harness_dir = target / subdir
    elif in_home is not None:
        harness_dir = target / in_home
    elif not selected.is_harness_dir_plugin and _is_own_dir(target, selected):
        harness_dir = target
        project_root = target.parent
    else:
        harness_dir = target / selected.project_harness_dir
    return InstallTarget(harness=name, harness_dir=harness_dir, project_root=project_root)


def _absolute_user_dir(harness: Harness) -> Path | None:
    """`harness`'s user harness directory, `~` expanded, or None where it is relative: a relative one
    names no directory of its own."""
    path = harness.user_dir
    return path if path.is_absolute() else None


def user_dir_harnesses(directory: Path) -> list[str]:
    """Every harness whose absolute user harness directory is `directory`, both resolved so two
    spellings of one directory compare equal."""
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
    raise InputError(f"cannot infer the harness for '{directory}': {cause} — pass --harness, one of {inferable}")
