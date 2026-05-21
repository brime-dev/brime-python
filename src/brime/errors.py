"""Brime API error hierarchy.

Brime native errors come back as::

    {"error": {"code": "<code>", "message": "<msg>", "details": ...}}

This module maps `code` → exception class and provides friendly defaults.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Type


class BrimeError(Exception):
    """Base class for all Brime API errors."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str,
        details: Optional[Any] = None,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.details = details
        self.request_id = request_id

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status={self.status}, code={self.code!r}, "
            f"message={str(self)!r})"
        )


class AuthenticationError(BrimeError):
    """401 — invalid or missing API key."""


class RateLimitError(BrimeError):
    """429 — rate limit exceeded."""


class InsufficientCreditsError(BrimeError):
    """402 — account out of credits."""


class InvalidRequestError(BrimeError):
    """400/422 — malformed request body."""


class NotFoundError(BrimeError):
    """404 — resource (job_id, etc.) not found."""


class UpstreamError(BrimeError):
    """502/503/504 — Brime upstream (SERP, LLM, extract worker) failure."""


class InternalError(BrimeError):
    """500 — unexpected Brime engine error."""


_CODE_TO_CLASS: Dict[str, Type[BrimeError]] = {
    "unauthorized": AuthenticationError,
    "rate_limited": RateLimitError,
    "insufficient_credits": InsufficientCreditsError,
    "invalid_request": InvalidRequestError,
    "not_found": NotFoundError,
    "upstream_error": UpstreamError,
    "internal_error": InternalError,
}


_FRIENDLY: Dict[str, str] = {
    "unauthorized": "Invalid Brime API key. Check api_key argument or BRIME_API_KEY env var.",
    "rate_limited": "Brime rate limit hit. Wait a moment and retry.",
    "insufficient_credits": "Brime account is out of credits for this period.",
    "invalid_request": "The request was invalid.",
    "not_found": "Resource not found.",
    "upstream_error": "Brime upstream service error. Try again shortly.",
    "internal_error": "Brime internal error. Try again shortly.",
}


def exception_from_response(
    status: int,
    body: Optional[Dict[str, Any]],
    request_id: Optional[str] = None,
) -> BrimeError:
    """Build the appropriate BrimeError subclass from an error response body."""
    err = (body or {}).get("error") or {}
    code = err.get("code")
    message = err.get("message")
    details = err.get("details")

    if not isinstance(code, str) or not code:
        # Fall back by status when payload is not Brime-shaped.
        if status == 401:
            code = "unauthorized"
        elif status == 402:
            code = "insufficient_credits"
        elif status == 404:
            code = "not_found"
        elif status == 429:
            code = "rate_limited"
        elif status in (502, 503, 504):
            code = "upstream_error"
        elif 400 <= status < 500:
            code = "invalid_request"
        else:
            code = "internal_error"

    if not isinstance(message, str) or not message:
        message = _FRIENDLY.get(code, f"Brime API error (HTTP {status})")

    cls = _CODE_TO_CLASS.get(code, InternalError)
    return cls(
        message,
        status=status,
        code=code,
        details=details,
        request_id=request_id,
    )
