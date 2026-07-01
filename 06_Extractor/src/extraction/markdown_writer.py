"""Markdown writer hooks for future article persistence."""


def build_frontmatter(metadata: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)
