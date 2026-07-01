from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from config import AppConfig


CONTENT_KEYWORDS = (
    "Noticias",
    "Novedades",
    "News",
    "Updates",
    "Blog",
    "Articles",
    "Announcements",
    "Comunidad",
    "Eventos",
    "Actualizaciones",
)


@dataclass(frozen=True)
class InternalLink:
    text: str
    href: str
    source: str
    matched_keywords: list[str]


@dataclass(frozen=True)
class MenuCandidate:
    selector_hint: str
    tag_name: str
    role: str
    text_preview: str
    link_count: int


@dataclass(frozen=True)
class ScreenshotRecord:
    name: str
    path: str
    url: str


@dataclass(frozen=True)
class GigOsStructureReport:
    generated_at: str
    dashboard_url: str
    final_url: str
    total_internal_links: int
    internal_links: list[InternalLink]
    content_sections: list[InternalLink]
    menu_candidates: list[MenuCandidate]
    screenshots: list[ScreenshotRecord]
    recommended_strategy: list[str]


def discover_gig_os_structure(config: AppConfig, logger: logging.Logger) -> GigOsStructureReport:
    state_path = config.project_root / "data" / "browser_state" / "gig_os_state.json"
    if not state_path.exists():
        raise FileNotFoundError(
            f"GIG-OS authenticated state not found: {state_path}. "
            "Run python main.py --platform gig_os --login-test first."
        )

    dashboard_url = config.gig_os.base_url or config.gig_os.login_url
    if not dashboard_url:
        raise ValueError("GIG_OS_BASE_URL or GIG_OS_LOGIN_URL must be configured.")

    screenshot_dir = config.project_root / "data" / "screenshots" / "structure"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting GIG-OS structure discovery.")
    logger.info("Using GIG-OS browser state: %s", state_path)
    logger.info("Dashboard URL: %s", dashboard_url)

    screenshots: list[ScreenshotRecord] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo_ms,
        )
        context = browser.new_context(storage_state=str(state_path))
        page = context.new_page()
        try:
            page.goto(dashboard_url, wait_until="domcontentloaded", timeout=60_000)
            _wait_for_page_ready(page)
            screenshots.append(_capture_screenshot(page, screenshot_dir, "dashboard", logger))

            menu_candidates = _detect_menu_candidates(page, logger)
            _try_expand_main_menu(page, logger)
            _wait_for_page_ready(page)
            screenshots.append(_capture_screenshot(page, screenshot_dir, "main_menu", logger))

            internal_links = _collect_internal_links(page, logger)
            content_sections = _find_content_sections(internal_links)

            if content_sections:
                section = content_sections[0]
                logger.info(
                    "Opening first GIG-OS candidate content section: %s -> %s",
                    section.text,
                    section.href,
                )
                page.goto(section.href, wait_until="domcontentloaded", timeout=60_000)
                _wait_for_page_ready(page)
                screenshots.append(
                    _capture_screenshot(page, screenshot_dir, "content_section_found", logger)
                )
                section_links = _collect_internal_links(page, logger)
                internal_links = _merge_links(internal_links, section_links)
                content_sections = _find_content_sections(internal_links)
            else:
                logger.info("No named GIG-OS content section found for deeper screenshot pass.")

            report = GigOsStructureReport(
                generated_at=datetime.now().astimezone().isoformat(),
                dashboard_url=dashboard_url,
                final_url=page.url,
                total_internal_links=len(internal_links),
                internal_links=internal_links,
                content_sections=content_sections,
                menu_candidates=menu_candidates,
                screenshots=screenshots,
                recommended_strategy=_build_recommended_strategy(content_sections, internal_links),
            )
        finally:
            context.close()
            browser.close()
            logger.info("GIG-OS structure discovery browser closed.")

    json_path = config.project_root / "data" / "gig_os_structure_report.json"
    markdown_path = config.output_root / "08_Reportes" / "gig_os_structure_report.md"
    _write_json_report(report, json_path, logger)
    _write_markdown_report(report, markdown_path, logger)
    logger.info("GIG-OS structure discovery completed.")
    return report


