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

from adjagent.errors import InputError

# A virtual environment a shipped tool builds beside its package: not install output, so it is neither
# copied nor compared, and its presence alone never makes an install proceed.
VENV_DIR = ".venv"


@dataclass(frozen=True)
class Difference:
    """What an install would do to its target, each path a real one: the files it would create, those
    whose bytes or mode it would change, and those it would remove; and the lines it would print on
    stderr — what it would leave alone or skip — naming the real target."""

    created: tuple[Path, ...]
    changed: tuple[Path, ...]
    removed: tuple[Path, ...]
    reports: tuple[str, ...]

    def is_empty(self) -> bool:
        return not (self.created or self.changed or self.removed)


def _scratch_bases(bases: Sequence[Path], *, scratch: Path) -> tuple[list[Path], list[int]]:
    """Each real base's counterpart under `scratch`, in order, and the indexes of the outermost bases. A
    base inside an earlier one (symlinks followed) sits at the same position below that one's
    counterpart, so the relation between them holds in the copy; any other base is outermost and sits
    at `scratch/<index>/<its own name>`."""
    resolved = [base.resolve() for base in bases]
    placed: list[Path] = []
    outermost: list[int] = []
    for index, base in enumerate(resolved):
        outer = next((earlier for earlier in range(index) if base.is_relative_to(resolved[earlier])), None)
        if outer is None:
            placed.append(scratch / str(index) / base.name)
            outermost.append(index)
        else:
            placed.append(placed[outer] / base.relative_to(resolved[outer]))
    return placed, outermost


def _copy_tree(real: Path, copy: Path) -> None:
    """`real`'s tree into `copy`, symlinks below it dereferenced and every `.venv` left out."""
    shutil.copytree(
        real,
        copy,
        symlinks=False,
        ignore=shutil.ignore_patterns(VENV_DIR),
        ignore_dangling_symlinks=True,
        dirs_exist_ok=True,
    )


def _copy_managed(
    managed: Sequence[tuple[Path, Sequence[str]]], *, scratch_bases: Sequence[Path], scratch: Path
) -> None:
    """Copy each managed path that exists to the same position below its base's counterpart, every
    `.venv` left out. A managed path that is a symlink, dangling included, stays a symlink, so the
    install's own checks see what the real install sees: to the copy of what it reaches where the copy
    holds that below a base, and otherwise to a stand-in under `scratch`, outside every scratch base,
    holding a copy of what it reaches and nothing where it dangles. Every other symlink is dereferenced,
    so nothing in the copy points back into the target. A directory a managed path sits in is created
    where the real one exists, since an install's checks read whether it does."""
    links: list[tuple[Path, Path]] = []
    for (base, paths), scratch_base in zip(managed, scratch_bases):
        if base.is_dir():
            scratch_base.mkdir(parents=True, exist_ok=True)
        for relative in paths:
            real, copy = base / relative, scratch_base / relative
            if real.parent.is_dir():
                copy.parent.mkdir(parents=True, exist_ok=True)
            if os.path.islink(real):
                links.append((real, copy))
            elif real.is_dir():
                _copy_tree(real, copy)
            elif real.is_file():
                shutil.copy2(real, copy)
    # Linked once everything else is copied, so a link reaching another managed path finds its copy.
    real_bases = [base.resolve() for base, _ in managed]
    for index, (real, copy) in enumerate(links):
        # A managed path below this link was copied through it; the link replaces that copy.
        if copy.is_dir() and not copy.is_symlink():
            shutil.rmtree(copy)
        elif os.path.lexists(copy):
            copy.unlink()
        reached = real.resolve()
        counterparts = (
            scratch_base / reached.relative_to(real_base)
            for real_base, scratch_base in zip(real_bases, scratch_bases)
            if reached.is_relative_to(real_base)
        )
        counterpart = next((path for path in counterparts if os.path.lexists(path)), None)
        if counterpart is None:
            counterpart = scratch / "links" / str(index)
            counterpart.parent.mkdir(exist_ok=True)
            if reached.is_dir():
                _copy_tree(reached, counterpart)
            elif reached.is_file():
                shutil.copy2(reached, counterpart)
        copy.symlink_to(counterpart)


def _tree_files(base: Path) -> set[Path]:
    """Every file below `base`, relative to it, outside any `.venv`."""
    found: set[Path] = set()
    for directory, subdirs, names in os.walk(base):
        subdirs[:] = [name for name in subdirs if name != VENV_DIR]
        found.update(Path(directory, name).relative_to(base) for name in names)
    return found


def _differs(copy: Path, real: Path) -> bool:
    """Whether `copy` and `real` differ in bytes or in permission bits, a symlink read through. Two
    dangling symlinks do not differ; one dangling beside one that reaches a file does."""
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
            _copy_managed(managed, scratch_bases=scratch_bases, scratch=scratch)
            before = [_tree_files(scratch_base) for _, scratch_base in outer]
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
        for (base, scratch_base), prior in zip(outer, before):
            after = _tree_files(scratch_base)
            created += [base / relative for relative in sorted(after - prior)]
            removed += [base / relative for relative in sorted(prior - after)]
            changed += [
                base / relative
                for relative in sorted(after & prior)
                if _differs(scratch_base / relative, base / relative)
            ]
    return Difference(created=tuple(created), changed=tuple(changed), removed=tuple(removed), reports=reports)


def _shown(path: Path, *, report_root: Path) -> str:
    """`path` relative to `report_root` where it sits below it, else whole."""
    return str(path.relative_to(report_root)) if path.is_relative_to(report_root) else str(path)


def run_preflighted(
    managed: Sequence[tuple[Path, Sequence[str]]],
    *,
    install: Callable[[Sequence[Path]], None],
    dry_run: bool,
    target: Path,
    report_root: Path,
    dry_run_notes: Sequence[str] = (),
) -> None:
    """Run `install` into the real bases only where `preflight` finds it would change something. Where
    it would change nothing, report `target` up to date and write nothing. With `dry_run`, print what
    would be created, changed and removed, each path relative to `report_root`, then `dry_run_notes`
    — what the install would do beyond the files compared — and write nothing.
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
    for note in dry_run_notes:
        print(note)
    _print_reports(difference)


def _print_reports(difference: Difference) -> None:
    for line in difference.reports:
        print(line, file=sys.stderr)
