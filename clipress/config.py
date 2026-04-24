import sys
import json
from pathlib import Path
from typing import Any
from ruamel.yaml import YAML

class _YamlWrapper:
    @staticmethod
    def safe_load(stream):
        return YAML(typ="safe").load(stream)

yaml = _YamlWrapper()

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
    assert config.get("engine", {}).get("min_lines_to_compress", 0) >= 5, "min_lines_to_compress must be >= 5"
    assert config.get("engine", {}).get("hot_cache_threshold", 0) >= 1, "hot_cache_threshold must be >= 1"

    assert isinstance(config.get("engine", {}).get("strip_ansi", True), bool), "strip_ansi must be a bool"
    assert isinstance(config.get("engine", {}).get("pass_through_on_error", True), bool), "pass_through_on_error must be a bool"

    max_bytes = config.get("engine", {}).get("max_output_bytes", 10_485_760)
    assert isinstance(max_bytes, int) and max_bytes > 0, "max_output_bytes must be a positive integer"

    patterns = config.get("safety", {}).get("security_patterns", [])
    assert isinstance(patterns, list), "security_patterns must be a list"
    assert all(isinstance(p, str) for p in patterns), "security_patterns must be a list of strings"

    # GAP-8: Validate per-command contract entries
    commands = config.get("commands", {})
    assert isinstance(commands, dict), "commands must be a mapping"
    for cmd, overrides in commands.items():
        assert isinstance(overrides, dict), f"commands.{cmd!r} must be a mapping"
        for field in ("always_keep", "always_strip"):
            if field in overrides:
                assert isinstance(overrides[field], list), f"commands.{cmd!r}.{field} must be a list"
                assert all(isinstance(p, str) for p in overrides[field]), (
                    f"commands.{cmd!r}.{field} must be a list of strings"
                )

def get_config(workspace: str) -> dict[str, Any]:
    global _CONFIG_CACHE
    if workspace in _CONFIG_CACHE:
        return _CONFIG_CACHE[workspace]

    defaults = load_defaults()
    workspace_path = Path(workspace)
    user_config_path = workspace_path / ".compressor" / "config.yaml"

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

def load_extensions(workspace: str) -> dict[str, Any]:
    workspace_path = Path(workspace)
    extensions_dir = workspace_path / ".compressor" / "extensions"
    extensions = {}
    
    if extensions_dir.exists() and extensions_dir.is_dir():
        for yaml_file in extensions_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    ext_data = yaml.safe_load(f)
                    if ext_data and isinstance(ext_data, dict):
                        for cmd, cfg in ext_data.items():
                            if isinstance(cfg, dict):
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

def clear_cache() -> None:
    global _CONFIG_CACHE
    global _SEED_CACHE
    _CONFIG_CACHE.clear()
    _SEED_CACHE.clear()
