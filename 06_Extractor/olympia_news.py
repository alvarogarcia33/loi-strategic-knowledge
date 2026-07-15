from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from config import AppConfig
from database import connect


PLATFORM = "olympia"
NEWS_CATEGORY_URLS = (
    "https://olympia-lab.com/es/news/",
    "https://olympia-lab.com/es/news/latest/",
    "https://olympia-lab.com/es/news/important/",
    "https://olympia-lab.com/es/news/mog/",
    "https://olympia-lab.com/es/news/para-la-comunidad/",
    "https://olympia-lab.com/es/news/materiales-educativos/",
    "https://olympia-lab.com/es/news/noticias-sobre-el-laboratorio/",
)
ARTICLE_PATH_PATTERN = "/es/news/post/"
DEFAULT_LIMIT = 5


@dataclass(frozen=True)
class ExtractedImage:
    source_url: str
    local_path: str | None
    filename: str
    content_type: str | None
    download_status: str
    error_message: str | None = None


@dataclass(frozen=True)
class ExtractedArticle:
    title: str
    visible_date: str | None
    source_url: str
    canonical_url: str
    text: str
    images: list[ExtractedImage]
    content_hash: str
    url_hash: str
    article_uid: str
    markdown_path: Path
    metadata_path: Path
    images_dir: Path


@dataclass
class OlympiaNewsExtractionSummary:
    articles_found: int = 0
    articles_new: int = 0
    duplicates_skipped: int = 0
    errors: int = 0
    found_urls: list[str] = field(default_factory=list)
    duplicate_urls: list[str] = field(default_factory=list)
    candidate_urls: list[str] = field(default_factory=list)
    processed_urls: list[str] = field(default_factory=list)
    created_markdown: list[str] = field(default_factory=list)
    created_metadata: list[str] = field(default_factory=list)
    created_images: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    skip_reasons: list[str] = field(default_factory=list)


def extract_olympia_news(
    config: AppConfig,
    logger: logging.Logger,
    limit: int | None = DEFAULT_LIMIT,
) -> OlympiaNewsExtractionSummary:
    if limit is not None and limit <= 0:
        raise ValueError("--limit must be greater than 0 for the safe extraction phase.")

    state_path = config.project_root / "data" / "browser_state" / "olympia_state.json"
    if not state_path.exists():
        raise FileNotFoundError(
            f"Olympia authenticated state not found: {state_path}. "
            "Run python main.py --platform olympia --login-test first."
        )

    output_dirs = _ensure_olympia_output_dirs(config)
    screenshot_dir = config.project_root / "data" / "screenshots" / "article_errors"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    summary = OlympiaNewsExtractionSummary()
    logger.info("Starting Olympia limited news extraction. limit=%s", limit)
    logger.info("Using Olympia browser state: %s", state_path)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo_ms,
        )
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()
        try:
            article_urls = _discover_article_urls(page, logger)
            summary.articles_found = len(article_urls)
            summary.found_urls = article_urls
            logger.info("Olympia article URLs discovered: %s", len(article_urls))

            candidate_urls, duplicate_urls = _split_existing_url_duplicates(
                config.database_path,
                article_urls,
                logger,
            )
            summary.candidate_urls = candidate_urls
            summary.duplicate_urls = duplicate_urls
            summary.duplicates_skipped += len(duplicate_urls)
            if duplicate_urls:
                logger.info(
                    "Skipped %s existing Olympia URLs before extraction.",
                    len(duplicate_urls),
                )
            logger.info(
                "Olympia extraction candidates after URL duplicate filtering: %s",
                len(candidate_urls),
            )

            for article_url in candidate_urls:
                if limit is not None and summary.articles_new >= limit:
                    logger.info("Olympia safe extraction limit reached: %s new articles.", limit)
                    break
                summary.processed_urls.append(article_url)
                try:
                    article = _extract_single_article(
                        page=page,
                        context_request=context.request,
                        article_url=article_url,
                        output_dirs=output_dirs,
                        screenshot_dir=screenshot_dir,
                        logger=logger,
                    )
                    duplicate_reason = _find_content_duplicate(config.database_path, article)
                    if duplicate_reason:
                        summary.duplicates_skipped += 1
                        summary.duplicate_urls.append(article_url)
                        summary.skip_reasons.append(f"{article_url}: duplicate {duplicate_reason}")
                        logger.info(
                            "Skipping duplicate Olympia article after extraction: %s (%s)",
                            article_url,
                            duplicate_reason,
                        )
                        _cleanup_article_files(article, logger)
                        continue

                    article_id = _insert_article(config.database_path, article)
                    _insert_article_images(config.database_path, article_id, article.images)

                    summary.articles_new += 1
                    summary.created_markdown.append(str(article.markdown_path))
                    summary.created_metadata.append(str(article.metadata_path))
                    summary.created_images.extend(
                        image.local_path
                        for image in article.images
                        if image.local_path and image.download_status == "downloaded"
                    )
                    logger.info("Olympia article stored: %s", article.source_url)
                except Exception as exc:
                    summary.errors += 1
                    message = f"{article_url}: {exc}"
                    summary.error_messages.append(message)
                    logger.error("Olympia article extraction failed: %s", message)
                    _capture_article_error_screenshot(page, screenshot_dir, article_url, logger)
                    continue
        finally:
            context.close()
            browser.close()
            logger.info("Olympia news extraction browser closed.")

    logger.info(
        "Olympia news extraction finished. found=%s new=%s duplicates=%s errors=%s",
        summary.articles_found,
        summary.articles_new,
        summary.duplicates_skipped,
        summary.errors,
    )
    return summary


