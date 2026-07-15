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


PLATFORM = "gig_os"
ROOT_NEWS_URL = "https://gig-os.com/es/gold-news"
ARTICLE_PATH_PREFIX = "/es/gold-news/read/"
DEFAULT_LIMIT = 5
DISCOVERY_SEED_URLS = (
    ROOT_NEWS_URL,
    "https://gig-os.com/es/gold-news/read/noticias-sobre-oro",
    "https://gig-os.com/es/gold-news/read/noticias-sobre-la-plataforma",
    "https://gig-os.com/es/gold-news/read/materiales-educativos",
    "https://gig-os.com/es/gold-news/read/para-la-comunidad",
    "https://gig-os.com/es/gold-news/read/redaccion-de-gig-os",
    "https://gig-os.com/es/gold-news/read/top-noticias",
    "https://gig-os.com/es/gold-news/read/ultimas-noticias",
)
LISTING_SLUGS = {
    "noticias-sobre-oro",
    "noticias-sobre-la-plataforma",
    "materiales-educativos",
    "para-la-comunidad",
    "redaccion-de-gig-os",
    "redaccion-de-global-intergold",
    "goalset-master-es",
    "seguridad-financiera",
    "top-noticias",
    "ultimas-noticias",
}
MAX_LISTING_PAGES = 200
MAX_INCREMENTAL_LISTING_PAGES = 16
MIN_INCREMENTAL_LISTING_PAGES = 4
CONSECUTIVE_KNOWN_PAGES_TO_STOP = 2


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
    author: str | None
    categories: list[str]
    images: list[ExtractedImage]
    content_hash: str
    url_hash: str
    article_uid: str
    markdown_path: Path
    metadata_path: Path
    images_dir: Path


@dataclass
class GigOsNewsExtractionSummary:
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
    listing_pages_scanned: list[str] = field(default_factory=list)


