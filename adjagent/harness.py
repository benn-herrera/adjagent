"""The harness dataclass. The instances, one module each, are in `adjagent.harnesses`.

A harness is everything rendered output differs on between harnesses: the
directory and file names prose spells, the tool spellings, the model shape it
accepts and the words that render no model at all, whether a map flag's bare
value names the whole map, the frontmatter lines it reads, the rule a dispatched
agent follows when running recipes in its shell, the files it
renders beside the definitions, the definitions it renders nothing for, the
prefix a definition's name takes where other definition text names it, the
path below its harness directory the set is written into, the
settings file it registers an MCP server in, the guardrail hook it
registers, where it has one, and the entries earlier installs wrote that an
install removes. It holds no tier map, no family and
no knowledge of any one definition. Its emitter only lays out lines; the
renderer maps tools to spellings and computes the governed keys.

The plugin name and the plugin manifest every plugin-form harness renders are here, so each value
derived from the name has one source.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from adjagent import __version__
from adjagent.errors import InputError
from adjagent.vocabulary import IDENTIFIER, HarnessText, OptionalHarnessText, Tool

PLUGIN_NAME = "adjagent"
"""The one spelling of the plugin's name: its manifest name, and the source of every reference prefix,
plugin directory and plugin MCP prefix a harness derives from it."""


@dataclass(frozen=True)
class AgentFields:
    """One agent's frontmatter values in the one form every emitter reads: neutral except tool spellings."""

    name: str
    description: str
    model: str  # rendered model text; "" elides the model line
    color: str | None
    tools: tuple[str, ...] | None  # harness spellings, authored order, lists flattened; None = ALL
    governed: tuple[str, ...]  # the image of Harness.tools in table order, de-duplicated


@dataclass(frozen=True)
class HarnessFile:
    """A file a harness renders into the output root beside the definitions: the path below the root,
    the builder for its whole text, and the marker a file at that path must hold to be one this
    repository wrote (a format admitting no comment carries its ownership as a value inside it)."""

    path: str  # harness-relative, e.g. ".claude-plugin/plugin.json"
    text: Callable[[], str]  # the whole file, final newline included
    marker: str  # the value inside the file that makes it ours


def _plugin_json() -> str:
    """The plugin manifest's whole text: name, version and description, with `json.dumps`'s default
    separators, whose space after each colon the marker is a substring of."""
    manifest = {"name": PLUGIN_NAME, "version": __version__, "description": "Adjagent skills, agents, and MCP tools"}
    return json.dumps(manifest, indent=2) + "\n"


PLUGIN_MANIFEST = HarnessFile(path=".claude-plugin/plugin.json", text=_plugin_json, marker=f'"name": "{PLUGIN_NAME}"')
"""The plugin manifest every harness that writes its set as a plugin renders beside it."""


class McpEntryBuilder(Protocol):
    """Builds the `kbase` server entry and the container path it nests under, from the server command,
    which the entry names as given."""

    def __call__(self, *, command: str) -> tuple[dict[str, str | list[str]], tuple[str, ...]]: ...


class McpSite(Enum):
    """Where a harness's MCP settings file lives: at the project root, where the file is the project's own
    and the install edits it in place; or at ROOT, where it is the plugin's own, beside `skills/`."""

    PROJECT = "project"
    HARNESS = "harness"


@dataclass(frozen=True)
class McpSettings:
    """The settings file a harness registers the `kbase` MCP server in. `canonical` is the path relative
    to `site`, created when absent; `alternatives` are the discovered names probed in precedence order,
    a found one overriding the canonical; `site` is the directory those paths are joined to; `entry`
    builds the server entry and the container path it nests under."""

    canonical: str
    alternatives: tuple[str, ...]
    site: McpSite
    entry: McpEntryBuilder


class EntryClaim(Enum):
    """What one item of a settings file holds of an entry an earlier install wrote: none of it, only it,
    or it beside a command of the project's own."""

    NONE = "none"
    ALONE = "alone"
    SHARED = "shared"


@dataclass(frozen=True)
class GuardrailHook:
    """The guardrail hook a harness ships and registers in a file of its own. `script` is the hook
    script's path under `resources/<harness>/`, which is also its path under ROOT; `registration` is
    the file below ROOT registering it, written only where the script runs on the installing machine."""

    script: str
    registration: HarnessFile


class Replacement(Enum):
    """What an install writes in place of a retired entry, so the entry goes only on an install that
    writes it: the guardrail registration, written where the guardrail probe passes, or the `kbase` MCP
    entry, written on a kb install."""

    GUARDRAIL = "guardrail"
    MCP = "mcp"


@dataclass(frozen=True)
class RetiredEntry:
    """An entry an earlier install registered in a settings file the project owns, which an install
    writing its `replacement` removes. `settings` is the file relative to the project root; `container`
    is the path in it to the array or object holding the entry; `member` is the entry's key in that
    object, "" where the entry is an element of that array; `claim` reads an element, or the member's
    value, as an earlier install wrote it; `trace` is text the entry leaves in the file as written, which
    a file that cannot be parsed or edited in place is searched for."""

    settings: str
    container: tuple[str, ...]
    member: str
    claim: Callable[[object], EntryClaim]
    replacement: Replacement
    trace: str


