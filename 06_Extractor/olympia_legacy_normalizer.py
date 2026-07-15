from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import AppConfig
from database import connect


PLATFORM = "olympia"


@dataclass
class OlympiaArticleRecord:
    stem: str
    title: str
    article_uid: str
    source_url: str
    canonical_url: str
    content_hash: str
    url_hash: str
    markdown_path: Path
    metadata_path: Path
    images_dir: Path
    metadata: dict


@dataclass
class OlympiaNormalizationSummary:
    backup_root: Path
    sqlite_backup_path: Path
    inventory_report_path: Path
    final_report_json_path: Path
    final_report_md_path: Path
    legacy_articles_found: int = 0
    current_articles_found: int = 0
    duplicates_omitted: list[dict] = field(default_factory=list)
    moved_articles: list[dict] = field(default_factory=list)
    conflicts_detected: list[dict] = field(default_factory=list)
    left_unmoved: list[dict] = field(default_factory=list)


def normalize_olympia_legacy(
    config: AppConfig,
    logger: logging.Logger,
) -> OlympiaNormalizationSummary:
    legacy_root = config.output_root / "02_Olympia"
    current_root = config.output_root / "01_Olympia"

    if not legacy_root.exists():
        raise FileNotFoundError(f"Legacy Olympia folder not found: {legacy_root}")
    if not current_root.exists():
        raise FileNotFoundError(f"Current Olympia folder not found: {current_root}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = config.project_root / "data" / "backups" / f"olympia_legacy_normalization_{timestamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    sqlite_backup_path = backup_root / "articles.sqlite"
    shutil.copy2(config.database_path, sqlite_backup_path)

    legacy_snapshot_root = backup_root / "02_Olympia_snapshot"
    shutil.copytree(legacy_root, legacy_snapshot_root)

    current_articles = _load_articles_from_metadata(current_root / "metadata")
    legacy_articles = _load_articles_from_metadata(legacy_root / "metadata")

    inventory_report_path = backup_root / "inventory_before.json"
    inventory_report = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "current_root": str(current_root),
        "legacy_root": str(legacy_root),
        "current_articles": [_article_inventory_dict(article) for article in current_articles],
        "legacy_articles": [_article_inventory_dict(article) for article in legacy_articles],
        "legacy_all_files": _inventory_files(legacy_root),
        "current_all_files": _inventory_files(current_root),
    }
    inventory_report_path.write_text(
        json.dumps(inventory_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = OlympiaNormalizationSummary(
        backup_root=backup_root,
        sqlite_backup_path=sqlite_backup_path,
        inventory_report_path=inventory_report_path,
        final_report_json_path=config.output_root / "08_Reportes" / f"olympia_legacy_normalization_{timestamp}.json",
        final_report_md_path=config.output_root / "08_Reportes" / f"olympia_legacy_normalization_{timestamp}.md",
        legacy_articles_found=len(legacy_articles),
        current_articles_found=len(current_articles),
    )

    current_by_stem = {article.stem: article for article in current_articles}
    current_by_url = {}
    current_by_hash = {}
    for article in current_articles:
        for url in filter(None, (article.source_url, article.canonical_url)):
            current_by_url[url] = article
        if article.content_hash:
            current_by_hash[article.content_hash] = article

    for legacy_article in legacy_articles:
        match_reasons: list[str] = []
        if legacy_article.stem in current_by_stem:
            match_reasons.append("name")
        if legacy_article.source_url in current_by_url or legacy_article.canonical_url in current_by_url:
            match_reasons.append("url")
        if legacy_article.content_hash and legacy_article.content_hash in current_by_hash:
            match_reasons.append("content_hash")

        duplicate = "url" in match_reasons or "content_hash" in match_reasons
        conflict = "name" in match_reasons and not duplicate

        if duplicate:
            entry = {
                "title": legacy_article.title,
                "source_url": legacy_article.source_url,
                "stem": legacy_article.stem,
                "reasons": match_reasons,
            }
            summary.duplicates_omitted.append(entry)
            summary.left_unmoved.append({**entry, "why": "duplicate"})
            continue

        target_stem = legacy_article.stem
        if conflict:
            target_stem = _unique_conflict_stem(current_root / "metadata", legacy_article.stem)
            summary.conflicts_detected.append(
                {
                    "title": legacy_article.title,
                    "source_url": legacy_article.source_url,
                    "legacy_stem": legacy_article.stem,
                    "target_stem": target_stem,
                    "reasons": match_reasons,
                }
            )

        result = _move_article_to_current(
            database_path=config.database_path,
            current_root=current_root,
            legacy_article=legacy_article,
            target_stem=target_stem,
            logger=logger,
        )
        summary.moved_articles.append(result)

    remaining_legacy_articles = _load_articles_from_metadata(legacy_root / "metadata")
    moved_source_urls = {item["source_url"] for item in summary.moved_articles}
    known_left_urls = {item["source_url"] for item in summary.left_unmoved}
    for article in remaining_legacy_articles:
        if article.source_url in moved_source_urls or article.source_url in known_left_urls:
            continue
        summary.left_unmoved.append(
            {
                "title": article.title,
                "source_url": article.source_url,
                "stem": article.stem,
                "why": "remaining_in_legacy",
            }
        )

    _write_reports(summary)
    logger.info("Olympia legacy normalization completed. Report: %s", summary.final_report_json_path)
    return summary


def _load_articles_from_metadata(metadata_dir: Path) -> list[OlympiaArticleRecord]:
    if not metadata_dir.exists():
        return []

    articles: list[OlympiaArticleRecord] = []
    for metadata_path in sorted(metadata_dir.glob("*.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        markdown_path = Path(metadata.get("markdown_path") or metadata_path.with_suffix(".md"))
        images_dir = Path(metadata.get("images_dir") or metadata_path.parent.parent / "images" / metadata_path.stem)
        articles.append(
            OlympiaArticleRecord(
                stem=metadata_path.stem,
                title=metadata.get("title") or metadata_path.stem,
                article_uid=metadata.get("article_uid") or "",
                source_url=metadata.get("source_url") or "",
                canonical_url=metadata.get("canonical_url") or metadata.get("source_url") or "",
                content_hash=metadata.get("content_hash") or "",
                url_hash=metadata.get("url_hash") or "",
                markdown_path=markdown_path,
                metadata_path=metadata_path,
                images_dir=images_dir,
                metadata=metadata,
            )
        )
    return articles


def _article_inventory_dict(article: OlympiaArticleRecord) -> dict:
    return {
        "stem": article.stem,
        "title": article.title,
        "article_uid": article.article_uid,
        "source_url": article.source_url,
        "canonical_url": article.canonical_url,
        "content_hash": article.content_hash,
        "url_hash": article.url_hash,
        "markdown_path": str(article.markdown_path),
        "metadata_path": str(article.metadata_path),
        "images_dir": str(article.images_dir),
    }


def _inventory_files(root: Path) -> list[dict]:
    files: list[dict] = []
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        files.append(
            {
                "path": str(path),
                "kind": "dir" if path.is_dir() else "file",
                "size": path.stat().st_size if path.is_file() else None,
            }
        )
    return files


def _unique_conflict_stem(metadata_dir: Path, base_stem: str) -> str:
    candidate = f"{base_stem}_legacy"
    counter = 2
    while (metadata_dir / f"{candidate}.json").exists():
        candidate = f"{base_stem}_legacy_{counter}"
        counter += 1
    return candidate


def _move_article_to_current(
    database_path: Path,
    current_root: Path,
    legacy_article: OlympiaArticleRecord,
    target_stem: str,
    logger: logging.Logger,
) -> dict:
    target_markdown = current_root / "markdown" / f"{target_stem}.md"
    target_metadata = current_root / "metadata" / f"{target_stem}.json"
    target_images_dir = current_root / "images" / target_stem

    target_markdown.parent.mkdir(parents=True, exist_ok=True)
    target_metadata.parent.mkdir(parents=True, exist_ok=True)
    target_images_dir.parent.mkdir(parents=True, exist_ok=True)

    moved_markdown = False
    moved_metadata = False
    moved_images = False

    if legacy_article.markdown_path.exists():
        markdown_text = legacy_article.markdown_path.read_text(encoding="utf-8")
        if target_stem != legacy_article.stem:
            markdown_text = markdown_text.replace(
                f"../images/{legacy_article.stem}/",
                f"../images/{target_stem}/",
            )
        target_markdown.write_text(markdown_text, encoding="utf-8")
        legacy_article.markdown_path.unlink()
        moved_markdown = True

    metadata = dict(legacy_article.metadata)
    metadata["markdown_path"] = str(target_markdown)
    metadata["metadata_path"] = str(target_metadata)
    metadata["images_dir"] = str(target_images_dir)
    metadata["legacy_origin_path"] = str(legacy_article.metadata_path)
    metadata["normalized_at"] = datetime.now().astimezone().isoformat()

    image_records = []
    if legacy_article.images_dir.exists():
        if target_images_dir.exists():
            shutil.rmtree(target_images_dir)
        shutil.move(str(legacy_article.images_dir), str(target_images_dir))
        moved_images = True

    for image in metadata.get("images", []):
        image_copy = dict(image)
        local_path = image_copy.get("local_path")
        filename = image_copy.get("filename")
        if local_path and filename:
            image_copy["local_path"] = str(target_images_dir / filename)
        image_records.append(image_copy)
    metadata["images"] = image_records

    target_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if legacy_article.metadata_path.exists():
        legacy_article.metadata_path.unlink()
        moved_metadata = True

    _upsert_article_paths_in_sqlite(
        database_path=database_path,
        metadata=metadata,
        target_markdown=target_markdown,
        target_metadata=target_metadata,
        target_images_dir=target_images_dir,
    )

    logger.info(
        "Olympia legacy article consolidated: %s -> %s",
        legacy_article.source_url,
        target_metadata,
    )
    return {
        "title": legacy_article.title,
        "source_url": legacy_article.source_url,
        "legacy_stem": legacy_article.stem,
        "target_stem": target_stem,
        "target_markdown": str(target_markdown),
        "target_metadata": str(target_metadata),
        "target_images_dir": str(target_images_dir),
        "moved_markdown": moved_markdown,
        "moved_metadata": moved_metadata,
        "moved_images": moved_images,
        "conflict_renamed": target_stem != legacy_article.stem,
    }


def _upsert_article_paths_in_sqlite(
    database_path: Path,
    metadata: dict,
    target_markdown: Path,
    target_metadata: Path,
    target_images_dir: Path,
) -> None:
    image_records = metadata.get("images", [])
    downloaded_images = [image for image in image_records if image.get("download_status") == "downloaded"]

    with connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id
            FROM articles
            WHERE platform = ?
              AND (
                article_uid = ?
                OR source_url = ?
                OR canonical_url = ?
                OR content_hash = ?
                OR url_hash = ?
              )
            LIMIT 1
            """,
            (
                PLATFORM,
                metadata.get("article_uid"),
                metadata.get("source_url"),
                metadata.get("canonical_url"),
                metadata.get("content_hash"),
                metadata.get("url_hash"),
            ),
        ).fetchone()

        if row:
            article_id = int(row["id"])
            connection.execute(
                """
                UPDATE articles
                SET title = ?,
                    published_date = ?,
                    markdown_path = ?,
                    metadata_path = ?,
                    images_dir = ?,
                    images_count = ?,
                    status = 'downloaded',
                    downloaded_at = COALESCE(downloaded_at, CURRENT_TIMESTAMP),
                    last_seen_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    error_message = NULL
                WHERE id = ?
                """,
                (
                    metadata.get("title") or "",
                    metadata.get("date"),
                    str(target_markdown),
                    str(target_metadata),
                    str(target_images_dir),
                    len(downloaded_images),
                    article_id,
                ),
            )
        else:
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
                    metadata.get("source_url") or "",
                    metadata.get("canonical_url") or metadata.get("source_url") or "",
                    metadata.get("title") or "",
                    metadata.get("date"),
                    metadata.get("content_hash") or "",
                    metadata.get("url_hash") or "",
                    metadata.get("article_uid") or "",
                    str(target_markdown),
                    str(target_metadata),
                    str(target_images_dir),
                    len(downloaded_images),
                ),
            )
            article_id = int(cursor.lastrowid)

        for image in image_records:
            connection.execute(
                """
                INSERT INTO article_images (
                    article_id,
                    source_url,
                    local_path,
                    filename,
                    content_type,
                    download_status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id, source_url) DO UPDATE SET
                    local_path = excluded.local_path,
                    filename = excluded.filename,
                    content_type = excluded.content_type,
                    download_status = excluded.download_status,
                    error_message = excluded.error_message
                """,
                (
                    article_id,
                    image.get("source_url") or "",
                    image.get("local_path"),
                    image.get("filename"),
                    image.get("content_type"),
                    image.get("download_status") or "pending",
                    image.get("error_message"),
                ),
            )
        connection.commit()


def _write_reports(summary: OlympiaNormalizationSummary) -> None:
    summary.final_report_json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "backup_root": str(summary.backup_root),
        "sqlite_backup_path": str(summary.sqlite_backup_path),
        "inventory_report_path": str(summary.inventory_report_path),
        "legacy_articles_found": summary.legacy_articles_found,
        "current_articles_found": summary.current_articles_found,
        "duplicates_omitted": summary.duplicates_omitted,
        "moved_articles": summary.moved_articles,
        "conflicts_detected": summary.conflicts_detected,
        "left_unmoved": summary.left_unmoved,
    }
    summary.final_report_json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Olympia legacy normalization",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Backup root: `{summary.backup_root}`",
        f"- SQLite backup: `{summary.sqlite_backup_path}`",
        f"- Inventory report: `{summary.inventory_report_path}`",
        f"- Legacy articles found: `{summary.legacy_articles_found}`",
        f"- Current articles found: `{summary.current_articles_found}`",
        f"- Duplicates omitted: `{len(summary.duplicates_omitted)}`",
        f"- Moved to 01_Olympia: `{len(summary.moved_articles)}`",
        f"- Conflicts detected: `{len(summary.conflicts_detected)}`",
        f"- Left unmoved: `{len(summary.left_unmoved)}`",
        "",
        "## Duplicates omitted",
        "",
    ]
    if summary.duplicates_omitted:
        for item in summary.duplicates_omitted:
            lines.append(
                f"- `{item['stem']}` | reasons={','.join(item['reasons'])} | {item['source_url']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Moved to 01_Olympia", ""])
    if summary.moved_articles:
        for item in summary.moved_articles:
            suffix = " (renamed _legacy)" if item["conflict_renamed"] else ""
            lines.append(f"- `{item['legacy_stem']}` -> `{item['target_stem']}`{suffix}")
    else:
        lines.append("- None")

    lines.extend(["", "## Conflicts detected", ""])
    if summary.conflicts_detected:
        for item in summary.conflicts_detected:
            lines.append(
                f"- `{item['legacy_stem']}` -> `{item['target_stem']}` | reasons={','.join(item['reasons'])}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Left unmoved", ""])
    if summary.left_unmoved:
        for item in summary.left_unmoved:
            lines.append(f"- `{item['stem']}` | {item['why']}")
    else:
        lines.append("- None")

    summary.final_report_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
