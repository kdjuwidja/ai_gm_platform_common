"""Both ends of the service token on /internal/: the caller attaches it to
every request, and the receiver lets through only a request carrying it."""
import asyncio
import json

import httpx2
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from shared.internal_auth import SERVICE_TOKEN_HEADER, internal_caller
from shared.internal_client import InternalClient

TOKEN = "internal-test-token"


def receiver() -> FastAPI:
    app = FastAPI()
    app.state.shared = type("Shared", (), {})()
    app.state.shared.internal_token = TOKEN

    @app.post("/internal/ping", dependencies=[Depends(internal_caller)])
    def ping():
        return {"ok": True}

    return app


def test_the_receiver_needs_the_token():
    with TestClient(receiver()) as client:
        assert client.post("/internal/ping").status_code == 401
        assert client.post("/internal/ping", headers={SERVICE_TOKEN_HEADER: "wrong"}).status_code == 401
        assert client.post("/internal/ping", headers={SERVICE_TOKEN_HEADER: TOKEN}).json() == {"ok": True}


def test_the_caller_attaches_the_token_to_every_request():
    seen = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        seen.append((request.method, str(request.url), request.headers.get(SERVICE_TOKEN_HEADER),
                     request.content or None))
        return httpx2.Response(200, json={"ok": True})

    client = InternalClient(TOKEN, transport=httpx2.MockTransport(handle))

    async def calls():
        await client.get("http://hub-service:8000/internal/a")
        await client.post("http://hub-service:8000/internal/b", {"x": 1})

    asyncio.run(calls())
    assert [(m, u, t) for m, u, t, _ in seen] == [
        ("GET", "http://hub-service:8000/internal/a", TOKEN),
        ("POST", "http://hub-service:8000/internal/b", TOKEN),
    ]
    assert json.loads(seen[1][3]) == {"x": 1}
