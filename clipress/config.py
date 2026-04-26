import sys
import json
import yaml
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when the user's config.yaml fails validation."""

_CONFIG_CACHE: dict[str, dict[str, Any]] = {}
_SEED_CACHE: dict[str, dict[str, Any]] = {}

def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_defaults() -> dict[str, Any]:
    pkg_dir = Path(__file__).parent
    default_path = pkg_dir / "defaults" / "config.yaml"
    with open(default_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _validate(config: dict[str, Any]) -> None:
    def check(condition: bool, msg: str) -> None:
        if not condition:
            raise ConfigError(msg)

    check(config.get("engine", {}).get("min_lines_to_compress", 0) >= 5, "min_lines_to_compress must be >= 5")
    check(config.get("engine", {}).get("hot_cache_threshold", 0) >= 1, "hot_cache_threshold must be >= 1")
    check(isinstance(config.get("engine", {}).get("strip_ansi", True), bool), "strip_ansi must be a bool")
    check(isinstance(config.get("engine", {}).get("pass_through_on_error", True), bool), "pass_through_on_error must be a bool")
    check(
        isinstance(config.get("engine", {}).get("save_history", True), bool),
        "save_history must be a bool",
    )

    max_bytes = config.get("engine", {}).get("max_output_bytes", 10_485_760)
    check(isinstance(max_bytes, int) and max_bytes > 0, "max_output_bytes must be a positive integer")
    target_max_tokens = config.get("engine", {}).get("target_max_tokens", 0)
    check(
        isinstance(target_max_tokens, int) and target_max_tokens >= 0,
        "target_max_tokens must be an integer >= 0",
    )
    min_savings_ratio = config.get("engine", {}).get("min_savings_ratio", 0.10)
    check(
        isinstance(min_savings_ratio, (int, float)) and 0 <= float(min_savings_ratio) <= 1,
        "min_savings_ratio must be between 0 and 1",
    )
    min_raw_tokens = config.get("engine", {}).get("min_raw_tokens_for_cost_guard", 200)
    check(
        isinstance(min_raw_tokens, int) and min_raw_tokens >= 0,
        "min_raw_tokens_for_cost_guard must be an integer >= 0",
    )
    history_max_entries = config.get("engine", {}).get("history_max_entries", 100)
    check(
        isinstance(history_max_entries, int) and history_max_entries >= 1,
        "history_max_entries must be an integer >= 1",
    )

    patterns = config.get("safety", {}).get("security_patterns", [])
    check(isinstance(patterns, list), "security_patterns must be a list")
    check(all(isinstance(p, str) for p in patterns), "security_patterns must be a list of strings")

    commands = config.get("commands", {})
    check(isinstance(commands, dict), "commands must be a mapping")
    for cmd, overrides in commands.items():
        check(isinstance(overrides, dict), f"commands.{cmd!r} must be a mapping")
        for field in ("always_keep", "always_strip"):
            if field in overrides:
                check(isinstance(overrides[field], list), f"commands.{cmd!r}.{field} must be a list")
                check(
                    all(isinstance(p, str) for p in overrides[field]),
                    f"commands.{cmd!r}.{field} must be a list of strings",
                )
        if "params" in overrides:
            check(
                isinstance(overrides["params"], dict),
                f"commands.{cmd!r}.params must be a mapping",
            )


def get_config(workspace: str) -> dict[str, Any]:
    global _CONFIG_CACHE
    if workspace in _CONFIG_CACHE:
        return _CONFIG_CACHE[workspace]

    defaults = load_defaults()
    workspace_path = Path(workspace)
    user_config_path = workspace_path / ".clipress" / "config.yaml"

    config = defaults.copy()

    if user_config_path.exists():
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f)
                if user_config and isinstance(user_config, dict):
                    merged = deep_merge(defaults, user_config)
                    _validate(merged)
                    config = merged
        except Exception as e:
            print(f"clipress: invalid user config: {e}", file=sys.stderr)
            # fallback to defaults

    _CONFIG_CACHE[workspace] = config
    return config

_KNOWN_EXTENSION_KEYS = frozenset({"strategy", "params", "streamable", "user_override"})
_KNOWN_STRATEGIES = frozenset({
    "generic", "list", "progress", "test", "diff", "table", "keyvalue", "error"
})


