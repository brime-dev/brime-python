"""Raw HTTP response wrappers for observability.

`Brime.with_raw_response.search(...)` returns an `APIResponse[SearchResponse]`
instead of the parsed model. Callers can read status, headers, request_id,
and only parse the model when they actually need it.

Mirrors openai-python's `_response.APIResponse` / `AsyncAPIResponse` design
without the codegen overhead — small, hand-rolled, identical ergonomics.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class APIResponse(Generic[T]):
    """Synchronous raw response wrapper.

    `parse()` returns the typed Pydantic model. `headers`, `status_code`,
    and `request_id` are populated even when the consumer never calls parse.
    """

    def __init__(
        self,
        raw: httpx.Response,
        parsed: Any,
        *,
        model_cls: type[T],
        retries_taken: int = 0,
    ) -> None:
        self._raw = raw
        self._parsed_data = parsed
        self._model_cls = model_cls
        self._cached: T | None = None
        self.retries_taken = retries_taken

    @property
    def status_code(self) -> int:
        return self._raw.status_code

    @property
    def headers(self) -> Mapping[str, str]:
        return self._raw.headers

    @property
    def request_id(self) -> str | None:
        value = self._raw.headers.get("x-request-id")
        return value if isinstance(value, str) else None

    @property
    def http_response(self) -> httpx.Response:
        """The underlying httpx.Response (advanced use)."""
        return self._raw

    def parse(self) -> T:
        """Validate and return the typed Pydantic model. Cached on first call."""
        if self._cached is None:
            self._cached = self._model_cls.model_validate(self._parsed_data)
        return self._cached

    def __repr__(self) -> str:
        return (
            f"APIResponse[{self._model_cls.__name__}]"
            f"(status={self.status_code}, request_id={self.request_id!r})"
        )


class AsyncAPIResponse(APIResponse[T]):
    """Async variant. Same shape — distinct class so type checkers can branch."""

    # The semantics are identical; the class exists so consumers using
    # `AsyncBrime.with_raw_response.search(...)` get a precise type instead
    # of a sync APIResponse leaking through.
