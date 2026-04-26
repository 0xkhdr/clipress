"""
Golden output tests — verify that compression produces the expected structure
and never regresses on known real-world command outputs.

These are structural invariant tests, not exact-content snapshots, so they
remain valid as strategy implementations evolve.
"""

from clipress.strategies.list_strategy import ListStrategy
from clipress.strategies.diff_strategy import DiffStrategy
from clipress.strategies.test_strategy import TestStrategy
from clipress.strategies.error_strategy import ErrorStrategy
from clipress.strategies.table_strategy import TableStrategy
from clipress.strategies.keyvalue_strategy import KeyvalueStrategy as KeyValueStrategy
from clipress.strategies.progress_strategy import ProgressStrategy
from clipress.strategies.generic_strategy import GenericStrategy


# ---------------------------------------------------------------------------
# git log
# ---------------------------------------------------------------------------

GIT_LOG = "\n".join(
    [f"abc{i:04d} feat: commit number {i}" for i in range(100)]
)


def test_git_log_list_reduces_lines():
    s = ListStrategy()
    result = s.compress(GIT_LOG, {"max_lines": 30, "head_lines": 20, "tail_lines": 10}, {})
    assert len(result.splitlines()) <= 31  # 30 lines + optional truncation marker
    assert "feat: commit number 0" in result  # head preserved
    assert "feat: commit number 99" in result  # tail preserved


def test_git_log_list_includes_truncation_marker():
    s = ListStrategy()
    result = s.compress(GIT_LOG, {"max_lines": 20}, {})
    assert "..." in result or "[" in result, "must include truncation marker for large input"


# ---------------------------------------------------------------------------
# docker build progress
# ---------------------------------------------------------------------------

DOCKER_BUILD = "\n".join(
    [f"Step {i}/20 : RUN command_{i}" for i in range(1, 21)]
    + [" ---> abc123", "Successfully built xyz789"]
)


def test_docker_build_final_line_preserved():
    s = ProgressStrategy()
    result = s.compress(DOCKER_BUILD, {"keep": "final_line"}, {})
    assert "Successfully built" in result


def test_docker_build_errors_captured():
    output = (
        "Step 1/5 : FROM ubuntu:22.04\n"
        "Step 2/5 : RUN apt-get install something\n"
        "ERROR: package not found\n"
        "Step 3/5 : COPY .\n"
        "Successfully built xyz\n"
    )
    s = ProgressStrategy()
    result = s.compress(output, {"keep": "errors_and_final"}, {})
    assert "ERROR: package not found" in result
    assert "Successfully built" in result
    assert "Step 1" not in result


# ---------------------------------------------------------------------------
# pytest output
# ---------------------------------------------------------------------------

PYTEST_OUTPUT = (
    "============================= test session starts ==============================\n"
    "platform linux -- Python 3.12.0\n"
    "collected 50 items\n"
    "\n"
    "tests/test_foo.py::test_alpha PASSED\n"
    "tests/test_foo.py::test_beta FAILED\n"
    "tests/test_bar.py::test_gamma PASSED\n"
    "tests/test_bar.py::test_delta ERROR\n"
    "\n"
    "FAILURES\n"
    "tests/test_foo.py::test_beta\n"
    "    AssertionError: expected True, got False\n"
    "\n"
    "===== 2 failed, 2 passed in 1.23s =====\n"
)


def test_pytest_failed_only_excludes_passed():
    s = TestStrategy()
    result = s.compress(PYTEST_OUTPUT, {"keep": "failed_only"}, {})
    assert "test_beta" in result
    assert "test_delta" in result
    assert "FAILED" in result or "ERROR" in result
    assert "test_alpha PASSED" not in result
    assert "test_gamma PASSED" not in result


def test_pytest_always_includes_summary():
    s = TestStrategy()
    result = s.compress(PYTEST_OUTPUT, {"keep": "failed_only"}, {})
    assert "2 failed" in result or "failed" in result


# ---------------------------------------------------------------------------
# git diff
# ---------------------------------------------------------------------------

GIT_DIFF = (
    "diff --git a/src/foo.py b/src/foo.py\n"
    "index abc..def 100644\n"
    "--- a/src/foo.py\n"
    "+++ b/src/foo.py\n"
    "@@ -10,7 +10,7 @@ class Foo:\n"
    " def method(self):\n"
    "-    return old_value\n"
    "+    return new_value\n"
    " # end\n"
    "diff --git a/src/bar.py b/src/bar.py\n"
    "--- a/src/bar.py\n"
    "+++ b/src/bar.py\n"
    "@@ -1,3 +1,4 @@\n"
    "+import sys\n"
    " x = 1\n"
    " y = 2\n"
    " z = 3\n"
)


