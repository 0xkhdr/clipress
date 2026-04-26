import yaml
from clipress import config


def test_config_deep_merge():
    base = {"a": 1, "b": {"x": 10, "y": 20}, "c": [1, 2, 3]}
    override = {"b": {"y": 30, "z": 40}, "c": [4, 5]}
    merged = config.deep_merge(base, override)

    assert merged["a"] == 1
    assert merged["b"]["x"] == 10
    assert merged["b"]["y"] == 30
    assert merged["b"]["z"] == 40
    assert merged["c"] == [4, 5]  # list replaced


def test_load_defaults():
    defaults = config.load_defaults()
    assert defaults["engine"]["min_lines_to_compress"] == 15
    assert "safety" in defaults


def test_get_config_no_user_config(tmp_path):
    config.clear_cache()
    c = config.get_config(str(tmp_path))
    assert c["engine"]["min_lines_to_compress"] == 15


def test_get_config_with_user_override(tmp_path):
    config.clear_cache()
    comp_dir = tmp_path / ".clipress"
    comp_dir.mkdir()
    user_cfg = {"engine": {"min_lines_to_compress": 10}}
    with open(comp_dir / "config.yaml", "w") as f:
        yaml.dump(user_cfg, f)

    c = config.get_config(str(tmp_path))
    assert c["engine"]["min_lines_to_compress"] == 10
    # ensure it merged with defaults
    assert c["engine"]["hot_cache_threshold"] == 10


def test_get_config_invalid_user_config(tmp_path, capsys):
    config.clear_cache()
    comp_dir = tmp_path / ".clipress"
    comp_dir.mkdir()
    # Invalid validation condition: min_lines_to_compress < 5
    user_cfg = {"engine": {"min_lines_to_compress": 2}}
    with open(comp_dir / "config.yaml", "w") as f:
        yaml.dump(user_cfg, f)

    c = config.get_config(str(tmp_path))
    # It should fallback to default 15
    assert c["engine"]["min_lines_to_compress"] == 15

    captured = capsys.readouterr()
    assert "clipress: invalid user config" in captured.err

def test_loads_user_extensions(tmp_path):
    config.clear_cache()
    ext_dir = tmp_path / ".clipress" / "extensions"
    ext_dir.mkdir(parents=True)
    ext_cfg = {"my_cmd": {"strategy": "generic"}}
    with open(ext_dir / "my_ext.yaml", "w") as f:
        yaml.dump(ext_cfg, f)
    
    extensions = config.load_extensions(str(tmp_path))
    assert "my_cmd" in extensions
    assert extensions["my_cmd"]["strategy"] == "generic"
    assert extensions["my_cmd"]["user_override"] is True

def test_user_extension_overrides_builtin_seed(tmp_path):
    config.clear_cache()
    ext_dir = tmp_path / ".clipress" / "extensions"
    ext_dir.mkdir(parents=True)
    ext_cfg = {"ls": {"strategy": "table"}}
    with open(ext_dir / "my_ls.yaml", "w") as f:
        yaml.dump(ext_cfg, f)
    
    seeds = config.build_seed_registry(str(tmp_path))
    assert seeds["ls"]["strategy"] == "table"
    assert seeds["ls"]["user_override"] is True

def test_seed_matching_ordered_by_length(tmp_path):
    config.clear_cache()
    ext_dir = tmp_path / ".clipress" / "extensions"
    ext_dir.mkdir(parents=True)
    ext_cfg = {
        "docker ps -a": {"strategy": "list"},
        "docker ps": {"strategy": "table"}
    }
    with open(ext_dir / "docker.yaml", "w") as f:
        yaml.dump(ext_cfg, f)
        
    seeds = config.build_seed_registry(str(tmp_path))
    keys = list(seeds.keys())
    assert keys.index("docker ps -a") < keys.index("docker ps")

def test_per_command_contracts_merged(tmp_path):
    config.clear_cache()
    comp_dir = tmp_path / ".clipress"
    comp_dir.mkdir()
    user_cfg = {
        "contracts": {"global": {"always_keep": ["GLOBAL_KEEP"]}},
        "commands": {"git status": {"always_keep": ["GIT_KEEP"]}}
    }
    with open(comp_dir / "config.yaml", "w") as f:
        yaml.dump(user_cfg, f)
        
    c = config.get_config(str(tmp_path))
    assert "GLOBAL_KEEP" in c["contracts"]["global"]["always_keep"]
    assert "GIT_KEEP" in c["commands"]["git status"]["always_keep"]


def test_invalid_max_output_bytes_falls_back_to_defaults(tmp_path, capsys):
    config.clear_cache()
    comp_dir = tmp_path / ".clipress"
    comp_dir.mkdir()
    # Negative value should fail validation
    user_cfg = {"engine": {"max_output_bytes": -1}}
    with open(comp_dir / "config.yaml", "w") as f:
        yaml.dump(user_cfg, f)

    c = config.get_config(str(tmp_path))
    # Should fallback to default (10 MB)
    assert c["engine"]["max_output_bytes"] == 10485760

    captured = capsys.readouterr()
    assert "clipress: invalid user config" in captured.err
