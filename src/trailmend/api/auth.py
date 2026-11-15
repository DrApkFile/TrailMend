import secrets

from trailmend.api.state import Live
from trailmend.errors import ErrorCode, TrailMendError


def require_admin(live: Live, token: str | None) -> None:
    expected = live.settings.admin_token.get_secret_value()
    if not token or not secrets.compare_digest(token, expected):
        raise TrailMendError(ErrorCode.INVALID_REQUEST, "this endpoint needs a valid admin token")
