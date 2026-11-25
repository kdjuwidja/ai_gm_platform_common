"""The request dependencies every service's routes use: who is calling, what
roles they hold, and how a service's outcomes become HTTP responses."""
import time

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared import deps
from shared.auth import TokenVerifier
from shared.errors import Conflict, Forbidden, Invalid, NotFound, PaymentRequired, Unavailable
from shared.roles import ROLE_ADMIN, ROLE_CREATOR, display_name

SECRET = "shared-test-secret-at-least-32-bytes-long"


class FakeCallers:
    """Stands in for `app.state.shared.callers`: hub-service's Users, or
    authoring-service's client for it."""

    def __init__(self, records: dict[str, dict], down: bool = False) -> None:
        self.records = records
        self.down = down
        self.touched: list[str] = []

    async def touch(self, sub: str) -> dict:
        if self.down:
            raise Unavailable("hub-service is down")
        self.touched.append(sub)
        return self.records.get(sub, {"roles": [], "profile": None})


def bearer(sub: str) -> dict:
    claims = {"sub": sub, "scope": "read write", "exp": int(time.time()) + 600}
    return {"Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}"}


def make_app(callers: FakeCallers) -> FastAPI:
    app = FastAPI()
    app.state.shared = type("Shared", (), {})()
    app.state.shared.verifier = TokenVerifier(SECRET, ("read", "write"))
    app.state.shared.callers = callers

    @app.get("/optional")
    def optional(sub: str | None = Depends(deps.optional_user)):
        return {"sub": sub}

    @app.get("/caller")
    def who(c: deps.Caller = Depends(deps.caller)):
        return {"sub": c.sub, "roles": sorted(c.roles), "name": c.display_name, "admin": c.is_admin}

    @app.get("/creator")
    def creator(c: deps.Caller = Depends(deps.creator)):
        return {"sub": c.sub}

    @app.get("/admin")
    def admin(c: deps.Caller = Depends(deps.admin)):
        return {"sub": c.sub}

    @app.get("/credited")
    def credited(c: deps.Caller = Depends(deps.credited_creator)):
        return {"sub": c.sub}

    @app.get("/raise/{kind}")
    def raises(kind: str):
        errors = {"notfound": NotFound("gone"), "forbidden": Forbidden("no"), "conflict": Conflict("clash"),
                  "payment": PaymentRequired("broke"), "unavailable": Unavailable("down"),
                  "invalid": Invalid(["one", "two"])}
        with deps.service_errors():
            raise errors[kind]

    return app


RECORDS = {
    "alice": {"roles": [ROLE_CREATOR], "profile": {"display_name": "Alice"}},
    "bob": {"roles": [ROLE_CREATOR], "profile": None},
    "root": {"roles": [ROLE_ADMIN], "profile": {"display_name": "Root"}},
}


@pytest.fixture
def client():
    callers = FakeCallers(RECORDS)
    with TestClient(make_app(callers)) as c:
        c.callers = callers
        yield c


def test_no_token_is_anonymous_where_that_is_allowed(client):
    assert client.get("/optional").json() == {"sub": None}
    assert client.get("/optional", headers=bearer("alice")).json() == {"sub": "alice"}


def test_a_bad_token_is_401_even_where_anonymous_is_allowed(client):
    assert client.get("/optional", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/optional", headers={"Authorization": "Basic abc"}).status_code == 401


def test_signing_in_is_required_for_a_caller(client):
    assert client.get("/caller").status_code == 401


def test_the_caller_is_touched_and_carries_their_roles(client):
    res = client.get("/caller", headers=bearer("alice"))
    assert res.json() == {"sub": "alice", "roles": [ROLE_CREATOR], "name": "Alice", "admin": False}
    assert client.callers.touched == ["alice"]


def test_roles_are_checked(client):
    assert client.get("/creator", headers=bearer("alice")).status_code == 200
    assert client.get("/creator", headers=bearer("root")).status_code == 403
    assert client.get("/admin", headers=bearer("root")).status_code == 200
    assert client.get("/admin", headers=bearer("alice")).status_code == 403


def test_a_credited_creator_needs_a_profile(client):
    assert client.get("/credited", headers=bearer("alice")).status_code == 200
    assert client.get("/credited", headers=bearer("bob")).status_code == 409


def test_no_record_means_nothing_signed_in_gets_through():
    with TestClient(make_app(FakeCallers(RECORDS, down=True))) as c:
        assert c.get("/caller", headers=bearer("alice")).status_code == 503


@pytest.mark.parametrize("kind, status", [("notfound", 404), ("forbidden", 403), ("conflict", 409),
                                          ("payment", 402), ("unavailable", 503), ("invalid", 422)])
def test_service_outcomes_become_http(client, kind, status):
    assert client.get(f"/raise/{kind}").status_code == status


def test_invalid_lists_every_reason(client):
    assert client.get("/raise/invalid").json() == {"detail": {"errors": ["one", "two"]}}


@pytest.mark.parametrize("doc, name", [(None, None), ({}, None), ({"profile": None}, None),
                                       ({"profile": {"display_name": "Alice"}}, "Alice")])
def test_display_name(doc, name):
    assert display_name(doc) == name
