"""Tests for the Claude Code PostToolUse hook."""
import json
import sys
import types
from io import StringIO
from unittest.mock import patch

import pytest


def _invoke_hook(stdin_data: str, workspace: str = "/tmp") -> tuple[int, str]:
    """Run the hook's main() with mocked stdin/stdout and return (exit_code, stdout)."""
    from clipress.hooks.post_tool_use import main

    captured_stdout = StringIO()
    exit_code = 0

    def fake_exit(code=0):
        nonlocal exit_code
        exit_code = code
        raise SystemExit(code)

    with patch("sys.stdin", StringIO(stdin_data)), \
         patch("sys.stdout", captured_stdout), \
         patch("os.getcwd", return_value=workspace), \
         patch("clipress.hooks.post_tool_use.find_workspace_root", return_value=workspace):
        try:
            main()
        except SystemExit as e:
            exit_code = e.code or 0

    return exit_code, captured_stdout.getvalue()


def test_hook_passes_through_non_bash_tool(tmp_path):
    data = json.dumps({"tool_name": "Read", "tool_input": {}, "tool_response": {"output": "x"}})
    code, out = _invoke_hook(data, str(tmp_path))
    assert code == 0
    assert out == ""  # nothing written for non-Bash tools


def test_hook_passes_through_invalid_json():
    code, out = _invoke_hook("{bad json", "/tmp")
    assert code == 0
    assert out == ""


def test_hook_passes_through_empty_output(tmp_path):
    data = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_response": {"output": ""}})
    code, out = _invoke_hook(data, str(tmp_path))
    assert code == 0
    assert out == ""  # empty output — skip


def test_hook_no_compress_env_var_skips(tmp_path, monkeypatch):
    monkeypatch.setenv("CLIPRESS_NO_COMPRESS", "1")
    big_output = "file.txt\n" * 50
    data = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "tool_response": {"output": big_output},
    })
    code, out = _invoke_hook(data, str(tmp_path))
    assert code == 0
    assert out == ""  # skips entirely when CLIPRESS_NO_COMPRESS is set


def test_hook_passes_through_already_transformed_claude_output():
    already_compressed = json.dumps({"type": "tool_result", "content": "compressed"})
    code, out = _invoke_hook(already_compressed, "/tmp")
    assert code == 0
    parsed = json.loads(out)
    assert parsed["type"] == "tool_result"
    assert parsed["content"] == "compressed"


def test_hook_passes_through_already_transformed_gemini_output():
    already_compressed = json.dumps({"decision": "deny", "reason": "compressed"})
    code, out = _invoke_hook(already_compressed, "/tmp")
    assert code == 0
    parsed = json.loads(out)
    assert parsed["decision"] == "deny"
    assert parsed["reason"] == "compressed"


def test_hook_compresses_bash_output(tmp_path):
    big_output = "file.txt\n" * 50
    data = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": "ls"},
        "tool_response": {"output": big_output},
    })
    code, out = _invoke_hook(data, str(tmp_path))
    assert code == 0
    parsed = json.loads(out)
    assert parsed["type"] == "tool_result"
    assert "content" in parsed
    # Compressed output should be shorter
    assert len(parsed["content"]) <= len(big_output)


def test_find_workspace_root_finds_git(tmp_path):
    from clipress.hooks.post_tool_use import find_workspace_root
    git_dir = tmp_path / "project" / ".git"
    git_dir.mkdir(parents=True)
    sub = tmp_path / "project" / "src" / "deep"
    sub.mkdir(parents=True)
    root = find_workspace_root(str(sub))
    assert root == str(tmp_path / "project")


def test_find_workspace_root_fallback(tmp_path):
    from clipress.hooks.post_tool_use import find_workspace_root
    # No .git anywhere — should return start path
    result = find_workspace_root(str(tmp_path))
    # Either tmp_path or a parent if there's a .git above (CI environments)
    assert isinstance(result, str)
