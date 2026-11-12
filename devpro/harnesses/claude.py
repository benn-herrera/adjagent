"""The claude harness: the set written as one skills-directory plugin below the harness directory."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from devpro.harness import (
    COLD_READ_SCRIPT_RULE,
    FOREGROUND_RECIPE_RULE,
    PLUGIN_MANIFEST,
    FrontmatterForm,
    GuardrailHook,
    Harness,
    HarnessFile,
    ShippedDefinition,
    agent_frontmatter,
    mcp_json,
    scratch_rule,
)
from devpro.vocabulary import Tool

# Claude Code registers a freshly written plugin's components only after a restart or `/reload-plugins`.
# The sentence names the symptom and the remedy alone: the cause is Claude Code's and may change.
_RELOAD_RULE = (
    "If the new agents are not available after using `devpro install`, `/reload-plugins` rescans the agent list."
)


def _mcp_entry(*, command: str) -> dict[str, str | list[str]]:
    """A `command`/`args` entry."""
    return {"command": command, "args": ["mcp"]}


_GUARDRAIL_SCRIPT = "hooks/guardrail.pl"
# The hook command. Claude Code gives a plugin's hook processes the plugin's root, and runs a command
# with no `args` through a shell, so the path is quoted. Claude Code reads exit 2 as a block, and that
# is perl's status for a script it cannot open, so the command runs the script only where it stands
# and otherwise names it on stderr and exits 1, which Claude Code reports without blocking. The
# interpreter is `perl` on PATH, never an absolute path: the file registering it is often committed
# and shared across machines. The report it makes is also the registration's marker: no file carries
# it that this repository did not write.
_MISSING_SCRIPT_REPORT = "guardrail hook: no readable script at $s"
_PLUGIN_GUARDRAIL_COMMAND = (
    f's="${{CLAUDE_PLUGIN_ROOT}}/{_GUARDRAIL_SCRIPT}"; if [ -f "$s" ] && [ -r "$s" ]; then exec perl "$s"; fi; '
    f'echo "{_MISSING_SCRIPT_REPORT}" >&2; exit 1'
)


def _guardrail_registration(plugin: str, shipped: Sequence[ShippedDefinition]) -> str:
    """The plugin's `hooks/hooks.json`: one PreToolUse entry running the guardrail on every Bash and
    file-tool call, the same for every plugin."""
    entry = {
        "matcher": "Bash|Read|Write|Edit|NotebookEdit|Grep|Glob",
        "hooks": [{"type": "command", "command": _PLUGIN_GUARDRAIL_COMMAND}],
    }
    return json.dumps({"hooks": {"PreToolUse": [entry]}}, indent=2) + "\n"


_AGENTS_FILE = "CLAUDE.md"
_PROJECT_HARNESS_DIR = ".claude"
_PROJECT_TEMP_DIR = ".claude-temp"
_USER_HARNESS_DIR = "~/.claude"

HARNESS = Harness(
    name="claude",
    agents_file=_AGENTS_FILE,
    project_harness_dir=_PROJECT_HARNESS_DIR,
    project_temp_dir=_PROJECT_TEMP_DIR,
    display_name="claude code",
    user_harness_dir=_USER_HARNESS_DIR,
    plugin_dir="skills/{plugin}",
    # a plugin's components register only under the plugin's namespace, its MCP tools included
    reference_prefix="{plugin}:",
    mcp_tool_prefix="mcp__plugin_{plugin}_kbase__",
    scratch_rule=scratch_rule(temp_dir=_PROJECT_TEMP_DIR, harness_dir=_PROJECT_HARNESS_DIR),
    memory_file=f"`{_USER_HARNESS_DIR}/{_AGENTS_FILE}`",
    user_plugin_shadows=True,
    reload_rule=_RELOAD_RULE,
    cold_read_rule=COLD_READ_SCRIPT_RULE,
    recipe_rule=FOREGROUND_RECIPE_RULE,
    kbase_project_rule="",
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
    rendered_files=(PLUGIN_MANIFEST, mcp_json(_mcp_entry)),
    guardrail=GuardrailHook(
        script=_GUARDRAIL_SCRIPT,
        registration=HarnessFile(path="hooks/hooks.json", text=_guardrail_registration, marker=_MISSING_SCRIPT_REPORT),
    ),
)
