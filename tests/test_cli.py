import json
import os
import time

import pytest
from click.testing import CliRunner

from clipress.cli import main
from clipress.config import clear_cache


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """Ensure each test gets a fresh config cache."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_init(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "Initialized" in result.output
    assert (tmp_path / ".compressor" / "config.yaml").exists()


def test_cli_status(runner, tmp_path):
    os.chdir(tmp_path)
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "session report" in result.output


def test_cli_compress(runner, tmp_path):
    os.chdir(tmp_path)
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["compress", "ls"], input="file1\nfile2\nfile3\n" * 15)
    assert result.exit_code == 0
    assert "more items" in result.output


# --- validate ---

def test_cli_validate_no_user_config(runner, tmp_path):
    """With no user config the defaults are always valid."""
    os.chdir(tmp_path)
    result = runner.invoke(main, ["validate"])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_cli_validate_valid_config(runner, tmp_path):
    os.chdir(tmp_path)
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["validate"])
    assert result.exit_code == 0
    assert "Config is valid" in result.output


def test_cli_validate_invalid_config(runner, tmp_path):
    """An invalid user config must report invalid, NOT silently fall back."""
    os.chdir(tmp_path)
    comp_dir = tmp_path / ".compressor"
    comp_dir.mkdir()
    (comp_dir / "config.yaml").write_text("engine:\n  min_lines_to_compress: 2\n")
    result = runner.invoke(main, ["validate"])
    assert result.exit_code != 0
    assert "invalid" in result.output.lower()


def test_cli_validate_bad_yaml(runner, tmp_path):
    """Malformed YAML must report invalid."""
    os.chdir(tmp_path)
    comp_dir = tmp_path / ".compressor"
    comp_dir.mkdir()
    (comp_dir / "config.yaml").write_text("engine: [\n  bad yaml")
    result = runner.invoke(main, ["validate"])
    assert result.exit_code != 0


# --- learn reset ---

def test_cli_learn_reset_all(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["learn", "reset"])
    assert result.exit_code == 0
    assert "Reset all" in result.output


def test_cli_learn_reset_specific(runner, tmp_path):
    """Resetting a known command clears confidence, hot, and calls."""
    os.chdir(tmp_path)
    from clipress.learner import Learner
    learner = Learner(str(tmp_path))
    # Promote to hot manually
    for _ in range(12):
        learner.record("git log", "list", 100, 50)
    time.sleep(0.15)

    result = runner.invoke(main, ["learn", "reset", "git log"])
    assert result.exit_code == 0
    assert "Reset git log" in result.output

    learner2 = Learner(str(tmp_path))
    entry = learner2.data["entries"].get("git log")
    assert entry is not None
    assert entry["confidence"] == 0.50
    assert entry["hot"] is False
    assert entry["calls"] == 0


def test_cli_learn_reset_not_found(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["learn", "reset", "nonexistent cmd"])
    assert result.exit_code == 0
    assert "not found" in result.output.lower()


# --- error-passthrough ---

def test_cli_error_passthrough_on(runner, tmp_path):
    os.chdir(tmp_path)
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["error-passthrough", "on"])
    assert result.exit_code == 0
    assert "pass_through_on_error" in result.output

    from ruamel.yaml import YAML
    cfg = YAML(typ="safe").load((tmp_path / ".compressor" / "config.yaml").read_text())
    assert cfg["engine"]["pass_through_on_error"] is True


def test_cli_error_passthrough_off(runner, tmp_path):
    os.chdir(tmp_path)
    runner.invoke(main, ["init"])
    runner.invoke(main, ["error-passthrough", "on"])
    result = runner.invoke(main, ["error-passthrough", "off"])
    assert result.exit_code == 0

    from ruamel.yaml import YAML
    cfg = YAML(typ="safe").load((tmp_path / ".compressor" / "config.yaml").read_text())
    assert cfg["engine"]["pass_through_on_error"] is False


def test_cli_error_passthrough_invalid_state(runner, tmp_path):
    os.chdir(tmp_path)
    result = runner.invoke(main, ["error-passthrough", "maybe"])
    assert result.exit_code != 0
