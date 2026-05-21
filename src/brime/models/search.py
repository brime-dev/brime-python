from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SearchResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    url: str
    content: str
    score: Optional[float] = None
    published_date: Optional[str] = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    answer: Optional[str] = None
    results: List[SearchResultItem]
    request_id: str
    credits_used: float
    latency_ms: int
