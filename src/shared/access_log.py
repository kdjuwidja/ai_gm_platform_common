"""Keeps uvicorn's access log readable: the two requests that repeat all day
— each game server's heartbeat (every few seconds) and the waiting room's
poll (every 2 s per player in a lobby) — aren't logged when they succeed.
Every other request is, and so is either of those when it fails."""
import logging
import re

_QUIET = (
    ("POST", re.compile(r"^/internal/game-servers/[^/]+/heartbeat$")),
    ("GET", re.compile(r"^/hub/sessions/[^/]+$")),
)


class QuietRepeatedRequests(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # uvicorn's access record: (client, method, path, http version, status).
        try:
            _, method, path, _, status = record.args
        except (TypeError, ValueError):
            return True
        if int(status) >= 400:
            return True
        path = path.split("?", 1)[0]
        return not any(method == m and pattern.match(path) for m, pattern in _QUIET)


def install() -> None:
    logging.getLogger("uvicorn.access").addFilter(QuietRepeatedRequests())
