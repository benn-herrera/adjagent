"""The importable chat-completions request (``liaison_tools/openai_chat.py``), past what ``test_post_openai`` covers.

That suite drives the shared demux, reassembly and URL rules through the
command; this one covers what an in-process caller reaches that the command
does not: the reply classification, the content-only reassembly, and the
request's optional fields. Stdlib-only; never touches the network beyond
127.0.0.1.
"""

import contextlib
import http.server
import io
import json
import unittest

from liaison_tools import openai_chat
from liaison_tools.tests._stub_server import serve_for_test

_TEXT_BODY = (
    b'data: {"choices":[{"delta":{"content":"A"},"index":0}]}\n\n'
    b'data: {"choices":[{"delta":{},"index":0,"finish_reason":"stop"}]}\n\n'
    b"data: [DONE]\n\n"
)


class TestClassifyReply(unittest.TestCase):
    def test_table(self):
        cases = [
            ("A", "stop", openai_chat.Reply.COMPLETE),
            ("A", None, openai_chat.Reply.COMPLETE),
            ("A", "tool_calls", openai_chat.Reply.COMPLETE),
            ("", "stop", openai_chat.Reply.EMPTY),
            ("", None, openai_chat.Reply.EMPTY),
            ("The answer is", "length", openai_chat.Reply.INCOMPLETE),
            ("", "length", openai_chat.Reply.INCOMPLETE),
        ]
        for text, reason, expected in cases:
            with self.subTest(text=text, reason=reason):
                self.assertIs(openai_chat.classify_reply(text, reason), expected)


class TestReassembleContent(unittest.TestCase):
    def test_content_survives_a_tool_call_beside_it(self):
        call = {"index": 0, "id": "c1", "function": {"name": "Read", "arguments": "{}"}}
        chunks = [
            {"choices": [{"delta": {"content": "B"}}]},
            {"choices": [{"delta": {"tool_calls": [call]}}]},
            {"choices": [], "usage": {"prompt_tokens": 3}},
        ]
        self.assertEqual(openai_chat.reassemble_content(chunks), "B")
        self.assertTrue(openai_chat.reassemble_stream(chunks).startswith("TOOL_CALLS\n"))


class TestRequestFields(unittest.TestCase):
    """What the request carries, as the endpoint receives it."""

    def setUp(self):
        self.received = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(_TEXT_BODY)

            def log_message(self, *args):
                pass

        self.base = f"http://127.0.0.1:{serve_for_test(self, Handler).server_address[1]}"

    def _post(self, **overrides):
        arguments = {
            "model": "m",
            "base_url": self.base,
            "token": "t",
            "messages": [{"role": "user", "content": "hi"}],
            "enable_thinking": False,
            "temperature": 0.0,
        }
        arguments.update(overrides)
        with contextlib.redirect_stderr(io.StringIO()):
            return openai_chat.post_chat_streaming(**arguments)

    def test_usage_is_asked_for_only_when_the_caller_asks(self):
        self._post()
        self._post(include_usage=True)
        self.assertNotIn("stream_options", self.received[0])
        self.assertEqual(self.received[1]["stream_options"], {"include_usage": True})

    def test_no_tools_are_offered_and_thinking_is_as_asked(self):
        chunks, _, _, status = self._post()
        self.assertEqual(status, openai_chat.STREAM_CLEAN)
        self.assertEqual(openai_chat.reassemble_stream(chunks), "A")
        self.assertNotIn("tools", self.received[0])
        self.assertEqual(self.received[0]["chat_template_kwargs"], {"enable_thinking": False})


class TestPostEmbeddings(unittest.TestCase):
    """One embeddings batch against a stubbed endpoint that answers out of index order."""

    def setUp(self):
        self.received = []
        self.reply = {}
        received, test = self.received, self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path, json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))))
                body = json.dumps(test.reply).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.base = f"http://127.0.0.1:{serve_for_test(self, Handler).server_address[1]}/v1"

    def _embed(self, texts):
        return openai_chat.post_embeddings(base_url=self.base, token="t", model="m", texts=texts)

    def test_vectors_come_back_in_input_order(self):
        self.reply = {"data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}]}
        self.assertEqual(self._embed(["a", "b"]), [[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(self.received, [("/v1/embeddings", {"model": "m", "input": ["a", "b"]})])

    def test_a_short_reply_is_refused(self):
        self.reply = {"data": [{"index": 0, "embedding": [1.0]}]}
        with self.assertRaises(ValueError):
            self._embed(["a", "b"])


if __name__ == "__main__":
    unittest.main()
