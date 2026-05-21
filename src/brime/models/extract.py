from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ExtractMetadata(BaseModel):
    """Unified page metadata emitted by /v1/extract for every successful
    result. All fields optional — workers may not derive every field for
    every URL. `extra="allow"` keeps any future server-added fields
    accessible without an SDK upgrade.
    """

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    description: str | None = None
    author: str | None = None
    published_date: str | None = None
    canonical: str | None = None
    og_image: str | None = None
    language: str | None = None
    # Worker phase timings — only present when include_metadata=true.
    timings: dict[str, Any] | None = None


class ExtractResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    markdown: str
    method: str
    content_type: str
    status: int | None = None
    latency_ms: int | None = None
    render_latency_ms: int | None = None
    detection: str | None = None
    metadata: ExtractMetadata | None = None


class ExtractFailedError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    message: str
    needs_browser: bool | None = None


class ExtractFailedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    error: ExtractFailedError


class ExtractResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[ExtractResultItem]
    failed: list[ExtractFailedItem]
    request_id: str
    credits_used: float
    latency_ms: int
