from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS platforms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    base_url TEXT,
    last_full_scan_at TEXT,
    last_incremental_scan_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    source_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    published_date TEXT,
    content_hash TEXT NOT NULL,
    url_hash TEXT NOT NULL,
    article_uid TEXT NOT NULL,
    markdown_path TEXT,
    metadata_path TEXT,
    images_dir TEXT,
    images_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'discovered',
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    downloaded_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (platform) REFERENCES platforms(name) ON UPDATE CASCADE,
    UNIQUE (platform, source_url),
    UNIQUE (platform, canonical_url),
    UNIQUE (platform, content_hash),
    UNIQUE (platform, url_hash),
    UNIQUE (article_uid)
);

CREATE TABLE IF NOT EXISTS article_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT,
    filename TEXT,
    content_type TEXT,
    download_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    UNIQUE (article_id, source_url),
    UNIQUE (article_id, local_path)
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    mode TEXT NOT NULL,
    platform TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    articles_found INTEGER NOT NULL DEFAULT 0,
    articles_new INTEGER NOT NULL DEFAULT 0,
    articles_skipped INTEGER NOT NULL DEFAULT 0,
    articles_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    FOREIGN KEY (platform) REFERENCES platforms(name) ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS run_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    platform TEXT,
    article_url TEXT,
    message TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
    FOREIGN KEY (platform) REFERENCES platforms(name) ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_articles_platform_published_date
    ON articles(platform, published_date);

CREATE INDEX IF NOT EXISTS idx_articles_status
    ON articles(status);

CREATE INDEX IF NOT EXISTS idx_articles_article_uid
    ON articles(article_uid);

CREATE INDEX IF NOT EXISTS idx_article_images_article_id
    ON article_images(article_id);

CREATE INDEX IF NOT EXISTS idx_runs_started_at
    ON runs(started_at);

CREATE INDEX IF NOT EXISTS idx_runs_status
    ON runs(status);

CREATE INDEX IF NOT EXISTS idx_run_events_run_id
    ON run_events(run_id);
"""


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def initialize_database(database_path: Path, platform_base_urls: dict[str, str]) -> None:
    with connect(database_path) as connection:
        connection.executescript(SCHEMA_SQL)
        for platform_name, base_url in platform_base_urls.items():
            connection.execute(
                """
                INSERT INTO platforms (name, base_url)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    base_url = excluded.base_url,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (platform_name, base_url),
            )
        connection.commit()


def get_schema_details(database_path: Path) -> dict[str, list[str]]:
    with connect(database_path) as connection:
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        details: dict[str, list[str]] = {}
        for table in tables:
            table_name = table["name"]
            columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            details[table_name] = [
                f"{column['name']} {column['type']}".strip() for column in columns
            ]
        return details


def get_indexes(database_path: Path) -> dict[str, list[str]]:
    with connect(database_path) as connection:
        indexes = connection.execute(
            """
            SELECT tbl_name, name
            FROM sqlite_master
            WHERE type = 'index'
              AND name NOT LIKE 'sqlite_autoindex%'
            ORDER BY tbl_name, name
            """
        ).fetchall()
        result: dict[str, list[str]] = {}
        for index in indexes:
            result.setdefault(index["tbl_name"], []).append(index["name"])
        return result
