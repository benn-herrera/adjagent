"""The unit of composition: `Section`; `Prose` for a definition's own text, and
`FamilyText` for the text a family fills at an anchor."""

import dataclasses
from dataclasses import dataclass
from enum import Enum

from adjagent.context import Render
from adjagent.errors import InputError
from adjagent.vocabulary import Anchor, HarnessText

Part = tuple[str, str]
"""(label, paragraph text): label names the field(s) that supplied the paragraph, "" for shared text."""

_SHOWN_WIDTH = 60


def _shown(value: object) -> str:
    text = str(value) if isinstance(value, Enum) else repr(value)
    return text if len(text) <= _SHOWN_WIDTH else f"{text[:_SHOWN_WIDTH - 1]}…"


@dataclass(frozen=True)
class Section:
    """One section of a rendered definition. Subclasses declare fields for what varies between
    definitions and implement parts; the text they emit is their private module constants."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        """The section's paragraphs in order, each labelled; a paragraph has no leading or trailing
        newline. No parts is an empty section, which renders nothing."""
        raise NotImplementedError

    def render(self, ctx: Render) -> str:
        """The section's paragraphs joined by a blank line."""
        return "\n\n".join(text for _, text in self.parts(ctx))

    def header(self) -> str:
        """`[<SectionClass> field=value ...]` naming every field, each value cut to 60 characters with
        a trailing `…`; a field declared with repr=False is never shown."""
        shown = "".join(
            f" {spec.name}={_shown(getattr(self, spec.name))}" for spec in dataclasses.fields(self) if spec.repr
        )
        return f"[{type(self).__name__}{shown}]"


@dataclass(frozen=True, init=False)
class Prose(Section):
    """A definition's own text: its parts, each a string or a harness text, joined with nothing
    between them. The joined text is non-empty with no leading or trailing newline."""

    content: tuple[str | HarnessText, ...] = dataclasses.field(repr=False)

    def __init__(self, *parts: str | HarnessText) -> None:
        object.__setattr__(self, "content", parts)
        if not all(isinstance(part, (str, HarnessText)) for part in parts):
            raise InputError(f"prose section parts must be str or HarnessText: {parts!r:.60}")
        # A harness text is never empty (Harness refuses it), so only all-empty strings join to "".
        if not any(isinstance(part, HarnessText) or part for part in parts):
            raise InputError("prose section is empty")
        first, last = parts[0], parts[-1]
        if (isinstance(first, str) and first.startswith("\n")) or (isinstance(last, str) and last.endswith("\n")):
            raise InputError(f"prose section carries an edge newline: {parts!r:.60}")

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        text = "".join(part if isinstance(part, str) else ctx.harness.text(part) for part in self.content)
        return (("", text),)


@dataclass(frozen=True)
class FamilyText(Section):
    """The family's text at an anchor, for the definition's seat (`Render.overlay`); nothing where
    the family fills none."""

    anchor: Anchor

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        text = ctx.overlay(self.anchor)
        return (("anchor", text),) if text else ()
