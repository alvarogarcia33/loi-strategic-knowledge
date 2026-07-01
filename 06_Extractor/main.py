from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import ensure_required_directories, load_config
from database import get_indexes, get_schema_details, initialize_database
from gig_os_daily_update import run_gig_os_daily_update
from gig_os_login import run_gig_os_login_test
from gig_os_news import DEFAULT_LIMIT as GIG_OS_DEFAULT_LIMIT, extract_gig_os_news
from gig_os_structure import discover_gig_os_structure
from logging_config import configure_logging
from olympia_daily_update import run_olympia_daily_update
from olympia_legacy_normalizer import normalize_olympia_legacy
from olympia_login import run_olympia_login_test
from olympia_news import DEFAULT_LIMIT, extract_olympia_news
from olympia_structure import discover_olympia_structure


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LOI AI document extractor")
    parser.add_argument(
        "--platform",
        choices=("olympia", "gig_os"),
        help="Platform to operate on.",
    )
    parser.add_argument(
        "--login-test",
        action="store_true",
        help="Run an authentication test for the selected platform.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed event sequence for login diagnostics.",
    )
    parser.add_argument(
        "--discover-structure",
        action="store_true",
        help="Discover the authenticated platform content structure without scraping articles.",
    )
    parser.add_argument(
        "--extract-news",
        action="store_true",
        help="Extract a limited number of Olympia news articles.",
    )
    parser.add_argument(
        "--normalize-olympia-legacy",
        action="store_true",
        help="Consolidate legacy Olympia content from 02_Olympia into 01_Olympia with backup and report.",
    )
    parser.add_argument(
        "--daily-update",
        action="store_true",
        help="Run the daily Olympia update: detect and store only new news articles.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Maximum number of articles to extract in safe mode. "
            f"Default Olympia: {DEFAULT_LIMIT}. Default GIG-OS: {GIG_OS_DEFAULT_LIMIT}."
        ),
    )
    return parser.parse_args()


def enable_debug_logging(logger: object) -> None:
    import logging

    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)


def _format_path_status(paths: list[Path]) -> str:
    lines = []
    for path in paths:
        status = "OK" if path.exists() else "MISSING"
        lines.append(f"  [{status}] {path}")
    return "\n".join(lines)


