"""The binary monopolies, as a mechanical assertion rather than a convention.

``kb_tools/pandoc.py`` is the only module that knows how LaTeX gets read, and
``kb_tools/dot.py`` the only one that knows how a graph is drawn. Nothing else in
the package names either binary or spells one of its flags into an argv, so
replacing either is one module's rewrite rather than the package's.

**The sweep is the whole instrument.** Each binary is reached by subprocess, so
there is no import to observe: the property is entirely about what the sources
name, and the teeth (:func:`test_the_sweep_reads_argv_and_not_prose`) carry the
weight.

**What counts as naming a binary**: a string constant matching that seam's
rule, that is not a docstring or other bare string expression. ``from kb_tools
import pandoc`` is a module *using* the seam and reaches no such constant;
``subprocess.run(["pandoc", ...])`` is a second caller and does. A prose mention
is not a dependency. The two rules differ because the names do: ``pandoc`` is a
substring of nothing else, so any case of it counts, while ``dot`` is a
substring of ``dotted``, a Graphviz style this package writes — so it counts
only as a whole word, in the case the binary is spelled.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

import kb_tools

#: The swept package, and the two subtrees inside it that are out of scope:
#: ``_vendor`` is third-party source this repository never edits, and the test
#: tree names the binaries by construction — this module plants argv shapes
#: below, and each seam's own test drives the real binary.
_SWEPT_ROOT = Path(kb_tools.__file__).resolve().parent
_REPO_ROOT = _SWEPT_ROOT.parent
_UNSWEPT_PARTS = frozenset({"_vendor", "tests"})


@dataclass(frozen=True)
class Seam:
    """A binary's one module, named by path rather than found by rule: it is the definition site."""

    path: str
    names: re.Pattern[str]


PANDOC = Seam("kb_tools/pandoc.py", re.compile("pandoc", re.IGNORECASE))
DOT = Seam("kb_tools/dot.py", re.compile(r"\bdot\b"))
SEAMS = pytest.mark.parametrize("seam", [PANDOC, DOT], ids=["pandoc", "dot"])


def _named_in_argv(source: str, seam: Seam) -> set[str]:
    """Every string constant in ``source`` that names ``seam``'s binary, prose excluded.

    A bare string expression is a docstring or a comment by other means; every
    other string constant is data the module hands to something.
    """
    tree = ast.parse(source)
    prose = {id(node.value) for node in ast.walk(tree) if isinstance(node, ast.Expr)}
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and seam.names.search(node.value)
        and id(node) not in prose
    }


def _package_modules() -> dict[str, str]:
    return {
        path.relative_to(_REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(_SWEPT_ROOT.rglob("*.py"))
        if not _UNSWEPT_PARTS & set(path.relative_to(_SWEPT_ROOT).parts)
    }


@SEAMS
def test_only_the_seam_names_the_binary(seam: Seam) -> None:
    """The monopoly as a set difference, over every module in the package."""
    naming = {path for path, source in _package_modules().items() if _named_in_argv(source, seam)}

    assert naming == {seam.path}, sorted(naming)


@SEAMS
def test_the_sweep_can_see(seam: Seam) -> None:
    """A sweep over nothing passes vacuously; this is what says it did not.

    A floor rather than a count, so a module arriving or leaving does not edit
    this line — only a package that has quietly stopped being walked.
    """
    modules = _package_modules()

    assert len(modules) >= 30, sorted(modules)
    assert seam.path in modules
    assert _named_in_argv(modules[seam.path], seam), "the seam itself no longer names the binary — no subject"


@pytest.mark.parametrize(
    ("seam", "source", "expected"),
    [
        (PANDOC, 'BINARY = "pandoc"\n', True),
        (PANDOC, 'subprocess.run(["pandoc", "-f", "latex"], check=True)\n', True),
        (PANDOC, 'ARGV = ["Pandoc", "--citeproc"]\n', True),
        (PANDOC, 'COMMAND = f"pandoc {flags}"\n', True),
        (PANDOC, "from kb_tools import pandoc\n\npandoc.to_ast(text, bibliographies=())\n", False),
        (PANDOC, '"""Reads the volume through the pandoc seam."""\n', False),
        (PANDOC, "import subprocess\n\nsubprocess.run([BINARY], check=True)\n", False),
        (DOT, 'BINARY = "dot"\n', True),
        (DOT, 'subprocess.run(["dot", "-Tsvg"], input=text, check=True)\n', True),
        (DOT, 'COMMAND = f"dot -Tsvg {flags}"\n', True),
        (DOT, "from kb_tools import dot\n\ndot.to_svg(text)\n", False),
        (DOT, '"""Draws the sheet through the dot seam."""\n', False),
        (DOT, 'STYLE = "style=dotted"\n', False),
        (DOT, 'ARGV = ["Dot", "-Tsvg"]\n', False),
    ],
    ids=[
        "pandoc-constant",
        "pandoc-argv",
        "pandoc-case",
        "pandoc-fstring",
        "pandoc-seam-caller",
        "pandoc-docstring-only",
        "pandoc-clean",
        "dot-constant",
        "dot-argv",
        "dot-fstring",
        "dot-seam-caller",
        "dot-docstring-only",
        "dot-dotted-style",
        "dot-other-case",
    ],
)
def test_the_sweep_reads_argv_and_not_prose(seam: Seam, source: str, expected: bool) -> None:
    """The sweep's teeth, both directions: every argv shape fires, a mention and a use do not."""
    assert bool(_named_in_argv(source, seam)) is expected
