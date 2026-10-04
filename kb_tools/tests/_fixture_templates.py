"""Point the prompt composer at templates a test writes, so generation is tested against fixtures.

A composed prompt compared byte for byte with the working templates is a
checksum of their wording: every edit breaks it and no behaviour is guarded. A
generation test writes its own templates and fragments, composes real asks
through them, and compares the result with a golden held beside the fixture.
"""

from collections.abc import Mapping
from functools import partial
from pathlib import Path

import pytest

from kb_tools.kb_driver import prompt_templates


def compose_from_fixture_templates(
    monkeypatch: pytest.MonkeyPatch, directory: Path, templates: Mapping[str, str]
) -> None:
    """Write ``templates`` (path relative to the templates directory → body) under ``directory`` and compose from it."""
    for name, text in templates.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(prompt_templates, "render", partial(prompt_templates.render, directory=directory))
