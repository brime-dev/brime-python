"""Internal HTTP layer shared by sync and async clients.

Responsibilities:
    - Resolve api_key (arg → env BRIME_API_KEY)
    - Resolve base_url (arg → env BRIME_BASE_URL → https://api.brime.dev)
    - Build standard headers (Authorization, User-Agent, optional Idempotency-Key)
    - Decode error responses into Brime exceptions
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, Mapping, Optional

import httpx

from brime._version import __version__
from brime.errors import BrimeError, exception_from_response

DEFAULT_BASE_URL = "https://api.brime.dev"
DEFAULT_TIMEOUT_S = 30.0
DEEP_RESEARCH_TIMEOUT_S = 600.0
USER_AGENT = f"brime-python/{__version__}"


def resolve_api_key(api_key: Optional[str]) -> str:
    if api_key:
        return api_key
    env = os.environ.get("BRIME_API_KEY")
    if env:
        return env
    raise RuntimeError(
        "Brime API key not set. Pass api_key=... or set BRIME_API_KEY env var."
    )


def resolve_base_url(base_url: Optional[str]) -> str:
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
    idempotency_key: Optional[str] = None,
    accept: Optional[str] = None,
    extra: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    headers: Dict[str, str] = {
        "authorization": f"Bearer {api_key}",
        "user-agent": USER_AGENT,
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


def decode_response(res: httpx.Response) -> Any:
    """Parse JSON or raise the appropriate BrimeError on non-2xx."""
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

    err_body = body if isinstance(body, dict) else None
    raise exception_from_response(res.status_code, err_body, request_id_header)


def wrap_transport_error(exc: Exception) -> BrimeError:
    """Convert httpx transport-level errors to a BrimeError shape."""
    return exception_from_response(
        0,
        {"error": {"code": "internal_error", "message": f"network error: {exc!s}"}},
    )
