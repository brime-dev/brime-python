from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ExtractMetadata(BaseModel):
    """Unified page metadata emitted by /v1/extract for every successful
    result. All fields optional — workers may not derive every field for
    every URL. `extra="allow"` keeps any future server-added fields
    accessible without an SDK upgrade.
    """

    model_config = ConfigDict(extra="allow")

    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    canonical: Optional[str] = None
    og_image: Optional[str] = None
    language: Optional[str] = None
    # Worker phase timings — only present when include_metadata=true.
    timings: Optional[Dict[str, Any]] = None


class ExtractResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    markdown: str
    method: str
    content_type: str
    status: Optional[int] = None
    latency_ms: Optional[int] = None
    render_latency_ms: Optional[int] = None
    detection: Optional[str] = None
    metadata: Optional[ExtractMetadata] = None


class ExtractFailedError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    message: str
    needs_browser: Optional[bool] = None


class ExtractFailedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str
    error: ExtractFailedError


class ExtractResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: List[ExtractResultItem]
    failed: List[ExtractFailedItem]
    request_id: str
    credits_used: float
    latency_ms: int
