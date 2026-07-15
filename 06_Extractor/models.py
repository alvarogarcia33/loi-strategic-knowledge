from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ArticleStatus = Literal[
    "discovered",
    "downloaded",
    "skipped_duplicate",
    "failed",
    "needs_review",
    "updated",
]


class ImageAsset(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_url: str
    local_path: Path | None = None
    filename: str | None = None
    content_type: str | None = None
    download_status: Literal["pending", "downloaded", "failed", "skipped"] = "pending"
    error_message: str | None = None


class Article(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    platform: Literal["gig_os", "olympia"]
    source_url: str
    canonical_url: str
    title: str
    published_date: str | None = None
    content: str = ""
    content_hash: str
    url_hash: str
    article_uid: str
    markdown_path: Path | None = None
    metadata_path: Path | None = None
    images_dir: Path | None = None
    images: list[ImageAsset] = Field(default_factory=list)
    status: ArticleStatus = "discovered"


class ExtractionResult(BaseModel):
    platform: Literal["gig_os", "olympia"]
    articles_found: int = 0
    articles_new: int = 0
    articles_skipped: int = 0
    articles_failed: int = 0
    article_uids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class RunSummary(BaseModel):
    started_at: datetime
    finished_at: datetime | None = None
    mode: Literal["bootstrap", "full", "incremental", "retry-failed"] = "bootstrap"
    platform: Literal["gig_os", "olympia", "all"] = "all"
    status: Literal["running", "success", "failed", "partial"] = "running"
    articles_found: int = 0
    articles_new: int = 0
    articles_skipped: int = 0
    articles_failed: int = 0
    error_message: str | None = None
