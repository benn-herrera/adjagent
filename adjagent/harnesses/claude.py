"""The claude harness."""

import re
from pathlib import Path

from adjagent.harness import AgentFields, Harness, McpSettings, quoted
from adjagent.vocabulary import Tool


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


def _coder_dispatch(model: str) -> str:
    """The coder-dispatch bullet for a rendered model name."""
    return f"""- Coder dispatches: when the brief is fully mechanical — every edit enumerated, no design choice, no
  debugging — dispatch at `model: {model}`; otherwise the definition's pin stands."""


def _mcp_entry(*, command: str, kb_root: str, project_root: Path) -> tuple[dict[str, str | list[str]], tuple[str, ...]]:
    """The `kbase` server entry and the `mcpServers` container it nests under. The command is the
    executable's path relative to the project when it sits inside it, absolute otherwise: Claude Code
    reads an absolute path inside the project as a shared file outside it."""
    executable = Path(command).resolve()
    project = project_root.resolve()
    return {
        "command": executable.relative_to(project).as_posix() if executable.is_relative_to(project) else command,
        "args": ["mcp", "--kb-root", kb_root],
    }, ("mcpServers", "kbase")


HARNESS = Harness(
    name="claude",
    agents_file="CLAUDE.md",
    project_harness_dir=".claude",
    project_temp_dir=".claude-temp",
    user_harness_dir="~/.claude",
    mcp_tool_prefix="mcp__kbase__",
    coder_dispatch=_coder_dispatch,
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
    mcp=McpSettings(canonical=".mcp.json", alternatives=(), entry=_mcp_entry),
)
