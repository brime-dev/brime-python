"""Live e2e gates against a real Brime backend.

Requires env vars:
    BRIME_API_KEY  — a valid sk-brime-... key
    BRIME_BASE_URL — preview or production endpoint

Skipped if BRIME_API_KEY is not set. Run via::

    BRIME_API_KEY=sk-brime-... BRIME_BASE_URL=https://... \
        pytest tests/e2e -v -m live
"""

from __future__ import annotations

import os

import pytest

from brime import (
    AuthenticationError,
    Brime,
    ExtractResponse,
    InvalidRequestError,
    ResearchBasicResponse,
    ResearchSseEvent,
    ResearchStatusResponse,
    SearchResponse,
)

pytestmark = pytest.mark.live


needs_key = pytest.mark.skipif(
    not os.environ.get("BRIME_API_KEY"),
    reason="BRIME_API_KEY not set",
)


@needs_key
def test_g2_search_instant() -> None:
    res = Brime().search("BM25 ranking algorithm", depth="instant", max_results=5)
    assert isinstance(res, SearchResponse)
    assert res.results, "expected non-empty results"
    print(f"\n  G2 instant: {len(res.results)} results, latency={res.latency_ms}ms")


@needs_key
def test_g2_search_basic() -> None:
    res = Brime().search("python async io patterns", depth="basic", max_results=5)
    assert isinstance(res, SearchResponse)
    print(
        f"  G2 basic: {len(res.results)} results, answer_len={len(res.answer or '')}, lat={res.latency_ms}ms"
    )


@needs_key
def test_g3_extract() -> None:
    res = Brime().extract("https://example.com")
    assert isinstance(res, ExtractResponse)
    assert len(res.results) == 1
    r0 = res.results[0]
    assert r0.markdown
    assert r0.method
    print(f"  G3 extract: method={r0.method} ct={r0.content_type} md_len={len(r0.markdown)}")


@needs_key
def test_g4_research_basic() -> None:
    res = Brime(timeout=120.0).research("what is BM25", depth="basic", max_rounds=1)
    assert isinstance(res, ResearchBasicResponse)
    assert res.answer
    print(
        f"  G4 basic: answer_len={len(res.answer)}, sources={len(res.sources)}, lat={res.latency_ms}ms"
    )


@needs_key
def test_g5_research_deep_wait() -> None:
    res = Brime(timeout=60.0).research(
        "what is the okapi bm25 formula",
        depth="deep",
        max_rounds=2,
        wait=True,
        poll_interval=8.0,
        max_poll_interval=20.0,
        poll_timeout=420.0,
    )
    assert isinstance(res, ResearchStatusResponse)
    assert res.status in ("complete", "errored", "timeout")
    print(
        f"  G5 deep wait: status={res.status} answer_len={len(res.answer or '')} "
        f"sources={res.sources_count} steps={res.steps_count}"
    )
    assert res.status == "complete"


@needs_key
def test_g6_research_deep_stream() -> None:
    client = Brime(timeout=60.0)
    saw_events: list[str] = []
    terminal = False
    for evt in client.research_stream("what is BM25 ranking", depth="deep", max_rounds=2):
        assert isinstance(evt, ResearchSseEvent)
        saw_events.append(evt.event)
        if evt.event in ("complete", "error", "timeout"):
            terminal = True
            break
    print(f"  G6 deep stream: events={saw_events[:8]}... total={len(saw_events)}")
    assert terminal, f"no terminal event in {saw_events}"


@needs_key
def test_g7_error_bad_key() -> None:
    bad = Brime(api_key="sk-brime-totally-fake-key")
    with pytest.raises(AuthenticationError) as exc:
        bad.search("x")
    assert exc.value.status == 401
    assert exc.value.code == "unauthorized"
    print(f"  G7 bad key: {exc.value.code} status={exc.value.status}")


@needs_key
def test_g7_error_empty_query() -> None:
    with pytest.raises(InvalidRequestError) as exc:
        Brime().search("")
    assert 400 <= exc.value.status < 500
    print(f"  G7 empty query: {exc.value.code} status={exc.value.status}")


@needs_key
def test_g7_async_smoke() -> None:
    """Async surface symmetry: same response shape as the sync client."""
    import asyncio

    from brime import AsyncBrime

    async def _go() -> SearchResponse:
        async with AsyncBrime() as client:
            return await client.search("python async", depth="instant", max_results=3)

    res = asyncio.run(_go())
    assert isinstance(res, SearchResponse)
    print(f"  G7 async: {len(res.results)} results")
