"""The opencode harness."""

import re

from adjagent.harness import AgentFields, Harness, quoted
from adjagent.vocabulary import Tool


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


HARNESS = Harness(
    name="opencode",
    agents_file="AGENTS.md",
    project_harness_dir=".opencode",
    project_temp_dir=".opencode-temp",
    user_harness_dir="~/.config/opencode",
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
    model_pattern=re.compile(r"^(inherit|[^/\s]+/\S+)$"),
    model_shape=(
        "provider/model with the provider named as your opencode config names it, "
        "for example omlx/Qwen3.8-Flash-Next, or inherit"
    ),
    inherit_text="",
    frontmatter=_frontmatter,
    # An undispatchable reference document: listed as a subagent, never offered for dispatch.
    document_frontmatter=("mode: subagent", "disable: true"),
)
