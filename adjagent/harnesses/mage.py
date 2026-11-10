"""The mage harness: claude's vocabulary copied, the plugin manifest, and no `adjagent` skill."""

from __future__ import annotations

import re

from adjagent.harness import PLUGIN_MANIFEST, AgentFields, FrontmatterForm, Harness, mcp_json, quoted
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


_RECIPE_RULE = """A dispatched agent runs recipes in the foreground with the shell tool's timeout set to cover them.
If a recipe times out, the agent hands back naming it instead of rerunning it in the background."""

_KBASE_PROJECT_RULE = """This session's kbase server serves many projects, so run the probes above with `.` read as the
project path you have established for kbase's tool calls, not as the directory you are standing in."""


def _mcp_entry(*, command: str) -> dict[str, str | list[str]]:
    """A `command`/`args` entry. An application harness starts the server outside any one project, so
    `--project-dir-required` makes every tool call name its project with `project-dir` rather than fall
    back to the server's working directory."""
    return {"command": command, "args": ["mcp", "--project-dir-required"]}


_PROJECT_TEMP_DIR = ".mage-temp"

HARNESS = Harness(
    name="mage",
    # no redirect to AGENTS.md, used directly. file installed with agent set, not separately.
    agents_file="CLAUDE.md",
    # the plugin directory under the install target
    project_harness_dir="{plugin}",
    project_temp_dir=_PROJECT_TEMP_DIR,
    # the harness's own directory: CLAUDE.md sits beside .mcp.json, at the plugin's root
    user_harness_dir=".",
    plugin_parent_dir="Mage/Skills",
    # mage namespaces a plugin's agents, commands and skills as Claude Code does
    reference_prefix="{plugin}:",
    mcp_tool_prefix="mcp_kbase_",
    scratch_rule=(
        f"All scratch —\nthrowaway builds, probe harnesses, captured output — goes in `{_PROJECT_TEMP_DIR}/` under the\n"
        "active project root. If it doesn't exist, stop and say so; don't improvise a location."
    ),
    memory_file="the mage plugin's `CLAUDE.md` (outside its marker lines)",
    recipe_rule=_RECIPE_RULE,
    kbase_project_rule=_KBASE_PROJECT_RULE,
    # mage's copy of cold-read.sh refuses to run, so the reader is started by hand
    cold_read_rule=(
        "- Write a brief holding the question and the documents, pasted in full, and run each reader by "
        "hand as a new session with no tools and only the brief, started outside the project: a subagent "
        "of this session cannot be a cold reader, since it holds the project documents this session "
        "loaded and cannot set them aside when told to."
    ),
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
    definition_form=FrontmatterForm(agent=_frontmatter, document=()),
    guardrail=None,
    rendered_files=(PLUGIN_MANIFEST, mcp_json(_mcp_entry)),
    omits=frozenset({"adjagent"}),
)
