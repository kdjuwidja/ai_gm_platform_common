"""The access log leaves out the requests that repeat all day — a game
server's heartbeat and the waiting room's poll — only when they succeed."""
import logging

import pytest

from shared.access_log import QuietRepeatedRequests


def access(method: str, path: str, status: int) -> logging.LogRecord:
    return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                             ("10.0.0.1:5000", method, path, "1.1", status), None)


@pytest.mark.parametrize("method, path, status, logged", [
    ("POST", "/internal/game-servers/game-1/heartbeat", 204, False),
    ("GET", "/hub/sessions/0fb16f7f", 200, False),
    ("GET", "/hub/sessions/0fb16f7f?x=1", 200, False),
    ("POST", "/internal/game-servers/game-1/heartbeat", 401, True),    # a failure is always logged
    ("GET", "/hub/sessions/0fb16f7f", 404, True),
    ("GET", "/hub/sessions", 200, True),                               # "Your games"
    ("POST", "/hub/sessions/join", 200, True),
    ("GET", "/hub/sessions/0fb16f7f/connect", 200, True),
    ("POST", "/internal/sessions/s1/reports", 200, True),
])
def test_only_successful_repeats_are_left_out(method, path, status, logged):
    assert QuietRepeatedRequests().filter(access(method, path, status)) is logged