def _format_schema(schema: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for table_name, columns in schema.items():
        lines.append(f"  {table_name}")
        for column in columns:
            lines.append(f"    - {column}")
    return "\n".join(lines)


def _format_indexes(indexes: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for table_name, table_indexes in indexes.items():
        lines.append(f"  {table_name}")
        for index_name in table_indexes:
            lines.append(f"    - {index_name}")
    return "\n".join(lines) if lines else "  No custom indexes found."


def bootstrap_system(initialize_sqlite: bool = True) -> tuple[object, list[Path], object]:
    config = load_config()
    required_paths = ensure_required_directories(config)
    logger = configure_logging(config.log_dir, config.log_level)

    logger.info("Starting LOI AI extractor infrastructure bootstrap.")
    if initialize_sqlite:
        initialize_database(
            config.database_path,
            {
                config.gig_os.name: config.gig_os.base_url,
                config.olympia.name: config.olympia.base_url,
            },
        )
    else:
        logger.info("SQLite initialization skipped for read-only discovery command.")
    logger.info("Infrastructure bootstrap completed successfully.")
    return config, required_paths, logger


def print_system_summary(config: object, required_paths: list[Path]) -> None:
    schema = get_schema_details(config.database_path)
    indexes = get_indexes(config.database_path)

    print("\nLOI AI - Extractor")
    print("=" * 34)
    print("\nConfiguracion cargada:")
    print(f"  Project root: {config.project_root}")
    print(f"  Output root:  {config.output_root}")
    print(f"  Database:     {config.database_path}")
    print(f"  Log dir:      {config.log_dir}")
    print(f"  Log level:    {config.log_level}")
    print(f"  Headless:     {config.headless}")
    print(f"  Images:       {config.download_images}")

    print("\nRutas detectadas:")
    print(_format_path_status(required_paths))

    print("\nBase SQLite:")
    print(f"  [OK] {config.database_path}")

    print("\nTablas SQL:")
    print(_format_schema(schema))

    print("\nIndices SQL:")
    print(_format_indexes(indexes))


def main() -> None:
    args = parse_args()
    config, required_paths, logger = bootstrap_system(
        initialize_sqlite=not args.discover_structure
    )
    if args.debug:
        enable_debug_logging(logger)
        logger.debug("Debug mode enabled.")

    if args.login_test:
        if args.platform == "olympia":
            platform_name = "Olympia"
            runner = run_olympia_login_test
        elif args.platform == "gig_os":
            platform_name = "GIG-OS"
            runner = run_gig_os_login_test
        else:
            print("Error: --login-test requires --platform olympia or --platform gig_os.")
            sys.exit(2)

        try:
            result = runner(config, logger)
        except Exception as exc:
            logger.error("%s login test could not start: %s", platform_name, exc)
            print(f"\n{platform_name} login test")
            print("=" * 34)
            print("  Success:      False")
            print(f"  Message:      {exc}")
            sys.exit(1)

        print(f"\n{platform_name} login test")
        print("=" * 34)
        print(f"  Success:      {result.success}")
        print(f"  Reused state: {result.reused_state}")
        print(f"  State path:   {result.state_path}")
        print(f"  Final URL:    {result.final_url}")
        print(f"  Message:      {result.message}")
        if result.screenshot_path:
            print(f"  Screenshot:   {result.screenshot_path}")
        sys.exit(0 if result.success else 1)

    if args.discover_structure:
        if args.platform == "olympia":
            platform_name = "Olympia"
            runner = discover_olympia_structure
            json_report = r"C:\Users\alvar\Documents\LOI_AI\06_Extractor\data\olympia_structure_report.json"
            md_report = r"C:\Users\alvar\Documents\LOI_AI\08_Reportes\olympia_structure_report.md"
        elif args.platform == "gig_os":
            platform_name = "GIG-OS"
            runner = discover_gig_os_structure
            json_report = r"C:\Users\alvar\Documents\LOI_AI\06_Extractor\data\gig_os_structure_report.json"
            md_report = r"C:\Users\alvar\Documents\LOI_AI\08_Reportes\gig_os_structure_report.md"
        else:
            print("Error: --discover-structure requires --platform olympia or --platform gig_os.")
            sys.exit(2)

        try:
            report = runner(config, logger)
        except Exception as exc:
            logger.error("%s structure discovery failed: %s", platform_name, exc)
            print(f"\n{platform_name} structure discovery")
            print("=" * 34)
            print("  Success: False")
            print(f"  Message: {exc}")
            sys.exit(1)

        print(f"\n{platform_name} structure discovery")
        print("=" * 34)
        print(f"  Success: True")
        print(f"  URLs found: {report.total_internal_links}")
        print(f"  Content sections: {len(report.content_sections)}")
        print(f"  JSON report: {json_report}")
        print(f"  Markdown report: {md_report}")
        print("\nPossible content sections:")
        if report.content_sections:
            for section in report.content_sections:
                print(f"  - {section.text} -> {section.href}")
        else:
            print("  - None found")
        print("\nScreenshots:")
        for screenshot in report.screenshots:
            print(f"  - {screenshot.name}: {screenshot.path}")
        print("\nRecommended strategy:")
        for item in report.recommended_strategy:
            print(f"  - {item}")
        sys.exit(0)

    if args.extract_news:
        if args.platform == "olympia":
            platform_name = "Olympia"
            runner = extract_olympia_news
        elif args.platform == "gig_os":
            platform_name = "GIG-OS"
            runner = extract_gig_os_news
        else:
            print("Error: --extract-news requires --platform olympia or --platform gig_os.")
            sys.exit(2)

        try:
            summary = runner(config, logger, limit=args.limit)
        except Exception as exc:
            logger.error("%s news extraction could not start: %s", platform_name, exc)
            print(f"\n{platform_name} news extraction")
            print("=" * 34)
            print("  Success: False")
            print(f"  Message: {exc}")
            sys.exit(1)

        print(f"\n{platform_name} news extraction")
        print("=" * 34)
        print(f"  Articles found:       {summary.articles_found}")
        print(f"  New articles:         {summary.articles_new}")
        print(f"  Duplicates skipped:   {summary.duplicates_skipped}")
        print(f"  Errors:               {summary.errors}")
        print(f"  Candidate URLs:       {len(summary.candidate_urls)}")
        print(f"  Processed URLs:       {len(summary.processed_urls)}")
        print("\nDiscovered URLs:")
        for url in summary.found_urls:
            print(f"  - {url}")
        print("\nDuplicate URLs:")
        if summary.duplicate_urls:
            for url in summary.duplicate_urls:
                print(f"  - {url}")
        else:
            print("  - None")
        print("\nFinal candidate URLs:")
        if summary.candidate_urls:
            for url in summary.candidate_urls:
                print(f"  - {url}")
        else:
            print("  - None")
        print("\nProcessed URLs:")
        if summary.processed_urls:
            for url in summary.processed_urls:
                print(f"  - {url}")
        else:
            print("  - None")
        print("\nCreated Markdown files:")
        if summary.created_markdown:
            for path in summary.created_markdown:
                print(f"  - {path}")
        else:
            print("  - None")
        print("\nCreated metadata files:")
        if summary.created_metadata:
            for path in summary.created_metadata:
                print(f"  - {path}")
        else:
            print("  - None")
        print("\nCreated image files:")
        if summary.created_images:
            for path in summary.created_images:
                print(f"  - {path}")
        else:
            print("  - None")
        if summary.error_messages:
            print("\nErrors:")
            for message in summary.error_messages:
                print(f"  - {message}")
        if summary.skip_reasons:
            print("\nSkip reasons:")
            for message in summary.skip_reasons:
                print(f"  - {message}")
        if getattr(summary, "listing_pages_scanned", None):
            print("\nListing pages scanned:")
            for url in summary.listing_pages_scanned:
                print(f"  - {url}")
        sys.exit(0 if summary.errors == 0 else 1)

    if args.normalize_olympia_legacy:
        if args.platform != "olympia":
            print("Error: --normalize-olympia-legacy is currently implemented only for --platform olympia.")
            sys.exit(2)

        try:
            summary = normalize_olympia_legacy(config, logger)
        except Exception as exc:
            logger.error("Olympia legacy normalization failed: %s", exc)
            print("\nOlympia legacy normalization")
            print("=" * 34)
            print("  Success: False")
            print(f"  Message: {exc}")
            sys.exit(1)

        print("\nOlympia legacy normalization")
        print("=" * 34)
        print("  Success: True")
        print(f"  Legacy articles found: {summary.legacy_articles_found}")
        print(f"  Current articles found: {summary.current_articles_found}")
        print(f"  Duplicates omitted: {len(summary.duplicates_omitted)}")
        print(f"  Moved to 01_Olympia: {len(summary.moved_articles)}")
        print(f"  Conflicts detected: {len(summary.conflicts_detected)}")
        print(f"  Left unmoved: {len(summary.left_unmoved)}")
        print(f"  Backup root: {summary.backup_root}")
        print(f"  SQLite backup: {summary.sqlite_backup_path}")
        print(f"  Inventory report: {summary.inventory_report_path}")
        print(f"  Final JSON report: {summary.final_report_json_path}")
        print(f"  Final Markdown report: {summary.final_report_md_path}")
        sys.exit(0)

    if args.daily_update:
        if args.platform == "olympia":
            platform_name = "Olympia"
            runner = run_olympia_daily_update
        elif args.platform == "gig_os":
            platform_name = "GIG-OS"
            runner = run_gig_os_daily_update
        else:
            print("Error: --daily-update requires --platform olympia or --platform gig_os.")
            sys.exit(2)

        try:
            result = runner(config, logger)
        except Exception as exc:
            logger.error("%s daily update failed: %s", platform_name, exc)
            print(f"\n{platform_name} daily update")
            print("=" * 34)
            print("  Success: False")
            print(f"  Message: {exc}")
            sys.exit(1)

        print(f"\n{platform_name} daily update")
        print("=" * 34)
        print("  Success: True")
        print(f"  Run ID:               {result.run_id}")
        print(f"  Started at:           {result.started_at}")
        print(f"  Finished at:          {result.finished_at}")
        print(f"  Articles found:       {result.articles_found}")
        print(f"  New articles:         {result.articles_new}")
        print(f"  Duplicates skipped:   {result.duplicates_skipped}")
        print(f"  Errors:               {result.errors}")
        print(f"  Candidate URLs:       {result.candidate_urls}")
        print(f"  Processed URLs:       {result.processed_urls}")
        print(f"  JSON report:          {result.report_json_path}")
        print(f"  Markdown report:      {result.report_md_path}")
        sys.exit(0 if result.errors == 0 else 1)

    print_system_summary(config, required_paths)


if __name__ == "__main__":
    main()