def _validate_extension_entry(cmd: str, cfg: dict[str, Any], filename: str) -> bool:
    """Validate a single extension entry. Returns True if valid, False to skip."""
    unknown_keys = set(cfg.keys()) - _KNOWN_EXTENSION_KEYS - {"user_override"}
    if unknown_keys:
        print(
            f"clipress: extension {filename!r} command {cmd!r} has unknown keys:"
            f" {sorted(unknown_keys)} — skipping",
            file=sys.stderr,
        )
        return False
    strategy = cfg.get("strategy")
    if strategy is not None and strategy not in _KNOWN_STRATEGIES:
        print(
            f"clipress: extension {filename!r} command {cmd!r} has unknown strategy"
            f" {strategy!r} — skipping",
            file=sys.stderr,
        )
        return False
    params = cfg.get("params")
    if params is not None and not isinstance(params, dict):
        print(
            f"clipress: extension {filename!r} command {cmd!r}.params must be a mapping — skipping",
            file=sys.stderr,
        )
        return False
    streamable = cfg.get("streamable")
    if streamable is not None and not isinstance(streamable, bool):
        print(
            f"clipress: extension {filename!r} command {cmd!r}.streamable must be a bool — skipping",
            file=sys.stderr,
        )
        return False
    return True


def load_extensions(workspace: str) -> dict[str, Any]:
    workspace_path = Path(workspace)
    extensions_dir = workspace_path / ".clipress" / "extensions"
    extensions = {}

    if extensions_dir.exists() and extensions_dir.is_dir():
        for yaml_file in sorted(extensions_dir.glob("*.yaml")):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    ext_data = yaml.safe_load(f)
                    if ext_data and isinstance(ext_data, dict):
                        for cmd, cfg in ext_data.items():
                            if isinstance(cfg, dict):
                                if _validate_extension_entry(cmd, cfg, yaml_file.name):
                                    cfg["user_override"] = True
                                    extensions[cmd] = cfg
            except Exception as e:
                print(f"clipress: invalid extension config {yaml_file.name}: {e}", file=sys.stderr)
    return extensions

def build_seed_registry(workspace: str) -> dict[str, Any]:
    global _SEED_CACHE
    if workspace in _SEED_CACHE:
        return _SEED_CACHE[workspace]

    pkg_dir = Path(__file__).parent
    seeds_path = pkg_dir / "registry" / "seeds.json"

    seeds = {}
    if seeds_path.exists():
        with open(seeds_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            seeds = data.get("seeds", {})

    extensions = load_extensions(workspace)

    for cmd, cfg in extensions.items():
        seeds[cmd] = cfg

    sorted_seeds = dict(sorted(seeds.items(), key=lambda item: len(item[0]), reverse=True))
    _SEED_CACHE[workspace] = sorted_seeds
    return sorted_seeds


def validate_config_file(workspace: str) -> None:
    """
    Validate the workspace config.yaml, raising ConfigError on any problem.
    Used by the `clipress validate` CLI command.
    """
    defaults = load_defaults()
    user_config_path = Path(workspace) / ".clipress" / "config.yaml"
    if not user_config_path.exists():
        return  # No user config — defaults are always valid

    with open(user_config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f)

    if user_config is None:
        return  # Empty file — treat as defaults

    if not isinstance(user_config, dict):
        raise ConfigError("config.yaml must be a YAML mapping at the top level")

    merged = deep_merge(defaults, user_config)
    _validate(merged)  # raises ConfigError on failure


def clear_cache() -> None:
    global _CONFIG_CACHE
    global _SEED_CACHE
    _CONFIG_CACHE.clear()
    _SEED_CACHE.clear()


def resolve_command_overrides(config: dict[str, Any], command: str) -> dict[str, Any]:
    """
    Return the most specific command override (longest-prefix match) from
    config["commands"] for the provided normalized command.
    """
    commands = config.get("commands", {})
    if not isinstance(commands, dict) or not command:
        return {}

    best_key = None
    for key in commands:
        if command == key or command.startswith(key + " "):
            if best_key is None or len(key) > len(best_key):
                best_key = key

    if best_key is None:
        return {}
    value = commands.get(best_key, {})
    return value if isinstance(value, dict) else {}
