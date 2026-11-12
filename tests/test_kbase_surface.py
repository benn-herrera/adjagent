"""The kbase names the kbase skill cites, held to the surface the installed kbase offers.

One `kbase mcp` server per module, under a scratch `HOME`, is asked over stdio for `initialize`,
`tools/list`, `resources/list` and a `resources/read` of every `kbase://help/<name>` text, and nothing
else; with `--project-dir-required` it locates no project, so it reads no KB. kbase 0.11.0 offers no
resource templates, so every `kbase://` resource is in `resources/list`. The installed kbase must be at
least `KBASE_MIN_VERSION`.

A cited name is a backticked kebab-case word in a harness's render of the kbase skill, that harness's
`mcp_tool_prefix` removed. It is offered when it is a tool, an `operation` of the query tool, a name
with a `kbase://help/<name>` resource, or an argument: a tool's `inputSchema` property, or a help text's
`` `<name>` ( `` line after `Arguments:`. Any other cited name is offered when it is a whole word inside
a backticked or double-quoted span of the server's instructions or of a help text. A cited name kbase
does not offer is listed here with the reason the skill cites it. A missing `kbase` fails rather than
skips, because a skip would hide drift between the two.
"""

import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as ReadTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import pytest

from devpro.context import Render, harnesses
from devpro.definitions.kbase import KBASE_MIN_VERSION
from devpro.families.claude import FAMILY as CLAUDE_FAMILY
from devpro.harness import Harness
from devpro.plugins.kbase import PLUGIN as KBASE
from devpro.render import render_all, rendered_definitions

_READ_TIMEOUT_S = 10
_HELP = "kbase://help/"
_KEBAB = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
_ARGUMENT_LINE = re.compile(rf"^\s*`({_KEBAB})` \(", re.MULTILINE)
_QUOTED_SPAN = re.compile(r"`[^`\n]*`|\"[^\"\n]*\"")

# The cited names kbase does not offer, each with the reason the skill cites it.
_NOT_OFFERED = {
    "dirty": "a key of build-trail's result, which its help names unquoted",
    "started-at": "a key of build-trail's result, which its help names unquoted",
    "premises": "a key of show's result for a claim, whose fields show's help does not name",
    "unchanged": "a write entry's outcome, which the add helps name unquoted",
    "demoted": "the relation of an edge the build set aside, which add-edge's help names unquoted",
    "founds": "a scoring relation, which add-edge's help lists unquoted",
    "lifts": "a scoring relation, which add-edge's help lists unquoted",
    "refutes": "a scoring relation, which add-edge's help lists unquoted",
    "references": "the relation carrying no strength, which add-edge's help lists unquoted",
    "kbase": "the executable and the MCP server, named by the user's install, not by the server",
    "kb-stats": "a runner target devpro's kb install writes",
    "kb-update-format": "a runner target devpro's kb install writes",
    "kb-verify": "a runner target devpro's kb install writes",
    "clm-yl5n5v": "an example claim id in the skill's prose",
    "main": "a git branch",
    "bin": "Homebrew's directory of executables",
    "cd": "the shell command",
    "v": "the prefix `kbase --version` does not print",
}


@dataclass(frozen=True)
class _Surface:
    version: str  # `initialize`'s `serverInfo.version`
    commands: frozenset[str]  # the tools and the query tool's operations
    uris: frozenset[str]  # every listed resource's uri
    arguments: frozenset[str]  # every tool's `inputSchema` properties and every help text's arguments
    quoted: frozenset[str]  # every word inside a backticked or double-quoted span of the instructions or a help text

    @property
    def helped(self) -> frozenset[str]:
        return frozenset(uri[len(_HELP) :] for uri in self.uris if uri.startswith(_HELP))

    @property
    def offered(self) -> frozenset[str]:
        return self.commands | self.helped | self.arguments | self.quoted


class _Session:
    """JSON-RPC requests to a running `kbase mcp`, each reply read under the timeout. Every failure
    carries the server's stderr."""

    def __init__(self, server: subprocess.Popen, reader: ThreadPoolExecutor, stderr_path: Path) -> None:
        self._server = server
        self._reader = reader
        self._stderr_path = stderr_path
        self._next_id = 0

    def fail(self, message: str) -> NoReturn:
        pytest.fail(f"kbase mcp: {message}\nkbase stderr:\n{self._stderr_path.read_text(encoding='utf-8')}")

    def _send(self, message: dict) -> None:
        self._server.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
        self._server.stdin.flush()

    def notify(self, method: str) -> None:
        self._send({"method": method})

    def request(self, method: str, params: dict) -> dict:
        self._next_id += 1
        self._send({"id": self._next_id, "method": method, "params": params})
        deadline = time.monotonic() + _READ_TIMEOUT_S
        while True:
            try:
                line = self._reader.submit(self._server.stdout.readline).result(
                    timeout=max(0.0, deadline - time.monotonic())
                )
            except ReadTimeout:
                self.fail(f"no reply to {method} within {_READ_TIMEOUT_S} s")
            if not line:
                self.fail(f"stdout closed while waiting for the reply to {method}")
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                self.fail(f"a line that is not JSON while waiting for the reply to {method}: {line!r}")
            if reply.get("id") == self._next_id:
                if "error" in reply:
                    self.fail(f"{method} answered with error {reply['error']}")
                return reply["result"]


