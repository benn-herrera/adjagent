"""The opencode harness: the plugin written as one directory below the harness directory, its
bodies without frontmatter and its metadata in one registry, `registry.json`, the wire format this module
owns and the copied entry reads."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from adjagent import __version__
from adjagent.harness import (
    COLD_READ_SCRIPT_RULE,
    KBASE_NAME,
    KBASE_OWNER,
    KBASE_SERVER,
    AgentFields,
    Harness,
    HarnessFile,
    ShippedDefinition,
    scratch_rule,
)
from adjagent.vocabulary import Kind, Tool

_AGENTS_FILE = "AGENTS.md"
_PROJECT_HARNESS_DIR = ".opencode"
_PROJECT_TEMP_DIR = ".opencode-temp"
_USER_HARNESS_DIR = "~/.config/opencode"


def _mcp_entry(*, command: str) -> dict[str, str | list[str]]:
    """A local entry whose argv is the command and `mcp`. The server is started in the project directory
    and finds the KB from there, so the argv names no root."""
    return {"type": "local", "command": [command, "mcp"]}


def _agent_metadata(fields: AgentFields) -> dict[str, object]:
    """An agent's registry values: its description and `mode: subagent`; its model split into provider
    and id where the tier renders one; its color where set; and, unless every tool is allowed, one
    `allow` or `deny` per governed key."""
    record: dict[str, object] = {"description": fields.description, "mode": "subagent"}
    if fields.model:
        provider, _, model = fields.model.partition("/")
        record["model"] = {"providerID": provider, "id": model}
    if fields.color is not None:
        record["color"] = fields.color
    if fields.tools is not None:
        record["permission"] = {key: "allow" if key in fields.tools else "deny" for key in fields.governed}
    return record


def _record(defn: ShippedDefinition) -> dict[str, object]:
    """One definition's registry record: its registered id, which is the reference other definitions spell
    it as, its file below the install directory, its description where it has one, and an agent's or a
    document's metadata — a document is a hidden subagent."""
    record: dict[str, object] = {"id": defn.reference, "file": defn.path}
    if defn.description is not None:
        record["description"] = defn.description
    if defn.agent is not None:
        record.update(_agent_metadata(defn.agent))
    if defn.kind is Kind.DOCUMENT:
        record.update({"mode": "subagent", "hidden": True})
    return record


def _registry_json(plugin: str, shipped: Sequence[ShippedDefinition]) -> str:
    """The registry's whole text: the plugin's name and the version, a record per agent (documents
    included), command and skill, and the `kbase` MCP server where its owning definition ships; written by
    `json.dumps`, whose space after each colon the marker is a substring of."""

    def records(*kinds: Kind) -> list[dict[str, object]]:
        return [_record(defn) for defn in shipped if defn.kind in kinds]

    servers: dict[str, object] = {}
    if any(defn.name == KBASE_OWNER for defn in shipped):
        servers[KBASE_SERVER] = _mcp_entry(command=KBASE_NAME)
    registry = {
        "plugin": plugin,
        "version": __version__,
        "agents": records(Kind.AGENT, Kind.DOCUMENT),
        "commands": records(Kind.COMMAND),
        "skills": records(Kind.SKILL),
        "mcp": servers,
    }
    return json.dumps(registry, indent=2) + "\n"


REGISTRY = HarnessFile(path="registry.json", text=_registry_json, marker='"plugin": "{plugin}"')
"""The registry the copied entry registers the plugin's definitions from."""


HARNESS = Harness(
    name="opencode",
    agents_file=_AGENTS_FILE,
    project_harness_dir=_PROJECT_HARNESS_DIR,
    project_temp_dir=_PROJECT_TEMP_DIR,
    user_harness_dir=_USER_HARNESS_DIR,
    plugin_dir="plugins/{plugin}",
    # the entry registers each definition under the plugin's prefix, which names it everywhere
    reference_prefix="{plugin}-",
    entry_resource="index.ts",
    default_tier_spec="default",
    mcp_tool_prefix="kbase_",
    scratch_rule=scratch_rule(temp_dir=_PROJECT_TEMP_DIR, harness_dir=_PROJECT_HARNESS_DIR),
    memory_file=f"`{_USER_HARNESS_DIR}/{_AGENTS_FILE}`",
    recipe_rule="",
    kbase_project_rule="",
    cold_read_rule=(
        f"{COLD_READ_SCRIPT_RULE} Under opencode the script is not yet reliable: a provider plugin's models are "
        "unavailable in its fresh run directory."
    ),
    side_by_side_rule=(
        "**Installed for Claude Code too.** Where any adjagent plugin is also installed for Claude Code — in a "
        "`.claude/` of this directory or any above it, or in `~/.claude` — opencode also loads that "
        "install's skills: a skill this plugin ships can appear twice, under two names, beside the "
        "other install's. "
        "The session cannot change this; the user does, where the opencode server gets its environment: with "
        "the background service, the default, `opencode service set env OPENCODE_DISABLE_CLAUDE_CODE_SKILLS 1` "
        "then `opencode service restart`; with `--standalone` or the service disabled, "
        "`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` in the shell opencode starts from. It hides every skill "
        "under any `.claude/skills/`, `~/.claude/skills/` included, not only this plugin's."
    ),
    tools={
        Tool.READ: ("read",),
        Tool.GREP: ("grep",),
        Tool.GLOB: ("glob", "list"),
        Tool.EDIT: ("edit",),
        Tool.WRITE: ("edit",),
        Tool.BASH: ("shell",),
        Tool.WEBFETCH: ("webfetch",),
        Tool.WEBSEARCH: ("websearch",),
        Tool.AGENT: ("subagent",),
    },
    model_pattern=re.compile(r"^(inherit|default|[^/\s]+/\S+)$"),
    model_shape=(
        "provider/model with the provider named as your opencode config names it, "
        "for example omlx/Qwen3.8-Flash-Next, or inherit, also spelled default"
    ),
    inherit_text="",
    inherit_synonyms=("default",),
    bare_tier_spec_is_all=True,
    definition_form=REGISTRY,
    # The plugin entry runs the guardrail.
    guardrail=None,
)
