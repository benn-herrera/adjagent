"""The preflight `install` and `install-agents-file` run before writing anything: the unchanged install,
run into a scratch copy of the paths it manages, and that copy compared with the target. The result
decides the run: the target is up to date and untouched, or `--dry-run` prints what would change, or
the real install runs. The install itself decides what is written, run where its writes cannot reach
the target; `install._install_managed_paths` names where it may write, and the tests'
`_assert_dry_run_predicts` holds the two together."""

from __future__ import annotations

import contextlib
import filecmp
import io
import os
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from devpro.errors import InputError
from devpro.install_base import VENV_DIR


@dataclass(frozen=True)
class Difference:
    """What an install would do to its target, each path a real one: the files it would create, those
    whose bytes or mode it would change, and the files and directories it would remove; and the lines it would print on
    stderr — what it would leave alone or skip — naming the real target."""

    created: tuple[Path, ...]
    changed: tuple[Path, ...]
    removed: tuple[Path, ...]
    reports: tuple[str, ...]

    def is_empty(self) -> bool:
        return not (self.created or self.changed or self.removed)


def _scratch_bases(bases: Sequence[Path], *, scratch: Path) -> tuple[list[Path], list[int]]:
    """Each real base's counterpart under `scratch`, in order, and the indexes of the outermost bases. A
    base inside an earlier one, both made absolute and normalized, sits at the same position below that
    one's counterpart, so the relation between them holds in the copy; any other base is outermost and
    sits at `scratch/<index>/<its own name>`."""
    normalized = [Path(os.path.normpath(base.absolute())) for base in bases]
    placed: list[Path] = []
    outermost: list[int] = []
    for index, base in enumerate(bases):
        nesting = next(
            (
                (earlier, normalized[index].relative_to(normalized[earlier]))
                for earlier in range(index)
                if normalized[index].is_relative_to(normalized[earlier])
            ),
            None,
        )
        if nesting is None:
            placed.append(scratch / str(index) / base.name)
            outermost.append(index)
        else:
            earlier, relative = nesting
            placed.append(placed[earlier] / relative)
    return placed, outermost


def _copy_managed(managed: Sequence[tuple[Path, Sequence[str]]], *, scratch_bases: Sequence[Path]) -> None:
    """Copy each managed path that exists to the same position below its base's counterpart: a directory
    as its tree, every `.venv` left out, and a file as its bytes. A directory a managed path sits in is
    created where the real one exists, since an install's checks read whether it does; where a regular
    file stands in its place instead, or in a base's, the outermost such file is copied, so the install
    meets the same obstacle."""
    for (base, paths), scratch_base in zip(managed, scratch_bases):
        if base.is_dir():
            scratch_base.mkdir(parents=True, exist_ok=True)
        elif base.is_file():
            scratch_base.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(base, scratch_base)
            continue
        for relative in paths:
            real, copy = base / relative, scratch_base / relative
            if real.parent.is_dir():
                copy.parent.mkdir(parents=True, exist_ok=True)
            else:
                obstacle = next(
                    (
                        parent
                        for parent in reversed(tuple(Path(relative).parents)[:-1])
                        if (base / parent).exists() and not (base / parent).is_dir()
                    ),
                    None,
                )
                if obstacle is not None and (base / obstacle).is_file():
                    (scratch_base / obstacle).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(base / obstacle, scratch_base / obstacle)
            if real.is_dir():
                shutil.copytree(real, copy, ignore=shutil.ignore_patterns(VENV_DIR), dirs_exist_ok=True)
            elif real.is_file():
                shutil.copy2(real, copy)


def _tree(base: Path) -> tuple[set[Path], set[Path]]:
    """Every file and every directory below `base`, relative to it, outside any `.venv`."""
    files: set[Path] = set()
    directories: set[Path] = set()
    for directory, subdirs, names in os.walk(base):
        subdirs[:] = [name for name in subdirs if name != VENV_DIR]
        files.update(Path(directory, name).relative_to(base) for name in names)
        directories.update(Path(directory, name).relative_to(base) for name in subdirs)
    return files, directories


