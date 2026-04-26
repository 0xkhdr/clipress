import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

_DDL = """
CREATE TABLE IF NOT EXISTS history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    command           TEXT NOT NULL,
    strategy          TEXT NOT NULL,
    source            TEXT NOT NULL,
    raw_output        TEXT NOT NULL,
    compressed_output TEXT NOT NULL,
    raw_tokens        INTEGER NOT NULL,
    compressed_tokens INTEGER NOT NULL,
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_history_command_created ON history(command, created_at DESC);
"""


class ArchiveStore:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.dir_path = Path(workspace) / ".clipress"
        self.db_path = self.dir_path / "history.db"
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.dir_path.mkdir(mode=0o700, parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._conn = conn
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript(_DDL)
        conn.commit()

    def record(
        self,
        command: str,
        strategy: str,
        source: str,
        raw_output: str,
        compressed_output: str,
        raw_tokens: int,
        compressed_tokens: int,
        max_entries: int = 100,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO history
                   (command, strategy, source, raw_output, compressed_output,
                    raw_tokens, compressed_tokens, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    command,
                    strategy,
                    source,
                    raw_output,
                    compressed_output,
                    raw_tokens,
                    compressed_tokens,
                    now,
                ),
            )
            if max_entries > 0:
                conn.execute(
                    """DELETE FROM history
                       WHERE id NOT IN (
                           SELECT id FROM history ORDER BY id DESC LIMIT ?
                       )""",
                    (max_entries,),
                )
            conn.commit()

    def latest(self, command: str | None = None) -> dict[str, Any] | None:
        conn = self._get_conn()
        if command:
            row = conn.execute(
                """SELECT * FROM history
                   WHERE command = ?
                   ORDER BY id DESC
                   LIMIT 1""",
                (command,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM history ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def by_id(self, entry_id: int) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM history WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT id, command, strategy, source, raw_tokens,
                      compressed_tokens, created_at
               FROM history
               ORDER BY id DESC
               LIMIT ?""",
            (max(1, limit),),
        ).fetchall()
        return [dict(r) for r in rows]
