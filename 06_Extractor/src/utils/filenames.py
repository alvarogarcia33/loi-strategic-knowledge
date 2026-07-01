"""Filename helpers for safe local persistence."""

import re


def safe_filename(value: str, fallback: str = "untitled") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return cleaned or fallback
