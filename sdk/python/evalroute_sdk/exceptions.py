"""SDK exceptions."""

from __future__ import annotations


class EvalRouteError(Exception):
    """Base exception for SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthException(EvalRouteError):
    """Raised when auth fails."""


class RateLimitException(EvalRouteError):
    """Raised when request is rate limited."""
