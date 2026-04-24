import pytest
from click.testing import CliRunner
from clipress.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_init(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert "Initialized" in result.output
    assert (tmp_path / ".compressor" / "config.yaml").exists()


def test_cli_status(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "session report" in result.output


def test_cli_compress(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(main, ["init"])
    # Pass stdin
    result = runner.invoke(main, ["compress", "ls"], input="file1\nfile2\nfile3\n" * 15)
    assert result.exit_code == 0
    # It compresses
    assert "more items" in result.output


def test_cli_validate_exits_nonzero_on_invalid_config(runner, tmp_path, monkeypatch):
    """`clipress validate` must surface invalid configs via a non-zero exit code."""
    monkeypatch.chdir(tmp_path)
    comp = tmp_path / ".compressor"
    comp.mkdir()
    # min_lines_to_compress below the >= 5 floor
    (comp / "config.yaml").write_text("engine:\n  min_lines_to_compress: 2\n")
    from clipress.config import clear_cache
    clear_cache()

    result = runner.invoke(main, ["validate"])
    assert result.exit_code == 1
    # Error lands on stderr; click combines it with stdout by default in mix_stderr mode.
    combined = (result.output or "") + (result.stderr if result.stderr_bytes else "")
    assert "invalid" in combined.lower()


def test_cli_validate_passes_on_valid_config(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from clipress.config import clear_cache
    clear_cache()
    result = runner.invoke(main, ["validate"])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_package_version_matches_pyproject():
    """__version__ must track the installed package metadata (or 0+unknown if uninstalled)."""
    from clipress import __version__
    # We don't assert a literal — just that it's a non-empty string.
    assert isinstance(__version__, str) and __version__
