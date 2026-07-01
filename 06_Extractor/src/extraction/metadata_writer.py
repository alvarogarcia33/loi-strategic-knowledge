"""Metadata writer hooks for future JSON output."""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
