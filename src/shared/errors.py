"""Outcomes a service reports and the routes turn into HTTP responses —
services never import FastAPI."""


class NotFound(Exception):
    """No such campaign or version, or not one the caller may see. Callers
    can't tell those apart, by design."""


class Conflict(Exception):
    """The request clashes with the current state (e.g. publishing a version
    that is already public)."""


class Invalid(Exception):
    """The input was refused; `errors` lists every reason."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class Forbidden(Exception):
    """The caller is known but may not do this (e.g. a non-host ending a session)."""


class PaymentRequired(Exception):
    """The wallet doesn't hold enough credits."""


class Unavailable(Exception):
    """Something the request needs is down or not configured right now (e.g. no
    game server, the asset library); try again later."""
