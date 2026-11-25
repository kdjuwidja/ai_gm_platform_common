"""An access token is accepted only when it is signed with the secret, every
required scope is granted, and it names its player."""
import time

import jwt
import pytest

from shared.auth import AuthError, InsufficientScope, TokenVerifier

SECRET = "shared-test-secret-at-least-32-bytes-long"
VERIFIER = TokenVerifier(SECRET, ("read", "write"))


def token(secret: str = SECRET, **claims) -> str:
    body = {"sub": "alice", "scope": "read write", "exp": int(time.time()) + 600} | claims
    return jwt.encode({k: v for k, v in body.items() if v is not None}, secret, algorithm="HS256")


def test_a_good_token_gives_its_subject():
    assert VERIFIER.verify(token()) == "alice"


def test_extra_scopes_are_fine():
    assert VERIFIER.verify(token(scope="read write profile")) == "alice"


def test_another_secret_is_refused():
    with pytest.raises(AuthError):
        VERIFIER.verify(token(secret="another-secret-at-least-32-bytes-long!"))


def test_an_expired_token_is_refused():
    with pytest.raises(AuthError):
        VERIFIER.verify(token(exp=int(time.time()) - 10))


def test_a_missing_scope_is_named():
    with pytest.raises(InsufficientScope, match="write"):
        VERIFIER.verify(token(scope="read"))


@pytest.mark.parametrize("sub", [None, ""])
def test_a_token_without_a_subject_is_refused(sub):
    with pytest.raises(AuthError, match="subject"):
        VERIFIER.verify(token(sub=sub))


def test_garbage_is_refused():
    with pytest.raises(AuthError):
        VERIFIER.verify("not-a-token")
