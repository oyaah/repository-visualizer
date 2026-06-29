from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CacheEntry:
    summary: str
    content_hash: str
    model: str


class SummaryCache:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(".repository_visualizer_cache.sqlite")
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                  key TEXT PRIMARY KEY,
                  file_path TEXT NOT NULL,
                  content_hash TEXT NOT NULL,
                  provider TEXT NOT NULL DEFAULT 'openai',
                  prompt_version TEXT NOT NULL,
                  model TEXT NOT NULL,
                  summary TEXT NOT NULL,
                  created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(summaries)")}
            if "provider" not in columns:
                conn.execute("ALTER TABLE summaries ADD COLUMN provider TEXT NOT NULL DEFAULT 'openai'")

    def get(self, key: str) -> CacheEntry | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary, content_hash, model FROM summaries WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return CacheEntry(summary=row[0], content_hash=row[1], model=row[2])

    def set(self, key: str, file_path: str, content_hash: str, prompt_version: str, model: str, summary: str, provider: str = "openai") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO summaries
                  (key, file_path, content_hash, provider, prompt_version, model, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (key, file_path, content_hash, provider, prompt_version, model, summary),
            )
