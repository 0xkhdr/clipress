import os
import sys
import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

INITIAL_CONFIDENCE = 0.50
CONFIDENCE_GAIN = 0.08
CONFIDENCE_LOSS = 0.20
HOT_THRESHOLD = 0.85
LOCKED_THRESHOLD = 0.95
HOT_CALL_THRESHOLD = 10

_SESSION_PIDS: set[int] = set()

_DDL = """
CREATE TABLE IF NOT EXISTS entries (
    command             TEXT PRIMARY KEY,
    source              TEXT    DEFAULT 'learned',
    strategy            TEXT,
    calls               INTEGER DEFAULT 0,
    confidence          REAL    DEFAULT 0.5,
    avg_raw_tokens      REAL    DEFAULT 0,
    avg_compressed_tokens REAL  DEFAULT 0,
    compression_ratio   REAL    DEFAULT 0,
    hot                 INTEGER DEFAULT 0,
    user_override       INTEGER DEFAULT 0,
    last_seen           TEXT,
    params              TEXT    DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS stats (
    key   TEXT PRIMARY KEY,
    value TEXT
);
INSERT OR IGNORE INTO stats (key, value) VALUES
    ('total_commands_learned', '0'),
    ('total_tokens_saved',     '0'),
    ('session_count',          '0');
"""


