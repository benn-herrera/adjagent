"""A loopback chat-completions server for the suites that make a chat call, and nothing else.

It records every request and answers with a scripted SSE stream or HTTP status,
torn down as ``liaison_tools/tests/_stub_server.py`` does — no test needs a
model to be reachable. A test module takes the fixtures ``server`` (the stub
alone) and ``served`` (the stub, named by the environment a ``reaper-*.env``
file sets) by importing ``server_fixture`` and ``served_fixture``;
``conftest.no_reader_server`` clears that environment first.
"""

import http.server
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from kb_tools.inference import liaison_tools
from liaison_tools.tests._stub_server import POLL_INTERVAL_SECONDS

SERVED_MODEL = "local-model"
TOKEN = "stub-token"

USAGE = {"prompt_tokens": 7718, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 7711}}


def chunk(delta: dict[str, object], finish_reason: str | None = None) -> dict[str, object]:
    return {
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def sse(*objects: dict[str, object], done: bool = True) -> bytes:
    lines = [f"data: {json.dumps(obj)}\n\n" for obj in objects]
    return ("".join(lines) + ("data: [DONE]\n\n" if done else "")).encode("utf-8")


#: A letter reply in the shape the local server streams it: role, content, finish, then the usage chunk.
LETTER_A = sse(
    chunk({"role": "assistant"}),
    chunk({"content": "A"}),
    chunk({}, "stop"),
    {"object": "chat.completion.chunk", "choices": [], "usage": USAGE},
)


@dataclass
class StubServer:
    """What the stub answers, and every request it was sent.

    Each request takes the next ``(status, body)`` off ``script`` while it
    holds any, and ``status`` and ``body`` after that.
    """

    status: int = 200
    body: bytes = LETTER_A
    script: list[tuple[int, bytes]] = field(default_factory=list)
    requests: list[dict[str, object]] = field(default_factory=list)
    port: int = 0

    def answer(self) -> tuple[int, bytes]:
        return self.script.pop(0) if self.script else (self.status, self.body)


@pytest.fixture(name="server")
def server_fixture() -> Iterator[StubServer]:
    stub = StubServer()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            stub.requests.append(
                {"path": self.path, "authorization": self.headers.get("Authorization"), "body": json.loads(raw)}
            )
            status, body = stub.answer()
            self.send_response(status)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True).start()
    stub.port = httpd.server_address[1]
    yield stub
    httpd.shutdown()
    httpd.server_close()


def name_server(monkeypatch: pytest.MonkeyPatch, *, port: int, key_dir: Path) -> None:
    """The environment a ``reaper-*.env`` file sets, naming a loopback port: its root with ``/v1``, a model, a key file.

    Naming a server contacts nothing, so a suite whose calls a fake answers
    names one on any port to pass the environment check a run makes first.
    """
    key_file = key_dir / "api-key.txt"
    key_file.write_text(f"\n  {TOKEN}  \n", encoding="utf-8")
    monkeypatch.setenv(liaison_tools.BASE_URL_ENV, f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv(liaison_tools.MODEL_ENV, SERVED_MODEL)
    monkeypatch.setenv(liaison_tools.KEY_FILE_ENV, str(key_file))


@pytest.fixture(name="served")
def served_fixture(server: StubServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StubServer:
    """The stub, named by the environment (:func:`name_server`)."""
    name_server(monkeypatch, port=server.port, key_dir=tmp_path)
    return server
