"""The mage harness: claude's vocabulary copied, its own plugin manifest, and no `imgread`."""

import json
import re

from adjagent.harness import AgentFields, Harness, HarnessFile, McpSettings, McpSite, quoted
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

_KBASE_PROJECT_RULE = """This session's kbase server serves many projects and locates none of its own: every kbase tool call
passes `project-dir`, the project's absolute path — the git worktree root that holds `kb-root/` or
will — and a call without it fails. Establish that path before anything else, asking the user where
nothing in the session names it, and run the probes above with `.` read as that path rather than as
the directory you are standing in."""


def _mcp_entry(*, command: str) -> tuple[dict[str, str | list[str]], tuple[str, ...]]:
    """A `command`/`args` entry under `mcpServers`. An application harness starts the server outside any
    one project, so `--project-dir-required` makes every tool call name its project with `project-dir`
    rather than fall back to the server's working directory."""
    return {"command": command, "args": ["mcp", "--project-dir-required"]}, (
        "mcpServers",
        "kbase",
    )


HARNESS = Harness(
    name="mage",
    # no redirect to AGENTS.md, used directly. file installed with agent set, not separately.
    agents_file="CLAUDE.md",
    # the plugin's own directory under the install target
    project_harness_dir="adjagent",
    project_temp_dir=".mage-temp",
    # the harness's own directory: CLAUDE.md sits beside .mcp.json, at the plugin's root
    user_harness_dir=".",
    mcp_tool_prefix="mcp_kbase_",
    recipe_rule=_RECIPE_RULE,
    kbase_project_rule=_KBASE_PROJECT_RULE,
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
