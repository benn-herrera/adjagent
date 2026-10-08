"""The unit of composition: `Section`, and `Prose` for a definition's own text."""

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

from adjagent.errors import InputError

# Annotation only: context imports definition, which imports this module.
if TYPE_CHECKING:
    from adjagent.context import Render


@dataclass(frozen=True)
class Section:
    """One section of a rendered definition. Subclasses declare fields for what varies between
    definitions and implement render; the text they emit is their private module constants."""

    def render(self, ctx: "Render") -> str:
        """The section's text: no leading or trailing newline; paragraphs separated by a blank line."""
        raise NotImplementedError

    def header(self) -> str:
        """`[<SectionClass>]`, or `[<SectionClass> field=value ...]` naming each shown field whose value
        is not its default; a field declared with repr=False is never shown."""
        shown = [
            f" {spec.name}={getattr(self, spec.name)!r}"
            for spec in dataclasses.fields(self)
            if spec.repr and getattr(self, spec.name) != spec.default
        ]
        return f"[{type(self).__name__}{''.join(shown)}]"


@dataclass(frozen=True)
class Prose(Section):
    """A definition's own text, verbatim: non-empty, with no leading or trailing newline."""

    text: str = dataclasses.field(repr=False)

    def __post_init__(self) -> None:
        if not self.text or self.text.startswith("\n") or self.text.endswith("\n"):
            raise InputError(f"prose section is empty or carries an edge newline: {self.text[:40]!r}")

    def render(self, ctx: "Render") -> str:
        return self.text
