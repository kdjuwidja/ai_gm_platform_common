"""Verifies an OAuth access token (HS256 JWT, dev ADR 011) for every
service — a game server's LOGIN_REQ, hub-service's and authoring-service's
signed-in requests: signature with JWT_SECRET, then every required scope
present. Returns the token's `sub`, the player's user_id. The messages are
the library's; a caller that shows one to a player maps it to its own words
(game-service's handlers/ws_handler.py)."""
import jwt


class AuthError(Exception):
    """The token is missing, invalid, expired, or lacks a required scope."""


class InsufficientScope(AuthError):
    """A valid token that lacks a scope ai_gm requires."""


class TokenVerifier:
    def __init__(self, secret: str, required_scopes: tuple[str, ...]) -> None:
        self._secret = secret
        self._required_scopes = required_scopes

    def verify(self, token: str) -> str:
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"])
        except jwt.PyJWTError as e:
            raise AuthError(str(e)) from e
        granted = set(str(claims.get("scope", "")).split())
        missing = [s for s in self._required_scopes if s not in granted]
        if missing:
            raise InsufficientScope(f"Missing required scope(s): {', '.join(missing)}")
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise AuthError("Token has no subject")
        return sub
