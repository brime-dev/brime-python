"""Stream / AsyncStream wrapper tests — context manager + iteration + close."""

from __future__ import annotations

import httpx
import pytest
import respx

from brime import AsyncBrime, AsyncStream, Brime, ResearchSseEvent, Stream

SSE_BODY = (
    b'event: intent\ndata: {"query": "x"}\n\n'
    b'event: tool_call\ndata: {"round": 1, "queries": ["x"]}\n\n'
    b'event: final\ndata: {"answer": "done"}\n\n'
)


def _sse_response() -> httpx.Response:
    return httpx.Response(
        200,
        headers={
            "content-type": "text/event-stream",
            "x-request-id": "req_stream_test",
        },
        content=SSE_BODY,
    )


@respx.mock
def test_stream_iteration_yields_events_and_carries_request_id() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(return_value=_sse_response())
    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        with client.research_stream(query="test", depth="basic") as stream:
            assert isinstance(stream, Stream)
            assert stream.request_id == "req_stream_test"
            events = list(stream)
    finally:
        client.close()
    assert [e.event for e in events] == ["intent", "tool_call", "final"]
    assert all(isinstance(e, ResearchSseEvent) for e in events)


@respx.mock
def test_stream_close_idempotent() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(return_value=_sse_response())
    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        stream = client.research_stream(query="test", depth="basic")
        stream.close()
        stream.close()  # second close must be a no-op (not raise)
    finally:
        client.close()


@respx.mock
def test_stream_works_without_context_manager() -> None:
    """Old v0.1.x usage — `for evt in client.research_stream(...)` — must still work."""
    respx.post("https://api.brime.dev/v1/research").mock(return_value=_sse_response())
    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        events = list(client.research_stream(query="t", depth="basic"))
    finally:
        client.close()
    assert len(events) == 3


@respx.mock
def test_stream_raises_on_non_2xx_with_typed_error() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"code": "unauthorized", "message": "bad key"}},
        )
    )
    from brime import AuthenticationError

    client = Brime(api_key="sk-brime-test-key-32characters")
    try:
        with pytest.raises(AuthenticationError):
            client.research_stream(query="t", depth="basic")
    finally:
        client.close()


# ── Async parity ───────────────────────────────────────────────────────────


@respx.mock
async def test_async_stream_iteration() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(return_value=_sse_response())
    client = AsyncBrime(api_key="sk-brime-test-key-32characters")
    try:
        stream = await client.research_stream(query="t", depth="basic")
        assert isinstance(stream, AsyncStream)
        assert stream.request_id == "req_stream_test"
        events = [e async for e in stream]
    finally:
        await client.aclose()
    assert [e.event for e in events] == ["intent", "tool_call", "final"]


@respx.mock
async def test_async_stream_with_context_manager() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(return_value=_sse_response())
    client = AsyncBrime(api_key="sk-brime-test-key-32characters")
    try:
        async with await client.research_stream(query="t", depth="basic") as stream:
            events = [e async for e in stream]
    finally:
        await client.aclose()
    assert len(events) == 3
