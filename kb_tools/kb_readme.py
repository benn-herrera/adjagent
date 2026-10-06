"""The KB's overview document: the packaged template, filled once by the build.

``<kb-root>/README.md`` is written at ``overview-drafted`` and nothing re-renders
it, so it states only what stays true as the KB is edited. Every count and the
document listing are left to the commands the template names; what is filled
here is the project's name, the ``*pending*`` literal, and the passage saying
what this corpus is and where a reader starts — written by a model from the
excerpts :func:`compose_excerpts` takes out of the tree, and arriving as one
more entry in the same mapping.

**A slot the caller has no value for is a refusal, never a blank.** The template
and the value set are written by different hands; the one failure that must not
be silent is a KB shipping a README with ``{project-name}`` in it, so
:func:`fill` names every unfilled slot and writes nothing.

**The excerpts are a fixed list, in a fixed order, under two caps.** The entry
point, then for each document it lists, that document's index and then its own
opening prose where it has one — the child its index links as
``outline.OWN_PROSE_TITLE``. Nothing else in the tree is read, so the size
follows the number of volumes rather than the size of the corpus. Each body
loses its metadata block and its up-link, and each Markdown link is reduced to
its text, so no path reaches the prompt; any other markup stands. A body over
:data:`EXCERPT_DOCUMENT_CHARS`, or one that would take the whole past
:data:`EXCERPTS_TOTAL_CHARS`, is cut at a paragraph boundary and the cut is
returned for the caller to report. This module must not import
``kb_claimgraph``, whose tree reader would otherwise serve: ``kb_claimgraph``
imports ``kb_driver``, which imports this module.

Stdlib only.
"""

import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import kb_index_lib, kb_links, kb_pipeline, kb_schema
from .kb_docgraph.outline import OWN_PROSE_TITLE

#: The packaged template this module fills, under ``kb_tools/installed/``. Named
#: through ``kb_pipeline`` so the document's name has one spelling and the
#: stage's own postcondition looks for the file this writes.
TEMPLATE_DOC = kb_pipeline.OVERVIEW_DOC

#: The per-project name slot, spelled once for every packaged template: the
#: readiness docs already take this field, and a second spelling of it in
#: ``installed/`` would be a second name for one fact.
PROJECT_NAME_SLOT = kb_pipeline.PROJECT_NAME_FIELD.strip("{}")

#: The one slot the toolchain cannot fill — what this corpus argues, what it leaves
#: out, and which document a reader opens first. It is the whole of what the
#: stage asks a seat for, and the whole of what the seat returns.
PROSE_SLOT = "overview-passage"

# A slot is a lowercase hyphenated name in braces — the shape
# `kb_pipeline.PROJECT_NAME_FIELD` already writes. Prose in the template is
# Markdown and carries no braces of its own; one that did would be reported as
# an unfilled slot, which is loud rather than silent.
_SLOT_RE = re.compile(r"\{([a-z][a-z0-9-]*)\}")


class TemplateError(ValueError):
    """The template and the value set disagree about which slots exist."""


# --- the substitution --------------------------------------------------------


def slots(template: str) -> tuple[str, ...]:
    """Every slot the template names, in first-appearance order, without repeats."""
    return tuple(dict.fromkeys(_SLOT_RE.findall(template)))


def fill(template: str, values: Mapping[str, str]) -> str:
    """Substitute ``values`` into ``template``, refusing a slot nothing computes.

    One pass, so a value that happens to contain brace text is content rather
    than a slot of its own. A value the template never names is not an error:
    the value set is the toolchain's and the template picks from it.
    """
    missing = [name for name in slots(template) if name not in values]
    if missing:
        raise TemplateError(
            f"{TEMPLATE_DOC}: the template names slot(s) nothing computes: {', '.join(missing)} — "
            f"computed: {', '.join(sorted(values))}"
        )
    return _SLOT_RE.sub(lambda match: values[match.group(1)], template)


def template_text() -> str:
    """The packaged template's text.

    Its absence is an incomplete install of this toolchain, reported the way
    ``kb_pipeline.stamp_readiness_docs`` reports the same fault for the
    readiness templates.
    """
    source = kb_pipeline.installed_template(TEMPLATE_DOC)
    if not source.is_file():
        raise kb_pipeline.PipelineError(
            f"the packaged template {source} is missing; this kb_tools install is "
            f"incomplete — re-install the agent definitions."
        )
    return source.read_text(encoding="utf-8")


def assemble(*, project_name: str, prose: Mapping[str, str]) -> str:
    """The overview document: the packaged template, its fixed values, the seat's prose.

    ``prose`` is the seat's answer, keyed by the slot the template holds it in.
    It is merged over :func:`facts` so the two sets are one mapping, which is
    what lets a slot the template names be served by either without this
    function knowing which.
    """
    return fill(template_text(), {**facts(project_name=project_name), **prose})


# --- the values --------------------------------------------------------------


def facts(*, project_name: str) -> dict[str, str]:
    """Every value the template can name besides the seat's passage."""
    return {
        PROJECT_NAME_SLOT: project_name,
        "pending-literal": kb_schema.PENDING_LITERAL,
    }


# --- the excerpts the passage is written from ---------------------------------

