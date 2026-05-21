from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    url: str
    content: str | None = None
    score: float | None = None
    published_date: str | None = None


class ResearchBasicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    answer: str | None = None
    sources: list[ResearchSource]
    steps: list[dict[str, Any]] | None = None
    request_id: str
    credits_used: float
    latency_ms: int


class ResearchDeepInitResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: Literal["queued"]
    status_url: str
    stream_url: str
    request_id: str
    credits_used: float
    started_at: str


class ResearchStatusError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    message: str


class ResearchStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str
    status: Literal["queued", "running", "complete", "errored", "timeout"]
    current_round: int
    max_rounds: int
    query: str
    depth: Literal["basic", "deep"]
    started_at: str
    updated_at: str
    completed_at: str | None = None
    answer: str | None = None
    sources_count: int
    steps_count: int
    error: ResearchStatusError | None = None
    credits_used: float


class ResearchSseEvent(BaseModel):
    """A single SSE event emitted by /v1/research stream endpoints.

    `event` is one of: status, intent, tool_call, tool_result, sources,
    final, done, complete, error, timeout.

    `data` is typically a dict but may be a plain string for free-form
    progress events (e.g. status: "Round 1: thinking…"). Callers should
    `isinstance(evt.data, dict)` before subscripting.
    """

    model_config = ConfigDict(extra="ignore")

    event: str
    data: Any
    id: str | None = None
