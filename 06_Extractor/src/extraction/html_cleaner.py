"""HTML cleaning hooks for future article extraction."""


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())
