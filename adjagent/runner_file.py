"""The include lines an install writes into the consumer's runner file (justfile or Makefile) so the
project can reach the runner snippets its shipped packages carry. Which snippet sets exist is the
caller's: each function here takes the set it is given."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from adjagent import install_base
from adjagent.context import harnesses
from adjagent.install_base import report_left_alone, utf8_text
from adjagent.render import appended_paragraph, write_text_verbatim

JUSTFILE_NAMES = ("justfile", "Justfile", ".justfile")
MAKEFILE_NAMES = ("Makefile", "makefile", "GNUmakefile")


class SnippetSet(NamedTuple):
    """Runner snippets a shipped package carries: the name messages call the set by, the snippets
    directory — below ROOT in every set the functions here take — and the snippet each runner's include
    line names — a justfile's `.just`, a Makefile's `.mk`."""

    label: str
    directory: str
    snippets: Mapping[str, str]


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


def _snippets_path(snippet_set: SnippetSet, *, runner: str, harness_relpath: str) -> str:
    """The canonical path `runner`'s include line names for `snippet_set`, relative to the project root."""
    return f"{harness_relpath}/{snippet_set.directory}/{snippet_set.snippets[runner]}"


def include_line(snippet_set: SnippetSet, *, runner: str, harness_relpath: str) -> str:
    """The canonical include line for `snippet_set` and `runner`: the non-fatal `import?` form for a
    justfile (just >= 1.33), or the `-include` form for a Makefile, each naming the installed snippets
    under the ROOT `harness_relpath` names relative to the project root."""
    snippets = _snippets_path(snippet_set, runner=runner, harness_relpath=harness_relpath)
    return {"just": f"import? '{snippets}'", "make": f"-include {snippets}"}[runner]


def _snippet_pattern(snippet_set: SnippetSet, *, runner: str) -> re.Pattern[str]:
    """An include line is recognized by the shape of the path it names, never by a list of spellings:
    any path ending `<directory>/<the set's snippets directory name>/<that runner's snippet>`, so a tree
    no release here wrote — the consumer's own hand — is still a line this install owns rather than one
    it appends a second copy beside. The path's first segment is the harness directory the line is a
    line for."""
    directory = re.escape(PurePosixPath(snippet_set.directory).name)
    snippet = re.escape(snippet_set.snippets[runner])
    return re.compile(rf"(?P<path>[^\s/'\"]+(?:/[^\s/'\"]+)*/{directory}/{snippet})")


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


def _named_harnesses(text: str, snippet_set: SnippetSet, *, runner: str) -> list[_NamedLine]:
    """A `_NamedLine` for every non-comment line naming `runner`'s installed snippets of `snippet_set`,
    under whatever tree the path spells; empty when no line names one. A commented-out line is prose
    about an install, not one."""
    dirs = _harness_dirs()
    pattern = _snippet_pattern(snippet_set, runner=runner)
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


def _with_include_line(
    text: str, snippet_set: SnippetSet, *, runner: str, path: Path, harness_relpath: str
) -> tuple[str, str | None]:
    """`text` with `snippet_set`'s include line in place, and the message naming the change; `text`
    unchanged and None where the line is reported and left."""
    label = snippet_set.label
    named = _named_harnesses(text, snippet_set, runner=runner)
    if len(named) > 1:
        indexes = ", ".join(str(match.index + 1) for match in named)
        report_left_alone(
            f"no include line written: {path} names the {label} snippets on lines {indexes}; merge them into one"
        )
        return text, None
    if not named:
        line = include_line(snippet_set, runner=runner, harness_relpath=harness_relpath)
        return appended_paragraph(text, line), f"installed: appended the {label} include line to {path}"
    match = named[0]
    lines = text.splitlines(keepends=True)
    prior = lines[match.index]
    # The line is this install's when it spells the same first segment — the harness directory — as
    # ROOT's path does; the whole path token, ROOT's own path below that segment included, is then
    # this install's to replace.
    if prior[match.start : match.end].split("/", 1)[0] != harness_relpath.split("/", 1)[0]:
        report_left_alone(
            f"no include line written: {path} line {match.index + 1} already includes the {label} "
            f"snippets for harness '{match.name}'"
        )
        return text, None
    canonical = _snippets_path(snippet_set, runner=runner, harness_relpath=harness_relpath)
    rewritten = f"{prior[: match.start]}{canonical}{prior[match.end :]}"
    if rewritten == prior:
        report_left_alone(
            f"no include line written: {path} line {match.index + 1} already names the installed "
            f"{label} snippets for harness '{match.name}'"
        )
        return text, None
    lines[match.index] = rewritten
    return "".join(lines), f"rewrote the {label} include line in {path}"


def install_include_lines(
    project: Path, snippet_sets: Sequence[SnippetSet], *, harness_relpath: str, real_project: Path | None = None
) -> None:
    """Write each of `snippet_sets`' canonical include lines, in order, into `project`'s runner file:
    the justfile or Makefile probed there, else a `Makefile` created carrying every one.

    Each set is judged alone, and one set's line never counts as another's. One line per set. A line
    naming this run's harness directory is recognized by the shape of the snippets path it names,
    whatever tree sits between its first segment — the harness directory, matched against the first
    segment of `harness_relpath` — and the snippets directory, and its whole path token is rewritten in
    place to the canonical one — so an assignment's left-hand side and a trailing comment survive — with
    no second line appended. A line naming another harness directory is reported and left alone, and so
    is a file holding more than one line for the set, which the operator merges by hand; either leaves
    the other sets' lines to be written. Only the runner file this run selected is examined: a second
    runner file's stale line is left to the operator and is non-fatal. Nothing is written when `project`
    is this repository — its own runner is the generator's, not a consumer's. `real_project`, defaulting
    to `project`, is the project that is, where `project` is a scratch copy of it."""
    if (project if real_project is None else real_project).resolve() == install_base.REPO_ROOT:
        return
    labels = " and ".join(snippet_set.label for snippet_set in snippet_sets)
    found = _runner_file(project)
    if found is None:
        path = project / "Makefile"
        lines = "".join(
            f"{include_line(snippet_set, runner='make', harness_relpath=harness_relpath)}\n"
            for snippet_set in snippet_sets
        )
        path.write_text(
            "# Makefile — created by the adjagent installer.\n"
            f"# Each include line below pulls in targets from the installed tree under {harness_relpath} "
            f"({labels}); add project targets below them.\n\n{lines}",
            encoding="utf-8",
        )
        print(f"created {path} with the include lines for {labels}")
        return
    runner, path = found
    prior = utf8_text(path)
    text = prior
    messages: list[str] = []
    for snippet_set in snippet_sets:
        text, message = _with_include_line(
            text, snippet_set, runner=runner, path=path, harness_relpath=harness_relpath
        )
        if message is not None:
            messages.append(message)
    if text != prior:
        write_text_verbatim(path, text)
    for message in messages:
        print(message)
