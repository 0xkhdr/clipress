import sys
import collections
from pathlib import Path
from clipress.config import get_config, build_seed_registry
from clipress.safety import should_skip
from clipress.classifier import detect
from clipress.learner import Learner
from clipress.metrics import count_tokens
from clipress.strategies import get_strategy
from clipress.ansi import strip_ansi
from typing import Any

# Hot cache
_HOT_CACHE: collections.OrderedDict[str, Any] = collections.OrderedDict()
_HOT_CACHE_MAX_SIZE = 100

def compress(command: str, output: str, workspace: str) -> str:
    try:
        # Load config
        config = get_config(workspace)
        show_metrics = config.get("engine", {}).get("show_metrics", False)

        # PRE-PROCESSING: Global ANSI Stripping
        if config.get("engine", {}).get("strip_ansi", True):
            output = strip_ansi(output)

        # GATE: Safety Checker
        skip, reason = should_skip(command, output, workspace, config)
        if skip:
            if reason != "minimal output":
                print(f"clipress: skipped [{reason}]", file=sys.stderr)
            return output

        normalized_cmd = " ".join(command.strip().split())

        # Check Hot Cache
        entry = None
        if normalized_cmd in _HOT_CACHE:
            entry = _HOT_CACHE[normalized_cmd]
            # update LRU
            _HOT_CACHE.move_to_end(normalized_cmd)
        else:
            seeds = build_seed_registry(workspace)
            matched_seed = None
            # Layer 0a: Seeds
            for key, seed_info in seeds.items():
                # Since seeds are ordered longest-first, we can just use startswith
                if normalized_cmd == key or normalized_cmd.startswith(key + " "):
                    matched_seed = seed_info
                    break

            if matched_seed:
                entry = {
                    "strategy": matched_seed["strategy"],
                    "params": matched_seed.get("params", {}),
                    "hot": True,
                    "source": "seed",
                    "user_override": matched_seed.get("user_override", False)
                }
            else:
                learner = Learner(workspace)
                # Layer 0b: Workspace Registry
                learned_entry = learner.lookup(normalized_cmd)
                if learned_entry:
                    entry = learned_entry
                else:
                    # Layer 1: Classifier
                    shape, confidence = detect(output)
                    entry = {
                        "strategy": shape,
                        "params": {},
                        "hot": False,
                        "source": "classifier",
                    }

            if entry.get("hot") or entry.get("user_override"):
                if len(_HOT_CACHE) >= _HOT_CACHE_MAX_SIZE:
                    _HOT_CACHE.popitem(last=False)
                _HOT_CACHE[normalized_cmd] = entry

        # Layer 2: Apply strategy
        strategy = get_strategy(entry["strategy"])
        
        # Build contract (global merged with per-command overrides)
        global_contract = config.get("contracts", {}).get("global", {})
        cmd_contract = config.get("commands", {}).get(normalized_cmd, {})
        contract = {
            "always_keep": global_contract.get("always_keep", []) + cmd_contract.get("always_keep", []),
            "always_strip": global_contract.get("always_strip", []) + cmd_contract.get("always_strip", [])
        }

        # Track tokens before compression
        raw_tokens = 0
        if show_metrics or not entry.get("hot"):
            raw_tokens = count_tokens(output)

        compressed = strategy.compress(output, entry.get("params", {}), contract)

        # Ensure we never return an empty string for non-empty input
        if output and not compressed:
            compressed = output

        # Track tokens after compression
        compressed_tokens = 0
        if show_metrics or not entry.get("hot"):
            compressed_tokens = count_tokens(compressed)

        if show_metrics:
            saved = max(0, raw_tokens - compressed_tokens)
            if saved > 0:
                print(
                    f"clipress metrics: saved {saved} tokens ({entry['strategy']})",
                    file=sys.stderr,
                )

        # POST: Learner
        if not entry.get("source") == "seed":
            learner = Learner(workspace) # Make sure learner is instantiated
            learner.record(
                normalized_cmd, entry["strategy"], raw_tokens, compressed_tokens
            )

        return compressed

    except Exception as e:
        print(f"clipress error: {e}", file=sys.stderr)
        return output
