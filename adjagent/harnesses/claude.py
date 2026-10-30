"""The claude harness."""

import re

from adjagent.errors import InputError
from adjagent.harness import (
    AgentFields,
    GuardrailHook,
    Harness,
    HookClaim,
    McpSettings,
    McpSite,
    quoted,
)
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


_RECIPE_RULE = """A dispatched agent runs recipes in the foreground with the shell tool's timeout set to cover them, and
never hands back with a background command running. If a recipe times out, the agent hands back naming it
instead of rerunning it in the background."""


def _mcp_entry(*, command: str) -> tuple[dict[str, str | list[str]], tuple[str, ...]]:
    """A `command`/`args` entry under `mcpServers`."""
    return {"command": command, "args": ["mcp"]}, ("mcpServers", "kbase")


_GUARDRAIL_SCRIPT = "hooks/guardrail.pl"
# The hook command, split around the harness directory it names. Claude Code reads exit 2 as a block,
# and that is perl's status for a script it cannot open, so the command runs the script only where it
# stands and otherwise names it on stderr and exits 1, which Claude Code reports without blocking.
# The interpreter is `perl` on PATH, never an absolute path: the settings file is often committed and
# shared across machines.
_GUARDRAIL_COMMAND_HEAD = 's="$CLAUDE_PROJECT_DIR/'
_GUARDRAIL_COMMAND_TAIL = (
    f'{_GUARDRAIL_SCRIPT}"; if [ -f "$s" ] && [ -r "$s" ]; then exec perl "$s"; fi; '
    'echo "guardrail hook: no readable script at $s" >&2; exit 1'
)
# The characters a double-quoted shell word reads as syntax, as a regex class body: a harness directory
# holding one cannot be named in the command.
_UNQUOTABLE = r'"$`\\'
_GUARDRAIL_COMMAND = re.compile(
    rf"{re.escape(_GUARDRAIL_COMMAND_HEAD)}(?:[^{_UNQUOTABLE}]+/)?{re.escape(_GUARDRAIL_COMMAND_TAIL)}"
)


def _guardrail_entry(harness_relpath: str) -> dict[str, object]:
    """The PreToolUse entry running the guardrail on every Bash and file-tool call, named from `$CLAUDE_PROJECT_DIR`.
    A harness directory holding a character the double-quoted word would read as syntax is refused."""
    if re.search(f"[{_UNQUOTABLE}]", harness_relpath):
        raise InputError(
            f"harness directory '{harness_relpath}' holds a character the guardrail hook command cannot "
            'quote (", $, ` or \\) — install into a directory without one'
        )
    prefix = "" if harness_relpath == "." else f"{harness_relpath}/"
    command = f"{_GUARDRAIL_COMMAND_HEAD}{prefix}{_GUARDRAIL_COMMAND_TAIL}"
    return {"matcher": "Bash|Read|Write|Edit|NotebookEdit|Grep|Glob", "hooks": [{"type": "command", "command": command}]}


def _guardrail_claim(element: object) -> HookClaim:
    """What a PreToolUse element holds of the guardrail: a command is ours only when it is exactly the
    one `_guardrail_entry` writes, for any harness directory."""
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


HARNESS = Harness(
    name="claude",
    agents_file="CLAUDE.md",
    project_harness_dir=".claude",
    project_temp_dir=".claude-temp",
    user_harness_dir="~/.claude",
    mcp_tool_prefix="mcp__kbase__",
    recipe_rule=_RECIPE_RULE,
    kbase_project_rule="",
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
    mcp=McpSettings(canonical=".mcp.json", alternatives=(), site=McpSite.PROJECT, entry=_mcp_entry),
    # Claude Code reads project hooks from this one path, whatever directory the harness is installed in.
    guardrail=GuardrailHook(
        script=_GUARDRAIL_SCRIPT,
        settings=".claude/settings.json",
        container=("hooks", "PreToolUse"),
        entry=_guardrail_entry,
        claim=_guardrail_claim,
    ),
)
