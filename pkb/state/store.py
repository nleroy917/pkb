import json
import sqlite3

from datetime import datetime
from pathlib import Path
from typing import Optional

from pkb.core.exceptions import StateStoreException
from pkb.core.models import FileState


class StateStore:
    """
    SQLite-based storage for tracking file states.
    Used to detect changes (added/modified/deleted) across indexing runs.
    """

    def __init__(self, db_path: str | Path = "~/.pkb/state.db"):
        """
        Initialize the state store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_state (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    mtime REAL NOT NULL,
                    size INTEGER NOT NULL,
                    metadata TEXT,
                    last_indexed TEXT NOT NULL,
                    UNIQUE(source, file_path)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_source ON file_state(source)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_path ON file_state(file_path)
            """)
            conn.commit()

    def save_state(self, state: FileState) -> None:
        """
        Save or update a file state.

        Args:
            state: FileState to save
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO file_state
                    (id, source, file_path, content_hash, mtime, size, metadata, last_indexed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        state.id,
                        state.source,
                        state.file_path,
                        state.content_hash,
                        state.mtime,
                        state.size,
                        json.dumps(state.metadata),
                        state.last_indexed.isoformat(),
                    ),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to save state: {e}")

    def get_state(self, id: str) -> Optional[FileState]:
        """
        Get file state by ID.

        Args:
            id: File state ID

        Returns:
            FileState if found, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM file_state WHERE id = ?", (id,))
                row = cursor.fetchone()

                if row is None:
                    return None

                return self._row_to_state(row)
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to get state: {e}")

    def get_states_by_source(self, source: str) -> list[FileState]:
        """
        Get all file states for a given source.

        Args:
            source: Data source name

        Returns:
            List of FileState objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM file_state WHERE source = ?", (source,)
                )
                rows = cursor.fetchall()

                return [self._row_to_state(row) for row in rows]
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to get states by source: {e}")

    def get_all_states(self) -> list[FileState]:
        """
        Get all file states.

        Returns:
            List of all FileState objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM file_state")
                rows = cursor.fetchall()

                return [self._row_to_state(row) for row in rows]
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to get all states: {e}")

    def delete_state(self, id: str) -> bool:
        """
        Delete a file state.

        Args:
            id: File state ID

        Returns:
            True if deleted, False if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM file_state WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to delete state: {e}")

    def delete_states_by_source(self, source: str) -> int:
        """
        Delete all file states for a given source.

        Args:
            source: Data source name

        Returns:
            Number of states deleted
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM file_state WHERE source = ?", (source,)
                )
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to delete states by source: {e}")

    def clear(self) -> None:
        """
        Delete all file states.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM file_state")
                conn.commit()
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to clear state store: {e}")

    def get_state_count(self, source: Optional[str] = None) -> int:
        """
        Get count of stored states.

        Args:
            source: Optional source filter

        Returns:
            Number of states
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if source:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM file_state WHERE source = ?", (source,)
                    )
                else:
                    cursor = conn.execute("SELECT COUNT(*) FROM file_state")

                return cursor.fetchone()[0]
        except sqlite3.Error as e:
            raise StateStoreException(f"Failed to get state count: {e}")

    def _row_to_state(self, row: sqlite3.Row) -> FileState:
        """
        Convert database row to FileState object.
        """
        return FileState(
            id=row["id"],
            source=row["source"],
            file_path=row["file_path"],
            content_hash=row["content_hash"],
            mtime=row["mtime"],
            size=row["size"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            last_indexed=datetime.fromisoformat(row["last_indexed"]),
        )

    def __repr__(self) -> str:
        return f"StateStore(db_path={self.db_path}, count={self.get_state_count()})"
