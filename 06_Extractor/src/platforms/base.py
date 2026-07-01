"""Base platform connector contracts for future Playwright implementation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformIdentity:
    name: str
    display_name: str
