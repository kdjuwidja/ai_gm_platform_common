"""Request dependencies shared by every route: the caller's identity from
the Authorization header, their roles, and the mapping from service outcomes
to HTTP responses.

The caller's record comes from `app.state.shared.callers`, which each service
sets: hub-service's Users interface, or authoring-service's client for
hub-service's /internal/users/ (dev ADR 043). Either answers `touch(sub)`
with the record's `roles` and `profile`."""
from contextlib import contextmanager

from fastapi import Depends, Header, HTTPException, Request

from shared.auth import AuthError, TokenVerifier
from shared.errors import Conflict, Forbidden, Invalid, NotFound, PaymentRequired, Unavailable
from shared.roles import ROLE_ADMIN, ROLE_CREATOR, display_name


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Authorization must be a Bearer token")
    return token


def _verify(request: Request, token: str) -> str:
    verifier: TokenVerifier = request.app.state.shared.verifier
    try:
        return verifier.verify(token)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


def optional_user(request: Request, authorization: str | None = Header(default=None)) -> str | None:
    """The caller's sub, or None when no token was sent. A token that is sent
    but invalid is a 401, not an anonymous request."""
    token = _bearer(authorization)
    return _verify(request, token) if token else None


def required_user(request: Request, authorization: str | None = Header(default=None)) -> str:
    token = _bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in required")
    return _verify(request, token)


class Caller:
    """A signed-in caller and their app roles."""

    def __init__(self, sub: str, user: dict) -> None:
        self.sub = sub
        self.roles = set(user.get("roles", []))
        self.display_name = display_name(user)

    @property
    def is_admin(self) -> bool:
        return ROLE_ADMIN in self.roles


async def caller(request: Request, sub: str = Depends(required_user)) -> Caller:
    try:
        return Caller(sub, await request.app.state.shared.callers.touch(sub))
    except Unavailable as e:
        # authoring-service couldn't reach hub-service for the record: no roles
        # known, so nothing signed in is let through.
        raise HTTPException(status_code=503, detail=str(e)) from e


async def creator(who: Caller = Depends(caller)) -> Caller:
    if ROLE_CREATOR not in who.roles:
        raise HTTPException(status_code=403, detail="This needs the creator role.")
    return who


async def admin(who: Caller = Depends(caller)) -> Caller:
    if not who.is_admin:
        raise HTTPException(status_code=403, detail="This needs the admin role.")
    return who


async def credited_creator(who: Caller = Depends(creator)) -> Caller:
    """A creator with a profile — its display name is what their campaigns are credited to."""
    if not who.display_name:
        raise HTTPException(status_code=409, detail="Create your profile first — its name is shown as the campaign's author.")
    return who


@contextmanager
def service_errors():
    """Turns a service's outcomes into HTTP: NotFound 404, Forbidden 403,
    Conflict 409, Invalid 422, PaymentRequired 402, Unavailable 503."""
    try:
        yield
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Forbidden as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except PaymentRequired as e:
        raise HTTPException(status_code=402, detail=str(e)) from e
    except Unavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Conflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Invalid as e:
        raise HTTPException(status_code=422, detail={"errors": e.errors}) from e
