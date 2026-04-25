#!/usr/bin/env python3
"""
Claude Code / Gemini CLI PostToolUse hook for clipress.
Registered in .claude/settings.json (Claude Code) and .gemini/settings.json (Gemini CLI).
Receives hook data via stdin as JSON, writes compressed output to stdout as JSON.

Claude Code hook input:
  { "tool_name": "Bash", "tool_input": {"command": "..."}, "tool_response": {"output": "..."} }

Gemini CLI hook input:
  { "tool_name": "run_shell_command", "tool_input": {"command": "..."}, "tool_response": {"output": "..."} }

Hook output (both agents):
  { "type": "tool_result", "content": "compressed output" }
"""

import sys
import json
import os

# Tool names for shell execution in each supported agent
_SHELL_TOOL_NAMES = {"Bash", "run_shell_command"}


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if not isinstance(data, dict):
        sys.exit(0)

    if data.get("tool_name") not in _SHELL_TOOL_NAMES:
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    tool_response = data.get("tool_response", {})

    # Normalise output field: prefer "output", fall back to "stdout", then "stderr".
    # Some agents combine stdout+stderr in "output"; others split them.
    if isinstance(tool_response, str):
        raw_output = tool_response
    else:
        raw_output = (
            tool_response.get("output")
            or tool_response.get("stdout", "")
        )
        # Also append stderr if present and not already in output
        stderr_text = tool_response.get("stderr", "") if isinstance(tool_response, dict) else ""
        if stderr_text and raw_output and stderr_text not in raw_output:
            raw_output = raw_output + "\n" + stderr_text
        elif stderr_text and not raw_output:
            raw_output = stderr_text

    if not command or not raw_output:
        sys.exit(0)

    output = raw_output if isinstance(raw_output, str) else str(raw_output)

    workspace = find_workspace_root(os.getcwd())

    from clipress.engine import compress

    compressed = compress(command, output, workspace)

    print(json.dumps({"type": "tool_result", "content": compressed}))
    sys.exit(0)


def find_workspace_root(start: str) -> str:
    """Walk up directory tree to find .clipress/ root, then .git, then fall back to start."""
    path = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(path, ".clipress")):
            return path
        if os.path.exists(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return start


if __name__ == "__main__":
    main()
