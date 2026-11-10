"""The include line an install writes into the consumer's runner file (justfile or Makefile) so the
project can reach the kb toolchain's installed snippets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from adjagent import install_base
from adjagent.context import harnesses
from adjagent.install_base import KB_TOOLS_DIR, report_left_alone, utf8_text
from adjagent.render import appended_paragraph, write_text_verbatim

RUNNER_SNIPPETS = "runner-snippets"
KB_TOOLS_SNIPPETS = f"{KB_TOOLS_DIR}/{RUNNER_SNIPPETS}"
# The snippet each runner's include line pulls in — a justfile imports `kb.just`, a Makefile includes
# `kb.mk` — and the suffix that makes a line a line for that runner.
KB_SNIPPET_NAMES = {"just": "kb.just", "make": "kb.mk"}
# A runner include line is recognized by the shape of the path it names, never by a list of spellings:
# any path ending `<directory>/runner-snippets/<that runner's snippet>`, so a tree no release here
# wrote — the consumer's own hand — is still a line this install
# owns rather than one it appends a second copy beside. The path's first segment is the harness
# directory the line is a line for.
_SNIPPET_PATTERNS = {
    runner: re.compile(rf"(?P<path>[^\s/'\"]+(?:/[^\s/'\"]+)*/{RUNNER_SNIPPETS}/{re.escape(snippet)})")
    for runner, snippet in KB_SNIPPET_NAMES.items()
}
JUSTFILE_NAMES = ("justfile", "Justfile", ".justfile")
MAKEFILE_NAMES = ("Makefile", "makefile", "GNUmakefile")


def _runner_file(project: Path) -> tuple[str, Path] | None:
    """(runner, file) probed at the project root: any justfile variant selects `just`, else any make
    variant selects `make`."""
    for runner, names in (("just", JUSTFILE_NAMES), ("make", MAKEFILE_NAMES)):
        for name in names:
            if (project / name).exists():
                return runner, project / name
    return None


def check_runner(project: Path) -> None:
    """Read `project`'s runner file before an install's first write: an unreadable or undecodable file is
    refused there, not raised out of the write phase with packages and renders already landed."""
    found = _runner_file(project)
    if found is not None:
        utf8_text(found[1])


def kb_include_line(*, runner: str, harness_relpath: str) -> str:
    """The canonical KB include line for `runner`: the non-fatal `import?` form for a justfile (just
    >= 1.33), or the `-include` form for a Makefile, each naming the installed snippets under the ROOT
    `harness_relpath` names relative to the project root."""
    snippets = f"{harness_relpath}/{KB_TOOLS_SNIPPETS}/{KB_SNIPPET_NAMES[runner]}"
    return {"just": f"import? '{snippets}'", "make": f"-include {snippets}"}[runner]


def _harness_dirs() -> dict[str, str]:
    """harness name → its project-harness-dir, for every harness this installation knows."""
    return {name: harness.project_harness_dir for name, harness in harnesses().items()}


class _NamedLine(NamedTuple):
    """An existing runner include line `_named_harnesses` recognized: the harness it names — or the raw
    first path segment when no harness claims it — its index in the file, and the span of the snippets
    path it spells."""

    name: str
    index: int
    start: int
    end: int


def _named_harnesses(text: str, *, runner: str) -> list[_NamedLine]:
    """A `_NamedLine` for every non-comment line naming `runner`'s installed kb-tools snippets, under
    whatever tree the path spells; empty when no line names one. A commented-out line is prose about an
    install, not one."""
    dirs = _harness_dirs()
    pattern = _SNIPPET_PATTERNS[runner]
    found: list[_NamedLine] = []
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("#"):
            continue
        match = pattern.search(line)
        if match is None:
            continue
        start, end = match.span("path")
        segment = line[start:end].split("/", 1)[0]
        name = next((name for name, directory in dirs.items() if directory == segment), segment)
        found.append(_NamedLine(name, index, start, end))
    return found


def install_kb_include_line(project: Path, *, harness_relpath: str, real_project: Path | None = None) -> None:
    """Write the canonical KB include line into `project`'s runner file: the justfile or Makefile
    probed there, else a `Makefile` created carrying it.

    One line only. A line naming this run's harness directory is recognized by the shape of the snippets
    path it names, whatever tree sits between its first segment — the harness directory, matched against
    the first segment of `harness_relpath` — and `runner-snippets/`, and its whole path token is
    rewritten in place to the canonical one — so an assignment's left-hand side and a trailing comment
    survive — with no second line appended. A line naming another harness directory is reported and
    left alone, and so is a file holding more
    than one such line, which the operator merges by hand. Only the runner file this run selected is
    examined: a second runner file's stale line is left to the operator and is non-fatal. Nothing is
    written when `project` is this repository — its own runner is the generator's, not a consumer's.
    `real_project`, defaulting to `project`, is the project that is, where `project` is a scratch copy
    of it."""
    if (project if real_project is None else real_project).resolve() == install_base.REPO_ROOT:
        return
    found = _runner_file(project)
    if found is None:
        path = project / "Makefile"
        path.write_text(
            "# Makefile — created by the adjagent installer.\n"
            f"# The line below pulls in the KB maintenance targets from the installed tree under "
            f"{harness_relpath}; add project targets below it.\n\n"
            f"{kb_include_line(runner='make', harness_relpath=harness_relpath)}\n",
            encoding="utf-8",
        )
        print(f"created {path} with the KB include line")
        return
    runner, path = found
    text = utf8_text(path)
    named = _named_harnesses(text, runner=runner)
    if len(named) > 1:
        indexes = ", ".join(str(match.index + 1) for match in named)
        report_left_alone(
            f"no include line written: {path} names the kb snippets on lines {indexes}; merge them into one"
        )
        return
    if named:
        match = named[0]
        lines = text.splitlines(keepends=True)
        prior = lines[match.index]
        # The line is this install's when it spells the same first segment — the harness directory — as
        # ROOT's path does; the whole path token, ROOT's own path below that segment included, is then
        # this install's to replace.
        if prior[match.start : match.end].split("/", 1)[0] != harness_relpath.split("/", 1)[0]:
            report_left_alone(
                f"no include line written: {path} line {match.index + 1} already includes the kb "
                f"snippets for harness '{match.name}'"
            )
            return
        canonical = f"{harness_relpath}/{KB_TOOLS_SNIPPETS}/{KB_SNIPPET_NAMES[runner]}"
        rewritten = f"{prior[: match.start]}{canonical}{prior[match.end :]}"
        if rewritten == prior:
            report_left_alone(
                f"no include line written: {path} line {match.index + 1} already names the installed "
                f"kb snippets for harness '{match.name}'"
            )
            return
        lines[match.index] = rewritten
        write_text_verbatim(path, "".join(lines))
        print(f"rewrote the KB include line in {path}")
        return
    line = kb_include_line(runner=runner, harness_relpath=harness_relpath)
    write_text_verbatim(path, appended_paragraph(text, line))
    print(f"installed: appended the KB include line to {path}")
