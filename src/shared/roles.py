"""The app roles a player can hold, and the display name on their record —
one definition for every service (dev ADR 043). hub-service's Users module
writes them (ai_gm_users.users); each product's authoring-service reads them
through hub-service's /internal/users/ routes."""

ROLE_CREATOR = "creator"
ROLE_ADMIN = "admin"


def display_name(doc: dict | None) -> str | None:
    """A player's display name, from their profile — None until they create it."""
    return ((doc or {}).get("profile") or {}).get("display_name")
