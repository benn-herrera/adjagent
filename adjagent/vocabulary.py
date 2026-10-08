"""The vocabulary every other module is written in: identifiers, tiers, tools,
overlay anchors, definition kinds, and the harness text a definition's prose may
name. Imports nothing from the package, so every module may import it."""

from enum import Enum
from typing import Literal

IDENTIFIER = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
"""Output, family and harness names, and each folder part: strict kebab, as CONVENTIONS.md states the class."""

Tier = Literal["highest", "high", "medium", "low", "lowest"]
TIERS: tuple[Tier, ...] = ("highest", "high", "medium", "low", "lowest")
"""Canonical order; every serialization of a tier map uses it."""


class Tool(Enum):
    """The harness-neutral tool vocabulary; member order is the order every harness table follows."""

    READ = "read"
    GREP = "grep"
    GLOB = "glob"
    EDIT = "edit"
    WRITE = "write"
    BASH = "bash"
    WEBFETCH = "webfetch"
    WEBSEARCH = "websearch"
    AGENT = "agent"


class Unrestricted(Enum):
    """The typed sentinel for 'no tool restriction authored'."""

    ALL = "all"


ALL = Unrestricted.ALL
Tools = tuple[Tool, ...] | Unrestricted
"""An authored allowlist in authored order, or ALL. ALL emits no tools field on any harness,
which is not the same as a tuple naming all nine tools."""


class Anchor(Enum):
    """The overlay anchors a definition may expose; a family fills them by this key."""

    GAP_AVERSION = "gap-aversion"
    ASK_VS_STIPULATE = "ask-vs-stipulate"


class Kind(Enum):
    """What a definition renders as. An agent is dispatchable and carries the harness's agent
    frontmatter; a document is read by agents and carries the harness's document frontmatter; a
    command carries no field lines."""

    AGENT = "agent"
    DOCUMENT = "document"
    COMMAND = "command"


class HarnessText(Enum):
    """A harness string a definition's prose may name; each value is the `Harness` field it reads."""

    AGENTS_FILE = "agents_file"
    PROJECT_HARNESS_DIR = "project_harness_dir"
    PROJECT_TEMP_DIR = "project_temp_dir"
    USER_HARNESS_DIR = "user_harness_dir"
