"""High-level Stream / AsyncStream wrappers around the raw SSE iterators.

Provides:
  - Context manager protocol so consumers can `with` / `async with` a stream
    and know the underlying HTTP response will be closed even on early exit
  - `request_id` accessor on the stream itself, so users can correlate logs
    without consuming any events
  - Same iteration protocol as the raw iterator (drop-in compatible) — every
    `for evt in stream:` loop that worked on v0.1 keeps working

The class wraps the lower-level `iter_sse_sync` / `iter_sse_async` generators
from `_sse.py`; those functions remain available for advanced callers that
want to drive parsing themselves.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from types import TracebackType
from typing import Generic, TypeVar

import httpx

from brime._sse import iter_sse_async, iter_sse_sync
from brime.models.research import ResearchSseEvent

T = TypeVar("T")


def _to_event(raw: dict[str, object]) -> ResearchSseEvent:
    """Normalise a raw SSE frame dict into a ResearchSseEvent model."""
    event = raw.get("event")
    data = raw.get("data")
    evt_id = raw.get("id")
    return ResearchSseEvent.model_validate(
        {
            "event": event if isinstance(event, str) else "message",
            "data": data,
            "id": evt_id if isinstance(evt_id, str) else None,
        }
    )


class Stream(Generic[T]):
    """Synchronous SSE stream wrapper.

    Iterating the stream yields `ResearchSseEvent` instances. Closing the
    stream releases the underlying httpx connection. Supports `with` syntax::

        with brime.research_stream(query="...") as stream:
            for evt in stream:
                if evt.event == "final":
                    print(evt.data)
                    break
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._closed = False

    @property
    def request_id(self) -> str | None:
        value = self._response.headers.get("x-request-id")
        return value if isinstance(value, str) else None

    @property
    def status_code(self) -> int:
        return self._response.status_code

    def __iter__(self) -> Iterator[ResearchSseEvent]:
        if self._closed:
            raise RuntimeError("Stream already closed")
        try:
            for raw in iter_sse_sync(self._response.iter_bytes()):
                yield _to_event(raw)
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._response.close()

    def __enter__(self) -> Stream[T]:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class AsyncStream(Generic[T]):
    """Asynchronous SSE stream wrapper. Same shape as `Stream`, async-aware."""

    def __init__(self, response: httpx.Response) -> None:
        self._response = response
        self._closed = False

    @property
    def request_id(self) -> str | None:
        value = self._response.headers.get("x-request-id")
        return value if isinstance(value, str) else None

    @property
    def status_code(self) -> int:
        return self._response.status_code

    async def __aiter__(self) -> AsyncIterator[ResearchSseEvent]:
        if self._closed:
            raise RuntimeError("Stream already closed")
        try:
            async for raw in iter_sse_async(self._response.aiter_bytes()):
                yield _to_event(raw)
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._response.aclose()

    async def __aenter__(self) -> AsyncStream[T]:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


__all__ = ["AsyncStream", "Stream"]
