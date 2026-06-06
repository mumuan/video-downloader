import os
import sqlite3
import threading
import time
from datetime import datetime

from src.widgets.download_list_widget import DownloadItem


class DownloadHistory:
    """Manages persistent download records using SQLite."""

    _UPDATE_FIELDS = {
        "title",
        "output_filename",
        "source_site",
        "state",
        "progress",
        "file_path",
        "url",
        "direct_url",
        "size_str",
        "error_message",
        "finished_at",
        "duration",
        "thumbnail",
    }

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database and create schema if not exists."""
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS download_records (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    output_filename TEXT NOT NULL,
                    source_site TEXT NOT NULL,
                    state TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    file_path TEXT,
                    url TEXT,
                    direct_url TEXT,
                    size_str TEXT DEFAULT '',
                    error_message TEXT,
                    added_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    finished_at INTEGER,
                    duration INTEGER DEFAULT 0,
                    thumbnail TEXT
                )
            """)

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_state ON download_records(state)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_added_at ON download_records(added_at DESC)"
            )

            conn.commit()
            conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def add_record(
        self,
        item: DownloadItem,
        url: str | None = None,
        direct_url: str | None = None,
        duration: int = 0,
        thumbnail: str = "",
    ) -> None:
        """Add a new download record."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = int(time.time())
            cursor.execute(
                """
                INSERT OR REPLACE INTO download_records
                (id, title, output_filename, source_site, state, progress,
                 file_path, url, direct_url, size_str, error_message,
                 added_at, updated_at, finished_at, duration, thumbnail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    item.id,
                    item.title,
                    item.output_filename,
                    item.source_site,
                    item.state,
                    item.progress,
                    item.file_path,
                    url,
                    direct_url,
                    item.size_str,
                    item.error_message,
                    now,
                    now,
                    None,
                    duration,
                    thumbnail,
                ),
            )

            conn.commit()
            conn.close()

    def update_record(self, item_id: str, **kwargs) -> None:
        """Update an existing download record."""
        if not kwargs:
            return

        invalid_fields = set(kwargs) - self._UPDATE_FIELDS
        if invalid_fields:
            invalid = ", ".join(sorted(invalid_fields))
            raise ValueError(f"Unsupported download history field(s): {invalid}")

        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Always update updated_at
            kwargs["updated_at"] = int(time.time())

            set_clause = ", ".join(f"{key} = ?" for key in kwargs.keys())
            values = list(kwargs.values())
            values.append(item_id)

            cursor.execute(
                f"UPDATE download_records SET {set_clause} WHERE id = ?", values
            )

            conn.commit()
            conn.close()

    def get_record(self, item_id: str) -> dict | None:
        """Get a single download record by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM download_records WHERE id = ?", (item_id,))
        row = cursor.fetchone()

        conn.close()

        if row:
            return dict(row)
        return None

    def delete_record(self, item_id: str) -> None:
        """Delete a download record."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM download_records WHERE id = ?", (item_id,))

            conn.commit()
            conn.close()

    def get_all_records(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all download records with pagination."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM download_records ORDER BY added_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def get_by_state(self, state: str) -> list[dict]:
        """Get download records by state."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM download_records WHERE state = ? ORDER BY added_at DESC",
            (state,),
        )
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def get_incomplete_downloads(self) -> list[dict]:
        """Get all incomplete downloads (paused or downloading)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM download_records
            WHERE state IN ('paused', 'downloading')
            ORDER BY added_at DESC
        """
        )
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def get_finished_downloads(self) -> list[dict]:
        """Get all finished downloads."""
        return self.get_by_state("finished")

    def get_failed_downloads(self) -> list[dict]:
        """Get all failed downloads."""
        return self.get_by_state("error")

    def record_exists(self, item_id: str) -> bool:
        """Check if a record exists."""
        return self.get_record(item_id) is not None

    def cleanup_orphaned_records(self, output_dir: str) -> int:
        """Remove records where the file doesn't exist. Returns count of cleaned records."""
        records = self.get_all_records(limit=10000)
        cleaned = 0

        for record in records:
            if record["state"] != "finished":
                continue

            filename = record["output_filename"]
            full_path = os.path.join(output_dir, filename)

            if not os.path.exists(full_path):
                self.delete_record(record["id"])
                cleaned += 1

        return cleaned

    def get_downloaded_ids(self) -> set[str]:
        """Get set of all finished download IDs."""
        finished = self.get_finished_downloads()
        return {record["id"] for record in finished}

    def search_by_title(self, query: str, limit: int = 100) -> list[dict]:
        """Search download records by title."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM download_records
            WHERE title LIKE ?
            ORDER BY added_at DESC
            LIMIT ?
        """,
            (f"%{query}%", limit),
        )
        rows = cursor.fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def get_statistics(self) -> dict:
        """Get download statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as total FROM download_records")
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) as finished FROM download_records WHERE state = 'finished'"
        )
        finished = cursor.fetchone()["finished"]

        cursor.execute(
            "SELECT COUNT(*) as failed FROM download_records WHERE state = 'error'"
        )
        failed = cursor.fetchone()["failed"]

        cursor.execute(
            "SELECT COUNT(*) as paused FROM download_records WHERE state = 'paused'"
        )
        paused = cursor.fetchone()["paused"]

        conn.close()

        return {
            "total": total,
            "finished": finished,
            "failed": failed,
            "paused": paused,
            "success_rate": (finished / total * 100) if total > 0 else 0,
        }
