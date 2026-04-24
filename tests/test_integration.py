from clipress.engine import compress
from tests.conftest import load_fixture


def test_integration_git_status(fixtures_dir, tmp_path):
    output = load_fixture(fixtures_dir, "git_status.txt")
    res = compress("git status", output, str(tmp_path))
    assert "modified:   clipress/engine.py" in res
    assert "Untracked files:" in res


def test_integration_pytest(fixtures_dir, tmp_path):
    output = load_fixture(fixtures_dir, "pytest_output.txt")
    res = compress("pytest", output, str(tmp_path))
    assert "FAILED tests/test_broken.py::test_error" in res
    assert "tests/test_engine.py ....." not in res
