import os
import sys
import json
import fcntl
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


# Single background writer coalesces bursts of record() calls into one save.
# A per-instance Event is flipped by record() and consumed by a daemon thread
# that owns the actual disk I/O. This avoids spawning one thread per record.
class _SaveWorker:
    def __init__(self, save_fn):
        self._save_fn = save_fn
        self._event = threading.Event()
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop:
            self._event.wait()
            if self._stop:
                return
            self._event.clear()
            try:
                self._save_fn()
            except Exception as e:
                if os.environ.get("CLIPRESS_DEBUG"):
                    print(f"clipress: save failed: {e}", file=sys.stderr)

    def request(self) -> None:
        self._event.set()


class Learner:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.dir_path = Path(workspace) / ".compressor"
        self.path = self.dir_path / "registry.json"
        self.data: dict[str, Any] = self._default_data()
        self._load()
        # Backfill any missing keys introduced by newer versions so older registries load cleanly.
        self._ensure_shape()
        self.data["stats"]["session_count"] += 1
        self._save_worker = _SaveWorker(self._save)

    def _default_data(self) -> dict[str, Any]:
        return {
            "version": "1.0",
            "workspace": os.path.abspath(self.workspace),
            "entries": {},
            "stats": {
                "total_commands_learned": 0,
                "total_tokens_saved": 0,
                "session_count": 0,
            },
        }

    def _ensure_shape(self) -> None:
        default = self._default_data()
        if not isinstance(self.data, dict):
            self.data = default
            return
        for key, value in default.items():
            if key not in self.data:
                self.data[key] = value
        stats = self.data.get("stats")
        if not isinstance(stats, dict):
            self.data["stats"] = default["stats"]
        else:
            for key, value in default["stats"].items():
                stats.setdefault(key, value)
        if not isinstance(self.data.get("entries"), dict):
            self.data["entries"] = {}

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        self.data = json.loads(content)
            except Exception:
                pass  # Return silently on error, keep default empty data

    def _save(self) -> None:
        try:
            self.dir_path.mkdir(mode=0o700, parents=True, exist_ok=True)
            # GAP-2: Exclusive file lock prevents concurrent writers from corrupting registry.json
            lock_path = self.dir_path / "registry.lock"
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                tmp_path = self.path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    os.chmod(tmp_path, 0o600)
                    json.dump(self.data, f, indent=2)
                tmp_path.replace(self.path)
                # lock released on context-manager exit
        except Exception:
            pass  # No-op on error

    def _async_save(self) -> None:
        self._save_worker.request()

    def lookup(self, command: str) -> dict[str, Any] | None:
        try:
            entry = self.data["entries"].get(command)
            if not entry:
                return None
            if entry.get("user_override") or entry.get("confidence", 0) >= HOT_THRESHOLD:
                return entry
            return None
        except Exception:
            return None

    def record(
        self, command: str, shape: str, raw_tokens: int, compressed_tokens: int
    ) -> None:
        try:
            entries = self.data["entries"]
            stats = self.data["stats"]

            saved = max(0, raw_tokens - compressed_tokens)
            stats["total_tokens_saved"] += saved

            now = datetime.now(timezone.utc).isoformat()

            if command not in entries:
                stats["total_commands_learned"] += 1
                entries[command] = {
                    "source": "learned",
                    "strategy": shape,
                    "calls": 1,
                    "confidence": INITIAL_CONFIDENCE,
                    "avg_raw_tokens": raw_tokens,
                    "avg_compressed_tokens": compressed_tokens,
                    "compression_ratio": (
                        (compressed_tokens / raw_tokens) if raw_tokens else 0.0
                    ),
                    "hot": False,
                    "user_override": False,
                    "last_seen": now,
                    "params": {},
                }
            else:
                entry = entries[command]
                entry["calls"] += 1
                entry["last_seen"] = now

                # Update averages
                calls = entry["calls"]
                entry["avg_raw_tokens"] = (
                    (entry["avg_raw_tokens"] * (calls - 1)) + raw_tokens
                ) / calls
                entry["avg_compressed_tokens"] = (
                    (entry["avg_compressed_tokens"] * (calls - 1)) + compressed_tokens
                ) / calls

                if entry["avg_raw_tokens"] > 0:
                    entry["compression_ratio"] = (
                        entry["avg_compressed_tokens"] / entry["avg_raw_tokens"]
                    )

                if entry["source"] == "user" or entry["confidence"] >= LOCKED_THRESHOLD:
                    pass  # Don't update confidence for locked or user overrides
                elif entry["strategy"] == shape:
                    entry["confidence"] = min(
                        1.0, entry["confidence"] + CONFIDENCE_GAIN
                    )
                else:
                    entry["confidence"] = max(
                        0.0, entry["confidence"] - CONFIDENCE_LOSS
                    )
                    if entry["confidence"] < INITIAL_CONFIDENCE:
                        # Reset to new shape
                        entry["strategy"] = shape
                        entry["confidence"] = INITIAL_CONFIDENCE

                if (
                    entry["calls"] >= HOT_CALL_THRESHOLD
                    and entry["confidence"] >= HOT_THRESHOLD
                ):
                    entry["hot"] = True

            self._async_save()
        except Exception as e:
            if os.environ.get("CLIPRESS_DEBUG"):
                print(f"clipress: learner.record failed: {e}", file=sys.stderr)

    def summary(self) -> dict[str, Any]:
        hot_commands = [
            cmd for cmd, info in self.data.get("entries", {}).items() if info.get("hot")
        ]
        return {
            "total_learned": self.data.get("stats", {}).get(
                "total_commands_learned", 0
            ),
            "total_tokens_saved": self.data.get("stats", {}).get(
                "total_tokens_saved", 0
            ),
            "hot_commands": hot_commands,
        }
