"""The receiving side of /internal/ calls between services (dev ADR 037,
043): every /internal/ route requires the shared service token.
The edge never routes /internal/ either — the token is the second lock, and
the one mTLS replaces later. The calling side is shared/internal_client.py."""
import hmac

from fastapi import Header, HTTPException, Request

SERVICE_TOKEN_HEADER = "X-Service-Token"


def internal_caller(request: Request, x_service_token: str | None = Header(default=None)) -> None:
    expected: str = request.app.state.shared.internal_token
    if not x_service_token or not hmac.compare_digest(x_service_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Internal endpoint")
