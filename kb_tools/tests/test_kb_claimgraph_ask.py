"""A claim-graph ask, at the invocation seam: the argv every one of them is spawned with.

Every other check over this package's asks runs above :class:`ask.SeatAsk`, so
none of them sees how a call is made. These run the production ask below it,
against a substituted :class:`~kb_tools.inference.Invoker`, and read the argv
the CLI would have been handed.
"""

import functools
import inspect
import json
from pathlib import Path

import pytest

from kb_tools.inference import seat
from kb_tools.kb_claimgraph import ask
from kb_tools.kb_driver import prompt_templates
from kb_tools.tests.test_inference import ScriptedCall, ScriptedInvoker, init_event, result_event

BODY = "You are a mathematician.\n\nCheck every step."


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """The claim-graph seat, installed with frontmatter granting it tools."""
    agents = tmp_path / seat.seat_directory()
    agents.mkdir(parents=True)
    (agents / f"{ask.SEAT}.md").write_text(
        f"---\nname: {ask.SEAT}\ntools: Read, Grep, Glob, Bash\nmodel: opus\n---\n\n{BODY}\n", encoding="utf-8"
    )
    return tmp_path


def _argv_of_one_ask(project: Path) -> tuple[str, ...]:
    invoker = ScriptedInvoker(ScriptedCall(lines=(init_event(), result_event("answer"))))
    production = functools.partial(ask.ask_without_tools, invoker=invoker)

    text, outcome = production(seat=ask.SEAT, prompt="judge this\n", cwd=project)

    assert outcome.ok and text == "answer"
    assert len(invoker.calls) == 1
    return invoker.calls[0].argv


def test_a_claim_graph_ask_cannot_call_a_tool_and_is_not_an_agent(project: Path) -> None:
    argv = _argv_of_one_ask(project)

    assert argv[argv.index("--tools") + 1] == ""
    assert "--agent" not in argv
    # No MCP server: strict, with no --mcp-config naming one.
    assert "--strict-mcp-config" in argv
    assert "--mcp-config" not in argv


def test_a_claim_graph_ask_reads_no_memory_and_keeps_keychain_auth(project: Path) -> None:
    argv = _argv_of_one_ask(project)

    settings = json.loads(argv[argv.index("--settings") + 1])
    assert "**/CLAUDE.md" in settings["claudeMdExcludes"]
    assert settings["autoMemoryEnabled"] is False
    assert "--bare" not in argv


def test_a_claim_graph_asks_system_prompt_is_the_seats_body_then_the_no_tools_fragment(project: Path) -> None:
    fragment = prompt_templates.render(prompt_templates.FRAGMENTS[ask.NO_TOOLS], slots={})

    argv = _argv_of_one_ask(project)

    assert argv[argv.index("--system-prompt") + 1] == f"{BODY}\n\n{fragment.strip()}"


def test_both_claim_graph_consumers_ask_through_the_tool_less_call_by_default() -> None:
    for consumer in (ask.ModelSelector, ask.ModelIdentifier):
        assert inspect.signature(consumer).parameters["ask"].default is ask.ask_without_tools
