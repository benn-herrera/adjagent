"""The harness dataclass. The instances, one module each, are in `devpro.harnesses`.

A harness is everything rendered output differs on between harnesses: the
directory and file names prose spells, the tool spellings, the model shape it
accepts and the words that render no model at all, whether a map flag's bare
value names the whole map, where a definition's metadata goes — the frontmatter
lines it reads, or the registry it reads them all from — the rule a dispatched
agent follows when running recipes in its shell, the files it renders beside the
definitions, the resource that registers the plugin where one does, the prefix a
definition's name takes where other definition text names it, the path below its
harness directory the set is written into, the guardrail hook it registers, where
it has one. It holds no tier map, no family and no knowledge of any one
definition. Its emitter only lays out lines; the renderer maps tools to spellings
and computes the governed keys.

The values that vary by plugin are templates over `{plugin}`, filled once by `Harness.bound`; a harness
takes the plugin's name as a string and knows nothing of its members. The manifest every
plugin-form harness renders is here, its name and marker the bound plugin's.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from devpro import __version__
from devpro.errors import InputError
from devpro.vocabulary import IDENTIFIER, HarnessText, Kind, OptionalHarnessText, Tool

KBASE_OWNER = "kbase"
"""The definition the kbase toolchain ships with: the kb-tools package, the runner include line and the
`kbase` MCP entry are delivered where it ships, and nowhere else."""
KBASE_NAME = "kbase"
"""The command every harness's `kbase` MCP entry names: the bare name, resolved from PATH, where the
user's own kbase install puts it."""
KBASE_SERVER = "kbase"
"""The name every harness registers the `kbase` MCP server under, which its `mcp_tool_prefix` spells."""


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
class ShippedDefinition:
    """One definition a render ships, in the general form a harness-rendered file reads: its name, the
    reference the render spells it as, and its kind, its output path below the output root, its
    description filled (None for a kind that has none), and its frontmatter values for an agent (None
    otherwise)."""

    name: str
    reference: str  # the harness's reference prefix and the name
    kind: Kind
    path: str
    description: str | None
    agent: AgentFields | None


@dataclass(frozen=True)
class HarnessFile:
    """A file a harness renders into the output root beside the definitions: the path below the root,
    the builder for its whole text from the bound plugin's name and the definitions the render ships, the
    marker a file at that path must hold to be one this repository wrote (a format admitting no comment
    carries its ownership as a value inside it), and the definition it is rendered with, if any."""

    path: str  # harness-relative, e.g. ".claude-plugin/plugin.json"
    text: Callable[[str, Sequence[ShippedDefinition]], str]  # the whole file, final newline included
    marker: str  # the value inside the file that makes it ours; may hold `{plugin}`
    owner: str | None = None  # rendered only where this definition ships; None: wherever the harness renders


def _plugin_json(plugin: str, shipped: Sequence[ShippedDefinition]) -> str:
    """The manifest's whole text: the plugin's name, the version and a description, with
    `json.dumps`'s default separators, whose space after each colon the marker is a substring of."""
    manifest = {
        "name": plugin,
        "version": __version__,
        "description": "Skills, agents, and MCP tools from the devpro project",
    }
    return json.dumps(manifest, indent=2) + "\n"


PLUGIN_MANIFEST = HarnessFile(path=".claude-plugin/plugin.json", text=_plugin_json, marker='"name": "{plugin}"')
"""The manifest every harness that writes its set as a plugin renders beside it."""


@dataclass(frozen=True)
class FrontmatterForm:
    """How a harness that carries each definition's metadata in the definition's own file writes it: the
    field lines between the fences of an agent's, and of a document's."""

    agent: Callable[[AgentFields], tuple[str, ...]]
    document: tuple[str, ...]


# "scratch directory" is the development skill's term for that slot: filled text is not rescanned, so
# this string cannot interpolate the term and must change with it.
COLD_READ_SCRIPT_RULE = (
    "- Write a brief holding the question and the documents, pasted in full, into the scratch directory, "
    "and run each reader with this skill's `scripts/cold-read.sh <agent> <brief>`. A subagent of this "
    "session cannot be a cold reader: it shares the session's harness, which loads the project documents "
    "into every session started in the repository, and a reader holding the old text cannot set it aside "
    "when told to. The script runs a new harness session instead, with no tools, from a fresh directory it "
    "creates under the one `DEVPRO_COLD_READ_DIR` names, holding nothing the harness loads as "
    "instructions, and removes it when the run ends: the one working location outside the scratch "
    "directory, and an explicit exception to the agents file's scratch-space rule. Where `DEVPRO_COLD_READ_DIR` is unset, or the directory it names is unsuitable, the "
    "script stops and says why. `DEVPRO_COLD_READ_MODEL`, where set, names the reader's model. Run the "
    "script from this harness's own copy of the skill."
)
"""The development skill's cold-read bullet under each harness whose install runs `cold-read.sh`."""