def _wait_for_page_ready(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightTimeoutError:
        page.wait_for_load_state("domcontentloaded", timeout=15_000)


def _capture_screenshot(
    page: Page,
    screenshot_dir: Path,
    name: str,
    logger: logging.Logger,
) -> ScreenshotRecord:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = screenshot_dir / f"gig_os_structure_{name}_{timestamp}.png"
    page.screenshot(path=str(path), full_page=True)
    logger.info("GIG-OS structure screenshot saved: %s", path)
    return ScreenshotRecord(name=name, path=str(path), url=page.url)


def _detect_menu_candidates(page: Page, logger: logging.Logger) -> list[MenuCandidate]:
    raw_candidates = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('nav, aside, header, [role="navigation"], [role="menu"]'))
          .map((element, index) => ({
            selector_hint: `${element.tagName.toLowerCase()}:nth-of-type(${index + 1})`,
            tag_name: element.tagName.toLowerCase(),
            role: element.getAttribute('role') || '',
            text_preview: (element.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 500),
            link_count: element.querySelectorAll('a[href]').length
          }))
          .filter(item => item.text_preview || item.link_count > 0)
        """
    )
    candidates = [
        MenuCandidate(
            selector_hint=item["selector_hint"],
            tag_name=item["tag_name"],
            role=item["role"],
            text_preview=item["text_preview"],
            link_count=item["link_count"],
        )
        for item in raw_candidates
    ]
    logger.info("Detected %s possible GIG-OS main menu containers.", len(candidates))
    return candidates


def _try_expand_main_menu(page: Page, logger: logging.Logger) -> None:
    button_selectors = (
        "button[aria-label*='menu' i]",
        "button[aria-label*='navigation' i]",
        "button:has-text('Menu')",
        "button:has-text('Menú')",
        "[role='button'][aria-label*='menu' i]",
        ".hamburger",
        ".navbar-toggler",
    )
    for selector in button_selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible(timeout=500):
                logger.info("Trying to expand GIG-OS menu with selector: %s", selector)
                locator.click(timeout=2_000)
                return
        except Exception as exc:
            logger.debug("GIG-OS menu expansion selector failed: %s (%s)", selector, exc)


def _collect_internal_links(page: Page, logger: logging.Logger) -> list[InternalLink]:
    current_url = page.url
    current_origin = _origin(current_url)
    raw_links = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href]')).map(anchor => ({
            text: (anchor.innerText || anchor.textContent || '').replace(/\\s+/g, ' ').trim(),
            href: anchor.getAttribute('href') || '',
            source: anchor.closest('nav, aside, header, main, section, footer')?.tagName?.toLowerCase() || 'body'
        }))
        """
    )

    links_by_href: dict[str, InternalLink] = {}
    for item in raw_links:
        href = urljoin(current_url, item["href"])
        parsed = urlparse(href)
        if parsed.scheme not in {"http", "https"}:
            continue
        if _origin(href) != current_origin:
            continue
        normalized_href = _strip_fragment(href)
        text = item["text"] or normalized_href
        keywords = _matched_keywords(text, normalized_href)
        existing = links_by_href.get(normalized_href)
        if existing and len(existing.text) >= len(text):
            continue
        links_by_href[normalized_href] = InternalLink(
            text=text,
            href=normalized_href,
            source=item["source"],
            matched_keywords=keywords,
        )

    links = sorted(links_by_href.values(), key=lambda link: (link.href, link.text.lower()))
    logger.info("Collected %s unique internal links from %s.", len(links), page.url)
    return links


def _find_content_sections(links: list[InternalLink]) -> list[InternalLink]:
    candidates = [
        link
        for link in links
        if link.matched_keywords and not _looks_like_article_url(link.href)
    ]
    return sorted(candidates, key=_content_section_sort_key)


def _content_section_sort_key(link: InternalLink) -> tuple[int, int, int, str]:
    normalized_text = link.text.strip().lower()
    exact_keyword = normalized_text in {keyword.lower() for keyword in CONTENT_KEYWORDS}
    return (
        0 if exact_keyword else 1,
        0 if any(token in link.href.lower() for token in ("/news", "/noticias", "/blog", "/updates")) else 1,
        len(link.text),
        link.text.lower(),
    )


