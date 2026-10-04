"""On-demand inference for any tooling that wants some: one tool-less chat call.

:mod:`liaison_tools` holds the whole of it — :func:`call_chat`, the
environment check every call runs (:func:`check_environment`), how a call ended
(:class:`Outcome`), and the one reader of the capture a call writes
(:func:`read_capture`). It knows nothing about a KB and parses nothing in the
reply, and it retries nothing: policy of every kind — retry, a re-ask, where a
bound's value comes from — is the caller's. It is tested against a loopback
stub server, so nothing here needs a reachable model.
"""

from .liaison_tools import (
    REQUEST_RECORD,
    CaptureStats,
    ChatEnvironment,
    Outcome,
    call_chat,
    check_environment,
    read_capture,
)

#: The logger tree this package writes to. It attaches no handler of its own —
#: an application wanting a call's lines in its own log attaches its handlers
#: here, and one that attaches none gets ``logging``'s default handling of a
#: warning.
LOGGER_NAME = __name__

__all__ = [
    "LOGGER_NAME",
    "REQUEST_RECORD",
    "CaptureStats",
    "ChatEnvironment",
    "Outcome",
    "call_chat",
    "check_environment",
    "read_capture",
]
