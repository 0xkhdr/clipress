#!/usr/bin/env python3
"""
Claude Code PostToolUse hook for clipress.
Registered in .claude/settings.json.
Receives hook data via stdin as JSON.
Writes compressed output to stdout as JSON.

Hook input schema (from Claude Code):
{
  "tool_name": "Bash",
  "tool_input": { "command": "git status" },
  "tool_response": { "output": "..." }
}

Hook output schema (to Claude Code):
{
  "type": "tool_result",
  "content": "compressed output here"
}
"""

import sys
import json
import os


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    output = data.get("tool_response", {}).get("output", "")

    if not command or not output:
        sys.exit(0)

    workspace = find_workspace_root(os.getcwd())

    from clipress.engine import compress

    compressed = compress(command, output, workspace)

    # Always output JSON envelope
    result = {"type": "tool_result", "content": compressed}
    print(json.dumps(result))
    sys.exit(0)


def find_workspace_root(start: str) -> str:
    """Walk up directory tree to find .git root."""
    path = os.path.abspath(start)
    while path != os.path.dirname(path):
        if os.path.exists(os.path.join(path, ".git")):
            return path
        path = os.path.dirname(path)
    return start


if __name__ == "__main__":
    main()
