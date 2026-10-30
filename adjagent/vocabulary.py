"""The vocabulary every other module is written in: identifiers, tiers, tools,
overlay anchors, definition kinds, the harness text a definition's prose may
name, and the placeholder spelling for both. Imports nothing from the package,
so every module may import it."""

from enum import Enum
from typing import Literal

IDENTIFIER = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
"""Output, family and harness names, and each folder part: strict kebab, letter-led segments joined by single hyphens."""

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
    command carries no field lines; a skill renders a directory — `skills/<name>/SKILL.md`, carrying
    the two fields every harness reads, and the supporting files it lists, each opened by a comment
    banner; an agents file renders to a block that an installer wraps the operator's text around; it
    has no output path and no frontmatter."""

    AGENT = "agent"
    DOCUMENT = "document"
    COMMAND = "command"
    SKILL = "skill"
    AGENTS_FILE = "agents file"


class HarnessText(Enum):
    """A harness string a definition's prose may name; each value is the `Harness` field it reads, and
    every harness supplies all of them, so a body naming one always renders its text."""

    AGENTS_FILE = "agents_file"
    PROJECT_HARNESS_DIR = "project_harness_dir"
    PROJECT_TEMP_DIR = "project_temp_dir"
    USER_HARNESS_DIR = "user_harness_dir"
    MCP_TOOL_PREFIX = "mcp_tool_prefix"


class OptionalHarnessText(Enum):
    """A harness string a definition's prose may name that a harness may supply nothing for; each value
    is the `Harness` field it reads. Spelled and filled as a `HarnessText` is, and a harness supplying
    nothing fills it to the empty string, which drops the paragraph the placeholder stands in."""

    RECIPE_RULE = "recipe_rule"
    KBASE_PROJECT_RULE = "kbase_project_rule"


class AgentsFileText(Enum):
    """A value only the agents file's prose names, bound when it renders."""

    SCOPE_NAME = "scope_name"
    CODER_DISPATCH = "coder_dispatch"


def key(name: HarnessText | OptionalHarnessText | Anchor | AgentsFileText) -> str:
    """A render-time value's flat key: its enum value with each "_" read as "-"."""
    return "-".join(name.value.split("_"))


def hole(name: HarnessText | OptionalHarnessText | Anchor | AgentsFileText) -> str:
    """The placeholder a definition body carries for a render-time value: `@!hrn-<key>!@` for a harness
    text, optional or not, `@!fam-<key>!@` for an overlay anchor, `@!agf-<key>!@` for an agents-file
    value. No rendered prose spells `@!`."""
    namespace = {HarnessText: "hrn", OptionalHarnessText: "hrn", Anchor: "fam", AgentsFileText: "agf"}[type(name)]
    return f"@!{namespace}-{key(name)}!@"
