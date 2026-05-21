"""Internal HTTP layer shared by sync and async clients.

Responsibilities:
    - Resolve api_key (arg → env BRIME_API_KEY)
    - Resolve base_url (arg → env BRIME_BASE_URL → https://api.brime.dev)
    - Build standard headers (Authorization, User-Agent, optional Idempotency-Key)
    - Decode JSON responses; raise structured BrimeError on non-2xx
    - Categorise transport-level failures into ConnectionError / TimeoutError
    - Retry policy primitives (exponential backoff with jitter)

The retry policy is enforced by the sync and async clients; this module only
exposes the building blocks (transient classification, sleep schedule, retry
budget tracking) so both implementations stay symmetric.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import random
import time
import uuid
from collections.abc import Mapping
from typing import Any, cast

import httpx

from brime._version import __version__
from brime.errors import (
    BrimeError,
    ConnectionError,
    RateLimitError,
    TimeoutError,
    exception_from_response,
)

DEFAULT_BASE_URL = "https://api.brime.dev"
DEFAULT_TIMEOUT_S = 30.0
DEEP_RESEARCH_TIMEOUT_S = 600.0
DEFAULT_MAX_RETRIES = 2

# Transient upstream statuses worth retrying. 429 is handled separately so
# the caller can surface `Retry-After` to the user without burning the retry
# budget on something that is rate-policy, not service-failure.
TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({500, 502, 503, 504})

USER_AGENT = (
    f"brime-python/{__version__} (httpx/{httpx.__version__}; "
    f"python/{platform.python_version()}; "
    f"{platform.system().lower()})"
)


def resolve_api_key(api_key: str | None) -> str:
    if api_key:
        return api_key
    env = os.environ.get("BRIME_API_KEY")
    if env:
        return env
    raise RuntimeError("Brime API key not set. Pass api_key=... or set BRIME_API_KEY env var.")


def resolve_base_url(base_url: str | None) -> str:
    if base_url:
        return base_url.rstrip("/")
    env = os.environ.get("BRIME_BASE_URL")
    if env:
        return env.rstrip("/")
    return DEFAULT_BASE_URL


def build_headers(
    api_key: str,
    *,
    json_body: bool = True,
    idempotency_key: str | None = None,
    accept: str | None = None,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {
        "authorization": f"Bearer {api_key}",
        "user-agent": USER_AGENT,
        "x-brime-client": f"brime-python/{__version__}",
        "accept": accept or "application/json",
    }
    if json_body:
        headers["content-type"] = "application/json"
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    if extra:
        for k, v in extra.items():
            headers[k.lower()] = v
    return headers


def new_idempotency_key() -> str:
    return str(uuid.uuid4())


def is_transient_status(status: int) -> bool:
    """True when the gateway returned a status that's worth retrying."""
    return status in TRANSIENT_STATUS_CODES


def retry_delay_seconds(attempt: int, *, base: float = 1.0, cap: float = 8.0) -> float:
    """Exponential backoff with jitter — 1s → 2s → 4s, jittered ± 250 ms.

    `attempt` is 1-indexed: the value returned is the delay BEFORE that
    attempt (so for the second retry overall — attempt=2 — we sleep ~2s).
    """
    raw = base * (2 ** (attempt - 1))
    delay = raw if raw < cap else cap
    jitter = random.uniform(0, 0.25)
    return float(delay + jitter)


def sleep_seconds(seconds: float) -> None:
    """Indirection so tests can monkey-patch sleep without freezing the event loop."""
    time.sleep(seconds)


def decode_response(res: httpx.Response, *, retries_taken: int = 0) -> Any:
    """Parse JSON; raise the appropriate BrimeError on non-2xx."""
    text = res.text
    body: Any = None
    if text:
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = None

    request_id_header = res.headers.get("x-request-id")

    if res.is_success:
        return body

    err_body: dict[str, Any] | None = None
    if isinstance(body, dict):
        err_body = cast("dict[str, Any]", body)

    exc = exception_from_response(res.status_code, err_body, request_id_header)
    exc.retries_taken = retries_taken
    if isinstance(exc, RateLimitError):
        retry_after_header = res.headers.get("retry-after")
        if retry_after_header:
            with contextlib.suppress(ValueError):
                exc.retry_after = int(retry_after_header)
    raise exc


def wrap_transport_error(exc: Exception, *, retries_taken: int = 0) -> BrimeError:
    """Convert httpx transport-level errors into the typed Brime hierarchy.

    Distinguishes:
        - `httpx.TimeoutException` (including ReadTimeout, ConnectTimeout, …)
          → `TimeoutError`
        - everything else (ConnectError, NetworkError, …) → `ConnectionError`
    """
    msg = str(exc) or type(exc).__name__
    if isinstance(exc, httpx.TimeoutException):
        return TimeoutError(
            f"request timed out: {msg}",
            status=0,
            code="timeout",
            retries_taken=retries_taken,
        )
    return ConnectionError(
        f"network error: {msg}",
        status=0,
        code="connection_error",
        retries_taken=retries_taken,
    )


# Convenience for places that surface the SDK version externally without
# pulling _version.py directly (kept for back-compat with older callers).
def get_version() -> str:
    return __version__


__all__ = [
    "DEEP_RESEARCH_TIMEOUT_S",
    "DEFAULT_BASE_URL",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT_S",
    "TRANSIENT_STATUS_CODES",
    "USER_AGENT",
    "build_headers",
    "decode_response",
    "is_transient_status",
    "new_idempotency_key",
    "resolve_api_key",
    "resolve_base_url",
    "retry_delay_seconds",
    "sleep_seconds",
    "wrap_transport_error",
]
