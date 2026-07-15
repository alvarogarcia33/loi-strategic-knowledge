from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config import AppConfig
from database import connect
from gig_os_news import extract_gig_os_news


PLATFORM = "gig_os"


@dataclass(frozen=True)
class GigOsDailyUpdateResult:
    run_id: int
    started_at: str
    finished_at: str
    report_json_path: Path
    report_md_path: Path
    articles_found: int
    articles_new: int
    duplicates_skipped: int
    errors: int
    candidate_urls: int
    processed_urls: int


def run_gig_os_daily_update(config: AppConfig, logger: object) -> GigOsDailyUpdateResult:
    started_at = datetime.now().astimezone().isoformat()
    run_id = _start_run(config.database_path, mode="daily_update", platform=PLATFORM)
    _add_run_event(config.database_path, run_id, "INFO", PLATFORM, None, "Daily GIG-OS update started.")

    try:
        summary = extract_gig_os_news(
            config=config,
            logger=logger,
            limit=None,
            incremental=True,
        )
        finished_at = datetime.now().astimezone().isoformat()
        report_json_path, report_md_path = _write_daily_reports(
            config=config,
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            summary=summary,
        )
        _record_summary_events(config.database_path, run_id, summary)
        _finish_run(
            database_path=config.database_path,
            run_id=run_id,
            status="completed" if summary.errors == 0 else "completed_with_errors",
            articles_found=summary.articles_found,
            articles_new=summary.articles_new,
            articles_skipped=summary.duplicates_skipped,
            articles_failed=summary.errors,
            error_message=None if summary.errors == 0 else "; ".join(summary.error_messages[:10]),
        )
        return GigOsDailyUpdateResult(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            articles_found=summary.articles_found,
            articles_new=summary.articles_new,
            duplicates_skipped=summary.duplicates_skipped,
            errors=summary.errors,
            candidate_urls=len(summary.candidate_urls),
            processed_urls=len(summary.processed_urls),
        )
    except Exception as exc:
        _add_run_event(config.database_path, run_id, "ERROR", PLATFORM, None, f"Daily GIG-OS update failed: {exc}")
        _finish_run(
            database_path=config.database_path,
            run_id=run_id,
            status="failed",
            articles_found=0,
            articles_new=0,
            articles_skipped=0,
            articles_failed=1,
            error_message=str(exc),
        )
        raise


def _start_run(database_path: Path, mode: str, platform: str) -> int:
    with connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO runs (mode, platform, status)
            VALUES (?, ?, 'running')
            """,
            (mode, platform),
        )
        connection.commit()
        return int(cursor.lastrowid)


def _finish_run(
    database_path: Path,
    run_id: int,
    status: str,
    articles_found: int,
    articles_new: int,
    articles_skipped: int,
    articles_failed: int,
    error_message: str | None,
) -> None:
    with connect(database_path) as connection:
        connection.execute(
            """
            UPDATE runs
            SET finished_at = CURRENT_TIMESTAMP,
                status = ?,
                articles_found = ?,
                articles_new = ?,
                articles_skipped = ?,
                articles_failed = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                status,
                articles_found,
                articles_new,
                articles_skipped,
                articles_failed,
                error_message,
                run_id,
            ),
        )
        connection.commit()


def _add_run_event(
    database_path: Path,
    run_id: int,
    level: str,
    platform: str | None,
    article_url: str | None,
    message: str,
) -> None:
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO run_events (run_id, level, platform, article_url, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, level, platform, article_url, message),
        )
        connection.commit()


def _record_summary_events(database_path: Path, run_id: int, summary: object) -> None:
    _add_run_event(
        database_path,
        run_id,
        "INFO",
        PLATFORM,
        None,
        (
            f"Discovery finished. found={summary.articles_found} "
            f"candidates={len(summary.candidate_urls)} duplicates={summary.duplicates_skipped}"
        ),
    )
    for url in summary.created_metadata:
        _add_run_event(database_path, run_id, "INFO", PLATFORM, None, f"Metadata created: {url}")
    for reason in summary.skip_reasons:
        _add_run_event(database_path, run_id, "INFO", PLATFORM, None, f"Skipped: {reason}")
    for message in summary.error_messages:
        _add_run_event(database_path, run_id, "ERROR", PLATFORM, None, message)


def _write_daily_reports(
    config: AppConfig,
    run_id: int,
    started_at: str,
    finished_at: str,
    summary: object,
) -> tuple[Path, Path]:
    report_root = config.output_root / "08_Reportes"
    report_root.mkdir(parents=True, exist_ok=True)

    day_stamp = datetime.now().strftime("%Y-%m-%d")
    time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_json_path = report_root / f"gig_os_daily_update_{day_stamp}_{time_stamp}.json"
    report_md_path = report_root / f"gig_os_daily_update_{day_stamp}_{time_stamp}.md"

    payload = {
        "run_id": run_id,
        "platform": PLATFORM,
        "started_at": started_at,
        "finished_at": finished_at,
        "articles_found": summary.articles_found,
        "articles_new": summary.articles_new,
        "duplicates_skipped": summary.duplicates_skipped,
        "errors": summary.errors,
        "candidate_urls": summary.candidate_urls,
        "processed_urls": summary.processed_urls,
        "found_urls": summary.found_urls,
        "duplicate_urls": summary.duplicate_urls,
        "created_markdown": summary.created_markdown,
        "created_metadata": summary.created_metadata,
        "created_images": summary.created_images,
        "error_messages": summary.error_messages,
        "skip_reasons": summary.skip_reasons,
        "listing_pages_scanned": summary.listing_pages_scanned,
    }
    report_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# GIG-OS daily update",
        "",
        f"- Run ID: `{run_id}`",
        f"- Started at: `{started_at}`",
        f"- Finished at: `{finished_at}`",
        f"- Articles found: `{summary.articles_found}`",
        f"- New articles: `{summary.articles_new}`",
        f"- Duplicates skipped: `{summary.duplicates_skipped}`",
        f"- Errors: `{summary.errors}`",
        f"- Candidate URLs: `{len(summary.candidate_urls)}`",
        f"- Processed URLs: `{len(summary.processed_urls)}`",
        "",
        "## Listing pages scanned",
        "",
    ]
    if summary.listing_pages_scanned:
        lines.extend(f"- `{url}`" for url in summary.listing_pages_scanned)
    else:
        lines.append("- None")

    lines.extend(["", "## New Markdown files", ""])
    if summary.created_markdown:
        lines.extend(f"- `{path}`" for path in summary.created_markdown)
    else:
        lines.append("- None")

    lines.extend(["", "## Errors", ""])
    if summary.error_messages:
        lines.extend(f"- {message}" for message in summary.error_messages)
    else:
        lines.append("- None")

    report_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_json_path, report_md_path