FOREGROUND_RECIPE_RULE = """A dispatched agent runs recipes in the foreground with the shell tool's timeout set to cover them.
If a recipe times out, the agent hands back naming it instead of rerunning it in the background."""
"""The recipe rule under each harness whose shell tool takes a per-command timeout and can run a command
in the background."""


def scratch_rule(*, temp_dir: str, harness_dir: str) -> str:
    """The agents file's scratch rule, after its `/tmp` sentence, for a harness whose project scratch
    directory sits beside its project harness directory."""
    return (
        f"All scratch —\nthrowaway builds, probe harnesses, captured output — goes in `{temp_dir}/` under the\n"
        f"active project root, beside `{harness_dir}/` and never inside it (writes there trip\n"
        "the permission system's own-settings protections). If it doesn't exist, stop and say so; don't\n"
        "improvise a location."
    )


class McpEntryBuilder(Protocol):
    """Builds the `kbase` server entry from the server command, which the entry names as given."""

    def __call__(self, *, command: str) -> dict[str, str | list[str]]: ...


def mcp_json(entry: McpEntryBuilder) -> HarnessFile:
    """The plugin's own `.mcp.json` at ROOT, rendered whole where `KBASE_OWNER` ships: the `kbase` server
    alone under `mcpServers`, its entry from `entry`. JSON admits no comment, so the marker is the
    command the entry names, with `json.dumps`'s space after the colon."""

    def text(plugin: str, shipped: Sequence[ShippedDefinition]) -> str:
        return json.dumps({"mcpServers": {KBASE_SERVER: entry(command=KBASE_NAME)}}, indent=2) + "\n"

    return HarnessFile(path=".mcp.json", text=text, marker=f'"command": "{KBASE_NAME}"', owner=KBASE_OWNER)


@dataclass(frozen=True)
class GuardrailHook:
    """The guardrail hook a harness ships and registers in a file of its own. `script` is the hook
    script's path under `resources/<harness>/`, which is also its path under ROOT; `registration` is
    the file below ROOT registering it, written only where the script runs on the installing machine."""

    script: str
    registration: HarnessFile