def _differs(copy: Path, real: Path) -> bool:
    """Whether `copy` and `real` differ in bytes or in permission bits."""
    if not (copy.exists() and real.exists()):
        return copy.exists() != real.exists()
    if not filecmp.cmp(copy, real, shallow=False):
        return True
    return stat.S_IMODE(copy.stat().st_mode) != stat.S_IMODE(real.stat().st_mode)


def _in_real_terms(message: str, *, scratch_bases: Sequence[Path], bases: Sequence[Path]) -> str:
    """`message` with every scratch base replaced by the real base it stands for, the longest first so
    a base nested in another is replaced whole."""
    for scratch_base, base in sorted(zip(scratch_bases, bases), key=lambda pair: len(str(pair[0])), reverse=True):
        message = message.replace(str(scratch_base), str(base))
    return message


def preflight(
    managed: Sequence[tuple[Path, Sequence[str]]], *, install: Callable[[Sequence[Path]], None]
) -> Difference:
    """The difference `install` would make to the files `managed` names, found by running it into a
    scratch copy of them and comparing. `managed` is (base, paths relative to it) per real directory the
    install writes under, outermost first; `install` takes the bases it is to write under, in the same
    order. Its stdout is discarded and its stderr kept as the difference's reports; an `InputError` it
    raises, or an `OSError` the copy or the run raises, is raised as an `InputError`; each names the
    real bases. The copy is removed before this returns."""
    bases = [base for base, _ in managed]
    with tempfile.TemporaryDirectory() as temp:
        scratch = Path(temp).resolve()
        scratch_bases, outermost = _scratch_bases(bases, scratch=scratch)
        # A nested base's files are found through the base that holds it.
        outer = [(bases[index], scratch_bases[index]) for index in outermost]
        stderr = io.StringIO()
        try:
            _copy_managed(managed, scratch_bases=scratch_bases)
            before = [_tree(scratch_base) for _, scratch_base in outer]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                install(scratch_bases)
        except (InputError, OSError) as exc:
            raise InputError(_in_real_terms(str(exc), scratch_bases=scratch_bases, bases=bases)) from exc
        reports = tuple(
            _in_real_terms(line, scratch_bases=scratch_bases, bases=bases) for line in stderr.getvalue().splitlines()
        )
        created: list[Path] = []
        changed: list[Path] = []
        removed: list[Path] = []
        for (base, scratch_base), (prior, prior_directories) in zip(outer, before):
            after, after_directories = _tree(scratch_base)
            created += [base / relative for relative in sorted(after - prior)]
            removed += [
                base / relative for relative in sorted((prior - after) | (prior_directories - after_directories))
            ]
            changed += [
                base / relative
                for relative in sorted(after & prior)
                if _differs(scratch_base / relative, base / relative)
            ]
    return Difference(created=tuple(created), changed=tuple(changed), removed=tuple(removed), reports=reports)


def _shown(path: Path, *, report_root: Path) -> str:
    """`path` relative to `report_root` where it sits below it, else whole; a directory with a trailing
    `/`."""
    shown = str(path.relative_to(report_root)) if path.is_relative_to(report_root) else str(path)
    return f"{shown}/" if path.is_dir() else shown


def run_preflighted(
    managed: Sequence[tuple[Path, Sequence[str]]],
    *,
    install: Callable[[Sequence[Path]], None],
    dry_run: bool,
    target: Path,
    report_root: Path,
) -> None:
    """Run `install` into the real bases only where `preflight` finds it would change something. Where
    it would change nothing, report `target` up to date and write nothing. With `dry_run`, print what
    would be created, changed and removed, each path relative to `report_root`, and write nothing.
    Where nothing is written, what the install would have left alone or skipped is printed on stderr;
    the real install prints its own."""
    difference = preflight(managed, install=install)
    if difference.is_empty():
        print(f"up to date: {target} — nothing written")
        _print_reports(difference)
        return
    if not dry_run:
        install([base for base, _ in managed])
        return
    print(f"dry run, nothing written — the install would change these files under {report_root}:")
    for group, paths in (
        ("created", difference.created),
        ("changed", difference.changed),
        ("removed", difference.removed),
    ):
        if paths:
            print(f"{group}:")
            for path in paths:
                print(f"  {_shown(path, report_root=report_root)}")
    _print_reports(difference)


def _print_reports(difference: Difference) -> None:
    for line in difference.reports:
        print(line, file=sys.stderr)
