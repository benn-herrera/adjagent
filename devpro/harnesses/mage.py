"""The mage harness: the shared frontmatter emitter and recipe rule from `devpro.harness`, the rest of
claude's vocabulary copied, the plugin manifest, and no `install` skill."""

from __future__ import annotations

import re

from devpro.harness import (
    FOREGROUND_RECIPE_RULE,
    PLUGIN_MANIFEST,
    FrontmatterForm,
    Harness,
    agent_frontmatter,
    mcp_json,
)
from devpro.vocabulary import Tool

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
    display_name="mage",
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
    recipe_rule=FOREGROUND_RECIPE_RULE,
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
    definition_form=FrontmatterForm(agent=agent_frontmatter, document=()),
    guardrail=None,
    rendered_files=(PLUGIN_MANIFEST, mcp_json(_mcp_entry)),
    omits=frozenset({"install"}),
)