def _ensure_olympia_output_dirs(config: AppConfig) -> dict[str, Path]:
    base = config.output_root / "01_Olympia"
    output_dirs = {
        "markdown": base / "markdown",
        "metadata": base / "metadata",
        "images": base / "images",
    }
    for directory in output_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return output_dirs


def _discover_article_urls(page: Page, logger: logging.Logger) -> list[str]:
    found: dict[str, None] = {}
    for category_url in NEWS_CATEGORY_URLS:
        logger.info("Opening Olympia news category: %s", category_url)
        page.goto(category_url, wait_until="domcontentloaded", timeout=60_000)
        _wait_for_page_ready(page)
        if _looks_unauthenticated(page):
            raise RuntimeError(
                "Olympia session is not authenticated. "
                "Run python main.py --platform olympia --login-test before extracting news."
            )
        category_links = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]'))
              .map(anchor => anchor.getAttribute('href') || '')
            """
        )
        for raw_href in category_links:
            href = _normalize_url(urljoin(category_url, raw_href))
            if ARTICLE_PATH_PATTERN in urlparse(href).path:
                found[href] = None
        logger.info("Olympia category links accumulated: %s", len(found))
    return list(found.keys())


def _looks_unauthenticated(page: Page) -> bool:
    try:
        password_visible = page.locator("input[type='password']").first.is_visible(timeout=500)
    except Exception:
        password_visible = False
    try:
        body_text = page.locator("body").inner_text(timeout=2_000).lower()
    except Exception:
        body_text = ""
    login_text_visible = "iniciar sesión" in body_text or "iniciar sesion" in body_text
    dashboard_text_visible = "salida" in body_text or "mi perfil" in body_text
    return (password_visible or login_text_visible) and not dashboard_text_visible


def _split_existing_url_duplicates(
    database_path: Path,
    article_urls: list[str],
    logger: logging.Logger,
) -> tuple[list[str], list[str]]:
    new_urls: list[str] = []
    duplicate_urls: list[str] = []
    with connect(database_path) as connection:
        for article_url in article_urls:
            canonical_url = _normalize_url(article_url)
            url_hash = _sha256_text(f"{PLATFORM}:{canonical_url}")
            existing = connection.execute(
                """
                SELECT id
                FROM articles
                WHERE platform = ?
                  AND (
                    source_url = ?
                    OR canonical_url = ?
                    OR url_hash = ?
                  )
                LIMIT 1
                """,
                (PLATFORM, article_url, canonical_url, url_hash),
            ).fetchone()
            if existing:
                logger.debug("Olympia URL duplicate detected: %s", article_url)
                duplicate_urls.append(article_url)
                continue
            new_urls.append(article_url)
    return new_urls, duplicate_urls


def _extract_single_article(
    page: Page,
    context_request: Any,
    article_url: str,
    output_dirs: dict[str, Path],
    screenshot_dir: Path,
    logger: logging.Logger,
) -> ExtractedArticle:
    logger.info("Opening Olympia article: %s", article_url)
    page.goto(article_url, wait_until="domcontentloaded", timeout=60_000)
    _wait_for_page_ready(page)

    payload = page.evaluate(
        """
        () => {
          const pickText = (selectors) => {
            for (const selector of selectors) {
              const element = document.querySelector(selector);
              const text = element?.innerText?.replace(/\\s+/g, ' ').trim();
              if (text) return text;
            }
            return '';
          };
          const contentRoot =
            document.querySelector('article') ||
            document.querySelector('main') ||
            document.querySelector('[class*="news"]') ||
            document.body;
          const title = pickText(['h1', 'article h1', 'main h1', '[class*="title"]']);
          const visibleDate = pickText([
            'time',
            '[datetime]',
            '[class*="date"]',
            '[class*="time"]',
            '[class*="created"]'
          ]);
          const text = (contentRoot?.innerText || document.body.innerText || '')
            .replace(/\\r/g, '')
            .replace(/[ \\t]+/g, ' ')
            .replace(/\\n{3,}/g, '\\n\\n')
            .trim();
          const images = Array.from(contentRoot.querySelectorAll('img[src], img[data-src]'))
            .map(img => img.getAttribute('src') || img.getAttribute('data-src') || '')
            .filter(Boolean);
          const canonical = document.querySelector('link[rel="canonical"]')?.href || window.location.href;
          return { title, visibleDate, text, images, canonical };
        }
        """
    )

    title = payload["title"] or _title_from_url(article_url)
    visible_date = payload["visibleDate"] or _date_from_text(payload["text"])
    canonical_url = _normalize_url(payload["canonical"] or article_url)
    source_url = _normalize_url(article_url)
    text = _clean_article_text(payload["text"])
    if not text:
        raise RuntimeError("Article text is empty.")

    content_hash = _sha256_text(f"{title}\n{visible_date or ''}\n{text}")
    url_hash = _sha256_text(f"{PLATFORM}:{canonical_url}")
    article_uid = f"{PLATFORM}_{_short_hash(url_hash)}"
    slug = _safe_filename(title)[:80]
    filename_stem = f"{_date_prefix(visible_date)}_{slug}_{_short_hash(url_hash)}"
    markdown_path = output_dirs["markdown"] / f"{filename_stem}.md"
    metadata_path = output_dirs["metadata"] / f"{filename_stem}.json"
    images_dir = output_dirs["images"] / filename_stem
    images_dir.mkdir(parents=True, exist_ok=True)

    image_urls = _unique_urls(urljoin(source_url, raw_url) for raw_url in payload["images"])
    images = _download_images(
        context_request=context_request,
        image_urls=image_urls,
        images_dir=images_dir,
        logger=logger,
    )

    article = ExtractedArticle(
        title=title,
        visible_date=visible_date,
        source_url=source_url,
        canonical_url=canonical_url,
        text=text,
        images=images,
        content_hash=content_hash,
        url_hash=url_hash,
        article_uid=article_uid,
        markdown_path=markdown_path,
        metadata_path=metadata_path,
        images_dir=images_dir,
    )
    _write_markdown(article)
    _write_metadata(article)
    logger.debug("Olympia article files written: %s", markdown_path)
    return article


def _download_images(
    context_request: Any,
    image_urls: list[str],
    images_dir: Path,
    logger: logging.Logger,
) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    for index, image_url in enumerate(image_urls, start=1):
        try:
            response = context_request.get(image_url, timeout=60_000)
            if not response.ok:
                raise RuntimeError(f"HTTP {response.status}")
            content_type = response.headers.get("content-type", "")
            extension = _extension_from_content_type(content_type) or _extension_from_url(image_url)
            filename = f"image_{index:02d}{extension}"
            local_path = images_dir / filename
            local_path.write_bytes(response.body())
            images.append(
                ExtractedImage(
                    source_url=image_url,
                    local_path=str(local_path),
                    filename=filename,
                    content_type=content_type,
                    download_status="downloaded",
                )
            )
            logger.info("Olympia article image saved: %s", local_path)
        except Exception as exc:
            logger.error("Olympia image download failed: %s (%s)", image_url, exc)
            images.append(
                ExtractedImage(
                    source_url=image_url,
                    local_path=None,
                    filename=f"image_{index:02d}",
                    content_type=None,
                    download_status="failed",
                    error_message=str(exc),
                )
            )
    return images


def _find_content_duplicate(database_path: Path, article: ExtractedArticle) -> str | None:
    with connect(database_path) as connection:
        existing = connection.execute(
            """
            SELECT id, source_url, canonical_url, content_hash, url_hash
            FROM articles
            WHERE platform = ?
              AND (
                source_url = ?
                OR canonical_url = ?
                OR content_hash = ?
                OR url_hash = ?
              )
            LIMIT 1
            """,
            (
                PLATFORM,
                article.source_url,
                article.canonical_url,
                article.content_hash,
                article.url_hash,
            ),
        ).fetchone()
    if not existing:
        return None
    if existing["source_url"] == article.source_url:
        return "source_url"
    if existing["canonical_url"] == article.canonical_url:
        return "canonical_url"
    if existing["content_hash"] == article.content_hash:
        return "content_hash"
    if existing["url_hash"] == article.url_hash:
        return "url_hash"
    return "unknown"


def _insert_article(database_path: Path, article: ExtractedArticle) -> int:
    with connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO articles (
                platform,
                source_url,
                canonical_url,
                title,
                published_date,
                content_hash,
                url_hash,
                article_uid,
                markdown_path,
                metadata_path,
                images_dir,
                images_count,
                status,
                downloaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'downloaded', CURRENT_TIMESTAMP)
            """,
            (
                PLATFORM,
                article.source_url,
                article.canonical_url,
                article.title,
                article.visible_date,
                article.content_hash,
                article.url_hash,
                article.article_uid,
                str(article.markdown_path),
                str(article.metadata_path),
                str(article.images_dir),
                len([image for image in article.images if image.download_status == "downloaded"]),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def _insert_article_images(
    database_path: Path,
    article_id: int,
    images: list[ExtractedImage],
) -> None:
    if not images:
        return
    with connect(database_path) as connection:
        for image in images:
            connection.execute(
                """
                INSERT OR IGNORE INTO article_images (
                    article_id,
                    source_url,
                    local_path,
                    filename,
                    content_type,
                    download_status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    image.source_url,
                    image.local_path,
                    image.filename,
                    image.content_type,
                    image.download_status,
                    image.error_message,
                ),
            )
        connection.commit()


def _write_markdown(article: ExtractedArticle) -> None:
    image_lines = []
    for image in article.images:
        if image.local_path and image.download_status == "downloaded":
            relative_path = Path(image.local_path).relative_to(article.markdown_path.parent.parent)
            image_lines.append(f"![{image.filename}](../{relative_path.as_posix()})")

    frontmatter = {
        "platform": PLATFORM,
        "title": article.title,
        "date": article.visible_date or "",
        "source_url": article.source_url,
        "canonical_url": article.canonical_url,
        "article_uid": article.article_uid,
        "content_hash": article.content_hash,
        "extracted_at": datetime.now().astimezone().isoformat(),
        "images_count": len([image for image in article.images if image.download_status == "downloaded"]),
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        escaped_value = str(value).replace('"', '\\"')
        lines.append(f'{key}: "{escaped_value}"')
    lines.extend(["---", "", f"# {article.title}", "", article.text])
    if image_lines:
        lines.extend(["", "## Imágenes", "", *image_lines])
    article.markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_metadata(article: ExtractedArticle) -> None:
    metadata = {
        "article_uid": article.article_uid,
        "platform": PLATFORM,
        "title": article.title,
        "date": article.visible_date,
        "source_url": article.source_url,
        "canonical_url": article.canonical_url,
        "content_hash": article.content_hash,
        "url_hash": article.url_hash,
        "markdown_path": str(article.markdown_path),
        "metadata_path": str(article.metadata_path),
        "images_dir": str(article.images_dir),
        "images": [image.__dict__ for image in article.images],
        "extracted_at": datetime.now().astimezone().isoformat(),
        "status": "downloaded",
    }
    article.metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _capture_article_error_screenshot(
    page: Page,
    screenshot_dir: Path,
    article_url: str,
    logger: logging.Logger,
) -> Path | None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = screenshot_dir / f"olympia_article_error_{timestamp}_{_short_hash(article_url)}.png"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.error("Olympia article error screenshot saved: %s", screenshot_path)
        return screenshot_path
    except Exception as screenshot_error:
        logger.error("Could not capture Olympia article error screenshot: %s", screenshot_error)
        return None


def _cleanup_article_files(article: ExtractedArticle, logger: logging.Logger) -> None:
    for path in (article.markdown_path, article.metadata_path):
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            logger.debug("Could not remove duplicate article file %s: %s", path, exc)
    for image in article.images:
        if image.local_path:
            try:
                image_path = Path(image.local_path)
                if image_path.exists():
                    image_path.unlink()
            except OSError as exc:
                logger.debug("Could not remove duplicate image file %s: %s", image.local_path, exc)
    try:
        if article.images_dir.exists() and not any(article.images_dir.iterdir()):
            article.images_dir.rmdir()
    except OSError as exc:
        logger.debug("Could not remove duplicate image directory %s: %s", article.images_dir, exc)


def _wait_for_page_ready(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeoutError:
        page.wait_for_load_state("domcontentloaded", timeout=15_000)


def _clean_article_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    kept = [line for line in lines if line]
    return "\n\n".join(kept)


def _date_from_text(text: str) -> str | None:
    patterns = (
        r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b",
        r"\b\d{4}[./-]\d{1,2}[./-]\d{1,2}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _title_from_url(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").strip().title() or "Olympia News Article"


def _date_prefix(visible_date: str | None) -> str:
    if not visible_date:
        return "undated"
    cleaned = re.sub(r"[^0-9]+", "-", visible_date).strip("-")
    return cleaned or "undated"


def _safe_filename(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9áéíóúñü]+", "-", normalized, flags=re.IGNORECASE)
    normalized = normalized.strip("-").lower()
    return normalized or "olympia-news"


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _short_hash(value: str) -> str:
    return _sha256_text(value)[:12]


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    clean = parsed._replace(fragment="")
    return clean.geturl().rstrip("/")


def _unique_urls(urls: Any) -> list[str]:
    seen: dict[str, None] = {}
    for url in urls:
        normalized = _normalize_url(str(url))
        if normalized.startswith("http"):
            seen[normalized] = None
    return list(seen.keys())


def _extension_from_content_type(content_type: str) -> str | None:
    lowered = content_type.lower().split(";")[0].strip()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/svg+xml": ".svg",
    }
    return mapping.get(lowered)


def _extension_from_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".bin"
