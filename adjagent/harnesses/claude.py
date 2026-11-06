"""The claude harness: the set written as one skills-directory plugin below the harness directory."""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from adjagent.harness import (
    PLUGIN_MANIFEST,
    PLUGIN_NAME,
    AgentFields,
    GuardrailHook,
    Harness,
    HarnessFile,
    HookClaim,
    McpSettings,
    McpSite,
    Replacement,
    RetiredEntry,
    quoted,
)
from adjagent.vocabulary import Tool

# Claude Code registers a freshly written plugin's components only after a restart or `/reload-plugins`.
# The sentence names the symptom and the remedy alone: the cause is Claude Code's and may change.
_RELOAD_RULE = (
    "If the new agents are not available after using `adjagent install`, use `/reload-plugins` to rescan the "
    "agent list."
)


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


def _mcp_entry(*, command: str) -> tuple[dict[str, str | list[str]], tuple[str, ...]]:
    """A `command`/`args` entry under `mcpServers`."""
    return {"command": command, "args": ["mcp"]}, ("mcpServers", "kbase")


_GUARDRAIL_SCRIPT = "hooks/guardrail.pl"
# The hook command, split around the directory it names the script in. Claude Code reads exit 2 as a
# block, and that is perl's status for a script it cannot open, so the command runs the script only
# where it stands and otherwise names it on stderr and exits 1, which Claude Code reports without
# blocking. The interpreter is `perl` on PATH, never an absolute path: the file registering it is often
# committed and shared across machines. The report it makes is also the registration's marker and the
# trace an earlier install's settings entry leaves: no file carries it that this repository did not write.
_MISSING_SCRIPT_REPORT = "guardrail hook: no readable script at $s"
_GUARDRAIL_COMMAND_TAIL = (
    f'{_GUARDRAIL_SCRIPT}"; if [ -f "$s" ] && [ -r "$s" ]; then exec perl "$s"; fi; '
    f'echo "{_MISSING_SCRIPT_REPORT}" >&2; exit 1'
)
# Claude Code gives a plugin's hook processes the plugin's root, and runs a command with no `args`
# through a shell, so the path is quoted.
_PLUGIN_GUARDRAIL_COMMAND = f's="${{CLAUDE_PLUGIN_ROOT}}/{_GUARDRAIL_COMMAND_TAIL}'


def _guardrail_registration() -> str:
    """The plugin's `hooks/hooks.json`: one PreToolUse entry running the guardrail on every Bash and
    file-tool call."""
    entry = {
        "matcher": "Bash|Read|Write|Edit|NotebookEdit|Grep|Glob",
        "hooks": [{"type": "command", "command": _PLUGIN_GUARDRAIL_COMMAND}],
    }
    return json.dumps({"hooks": {"PreToolUse": [entry]}}, indent=2) + "\n"


# The command an earlier install registered in the project's settings file, naming the script from
# `$CLAUDE_PROJECT_DIR` through whatever harness directory it was installed in: one holding a character
# a double-quoted shell word reads as syntax was refused, so none appears in it.
_GUARDRAIL_COMMAND_HEAD = 's="$CLAUDE_PROJECT_DIR/'
_UNQUOTABLE = r'"$`\\'
_GUARDRAIL_COMMAND = re.compile(
    rf"{re.escape(_GUARDRAIL_COMMAND_HEAD)}(?:[^{_UNQUOTABLE}]+/)?{re.escape(_GUARDRAIL_COMMAND_TAIL)}"
)


def _guardrail_claim(element: object) -> HookClaim:
    """What a PreToolUse element holds of the guardrail an earlier install registered in the project's
    settings file: a command is ours only when it is exactly the one that install wrote, for any harness
    directory."""
    commands = element.get("hooks") if isinstance(element, dict) else None
    if not isinstance(commands, list):
        return HookClaim.NONE
    ours = [
        isinstance(hook, dict)
        and isinstance(hook.get("command"), str)
        and _GUARDRAIL_COMMAND.fullmatch(hook["command"]) is not None
        for hook in commands
    ]
    if not any(ours):
        return HookClaim.NONE
    return HookClaim.ALONE if all(ours) else HookClaim.SHARED


def _kbase_claim(value: object) -> HookClaim:
    """Whether the project `.mcp.json`'s `kbase` server is the one an earlier install wrote, read from its
    command alone, the one field every earlier version wrote alike: the bare `kbase`, or a path to an
    executable of that name."""
    command = value.get("command") if isinstance(value, dict) else None
    ours = isinstance(command, str) and PurePosixPath(command).name == "kbase"
    return HookClaim.ALONE if ours else HookClaim.NONE


HARNESS = Harness(
    name="claude",
    agents_file="CLAUDE.md",
    project_harness_dir=".claude",
    project_temp_dir=".claude-temp",
    user_harness_dir="~/.claude",
    plugin_dir=f"skills/{PLUGIN_NAME}",
    # a plugin's components register only under the plugin's namespace, its MCP tools included
    reference_prefix=f"{PLUGIN_NAME}:",
    mcp_tool_prefix=f"mcp__plugin_{PLUGIN_NAME}_kbase__",
    reload_rule=_RELOAD_RULE,
    recipe_rule=_RECIPE_RULE,
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
    frontmatter=_frontmatter,
    document_frontmatter=(),
    mcp=McpSettings(canonical=".mcp.json", alternatives=(), site=McpSite.HARNESS, entry=_mcp_entry),
    rendered_files=(PLUGIN_MANIFEST,),
    guardrail=GuardrailHook(
        script=_GUARDRAIL_SCRIPT,
        registration=HarnessFile(path="hooks/hooks.json", text=_guardrail_registration, marker=_MISSING_SCRIPT_REPORT),
    ),
    # What the plugin's own registration and MCP entry replace. Claude Code reads project hooks from the
    # one settings path, whatever directory the harness was installed in.
    retired_entries=(
        RetiredEntry(
            settings=".claude/settings.json",
            container=("hooks", "PreToolUse"),
            member="",
            claim=_guardrail_claim,
            replacement=Replacement.GUARDRAIL,
            trace=_MISSING_SCRIPT_REPORT,
        ),
        RetiredEntry(
            settings=".mcp.json",
            container=("mcpServers",),
            member="kbase",
            claim=_kbase_claim,
            replacement=Replacement.MCP,
            trace='"kbase"',
        ),
    ),
)
