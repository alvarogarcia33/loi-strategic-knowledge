from src.extraction.markdown_writer import build_frontmatter


def test_build_frontmatter() -> None:
    assert build_frontmatter({"platform": "gig_os"}).startswith("---")