def test_diff_preserves_hunks():
    s = DiffStrategy()
    result = s.compress(GIT_DIFF, {}, {})
    assert "---" in result or "@@" in result
    assert "old_value" in result or "new_value" in result


def test_diff_strips_index_metadata():
    s = DiffStrategy()
    result = s.compress(GIT_DIFF, {}, {})
    assert "index abc..def" not in result


# ---------------------------------------------------------------------------
# Python traceback
# ---------------------------------------------------------------------------

TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "app.py", line 42, in main\n'
    "    result = process(data)\n"
    '  File "/usr/lib/python3.12/functools.py", line 888, in wrapper\n'
    "    return func(*args, **kwargs)\n"
    '  File "utils.py", line 15, in process\n'
    "    return transform(x)\n"
    "ValueError: invalid literal for int() with base 10: 'abc'\n"
)


def test_error_strategy_keeps_exception_message():
    s = ErrorStrategy()
    result = s.compress(TRACEBACK, {}, {})
    assert "ValueError" in result
    assert "invalid literal" in result


def test_error_strategy_strips_stdlib_frames():
    s = ErrorStrategy()
    result = s.compress(TRACEBACK, {"strip_stdlib_frames": True}, {})
    assert "/usr/lib/python3.12/functools.py" not in result


def test_error_strategy_keeps_user_frames():
    s = ErrorStrategy()
    result = s.compress(TRACEBACK, {"strip_stdlib_frames": True}, {})
    assert "app.py" in result or "utils.py" in result


# ---------------------------------------------------------------------------
# docker ps table
# ---------------------------------------------------------------------------

DOCKER_PS = (
    "CONTAINER ID   IMAGE         COMMAND   CREATED        STATUS        PORTS      NAMES\n"
    "------------   -----------   -------   ------------   -----------   --------   --------\n"
    + "\n".join(
        [
            f"abc{i:03d}         ubuntu        bash      2 hours ago    Up 2 hrs    80/tcp     web_{i}"
            for i in range(30)
        ]
    )
)


def test_table_strategy_preserves_header():
    s = TableStrategy()
    result = s.compress(DOCKER_PS, {"max_rows": 10}, {})
    assert "CONTAINER ID" in result


def test_table_strategy_limits_rows():
    s = TableStrategy()
    result = s.compress(DOCKER_PS, {"max_rows": 5}, {})
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) <= 8  # header + separator + 5 rows + possible truncation


# ---------------------------------------------------------------------------
# key-value (git config --list)
# ---------------------------------------------------------------------------

GIT_CONFIG = "\n".join(
    [f"section.key{i}: value{i}" for i in range(40)]
)


def test_keyvalue_reduces_output():
    s = KeyValueStrategy()
    result = s.compress(GIT_CONFIG, {"max_lines": 20}, {})
    assert len(result.splitlines()) <= 22  # 20 lines + omission note


# ---------------------------------------------------------------------------
# generic head/tail
# ---------------------------------------------------------------------------

LARGE_LOG = "\n".join([f"[2026-01-01 00:{i:02d}:00] INFO event_{i}" for i in range(200)])


def test_generic_strategy_head_tail_structure():
    s = GenericStrategy()
    result = s.compress(LARGE_LOG, {"max_lines": 40, "head_lines": 25, "tail_lines": 15}, {})
    lines = result.splitlines()
    assert "event_0" in result   # head line preserved
    assert "event_199" in result  # tail line preserved
    assert len(lines) <= 42      # max_lines + possible omission line


def test_generic_strategy_dedup_collapses_repeats():
    repeated = "\n".join(["repeated line"] * 100 + ["final line"])
    s = GenericStrategy()
    result = s.compress(repeated, {"max_lines": 30, "dedup_min_repeats": 3}, {})
    assert "repeated" in result
    assert len(result.splitlines()) < 10  # collapsed significantly


# ---------------------------------------------------------------------------
# contracts: always_keep / always_strip
# ---------------------------------------------------------------------------

def test_always_keep_contract_survives_any_strategy():
    output = "\n".join([f"line {i}" for i in range(100)]) + "\nCRITICAL_MARKER\n"
    s = GenericStrategy()
    result = s.compress(output, {"max_lines": 10}, {"always_keep": ["CRITICAL_MARKER"]})
    assert "CRITICAL_MARKER" in result


def test_always_strip_contract_removes_line():
    output = "\n".join([f"line {i}" for i in range(100)]) + "\nSECRET_TOKEN=abc123\n"
    s = GenericStrategy()
    result = s.compress(output, {"max_lines": 50}, {"always_strip": ["SECRET_TOKEN"]})
    assert "SECRET_TOKEN" not in result
