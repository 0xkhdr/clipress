#!/usr/bin/env python3
"""
Claude Code / Gemini CLI / Codex CLI post-tool-use hook for clipress.
Registered in .claude/settings.json, .gemini/settings.json, and .codex/hooks.json.
Receives hook data via stdin as JSON, writes compressed output to stdout as JSON.

Claude Code (PostToolUse) input:
  { "tool_name": "Bash", "tool_input": {"command": "..."}, "tool_response": {"output": "..."} }
Claude Code output:
  { "type": "tool_result", "content": "compressed output" }

Gemini CLI (AfterTool) input:
  { "tool_name": "run_shell_command", "tool_input": {"command": "..."}, "tool_response": {"llmContent": "...", "returnDisplay": "..."} }
Gemini CLI output:
  { "decision": "deny", "reason": "compressed output" }

Codex CLI (PostToolUse) input:
  { "turn_id": "...", "tool_use_id": "...", "tool_name": "Bash", "tool_input": {"command": "..."}, "tool_response": {"output": "..."} }
Codex CLI output:
  { "decision": "block", "reason": "compressed output" }
"""

import sys
import json
import os
import functools

# Tool names for shell execution in each supported agent
_SHELL_TOOL_NAMES = {"Bash", "run_shell_command"}

# Minimum output size that justifies the overhead of compression.
# Anything smaller is passed through unchanged (fast-exit).
_MIN_CHARS_FOR_COMPRESSION = 200
_MIN_LINES_FOR_COMPRESSION = 3


def main():
    # Respect user/agent request to skip compression
    if os.environ.get("CLIPRESS_NO_COMPRESS", "").lower() in ("1", "true", "yes"):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if not isinstance(data, dict):
        sys.exit(0)

    tool_name = data.get("tool_name")

    # If another hook already transformed the output, pass it through unchanged.
    # This prevents double-compression when both global and project hooks exist.
    if tool_name is None:
        if data.get("type") == "tool_result" or data.get("decision") in {"deny", "block"}:
            print(json.dumps(data))
        sys.exit(0)

    if tool_name not in _SHELL_TOOL_NAMES:
        sys.exit(0)

    is_gemini = tool_name == "run_shell_command"
    # Codex PostToolUse payload includes turn_id/tool_use_id fields.
    is_codex = "turn_id" in data and "tool_use_id" in data

    command = data.get("tool_input", {}).get("command", "")
    tool_response = data.get("tool_response", {})

    # Normalise output field across agents.
    # Claude Code uses "output"/"stdout"/"stderr".
    # Gemini CLI uses "llmContent" (may be str or list of Parts) and "returnDisplay".
    if isinstance(tool_response, str):
        raw_output = tool_response
    else:
        if is_gemini:
            llm_content = tool_response.get("llmContent", "")
            if isinstance(llm_content, list):
                raw_output = "\n".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in llm_content
                )
            else:
                raw_output = llm_content or tool_response.get("returnDisplay", "")
        else:
            raw_output = (
                tool_response.get("output")
                or tool_response.get("stdout", "")
            )
            stderr_text = tool_response.get("stderr", "") if isinstance(tool_response, dict) else ""
            if stderr_text and raw_output and stderr_text not in raw_output:
                raw_output = raw_output + "\n" + stderr_text
            elif stderr_text and not raw_output:
                raw_output = stderr_text

    if not command or not raw_output:
        sys.exit(0)

    output = raw_output if isinstance(raw_output, str) else str(raw_output)

    # Fast-path: trivial outputs are never worth compressing.  This avoids the
    # cost of workspace discovery, config loading, and strategy resolution for
    # the common case of short shell responses.
    if len(output) < _MIN_CHARS_FOR_COMPRESSION and output.count("\n") < _MIN_LINES_FOR_COMPRESSION:
        sys.exit(0)

    workspace = find_workspace_root(os.getcwd())

    # Lazy import so the hook starts instantly for pass-through calls.
    from clipress.engine import compress

    compressed = compress(command, output, workspace)

    if is_gemini:
        print(json.dumps({"decision": "deny", "reason": compressed}))
    elif is_codex:
        # In Codex PostToolUse, block+reason replaces tool result with our output.
        print(json.dumps({"decision": "block", "reason": compressed}))
    else:
        print(json.dumps({"type": "tool_result", "content": compressed}))
    sys.exit(0)


@functools.lru_cache(maxsize=128)
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