def _words_in_quoted_spans(text: str) -> set[str]:
    return {word for span in _QUOTED_SPAN.findall(text) for word in re.findall(r"[\w-]+", span)}


def _help_arguments(text: str) -> set[str]:
    return set(_ARGUMENT_LINE.findall(text.partition("\nArguments:\n")[2]))


@pytest.fixture(scope="module")
def surface(tmp_path_factory: pytest.TempPathFactory) -> _Surface:
    if shutil.which("kbase") is None:
        pytest.fail("kbase is not on PATH: the names the kbase skill cites cannot be checked without it")
    stderr_path = tmp_path_factory.mktemp("kbase") / "stderr.txt"
    env = {name: value for name, value in os.environ.items() if name not in ("KBASE_CONFIG_DIR", "XDG_STATE_HOME")}
    env["HOME"] = str(tmp_path_factory.mktemp("home"))
    with (
        stderr_path.open("w", encoding="utf-8") as stderr,
        subprocess.Popen(
            ["kbase", "mcp", "--project-dir-required"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            encoding="utf-8",
            env=env,
        ) as server,
        ThreadPoolExecutor(max_workers=1) as reader,
    ):
        try:
            session = _Session(server, reader, stderr_path)
            initialized = session.request(
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "devpro-tests", "version": "0"},
                },
            )
            session.notify("notifications/initialized")
            tools = session.request("tools/list", {})["tools"]
            uris = frozenset(resource["uri"] for resource in session.request("resources/list", {})["resources"])
            helps = [
                content["text"]
                for uri in sorted(uris)
                if uri.startswith(_HELP)
                for content in session.request("resources/read", {"uri": uri})["contents"]
            ]
            server.stdin.close()
            server.wait(timeout=_READ_TIMEOUT_S)
        finally:
            if server.poll() is None:
                server.kill()
    [query] = [tool for tool in tools if tool["name"] == "query"]
    operations = query["inputSchema"]["properties"]["operation"]["enum"]
    return _Surface(
        version=initialized["serverInfo"]["version"],
        commands=frozenset(tool["name"] for tool in tools) | frozenset(operations),
        uris=uris,
        arguments=frozenset(name for tool in tools for name in tool["inputSchema"].get("properties", {}))
        | frozenset(name for text in helps for name in _help_arguments(text)),
        quoted=frozenset(
            word for text in [initialized.get("instructions", ""), *helps] for word in _words_in_quoted_spans(text)
        ),
    )


def _kbase_skill_text(harness: Harness) -> str:
    """Every file of `harness`'s render of the kbase skill, as the kbase plugin ships it, joined."""
    ctx = Render(harness=harness, plugin=KBASE, family=CLAUDE_FAMILY, tier_map=dict(CLAUDE_FAMILY.tiers))
    [skill] = [defn for _, defn in rendered_definitions(ctx) if defn.name == "kbase"]
    rendered = dict(render_all(ctx))
    return "\n".join(rendered[path] for path in skill.output_paths)


def _cited(harness: Harness) -> set[str]:
    prefix = re.escape(harness.bound(KBASE.name).mcp_tool_prefix)
    return set(re.findall(rf"`(?:{prefix})?({_KEBAB})`", _kbase_skill_text(harness)))


def _release(version: str) -> tuple[int, ...]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        pytest.fail(f"{version!r} is not a major.minor.patch version")
    return tuple(int(part) for part in match.groups())


_HARNESSES = list(harnesses().values())


def test_the_installed_kbase_is_at_least_the_minimum(surface: _Surface) -> None:
    assert _release(surface.version) >= _release(
        KBASE_MIN_VERSION
    ), f"kbase {surface.version} is installed; the kbase skill needs {KBASE_MIN_VERSION} or later"


@pytest.mark.parametrize("harness", _HARNESSES, ids=lambda harness: harness.name)
def test_every_kbase_name_the_skill_cites_is_offered_or_listed(harness: Harness, surface: _Surface) -> None:
    cited = _cited(harness)
    assert cited, f"no kbase name found in {harness.name}'s render of the kbase skill"
    assert cited - surface.offered - _NOT_OFFERED.keys() == set()


def test_every_listed_name_is_cited_and_not_offered(surface: _Surface) -> None:
    cited = set().union(*(_cited(harness) for harness in _HARNESSES))
    assert _NOT_OFFERED.keys() - cited == set()
    assert _NOT_OFFERED.keys() & surface.offered == set()


@pytest.mark.parametrize("harness", _HARNESSES, ids=lambda harness: harness.name)
def test_every_kbase_uri_the_skill_cites_is_listed(harness: Harness, surface: _Surface) -> None:
    """A literal URI is in `resources/list`; a `kbase://help/<…>` placeholder holds when every tool or
    operation the skill cites has its help resource."""
    uris = set(re.findall(r"`(kbase://[^`]*)`", _kbase_skill_text(harness)))
    literals = {uri for uri in uris if "<" not in uri}
    assert literals - surface.uris == set()
    if literals != uris:
        assert (_cited(harness) & surface.commands) - surface.helped == set()
