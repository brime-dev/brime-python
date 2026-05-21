from __future__ import annotations

import httpx
import respx

from brime import (
    Brime,
    ResearchBasicResponse,
    ResearchDeepInitResponse,
    ResearchStatusResponse,
)


@respx.mock
def test_research_basic_returns_basic_response() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": "q",
                "answer": "a",
                "sources": [{"title": "t", "url": "https://x", "content": "c", "score": 0.5}],
                "request_id": "r",
                "credits_used": 2,
                "latency_ms": 1000,
            },
        )
    )
    res = Brime(api_key="sk-test").research("q", depth="basic")
    assert isinstance(res, ResearchBasicResponse)
    assert res.answer == "a"
    assert len(res.sources) == 1


@respx.mock
def test_research_deep_init_returns_init_response() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(
        return_value=httpx.Response(
            202,
            json={
                "job_id": "rsh_abc",
                "status": "queued",
                "status_url": "/v1/research/rsh_abc",
                "stream_url": "/v1/research/rsh_abc/stream",
                "request_id": "r",
                "credits_used": 5,
                "started_at": "2026-05-06T00:00:00Z",
            },
        )
    )
    res = Brime(api_key="sk-test").research("q", depth="deep")
    assert isinstance(res, ResearchDeepInitResponse)
    assert res.job_id == "rsh_abc"


@respx.mock
def test_research_deep_wait_polls_to_complete() -> None:
    respx.post("https://api.brime.dev/v1/research").mock(
        return_value=httpx.Response(
            202,
            json={
                "job_id": "j", "status": "queued",
                "status_url": "/v1/research/j", "stream_url": "/v1/research/j/stream",
                "request_id": "r", "credits_used": 5, "started_at": "2026-05-06T00:00:00Z",
            },
        )
    )

    def status_seq(values):
        it = iter(values)
        def h(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=next(it))
        return h

    base = {
        "job_id": "j", "current_round": 0, "max_rounds": 5, "query": "q",
        "depth": "deep", "started_at": "2026-05-06T00:00:00Z",
        "updated_at": "2026-05-06T00:00:01Z", "completed_at": None,
        "answer": None, "sources_count": 0, "steps_count": 0,
        "error": None, "credits_used": 5,
    }
    respx.get("https://api.brime.dev/v1/research/j").mock(
        side_effect=status_seq([
            {**base, "status": "queued"},
            {**base, "status": "running", "current_round": 2},
            {**base, "status": "complete", "current_round": 5, "answer": "done", "sources_count": 7,
             "completed_at": "2026-05-06T00:00:30Z"},
        ])
    )

    res = Brime(api_key="sk-test").research(
        "q",
        depth="deep",
        wait=True,
        poll_interval=0.01,
        max_poll_interval=0.05,
        poll_timeout=2.0,
    )
    assert isinstance(res, ResearchStatusResponse)
    assert res.status == "complete"
    assert res.answer == "done"
