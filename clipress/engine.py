import sys
import time
import collections
import threading
from clipress.config import get_config, build_seed_registry
from clipress.safety import should_skip, is_security_sensitive, _compile_user_patterns
from clipress.classifier import detect
from clipress.learner import Learner
from clipress.metrics import count_tokens
from clipress.strategies import get_strategy, get_stream_strategy_instance
from clipress.strategies.base import StreamStrategy
from clipress.ansi import strip_ansi
from typing import Any, Optional

# Hot cache — in-memory LRU, thread-safe
_HOT_CACHE: collections.OrderedDict[str, Any] = collections.OrderedDict()
_HOT_CACHE_MAX_SIZE = 100
_HOT_CACHE_LOCK = threading.Lock()


class _Heartbeat:
    """Emits periodic status lines to stderr while a long-running buffer fills."""

    def __init__(self, interval: float = 5.0, line_threshold: int = 500):
        self._interval = interval
        self._threshold = line_threshold
        self._lines = 0
        self._start = time.monotonic()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)

    def add_lines(self, n: int) -> None:
        self._lines += n

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            elapsed = time.monotonic() - self._start
            print(
                f"[clipress: still running (elapsed {elapsed:.0f}s,"
                f" {self._lines} lines buffered, shape pending)]",
                file=sys.stderr,
            )


def compress(command: str, output: str, workspace: str) -> str:
    try:
        config = get_config(workspace)
        show_metrics = config.get("engine", {}).get("show_metrics", True)

        # Size guard — prevents OOM on huge outputs
        max_bytes = config.get("engine", {}).get("max_output_bytes", 10_485_760)
        if len(output.encode("utf-8", errors="replace")) > max_bytes:
            print(
                f"clipress: output exceeds max_output_bytes ({max_bytes}), passing through",
                file=sys.stderr,
            )
            return output

        # Global ANSI stripping
        if config.get("engine", {}).get("strip_ansi", True):
            output = strip_ansi(output)

        # Safety gate
        skip, reason = should_skip(command, output, workspace, config)
        if skip:
            if reason != "minimal output":
                print(f"clipress: skipped [{reason}]", file=sys.stderr)
            return output

        normalized_cmd = " ".join(command.strip().split())

        # Thread-safe hot cache lookup
        entry = None
        learner: Learner | None = None
        with _HOT_CACHE_LOCK:
            if normalized_cmd in _HOT_CACHE:
                entry = _HOT_CACHE[normalized_cmd]
                _HOT_CACHE.move_to_end(normalized_cmd)

        if entry is None:
            seeds = build_seed_registry(workspace)
            matched_seed = None
            for key, seed_info in seeds.items():
                if normalized_cmd == key or normalized_cmd.startswith(key + " "):
                    matched_seed = seed_info
                    break

            if matched_seed:
                entry = {
                    "strategy": matched_seed["strategy"],
                    "params": matched_seed.get("params", {}),
                    "hot": True,
                    "source": "seed",
                    "user_override": matched_seed.get("user_override", False),
                }
            else:
                learner = Learner(workspace)
                learned_entry = learner.lookup(normalized_cmd)
                if learned_entry:
                    entry = learned_entry
                else:
                    # Unknown command — run classifier with optional heartbeat
                    hb_cfg = config.get("engine", {})
                    hb_enabled = hb_cfg.get("heartbeat_enabled", True)
                    hb_interval = float(hb_cfg.get("heartbeat_interval_seconds", 5))
                    hb_threshold = int(hb_cfg.get("heartbeat_line_threshold", 500))

                    hb: _Heartbeat | None = None
                    if hb_enabled:
                        hb = _Heartbeat(interval=hb_interval, line_threshold=hb_threshold)
                        hb.add_lines(len(output.splitlines()))
                        hb.start()

                    try:
                        shape, _confidence = detect(output)
                    finally:
                        if hb is not None:
                            hb.stop()

                    entry = {
                        "strategy": shape,
                        "params": {},
                        "hot": False,
                        "source": "classifier",
                    }

            if entry.get("hot") or entry.get("user_override"):
                with _HOT_CACHE_LOCK:
                    if len(_HOT_CACHE) >= _HOT_CACHE_MAX_SIZE:
                        _HOT_CACHE.popitem(last=False)
                    _HOT_CACHE[normalized_cmd] = entry

        # Apply strategy
        strategy = get_strategy(entry["strategy"])

        global_contract = config.get("contracts", {}).get("global", {})
        cmd_contract = config.get("commands", {}).get(normalized_cmd, {})
        contract = {
            "always_keep": global_contract.get("always_keep", []) + cmd_contract.get("always_keep", []),
            "always_strip": global_contract.get("always_strip", []) + cmd_contract.get("always_strip", []),
        }

        # Merge per-command params from user config (user overrides seed/learned params)
        user_params = cmd_contract.get("params", {})
        merged_params = {**entry.get("params", {}), **user_params}

        raw_tokens = count_tokens(output)
        compressed = strategy.compress(output, merged_params, contract)

        if output and not compressed:
            compressed = output

        compressed_tokens = count_tokens(compressed)

        # Size-regression guard
        if len(compressed) > len(output) or (
            raw_tokens > 0 and compressed_tokens > raw_tokens
        ):
            compressed = output
            compressed_tokens = raw_tokens

        if show_metrics:
            saved = max(0, raw_tokens - compressed_tokens)
            if saved > 0:
                ratio = 1.0 - (compressed_tokens / raw_tokens) if raw_tokens else 0.0
                print(
                    f"clipress: saved {saved} tokens ({ratio:.0%} reduction via {entry['strategy']})",
                    file=sys.stderr,
                )

        # Update learner (skip for seed entries)
        if entry.get("source") != "seed":
            if learner is None:
                learner = Learner(workspace)
            learner.record(normalized_cmd, entry["strategy"], raw_tokens, compressed_tokens)

        return compressed

    except Exception as e:
        print(f"clipress error: {e}", file=sys.stderr)
        return output


def get_stream_handler(
    command: str, workspace: str
) -> Optional[tuple[StreamStrategy, dict[str, Any]]]:
    """
    Return (stream_strategy_instance, merged_params) if the command maps to a
    streamable seed, or None otherwise.

    The returned strategy is freshly instantiated (stateful — one per run).
    The caller is responsible for calling process_line() per line and finalize()
    at stream end.
    """
    try:
        config = get_config(workspace)
        normalized_cmd = " ".join(command.strip().split())

        seeds = build_seed_registry(workspace)
        for key, seed_info in seeds.items():
            if normalized_cmd == key or normalized_cmd.startswith(key + " "):
                if not seed_info.get("streamable"):
                    return None
                strategy_name = seed_info["strategy"]
                seed_params = seed_info.get("params", {})
                user_params = config.get("commands", {}).get(normalized_cmd, {}).get("params", {})
                merged_params = {**seed_params, **user_params}
                instance = get_stream_strategy_instance(strategy_name, merged_params)
                if instance is not None:
                    return instance, merged_params
                return None

    except Exception:
        pass
    return None