@dataclass(frozen=True)
class Harness:
    """Everything a harness differs on; a new harness fills every field or fails at import."""

    name: str  # "claude", "opencode"; the --harness value
    agents_file: str  # "CLAUDE.md" / "AGENTS.md"
    project_harness_dir: str  # ".claude" / ".opencode"; may hold `{plugin}`
    project_temp_dir: str  # ".claude-temp" / ".opencode-temp"
    display_name: str  # "claude code" / "opencode"; the harness's name in prose, lowercase
    user_harness_dir: str  # "~/.claude" / "~/.config/opencode"
    mcp_tool_prefix: str  # this prefix + the tool's own name is its offered name; may hold `{plugin}`
    scratch_rule: str  # the agents file's rule for where scratch goes, after its `/tmp` sentence
    memory_file: str  # the agents file's name for the operator's own instructions file
    recipe_rule: str  # the rule a dispatched agent follows running recipes in its shell; "" where there is none
    kbase_project_rule: str  # how a kbase session locates its project where the server serves many; "" otherwise
    tools: Mapping[Tool, tuple[str, ...]]  # total over Tool, in Tool order, each non-empty
    model_pattern: re.Pattern[str]  # every tier's rendered text must fullmatch it
    model_shape: str  # the pattern in words; the only form a refusal shows
    inherit_text: str  # what a tier rendering "inherit" emits
    inherit_synonyms: tuple[str, ...]  # further words emitting inherit_text; model_pattern accepts them
    bare_tier_spec_is_all: bool  # a --model-tier-map value naming no tier is all=<value>
    # where each definition's metadata goes: frontmatter in its own file, or one registry file beside them all
    definition_form: FrontmatterForm | HarnessFile
    guardrail: GuardrailHook | None  # the guardrail hook it registers; None where its own file registers itself
    rendered_files: tuple[HarnessFile, ...] = ()  # files it renders beside the definitions
    default_tier_spec: str | None = None  # the --model-tier-map value used when none is given; None: the family's tiers
    plugin_parent_dir: str = (
        ""  # a harness-directory plugin's: the trailing path of the directory its plugins sit in; "" otherwise
    )
    reference_prefix: str = ""  # put before a definition's name wherever definition text names it; "" names it bare
    plugin_dir: str = ""  # below the harness directory, where the plugin is written (ROOT); "" for the directory
    entry_resource: str = ""  # the resource that registers the plugin, copied at user level too; "" for none
    user_plugin_shadows: bool = False  # a user-level install's plugin loads in place of a project's of its name
    reload_rule: str = ""  # what to do when an install's agents are not offered; printed after one, "" for none
    side_by_side_rule: str = ""  # what a session does where another harness's install also reaches it; "" for none
    cold_read_rule: str = ""  # the development skill's bullet on how a cold reader is run; "" for none

    def __post_init__(self) -> None:
        """Refuse a non-IDENTIFIER name, an empty HarnessText field or
        model_shape, a display_name that is not lowercase, an OptionalHarnessText field that is not a string, a tools table not total in
        Tool order, or a guardrail hook lacking a script path or a registration path, builder and
        marker.

        An empty string is refused of the fields a body naming them always renders, since every
        harness supplies each HarnessText and a model shape. An OptionalHarnessText is a rule a
        harness imposes or does not, so there "" is a value rather than a missing one: it drops the
        paragraph its placeholder stands in."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"harness '{self.name}': name is not a strict-kebab identifier")
        if not all(self.text(part) for part in HarnessText) or not self.model_shape:
            raise InputError(f"harness '{self.name}': an empty string field")
        if self.display_name != self.display_name.lower():
            raise InputError(f"harness '{self.name}': display_name is not lowercase")
        for part in OptionalHarnessText:
            if not isinstance(self.text(part), str):
                raise InputError(f"harness '{self.name}': {part.value} must be a string")
        if tuple(self.tools) != tuple(Tool) or not all(self.tools.values()):
            raise InputError(f"harness '{self.name}': tools table must name every Tool, in Tool order, non-empty")
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

    def bound(self, plugin_name: str) -> Harness:
        """This harness for the plugin `plugin_name`: every `{plugin}` template — the plugin directory, the
        project harness directory, the reference and MCP tool prefixes, and the marker of each rendered
        file, of the registry and of the guardrail registration — filled with it."""

        def filled(template: str) -> str:
            return template.replace("{plugin}", plugin_name)

        def marked(file: HarnessFile) -> HarnessFile:
            return dataclasses.replace(file, marker=filled(file.marker))

        form = self.definition_form
        guardrail = self.guardrail
        return dataclasses.replace(
            self,
            plugin_dir=filled(self.plugin_dir),
            project_harness_dir=filled(self.project_harness_dir),
            reference_prefix=filled(self.reference_prefix),
            mcp_tool_prefix=filled(self.mcp_tool_prefix),
            rendered_files=tuple(marked(file) for file in self.rendered_files),
            definition_form=marked(form) if isinstance(form, HarnessFile) else form,
            guardrail=(
                None
                if guardrail is None
                else dataclasses.replace(guardrail, registration=marked(guardrail.registration))
            ),
        )

    @property
    def harness_files(self) -> tuple[HarnessFile, ...]:
        """Every file this harness renders beside the definitions: its `rendered_files`, then its registry
        where its definition form is one."""
        registry = (self.definition_form,) if isinstance(self.definition_form, HarnessFile) else ()
        return (*self.rendered_files, *registry)

    @property
    def is_harness_dir_plugin(self) -> bool:
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


def agent_frontmatter(fields: AgentFields) -> tuple[str, ...]:
    """Agent frontmatter with a comma-joined `tools` list: name; description "…"; model if non-empty;
    color "…" if set; `tools: A, B` unless tools is None."""
    lines = [f"name: {fields.name}", f"description: {quoted(fields.description)}"]
    if fields.model:
        lines.append(f"model: {fields.model}")
    if fields.color is not None:
        lines.append(f"color: {quoted(fields.color)}")
    if fields.tools is not None:
        lines.append(f"tools: {', '.join(fields.tools)}")
    return tuple(lines)