def _looks_like_article_url(href: str) -> bool:
    parsed_path = urlparse(href).path.lower()
    article_markers = ("/post/", "/article/", "/articles/", "/blog/")
    return any(marker in parsed_path for marker in article_markers) and len(parsed_path.strip("/").split("/")) >= 3


def _merge_links(first: list[InternalLink], second: list[InternalLink]) -> list[InternalLink]:
    merged = {link.href: link for link in first}
    for link in second:
        existing = merged.get(link.href)
        if not existing or len(link.text) > len(existing.text):
            merged[link.href] = link
    return sorted(merged.values(), key=lambda link: (link.href, link.text.lower()))


def _build_recommended_strategy(
    content_sections: list[InternalLink],
    internal_links: list[InternalLink],
) -> list[str]:
    strategy = [
        "Use the authenticated Playwright storage state and start from the GIG-OS base URL.",
        "Seed discovery from same-origin internal links only.",
        "Prioritize sections mentioning Noticias, Novedades, Blog, Updates, Comunidad or Eventos.",
    ]
    if content_sections:
        strategy.append(
            "Visit each candidate section and detect repeated article-card links before opening individual pages."
        )
        strategy.append(
            "Once stable selectors are confirmed, run a full historical scan and then stop incremental runs on already-known URLs."
        )
    elif internal_links:
        strategy.append(
            "No named content section was found; next pass should inspect visible menu interactions and route changes after login."
        )
    else:
        strategy.append(
            "No internal links were detected; next pass should inspect authenticated API calls and client-side routing."
        )
    strategy.append("Do not write article bodies until the location of the real news feed is confirmed.")
    return strategy


def _write_json_report(report: GigOsStructureReport, path: Path, logger: logging.Logger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("GIG-OS JSON structure report saved: %s", path)


def _write_markdown_report(report: GigOsStructureReport, path: Path, logger: logging.Logger) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GIG-OS Structure Report",
        "",
        f"- Generated at: `{report.generated_at}`",
        f"- Dashboard URL: `{report.dashboard_url}`",
        f"- Final URL: `{report.final_url}`",
        f"- Internal links found: `{report.total_internal_links}`",
        f"- Candidate content sections: `{len(report.content_sections)}`",
        "",
        "## Possible Content Sections",
        "",
    ]
    if report.content_sections:
        for link in report.content_sections:
            lines.append(
                f"- [{_escape_markdown(link.text)}]({link.href}) "
                f"keywords: `{', '.join(link.matched_keywords)}` source: `{link.source}`"
            )
    else:
        lines.append("- No named content sections found.")

    lines.extend(["", "## Internal Links", ""])
    for link in report.internal_links:
        keyword_text = ", ".join(link.matched_keywords) if link.matched_keywords else "-"
        lines.append(f"- [{_escape_markdown(link.text)}]({link.href}) keywords: `{keyword_text}`")

    lines.extend(["", "## Menu Candidates", ""])
    if report.menu_candidates:
        for menu in report.menu_candidates:
            lines.append(
                f"- `{menu.tag_name}` role: `{menu.role or '-'}` links: `{menu.link_count}` "
                f"text: {_escape_markdown(menu.text_preview[:180])}"
            )
    else:
        lines.append("- No explicit menu containers detected.")

    lines.extend(["", "## Screenshots", ""])
    for screenshot in report.screenshots:
        lines.append(f"- `{screenshot.name}`: `{screenshot.path}` at `{screenshot.url}`")

    lines.extend(["", "## Recommended Scraping Strategy", ""])
    for item in report.recommended_strategy:
        lines.append(f"- {item}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("GIG-OS Markdown structure report saved: %s", path)


def _matched_keywords(text: str, href: str) -> list[str]:
    haystack = f"{text} {href}".lower()
    return [
        keyword
        for keyword in CONTENT_KEYWORDS
        if re.search(rf"\b{re.escape(keyword.lower())}\b", haystack)
    ]


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}".lower()


def _strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    without_fragment = parsed._replace(fragment="")
    return without_fragment.geturl()


def _escape_markdown(value: str) -> str:
    return value.replace("[", "\\[").replace("]", "\\]")
