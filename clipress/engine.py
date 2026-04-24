import sys
import collections
from pathlib import Path
from clipress.config import get_config
from clipress.safety import should_skip
from clipress.classifier import detect
from clipress.learner import Learner
from clipress.metrics import count_tokens
from clipress.strategies import get_strategy
from typing import Any
import json

# Hot cache
_HOT_CACHE: collections.OrderedDict[str, Any] = collections.OrderedDict()
_HOT_CACHE_MAX_SIZE = 100


def _get_seed_registry() -> dict:
    pkg_dir = Path(__file__).parent
    seed_path = pkg_dir / "registry" / "seeds.json"
    if seed_path.exists():
        with open(seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("seeds", {})
    return {}


_SEEDS = _get_seed_registry()


def compress(command: str, output: str, workspace: str) -> str:
    try:
        # Load config
        config = get_config(workspace)
        show_metrics = config.get("engine", {}).get("show_metrics", False)

        # Gate: Safety
        skip, reason = should_skip(command, output)
        if skip:
            if reason != "minimal output":
                print(f"clipress: skipped [{reason}]", file=sys.stderr)
            return output

        learner = Learner(workspace)

        normalized_cmd = " ".join(command.strip().split())

        # Check Hot Cache
        if normalized_cmd in _HOT_CACHE:
            entry = _HOT_CACHE[normalized_cmd]
            # update LRU
            _HOT_CACHE.move_to_end(normalized_cmd)
        else:
            # Layer 0a: Seeds
            # Prefix match
            matched_seed = None
            for key, seed_info in _SEEDS.items():
                if normalized_cmd == key or normalized_cmd.startswith(key + " "):
                    matched_seed = seed_info
                    break

            if matched_seed:
                entry = {
                    "strategy": matched_seed["strategy"],
                    "params": matched_seed.get("params", {}),
                    "hot": True,  # Seeds are always "hot"
                    "source": "seed",
                }
            else:
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

            if entry.get("hot"):
                if len(_HOT_CACHE) >= _HOT_CACHE_MAX_SIZE:
                    _HOT_CACHE.popitem(last=False)
                _HOT_CACHE[normalized_cmd] = entry

        # Layer 2: Apply strategy
        strategy = get_strategy(entry["strategy"])
        contract = config.get("contracts", {})

        raw_tokens = 0
        if show_metrics or not entry.get("hot"):
            raw_tokens = count_tokens(output)

        compressed = strategy.compress(output, entry.get("params", {}), contract)

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
        if not (entry.get("source") == "seed"):
            learner.record(
                normalized_cmd, entry["strategy"], raw_tokens, compressed_tokens
            )

        return compressed

    except Exception as e:
        print(f"clipress error: {e}", file=sys.stderr)
        return output
