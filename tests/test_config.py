from ruamel.yaml import YAML


class _YamlWrapper:
    @staticmethod
    def safe_load(stream):
        return YAML(typ="safe").load(stream)

    @staticmethod
    def dump(data, stream):
        YAML(typ="safe").dump(data, stream)


yaml = _YamlWrapper()
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
    comp_dir = tmp_path / ".compressor"
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
    comp_dir = tmp_path / ".compressor"
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