@dataclass(frozen=True)
class Harness:
    """Everything a harness differs on; a new harness fills every field or fails at import."""

    name: str  # "claude", "opencode"; the --harness value
    agents_file: str  # "CLAUDE.md" / "AGENTS.md"
    project_harness_dir: str  # ".claude" / ".opencode"
    project_temp_dir: str  # ".claude-temp" / ".opencode-temp"
    user_harness_dir: str  # "~/.claude" / "~/.config/opencode"
    mcp_tool_prefix: str  # this prefix + the tool's own name is its offered name
    recipe_rule: str  # the rule a dispatched agent follows running recipes in its shell; "" where there is none
    kbase_project_rule: str  # how a kbase session locates its project where the server serves many; "" otherwise
    tools: Mapping[Tool, tuple[str, ...]]  # total over Tool, in Tool order, each non-empty
    model_pattern: re.Pattern[str]  # every tier's rendered text must fullmatch it
    model_shape: str  # the pattern in words; the only form a refusal shows
    inherit_text: str  # what a tier rendering "inherit" emits
    inherit_synonyms: tuple[str, ...]  # further words emitting inherit_text; model_pattern accepts them
    bare_tier_spec_is_all: bool  # a --model-tier-map value naming no tier is all=<value>
    frontmatter: Callable[[AgentFields], tuple[str, ...]]  # an agent's field lines between the fences
    document_frontmatter: tuple[str, ...]  # a document's field lines between the fences
    mcp: McpSettings  # the settings file this harness registers the kbase server in
    guardrail: GuardrailHook | None  # the guardrail hook it registers; None where its own file registers itself
    rendered_files: tuple[HarnessFile, ...] = ()  # files it renders beside the definitions
    omits: frozenset[str] = frozenset()  # definition names it renders nothing for
    default_tier_spec: str | None = None  # the --model-tier-map value used when none is given; None: the family's tiers
    plugin_parent_dir: str = ""  # a plugin's: the trailing path of the directory its plugins sit in; "" otherwise
    reference_prefix: str = ""  # put before a definition's name wherever definition text names it; "" names it bare
    plugin_dir: str = ""  # below the harness directory, where the set is written (ROOT); "" for the directory
    reload_rule: str = ""  # what to do when an install's agents are not offered; printed after one, "" for none
    retired_entries: tuple[RetiredEntry, ...] = ()  # entries earlier installs wrote that an install removes

    def __post_init__(self) -> None:
        """Refuse a non-IDENTIFIER name or omitted definition name, an empty HarnessText field or
        model_shape, an OptionalHarnessText field that is not a string, a tools table not total in
        Tool order, an MCP settings contract lacking a canonical path, a non-empty alternative name,
        or a builder, a guardrail hook lacking a script path or a registration path, builder and
        marker, or a retired entry lacking a settings path, a container path, a recogniser or a trace.

        An empty string is refused of the fields a body naming them always renders, since every
        harness supplies each HarnessText and a model shape. An OptionalHarnessText is a rule a
        harness imposes or does not, so there "" is a value rather than a missing one: it drops the
        paragraph its placeholder stands in."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"harness '{self.name}': name is not a strict-kebab identifier")
        if any(re.fullmatch(IDENTIFIER, name) is None for name in self.omits):
            raise InputError(f"harness '{self.name}': omits holds a name that is not a strict-kebab identifier")
        if not all(self.text(part) for part in HarnessText) or not self.model_shape:
            raise InputError(f"harness '{self.name}': an empty string field")
        for part in OptionalHarnessText:
            if not isinstance(self.text(part), str):
                raise InputError(f"harness '{self.name}': {part.value} must be a string")
        if tuple(self.tools) != tuple(Tool) or not all(self.tools.values()):
            raise InputError(f"harness '{self.name}': tools table must name every Tool, in Tool order, non-empty")
        if not self.mcp.canonical or not all(self.mcp.alternatives) or not callable(self.mcp.entry):
            raise InputError(
                f"harness '{self.name}': MCP settings needs a canonical path, non-empty alternative names, "
                "and a builder"
            )
        guardrail = self.guardrail
        if guardrail is not None and not (
            guardrail.script
            and guardrail.registration.path
            and callable(guardrail.registration.text)
            and guardrail.registration.marker
        ):
            raise InputError(
                f"harness '{self.name}': guardrail hook needs a script path, and a registration path, "
                "builder and marker"
            )
        for retired in self.retired_entries:
            if not (
                retired.settings
                and retired.container
                and all(retired.container)
                and callable(retired.claim)
                and retired.trace
            ):
                raise InputError(
                    f"harness '{self.name}': a retired entry needs a settings path, a container path, a "
                    "recogniser, and a trace"
                )

    @property
    def is_standalone_plugin(self) -> bool:
        """Whether this harness's harness directory is itself a plugin: its files sit at its own root, so
        its user harness directory is `.`."""
        return self.user_harness_dir == "."

    @property
    def user_dir(self) -> Path:
        """The user harness directory, `~` read from HOME."""
        return Path(self.user_harness_dir).expanduser()

    def text(self, part: HarnessText | OptionalHarnessText) -> str:
        """The value of the string field `part` names; "" where an optional one is supplied nowhere."""
        return getattr(self, part.value)


def quoted(value: str) -> str:
    """A frontmatter value in double quotes, as every emitter writes description and color."""
    return f'"{value}"'
