"""Exception types for the Township America SDK."""

from __future__ import annotations

from typing import Optional


class TownshipAmericaError(Exception):
    """Base exception for all Township America SDK errors.

    ``code`` carries the machine-readable error code the Energy, Federal
    Land, and Texas APIs return in v1 error bodies
    (``{"error": {"code", "message"}}``), e.g. ``invalid_parameter``,
    ``plss_not_supported``, ``ambiguous_location``, ``not_found``,
    ``rate_limit_exceeded``. It is ``None`` for endpoints that do not
    send one.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class AuthenticationError(TownshipAmericaError):
    """Raised when the API key is missing or invalid (HTTP 401)."""


class NotFoundError(TownshipAmericaError):
    """Raised when no results are found (HTTP 404)."""


class ValidationError(TownshipAmericaError):
    """Raised when the request is invalid (HTTP 400)."""


class RateLimitError(TownshipAmericaError):
    """Raised when the rate limit is exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = 429,
        retry_after: Optional[float] = None,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, code=code)
        self.retry_after = retry_after


class PayloadTooLargeError(TownshipAmericaError):
    """Raised when the batch payload exceeds 100 items (HTTP 413)."""


class ServerError(TownshipAmericaError):
    """Raised on server-side errors (HTTP 5xx)."""
