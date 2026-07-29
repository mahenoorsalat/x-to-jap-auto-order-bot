import sqlite3
import os
import time
from typing import Optional, Set

DB_FILE = "processed_posts.db"

class StateManager:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite table for storing processed posts."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_posts (
                    guid TEXT PRIMARY KEY,
                    target_url TEXT,
                    order_id TEXT,
                    service_id TEXT,
                    processed_at INTEGER
                )
            """)
            conn.commit()

    def is_processed(self, guid: str) -> bool:
        """Check if post GUID has already been processed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_posts WHERE guid = ?", (guid,))
            return cursor.fetchone() is not None

    def mark_processed(self, guid: str, target_url: Optional[str] = None, order_id: Optional[str] = None, service_id: Optional[str] = None):
        """Record post GUID as processed to prevent double triggers."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO processed_posts (guid, target_url, order_id, service_id, processed_at) VALUES (?, ?, ?, ?, ?)",
                (guid, target_url or "", order_id or "", service_id or "", int(time.time()))
            )
            conn.commit()

    def get_all_processed_guids(self) -> Set[str]:
        """Fetch all processed post GUIDs."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT guid FROM processed_posts")
            return {row[0] for row in cursor.fetchall()}
