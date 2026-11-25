"""The calling side of /internal/ calls between services (dev ADR 037, 043):
hub-service to a game server or to a product's authoring-service,
authoring-service to hub-service. Attaches the shared service token to every request. The only
place on the calling side that knows the credential, so moving to mTLS
changes this class and shared/internal_auth.py, nothing else."""
import httpx2

from shared.internal_auth import SERVICE_TOKEN_HEADER


# A service that can't even be connected to is given up on quickly: placement
# moves on to the next game server (matchmaking/placement.py), and a caller
# waiting on another service fails fast instead of hanging.
CONNECT_TIMEOUT_SECONDS = 3


class InternalClient:
    def __init__(self, token: str, timeout_seconds: float = 10,
                 transport: httpx2.AsyncBaseTransport | None = None) -> None:
        self._headers = {SERVICE_TOKEN_HEADER: token}
        self._timeout = httpx2.Timeout(timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS)
        # Injected in tests to stand in for the service called.
        self._transport = transport

    async def post(self, url: str, body: dict) -> httpx2.Response:
        async with self._client() as client:
            return await client.post(url, json=body)

    async def get(self, url: str) -> httpx2.Response:
        async with self._client() as client:
            return await client.get(url)

    def _client(self) -> httpx2.AsyncClient:
        return httpx2.AsyncClient(headers=self._headers, timeout=self._timeout, transport=self._transport)
