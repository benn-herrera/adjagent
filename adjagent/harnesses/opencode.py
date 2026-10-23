"""The opencode harness."""

import re
from pathlib import Path

from adjagent.harness import AgentFields, Harness, McpSettings, project_relative, quoted
from adjagent.vocabulary import Tool

_PROJECT_HARNESS_DIR = ".opencode"


def _frontmatter(fields: AgentFields) -> tuple[str, ...]:
    """description "…"; model if non-empty; color "…" if set; unless tools is None, `permission:` and
    one `  <key>: allow|deny` line per governed key; then `mode: subagent`."""
    lines = [f"description: {quoted(fields.description)}"]
    if fields.model:
        lines.append(f"model: {fields.model}")
    if fields.color is not None:
        lines.append(f"color: {quoted(fields.color)}")
    if fields.tools is not None:
        lines.append("permission:")
        lines += [f"  {key}: {'allow' if key in fields.tools else 'deny'}" for key in fields.governed]
    lines.append("mode: subagent")
    return tuple(lines)


def _mcp_entry(*, command: str, project_root: Path) -> tuple[dict[str, str | list[str]], tuple[str, ...]]:
    """A local entry under `mcp.servers` whose argv is the command from `project_relative` and `mcp`.
    The server is started in the project directory and finds the KB from there, so the argv names no root."""
    return {"type": "local", "command": [project_relative(command, project_root), "mcp"]}, ("mcp", "servers", "kbase")


HARNESS = Harness(
    name="opencode",
    agents_file="AGENTS.md",
    project_harness_dir=_PROJECT_HARNESS_DIR,
    project_temp_dir=".opencode-temp",
    user_harness_dir="~/.config/opencode",
    mcp_tool_prefix="kbase_",
    recipe_rule="",
    coder_dispatch=None,
    tools={
        Tool.READ: ("read",),
        Tool.GREP: ("grep",),
        Tool.GLOB: ("glob", "list"),
        Tool.EDIT: ("edit",),
        Tool.WRITE: ("edit",),
        Tool.BASH: ("bash",),
        Tool.WEBFETCH: ("webfetch",),
        Tool.WEBSEARCH: ("websearch",),
        Tool.AGENT: ("task",),
    },
    model_pattern=re.compile(r"^(inherit|default|[^/\s]+/\S+)$"),
    model_shape=(
        "provider/model with the provider named as your opencode config names it, "
        "for example omlx/Qwen3.8-Flash-Next, or inherit, also spelled default"
    ),
    inherit_text="",
    inherit_synonyms=("default",),
    bare_tier_spec_is_all=True,
    frontmatter=_frontmatter,
    # An undispatchable reference document: listed as a subagent, never offered for dispatch.
    document_frontmatter=("mode: subagent", "disable: true"),
    mcp=McpSettings(
        canonical=f"{_PROJECT_HARNESS_DIR}/opencode.jsonc",
        alternatives=(f"{_PROJECT_HARNESS_DIR}/opencode.json", "opencode.jsonc", "opencode.json"),
        entry=_mcp_entry,
    ),
    # The guardrail plugin it ships registers itself.
    guardrail=None,
)
