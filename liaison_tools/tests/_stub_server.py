"""A loopback HTTP server for one end-to-end test, torn down without waiting out a poll.

``serve_forever`` checks for shutdown every ``poll_interval`` seconds, 0.5 by
default, and ``shutdown()`` blocks until it does — so every test that stopped a
server at the default paid up to half a second in its cleanup.
"""

import http.server
import threading
import unittest

#: How often the serving thread looks for a shutdown request.
POLL_INTERVAL_SECONDS = 0.01


def serve_for_test(
    test: unittest.TestCase, handler: type[http.server.BaseHTTPRequestHandler]
) -> http.server.ThreadingHTTPServer:
    """``handler`` served on an ephemeral loopback port until ``test``'s cleanup shuts it down and closes it."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": POLL_INTERVAL_SECONDS}, daemon=True).start()
    test.addCleanup(server.server_close)
    test.addCleanup(server.shutdown)
    return server
