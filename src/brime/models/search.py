from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SearchResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    url: str
    content: str
    score: float | None = None
    published_date: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    answer: str | None = None
    results: list[SearchResultItem]
    request_id: str
    credits_used: float
    latency_ms: int