#: The most of one document's body the excerpts carry, in characters.
EXCERPT_DOCUMENT_CHARS = 12_000

#: The most the excerpts carry altogether, in characters, separators included.
EXCERPTS_TOTAL_CHARS = 48_000

# A document's boundary line, carrying the document's title and never its path.
_SEPARATOR = "==> {title} <=="

# What joins a title to the title of the document it was reached from.
_TITLE_JOIN = " › "

_PARAGRAPH_BREAK = "\n\n"

_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ExcerptCut:
    """One document the caps shortened: by its title, what was kept and what was cut, in characters."""

    title: str
    kept_chars: int
    cut_chars: int


@dataclass(frozen=True)
class Excerpts:
    """The composed excerpts, and every cut the caps made to them."""

    text: str
    cuts: tuple[ExcerptCut, ...]


@dataclass(frozen=True)
class _Document:
    title: str
    body: str


def _link_text(match: "re.Match[str]") -> str:
    """The text of one ``kb_links.LINK_RE`` match, which captures only the destination."""
    return match.string[match.start() + 1 : match.string.rindex("](", match.start(), match.start(1))]


def _links(text: str) -> list[tuple[str, str]]:
    """Every link in ``text``, as (link text, destination), in document order."""
    return [(_link_text(match), match.group(1).strip("<>")) for match in kb_links.LINK_RE.finditer(text)]


def _without_uplink(text: str) -> str:
    """``text`` less the up-link's line (``kb_index_lib.uplink_index``), where that line links up to the parent."""
    at = kb_index_lib.uplink_index(text)
    lines = text.split("\n")
    if at is None or not lines[at].lstrip().startswith(f"[{kb_index_lib.UPLINK_MARKER}"):
        return text
    del lines[at]
    return "\n".join(lines)


def _body(text: str) -> str:
    """A document as an excerpt carries it: no metadata block, no up-link, every link reduced to its text."""
    body = kb_index_lib.strip_frontmatter(_without_uplink(text))
    return kb_links.LINK_RE.sub(_link_text, body).strip("\n")


def _heading(text: str) -> str:
    match = _HEADING_RE.search(text)
    return match.group(1) if match else ""


def _excerpted_documents(kb_root: Path) -> list[_Document]:
    """The documents the excerpts carry, in reading order."""
    entry_text = kb_index_lib.strip_frontmatter(
        (kb_root / kb_index_lib.ENTRY_POINT_FILENAME).read_text(encoding="utf-8")
    )
    documents = [_Document(title=_heading(entry_text), body=_body(entry_text))]
    for volume_title, target in dict.fromkeys(_links(entry_text)):
        index_path = posixpath.normpath(target)
        index_text = (kb_root / index_path).read_text(encoding="utf-8")
        documents.append(_Document(title=volume_title, body=_body(index_text)))
        own_prose = [
            dest
            for text, dest in _links(kb_index_lib.strip_frontmatter(_without_uplink(index_text)))
            if text == OWN_PROSE_TITLE
        ]
        if own_prose:
            leaf_path = posixpath.normpath(posixpath.join(posixpath.dirname(index_path), own_prose[0]))
            documents.append(
                _Document(
                    title=f"{volume_title}{_TITLE_JOIN}{OWN_PROSE_TITLE}",
                    body=_body((kb_root / leaf_path).read_text(encoding="utf-8")),
                )
            )
    return documents


def _cut_to(body: str, limit: int) -> str:
    """The longest run of ``body``'s leading paragraphs that fits in ``limit`` characters."""
    if len(body) <= limit:
        return body
    kept: list[str] = []
    size = 0
    for paragraph in body.split(_PARAGRAPH_BREAK):
        grown = size + len(paragraph) + (len(_PARAGRAPH_BREAK) if kept else 0)
        if grown > limit:
            break
        kept.append(paragraph)
        size = grown
    return _PARAGRAPH_BREAK.join(kept)


def _assemble_excerpts(documents: Sequence[_Document]) -> Excerpts:
    pieces: list[str] = []
    cuts: list[ExcerptCut] = []
    used = 0
    for document in documents:
        head = _SEPARATOR.format(title=document.title) + "\n"
        joiner = len(_PARAGRAPH_BREAK) if pieces else 0
        room = min(EXCERPT_DOCUMENT_CHARS, EXCERPTS_TOTAL_CHARS - used - joiner - len(head))
        body = _cut_to(document.body, room) if room > 0 else ""
        if len(body) < len(document.body):
            cuts.append(
                ExcerptCut(title=document.title, kept_chars=len(body), cut_chars=len(document.body) - len(body))
            )
        if not body:
            continue
        pieces.append(head + body)
        used += joiner + len(head) + len(body)
    return Excerpts(text=_PARAGRAPH_BREAK.join(pieces), cuts=tuple(cuts))


def compose_excerpts(kb_root: Path) -> Excerpts:
    """The excerpts of the tree under ``kb_root`` that the overview passage is written from.

    Byte-deterministic: the same tree gives the same text. Each document opens
    with a boundary line carrying its title; a document the caps emptied is left
    out, and listed among the cuts with the rest.
    """
    return _assemble_excerpts(_excerpted_documents(kb_root))
