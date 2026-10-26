"""The mage harness: claude's vocabulary copied, its own plugin manifest, and no `imgread`."""

import json
import re
from pathlib import Path

from adjagent.harness import AgentFields, Harness, HarnessFile, McpSettings, McpSite, command_relative, quoted
from adjagent.version import VERSION
from adjagent.vocabulary import Tool

_PLUGIN_NAME = "adjagent"
_PLUGIN_DESCRIPTION = "Adjagent skills, agents, and MCP tools"


def _plugin_json() -> str:
    """The plugin manifest's whole text: name, version and description, with `json.dumps`'s default
    separators, whose space after each colon the marker is a substring of."""
    return json.dumps({"name": _PLUGIN_NAME, "version": VERSION, "description": _PLUGIN_DESCRIPTION}, indent=2) + "\n"


FILES = (HarnessFile(path=".claude-plugin/plugin.json", text=_plugin_json, marker=f'"name": "{_PLUGIN_NAME}"'),)


def _frontmatter(fields: AgentFields) -> tuple[str, ...]:
    """name; description "…"; model if non-empty; color "…" if set; `tools: A, B` unless tools is None."""
    lines = [f"name: {fields.name}", f"description: {quoted(fields.description)}"]
    if fields.model:
        lines.append(f"model: {fields.model}")
    if fields.color is not None:
        lines.append(f"color: {quoted(fields.color)}")
    if fields.tools is not None:
        lines.append(f"tools: {', '.join(fields.tools)}")
    return tuple(lines)


_RECIPE_RULE = """A dispatched agent runs recipes in the foreground with the shell tool's timeout set to cover them, and
never hands back with a background command running. If a recipe times out, the agent hands back naming it
instead of rerunning it in the background."""


def _mcp_entry(*, command: str, base: Path) -> tuple[dict[str, str | list[str]], tuple[str, ...]]:
    """A `command`/`args` entry under `mcpServers`, its command from `command_relative`."""
    return {"command": command_relative(command, base), "args": ["mcp"]}, ("mcpServers", "kbase")


HARNESS = Harness(
    name="mage",
    # no redirect to AGENTS.md, used directly. file installed with agent set, not separately.
    agents_file="CLAUDE.md",
    # the plugin's own directory under the install target
    project_harness_dir="adjagent",
    project_temp_dir=".mage-temp",
    # the harness's own directory: CLAUDE.md sits beside .mcp.json, at the plugin's root
    user_harness_dir=".",
    mcp_tool_prefix="mcp__kbase__",
    recipe_rule=_RECIPE_RULE,
    coder_dispatch=None,
    tools={
        Tool.READ: ("Read",),
        Tool.GREP: ("Grep",),
        Tool.GLOB: ("Glob",),
        Tool.EDIT: ("Edit",),
        Tool.WRITE: ("Write",),
        Tool.BASH: ("Bash",),
        Tool.WEBFETCH: ("WebFetch",),
        Tool.WEBSEARCH: ("WebSearch",),
        Tool.AGENT: ("Agent",),
    },
    model_pattern=re.compile(r"^(fable|opus|sonnet|haiku|inherit|claude-\S+)$"),
    model_shape="a Claude alias (fable, opus, sonnet, haiku), a full model id such as claude-opus-4-1, or inherit",
    inherit_text="inherit",
    inherit_synonyms=(),
    bare_tier_spec_is_all=False,
    frontmatter=_frontmatter,
    document_frontmatter=(),
    mcp=McpSettings(canonical=".mcp.json", alternatives=(), site=McpSite.HARNESS, entry=_mcp_entry),
    guardrail=None,
    rendered_files=FILES,
    omits=frozenset({"imgread"}),
)
