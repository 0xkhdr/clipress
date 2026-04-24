import pytest
from click.testing import CliRunner
from clipress.cli import main
import os


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
    # Pass stdin
    result = runner.invoke(main, ["compress", "ls"], input="file1\nfile2\nfile3\n" * 15)
    assert result.exit_code == 0
    # It compresses
    assert "more items" in result.output