class Learner:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.dir_path = Path(workspace) / ".clipress"
        self.db_path = self.dir_path / "registry.db"
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()
        self._increment_session()

    # ------------------------------------------------------------------
    # Internal DB helpers
    # ------------------------------------------------------------------

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
        try:
            conn = self._get_conn()
            conn.executescript(_DDL)
            conn.commit()
            self._migrate_from_json()
        except Exception as e:
            if os.environ.get("CLIPRESS_DEBUG"):
                print(f"clipress: db init failed: {e}", file=sys.stderr)

    def _migrate_from_json(self) -> None:
        """One-time migration from legacy registry.json → registry.db."""
        json_path = self.dir_path / "registry.json"
        if not json_path.exists():
            return
        # Skip if db already has entries (migration already done)
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        if count > 0:
            return
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = data.get("entries", {})
            stats = data.get("stats", {})
            for cmd, e in entries.items():
                conn.execute(
                    """INSERT OR IGNORE INTO entries
                       (command, source, strategy, calls, confidence,
                        avg_raw_tokens, avg_compressed_tokens, compression_ratio,
                        hot, user_override, last_seen, params)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        cmd,
                        e.get("source", "learned"),
                        e.get("strategy", "generic"),
                        e.get("calls", 0),
                        e.get("confidence", INITIAL_CONFIDENCE),
                        e.get("avg_raw_tokens", 0),
                        e.get("avg_compressed_tokens", 0),
                        e.get("compression_ratio", 0),
                        int(e.get("hot", False)),
                        int(e.get("user_override", False)),
                        e.get("last_seen", ""),
                        json.dumps(e.get("params", {})),
                    ),
                )
            for key in ("total_commands_learned", "total_tokens_saved", "session_count"):
                val = stats.get(key, 0)
                conn.execute(
                    "UPDATE stats SET value = ? WHERE key = ?", (str(val), key)
                )
            conn.commit()
            # Rename json file so migration doesn't run again
            json_path.rename(json_path.with_suffix(".json.migrated"))
        except Exception as e:
            if os.environ.get("CLIPRESS_DEBUG"):
                print(f"clipress: json migration failed: {e}", file=sys.stderr)

    def _increment_session(self) -> None:
        pid = os.getpid()
        if pid not in _SESSION_PIDS:
            _SESSION_PIDS.add(pid)
            try:
                conn = self._get_conn()
                conn.execute(
                    "UPDATE stats SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) WHERE key = 'session_count'"
                )
                conn.commit()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, command: str) -> dict[str, Any] | None:
        try:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT source, strategy, calls, confidence, hot, user_override, params
                   FROM entries WHERE command = ?""",
                (command,),
            ).fetchone()
            if not row:
                return None
            entry = {
                "source": row["source"],
                "strategy": row["strategy"],
                "calls": row["calls"],
                "confidence": row["confidence"],
                "hot": bool(row["hot"]),
                "user_override": bool(row["user_override"]),
                "params": json.loads(row["params"] or "{}"),
            }
            if entry.get("user_override") or entry.get("confidence", 0) >= HOT_THRESHOLD:
                return entry
            return None
        except Exception:
            return None

    def record(
        self, command: str, shape: str, raw_tokens: int, compressed_tokens: int
    ) -> None:
        try:
            saved = max(0, raw_tokens - compressed_tokens)
            now = datetime.now(timezone.utc).isoformat()

            with self._lock:
                conn = self._get_conn()
                row = conn.execute(
                    """SELECT source, strategy, calls, confidence,
                              avg_raw_tokens, avg_compressed_tokens, user_override
                       FROM entries WHERE command = ?""",
                    (command,),
                ).fetchone()

                if row is None:
                    ratio = (compressed_tokens / raw_tokens) if raw_tokens else 0.0
                    conn.execute(
                        """INSERT INTO entries
                           (command, source, strategy, calls, confidence,
                            avg_raw_tokens, avg_compressed_tokens, compression_ratio,
                            hot, user_override, last_seen, params)
                           VALUES (?, 'learned', ?, 1, ?, ?, ?, ?, 0, 0, ?, '{}')""",
                        (
                            command, shape, INITIAL_CONFIDENCE,
                            raw_tokens, compressed_tokens, ratio, now,
                        ),
                    )
                    conn.execute(
                        "UPDATE stats SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT) WHERE key = 'total_commands_learned'"
                    )
                else:
                    src = row["source"]
                    prev_shape = row["strategy"]
                    calls = row["calls"] + 1
                    confidence = row["confidence"]
                    avg_raw = ((row["avg_raw_tokens"] * (calls - 1)) + raw_tokens) / calls
                    avg_comp = (
                        (row["avg_compressed_tokens"] * (calls - 1)) + compressed_tokens
                    ) / calls
                    ratio = avg_comp / avg_raw if avg_raw > 0 else 0.0
                    user_override = bool(row["user_override"])

                    if src != "user" and confidence < LOCKED_THRESHOLD and not user_override:
                        if prev_shape == shape:
                            confidence = min(1.0, confidence + CONFIDENCE_GAIN)
                        else:
                            confidence = max(0.0, confidence - CONFIDENCE_LOSS)
                            if confidence < INITIAL_CONFIDENCE:
                                prev_shape = shape
                                confidence = INITIAL_CONFIDENCE

                    hot = 1 if (calls >= HOT_CALL_THRESHOLD and confidence >= HOT_THRESHOLD) else 0

                    conn.execute(
                        """UPDATE entries SET strategy=?, calls=?, confidence=?,
                           avg_raw_tokens=?, avg_compressed_tokens=?, compression_ratio=?,
                           hot=?, last_seen=? WHERE command=?""",
                        (prev_shape, calls, confidence, avg_raw, avg_comp, ratio, hot, now, command),
                    )

                conn.execute(
                    "UPDATE stats SET value = CAST(CAST(value AS REAL) + ? AS TEXT) WHERE key = 'total_tokens_saved'",
                    (saved,),
                )
                conn.commit()
        except Exception as e:
            if os.environ.get("CLIPRESS_DEBUG"):
                print(f"clipress: learner.record failed: {e}", file=sys.stderr)

    def reset_command(self, command: str) -> bool:
        """Reset confidence for a specific command. Returns True if it existed."""
        try:
            conn = self._get_conn()
            with self._lock:
                row = conn.execute(
                    "SELECT 1 FROM entries WHERE command = ?", (command,)
                ).fetchone()
                if not row:
                    return False
                conn.execute(
                    "UPDATE entries SET confidence=?, hot=0, calls=0 WHERE command=?",
                    (INITIAL_CONFIDENCE, command),
                )
                conn.commit()
            return True
        except Exception:
            return False

    def reset_all(self) -> None:
        """Clear all learned entries."""
        try:
            conn = self._get_conn()
            with self._lock:
                conn.execute("DELETE FROM entries")
                for key in ("total_commands_learned", "total_tokens_saved"):
                    conn.execute("UPDATE stats SET value='0' WHERE key=?", (key,))
                conn.commit()
        except Exception:
            pass

    def all_entries(self) -> dict[str, Any]:
        """Return all entries as a plain dict (for CLI display)."""
        try:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT command, source, strategy, calls, confidence,
                          avg_raw_tokens, avg_compressed_tokens, compression_ratio,
                          hot, user_override, last_seen, params
                   FROM entries"""
            ).fetchall()
            return {
                row["command"]: {
                    "source": row["source"],
                    "strategy": row["strategy"],
                    "calls": row["calls"],
                    "confidence": row["confidence"],
                    "avg_raw_tokens": row["avg_raw_tokens"],
                    "avg_compressed_tokens": row["avg_compressed_tokens"],
                    "compression_ratio": row["compression_ratio"],
                    "hot": bool(row["hot"]),
                    "user_override": bool(row["user_override"]),
                    "last_seen": row["last_seen"],
                    "params": json.loads(row["params"] or "{}"),
                }
                for row in rows
            }
        except Exception:
            return {}

    def summary(self) -> dict[str, Any]:
        try:
            conn = self._get_conn()
            stats_rows = conn.execute("SELECT key, value FROM stats").fetchall()
            stats = {r["key"]: r["value"] for r in stats_rows}
            hot_commands = [
                r["command"]
                for r in conn.execute(
                    "SELECT command FROM entries WHERE hot = 1"
                ).fetchall()
            ]
            return {
                "total_learned": int(float(stats.get("total_commands_learned", 0))),
                "total_tokens_saved": float(stats.get("total_tokens_saved", 0)),
                "hot_commands": hot_commands,
            }
        except Exception:
            return {"total_learned": 0, "total_tokens_saved": 0, "hot_commands": []}

    # ------------------------------------------------------------------
    # Backward-compat shim: CLI code that accessed learner.data directly
    # ------------------------------------------------------------------

    @property
    def data(self) -> dict[str, Any]:
        """Return all entries and stats as a plain dict (backward-compat for tests)."""
        try:
            conn = self._get_conn()
            stats_rows = conn.execute("SELECT key, value FROM stats").fetchall()
            raw_stats = {r["key"]: r["value"] for r in stats_rows}
            stats = {
                "total_commands_learned": int(float(raw_stats.get("total_commands_learned", 0))),
                "total_tokens_saved": float(raw_stats.get("total_tokens_saved", 0)),
                "session_count": int(float(raw_stats.get("session_count", 0))),
            }
        except Exception:
            stats = {"total_commands_learned": 0, "total_tokens_saved": 0.0, "session_count": 0}
        return {"entries": self.all_entries(), "stats": stats}

    def _save(self) -> None:
        """No-op: SQLite commits inline. Here for backward-compat with older tests."""
        pass