def extract_gig_os_news(
    config: AppConfig,
    logger: logging.Logger,
    limit: int | None = DEFAULT_LIMIT,
    incremental: bool = False,
) -> GigOsNewsExtractionSummary:
    if limit is not None and limit <= 0:
        raise ValueError("--limit must be greater than 0 for the safe extraction phase.")

    state_path = config.project_root / "data" / "browser_state" / "gig_os_state.json"
    if not state_path.exists():
        raise FileNotFoundError(
            f"GIG-OS authenticated state not found: {state_path}. "
            "Run python main.py --platform gig_os --login-test first."
        )

    output_dirs = _ensure_gig_os_output_dirs(config)
    screenshot_dir = config.project_root / "data" / "screenshots" / "article_errors"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    summary = GigOsNewsExtractionSummary()
    logger.info("Starting GIG-OS news extraction. limit=%s", limit)
    logger.info("Using GIG-OS browser state: %s", state_path)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo_ms,
        )
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()
        try:
            article_urls, listing_pages = _discover_article_urls(
                page=page,
                logger=logger,
                database_path=config.database_path,
                limit=limit,
                incremental=incremental,
            )
            summary.articles_found = len(article_urls)
            summary.found_urls = article_urls
            summary.listing_pages_scanned = listing_pages
            logger.info("GIG-OS article URLs discovered: %s", len(article_urls))

            candidate_urls, duplicate_urls = _split_existing_url_duplicates(
                config.database_path,
                article_urls,
                logger,
            )
            summary.candidate_urls = candidate_urls
            summary.duplicate_urls = duplicate_urls
            summary.duplicates_skipped += len(duplicate_urls)
            logger.info(
                "GIG-OS extraction candidates after URL duplicate filtering: %s",
                len(candidate_urls),
            )

            for article_url in candidate_urls:
                if limit is not None and summary.articles_new >= limit:
                    logger.info("GIG-OS safe extraction limit reached: %s new articles.", limit)
                    break

                summary.processed_urls.append(article_url)
                try:
                    article = _extract_single_article(
                        page=page,
                        context_request=context.request,
                        article_url=article_url,
                        output_dirs=output_dirs,
                        logger=logger,
                    )
                    duplicate_reason = _find_content_duplicate(config.database_path, article)
                    if duplicate_reason:
                        summary.duplicates_skipped += 1
                        summary.duplicate_urls.append(article_url)
                        summary.skip_reasons.append(f"{article_url}: duplicate {duplicate_reason}")
                        logger.info(
                            "Skipping duplicate GIG-OS article after extraction: %s (%s)",
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
                    logger.info("GIG-OS article stored: %s", article.source_url)
                except Exception as exc:
                    summary.errors += 1
                    message = f"{article_url}: {exc}"
                    summary.error_messages.append(message)
                    logger.error("GIG-OS article extraction failed: %s", message)
                    _capture_article_error_screenshot(page, screenshot_dir, article_url, logger)
                    continue
        finally:
            context.close()
            browser.close()
            logger.info("GIG-OS news extraction browser closed.")

    logger.info(
        "GIG-OS news extraction finished. found=%s new=%s duplicates=%s errors=%s",
        summary.articles_found,
        summary.articles_new,
        summary.duplicates_skipped,
        summary.errors,
    )
    return summary


def _ensure_gig_os_output_dirs(config: AppConfig) -> dict[str, Path]:
    base = config.output_root / "02_GIG_OS"
    output_dirs = {
        "markdown": base / "markdown",
        "metadata": base / "metadata",
        "images": base / "images",
    }
    for directory in output_dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return output_dirs


def _discover_article_urls(
    page: Page,
    logger: logging.Logger,
    database_path: Path,
    limit: int | None,
    incremental: bool,
) -> tuple[list[str], list[str]]:
    queued_listing_urls: list[str] = list(DISCOVERY_SEED_URLS)
    seen_listing_urls: dict[str, None] = {}
    queued_lookup = {url: None for url in queued_listing_urls}
    article_urls: dict[str, None] = {}
    target_articles = None if limit is None else max(limit * 5, limit)
    known_urls = _load_known_url_keys(database_path) if incremental else set()
    consecutive_known_pages = 0

    while queued_listing_urls:
        max_listing_pages = MAX_INCREMENTAL_LISTING_PAGES if incremental else MAX_LISTING_PAGES
        if len(seen_listing_urls) >= max_listing_pages:
            logger.warning(
                "Reached GIG-OS listing-page safety cap: %s pages scanned.",
                max_listing_pages,
            )
            break

        if target_articles is not None and len(article_urls) >= target_articles:
            logger.info(
                "Stopping GIG-OS discovery early for safe extraction: %s candidate articles collected.",
                len(article_urls),
            )
            break

        listing_url = _normalize_url(queued_listing_urls.pop(0))
        queued_lookup.pop(listing_url, None)
        if listing_url in seen_listing_urls:
            continue

        seen_listing_urls[listing_url] = None
        logger.info("Opening GIG-OS listing page: %s", listing_url)
        page.goto(listing_url, wait_until="domcontentloaded", timeout=60_000)
        _wait_for_page_ready(page)

        if _looks_unauthenticated(page):
            raise RuntimeError(
                "GIG-OS session is not authenticated. "
                "Run python main.py --platform gig_os --login-test before extracting news."
            )

        category_links = page.evaluate(
            """
            () => Array.from(document.querySelectorAll('a[href]'))
              .map(anchor => anchor.getAttribute('href') || '')
            """
        )
        page_new_article_urls = 0
        for raw_href in category_links:
            href = _normalize_url(urljoin(listing_url, raw_href))
            if ARTICLE_PATH_PREFIX not in urlparse(href).path:
                continue
            if _is_listing_url(href):
                if href not in seen_listing_urls and href not in queued_lookup:
                    queued_listing_urls.append(href)
                    queued_lookup[href] = None
                continue
            if incremental and not _is_known_url(href, known_urls):
                page_new_article_urls += 1
            article_urls[href] = None

        if incremental:
            if page_new_article_urls == 0:
                consecutive_known_pages += 1
            else:
                consecutive_known_pages = 0

        logger.info(
            "GIG-OS discovery progress: listings=%s articles=%s queued=%s new_on_page=%s",
            len(seen_listing_urls),
            len(article_urls),
            len(queued_listing_urls),
            page_new_article_urls,
        )
        if (
            incremental
            and len(seen_listing_urls) >= MIN_INCREMENTAL_LISTING_PAGES
            and consecutive_known_pages >= CONSECUTIVE_KNOWN_PAGES_TO_STOP
        ):
            logger.info(
                "Stopping GIG-OS incremental discovery after %s consecutive known-only pages.",
                consecutive_known_pages,
            )
            break

    return sorted(article_urls), sorted(seen_listing_urls)


def _is_listing_url(url: str) -> bool:
    parsed_path = urlparse(url).path.lower().rstrip("/")
    if parsed_path == "/es/gold-news":
        return True
    if "/es/gold-news/read/" not in parsed_path:
        return False
    slug = parsed_path.split("/es/gold-news/read/", 1)[1]
    if slug in LISTING_SLUGS:
        return True
    return slug.startswith("ultimas-noticias/")


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
                logger.debug("GIG-OS URL duplicate detected: %s", article_url)
                duplicate_urls.append(article_url)
                continue
            new_urls.append(article_url)
    return new_urls, duplicate_urls


def _load_known_url_keys(database_path: Path) -> set[str]:
    keys: set[str] = set()
    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT source_url, canonical_url, url_hash
            FROM articles
            WHERE platform = ?
            """,
            (PLATFORM,),
        ).fetchall()
    for row in rows:
        for key in (row["source_url"], row["canonical_url"], row["url_hash"]):
            if key:
                keys.add(str(key))
    return keys


def _is_known_url(url: str, known_keys: set[str]) -> bool:
    url_hash = _sha256_text(f"{PLATFORM}:{_normalize_url(url)}")
    return url in known_keys or _normalize_url(url) in known_keys or url_hash in known_keys


def _extract_single_article(
    page: Page,
    context_request: Any,
    article_url: str,
    output_dirs: dict[str, Path],
    logger: logging.Logger,
) -> ExtractedArticle:
    logger.info("Opening GIG-OS article: %s", article_url)
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
            document.querySelector('.newsBlock__detailContent') ||
            document.querySelector('.newsBlockDetail__main') ||
            document.querySelector('.newsBlock__detail') ||
            document.querySelector('article') ||
            document.querySelector('main') ||
            document.body;

          const title = pickText([
            'h1.section__h4.newsBlockDetail__title',
            '.newsBlockDetail__title',
            'h1',
            '[class*=\"title\"]'
          ]);
          const visibleDate = pickText([
            '.rate-and-date',
            '.date.pull-right',
            '.date',
            'time',
            '[datetime]'
          ]);
          const author = pickText([
            '.newsBlockDetailContentAuthorBlockRight__name',
            '.newsBlock__detailContent-author .newsBlockDetailContentAuthorBlockRight__name',
            '.newsBlock__detailContent-author',
            '[class*=\"author\"] a',
            '[class*=\"author\"]'
          ]);
          const categories = Array.from(document.querySelectorAll('.newsBlockTopMenuLeft__categoryLink a, .newsBlockTopMenuLeft__categoryLink'))
            .map(node => (node.innerText || '').replace(/\\s+/g, ' ').trim())
            .filter(Boolean);
          const categoryAnchors = Array.from(document.querySelectorAll('.newsBlockTopMenuLeft__categoryLink a'))
            .map(node => (node.innerText || '').replace(/\\s+/g, ' ').trim())
            .filter(Boolean);
          const text = (contentRoot?.innerText || '')
            .replace(/\\u00a0/g, ' ')
            .replace(/\\r/g, '')
            .replace(/[ \\t]+/g, ' ')
            .replace(/\\n{3,}/g, '\\n\\n')
            .trim();
          const images = Array.from(contentRoot.querySelectorAll('img[src], img[data-src]'))
            .filter(img => !/(author|avatar)/i.test(img.className || ''))
            .map(img => img.getAttribute('src') || img.getAttribute('data-src') || '')
            .filter(Boolean);
          const canonical = document.querySelector('link[rel=\"canonical\"]')?.href || window.location.href;
          const readLinks = Array.from(document.querySelectorAll('a[href]'))
            .map(anchor => anchor.href)
            .filter(href => href.includes('/es/gold-news/read/'));
          return {
            title,
            visibleDate,
            author,
            categories: categoryAnchors.length ? categoryAnchors : categories,
            text,
            images,
            canonical,
            readLinksCount: Array.from(new Set(readLinks)).length
          };
        }
        """
    )

    title = payload["title"] or _title_from_url(article_url)
    if title.strip().lower() == "noticias" and payload["readLinksCount"] >= 8:
        raise RuntimeError("Detected listing page instead of article.")

    visible_date = _clean_visible_date(payload["visibleDate"]) or _date_from_text(payload["text"])
    canonical_url = _normalize_url(payload["canonical"] or article_url)
    source_url = _normalize_url(article_url)
    text = _clean_article_text(payload["text"])
    if not text or len(text) < 120:
        raise RuntimeError("Article text is empty or too short.")

    author = _clean_author(payload["author"])
    categories = _unique_strings(payload["categories"])
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
        author=author,
        categories=categories,
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
    logger.debug("GIG-OS article files written: %s", markdown_path)
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
            logger.info("GIG-OS article image saved: %s", local_path)
        except Exception as exc:
            logger.error("GIG-OS image download failed: %s (%s)", image_url, exc)
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
        "author": article.author or "",
        "categories": ", ".join(article.categories),
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
    lines.extend(["---", "", f"# {article.title}", ""])
    if article.visible_date:
        lines.append(f"Fecha: {article.visible_date}")
    if article.author:
        lines.append(f"Autor: {article.author}")
    if article.categories:
        lines.append(f"Categorías: {', '.join(article.categories)}")
    lines.extend(["", article.text])
    if image_lines:
        lines.extend(["", "## Imágenes", "", *image_lines])
    article.markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_metadata(article: ExtractedArticle) -> None:
    metadata = {
        "article_uid": article.article_uid,
        "platform": PLATFORM,
        "title": article.title,
        "date": article.visible_date,
        "author": article.author,
        "categories": article.categories,
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
    screenshot_path = screenshot_dir / f"gig_os_article_error_{timestamp}_{_short_hash(article_url)}.png"
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.error("GIG-OS article error screenshot saved: %s", screenshot_path)
        return screenshot_path
    except Exception as screenshot_error:
        logger.error("Could not capture GIG-OS article error screenshot: %s", screenshot_error)
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
    text = re.sub(r"\u00a0+", " ", text)
    lines = [line.strip() for line in text.splitlines()]
    kept = [line for line in lines if line]
    return "\n\n".join(kept)


def _clean_visible_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    value = re.sub(r"^Publicado:\s*", "", value, flags=re.IGNORECASE)
    return value or None


def _clean_author(value: str | None) -> str | None:
    if not value:
        return None
    parts = [part.strip() for part in re.split(r"[\r\n]+", value) if part.strip()]
    if not parts:
        return None
    return parts[0]


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
    return slug.replace("-", " ").strip().title() or "GIG-OS News Article"


def _date_prefix(visible_date: str | None) -> str:
    if not visible_date:
        return "undated"
    cleaned = re.sub(r"[^0-9]+", "-", visible_date).strip("-")
    return cleaned or "undated"


def _safe_filename(value: str) -> str:
    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9áéíóúñü]+", "-", normalized, flags=re.IGNORECASE)
    normalized = normalized.strip("-").lower()
    return normalized or "gig-os-news"


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


def _unique_strings(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        if normalized:
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
