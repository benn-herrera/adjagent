"""`Profile`: the facts about one language or platform that sections read."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    """The facts about one language or platform that sections read. Every field is prose a section
    interpolates; a field's docstring names the section and sentence it lands in. One instance per
    coder and per platform expert, defined in that definition's own module."""

    language: str
    """BuildSystem, the runner-recipes sentence: `A new <language> project's runner carries …`."""

    build_operations: str = field(repr=False)
    """BuildSystem, the build-system sentence: `… for all <build_operations> operations`."""

    build_tools: str = field(repr=False)
    """BuildSystem, the build-system sentence: `never invoke <build_tools> directly …`."""

    build_outputs: str = field(repr=False)
    """BuildSystem, the build-system sentence: `Build outputs belong in <build_outputs>, …`."""

    runner_recipes: str = field(repr=False)
    """BuildSystem, the runner-recipes sentence: `… runner carries <runner_recipes> alongside …`."""

    violation_routing: str = field(repr=False)
    """Testing, the boundary-check paragraph: `Route violations through <violation_routing>.`"""

    unit_tests: str = field(repr=False)
    """Testing, the unit-test paragraph: the framework text after `*Unit tests*: `."""

    unit_tests_closing: str = field(repr=False)
    """Testing, the unit-test paragraph: its last line, after the mocking rule."""

    integration_tests: str = field(repr=False)
    """Testing, the integration-test paragraph: the tooling text after the logging-signal sentence."""

    format_libraries: str = field(repr=False)
    """DataFormats: the libraries text continuing the data-formats paragraph."""

    registry: str = field(repr=False)
    """Dependencies, the vetting list's adoption item: `**Adoption count** — <registry> — …`."""

    logging: str = field(repr=False)
    """Logging: the language's logging rule, opening the logging paragraph."""

    logging_baseline: str = field(repr=False)
    """Logging, the closing sentence: `… framework unless <logging_baseline> demonstrably cannot …`."""
