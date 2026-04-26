# Integration Guide

clipress integrates with AI agents through hooks — small shell scripts that intercept tool output before it reaches the agent's context window. `clipress init` installs these hooks automatically.

---

## Claude Code

`clipress init` registers a `PostToolUse` hook in **`.claude/settings.json`** in your project directory. The hook fires on every `Bash` tool call and compresses the output before Claude sees it.

### Hook entry written to `.claude/settings.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "/your/project/.clipress/hook.sh" }]
      }
    ]
  }
}
```

### How it works

The hook reads JSON from stdin (provided by Claude Code), extracts `tool_response.output`, compresses it, and writes the result back as a `tool_result` JSON envelope.

### Scope

The hook is **project-scoped** — it only fires when Claude Code is running in that specific directory. Different projects have separate, isolated clipress workspaces.

### Global hook

`clipress init --global` installs the hook in `~/.claude/settings.json` instead, covering all projects by default. Running `clipress init` in a project directory after a global install automatically removes the global hook to prevent double compression.

---

## Gemini CLI

`clipress init` registers an `AfterTool` hook in **`.gemini/settings.json`** in your project directory. It intercepts every `run_shell_command` tool call transparently.

### Hook entry written to `.gemini/settings.json`

```json
{
  "hooks": {
    "AfterTool": [
      {
        "matcher": "run_shell_command",
        "hooks": [{ "type": "command", "command": "/your/project/.clipress/hook.sh" }]
      }
    ]
  }
}
```

The same `hook.sh` is shared between Claude Code and Gemini CLI. The `post_tool_use` module detects the tool name and formats the response accordingly:
- Claude Code: `tool_result` JSON envelope
- Gemini CLI: `{"decision": "deny", "reason": ...}` envelope

---

## How `hook.sh` Works

`clipress init` writes a small shell script to `.clipress/hook.sh` (or `~/.clipress/hook.sh` for global init). The agent settings point to this script, not to the clipress binary directly. At runtime the script discovers clipress using this priority order:

1. `clipress` on `PATH` — covers pipx, Homebrew, system pip, `uv tool install`, conda
2. Common single-user install locations — `~/.local/bin/clipress`, `~/.local/share/uv/tools/…`
3. Python module fallback — `python3 -m clipress.hooks.post_tool_use`
4. Silent `exit 0` — never blocks the agent if clipress is not found

This design means the hook survives:
- venv recreation
- Python version upgrades
- pipx reinstalls
- Machine migrations (after re-running `clipress init`)

> **Upgrading clipress** does not require re-running `clipress init`. The hook discovers the new binary automatically on the next invocation.

---

## Workspace Discovery

When a hook fires, it walks up the directory tree from the current working directory looking for the nearest `.clipress/` workspace. If none is found, it looks for a `.git/` root, then falls back to the current directory.

This means compression works correctly in **subdirectories** of a project — you don't need a `.clipress/` in every folder.

---

## Shell-Based Agents

For agents without a native hook system (Codex, Cursor terminal, etc.), source the shell hook and set `CLIPRESS_AGENT_MODE=true`:

```bash
export CLIPRESS_AGENT_MODE=true
source /path/to/project/.clipress/shell_hook.sh
```

This installs bash/zsh hooks that fire `clipress_compress()` around commands automatically.

You can also call compression explicitly:

```bash
some_command | clipress compress "some_command"
```

---

## Choosing the Right Mode

| Scenario | Recommended |
| :--- | :--- |
| Non-interactive command in a shell pipe | `cmd \| clipress compress "cmd"` |
| Long-running build (docker, cargo, npm) | `clipress run docker build -t app .` |
| Command that may prompt for input | `clipress run <cmd>` |
| Claude Code bash tool calls | Automatic via `PostToolUse` hook |
| Gemini CLI shell tool calls | Automatic via `AfterTool` hook |
| Shell agent (no native hook) | `source shell_hook.sh` + `CLIPRESS_AGENT_MODE=true` |

---

## Multi-Project Setup

Each project gets its own isolated clipress workspace:

```bash
# Project A
cd ~/projects/app-a
clipress init
# Creates app-a/.clipress/ and installs hooks there

# Project B
cd ~/projects/app-b
clipress init
# Creates app-b/.clipress/ — completely independent

# Global fallback for projects without a local workspace
clipress init --global
# ~/.claude/settings.json and ~/.gemini/settings.json updated
```

Per-project workspaces take priority over the global workspace. Use `clipress status` in any project to see which workspace is active.

---

## Verifying Hook Installation

```bash
clipress status
# Shows active workspace path, config path, hook locations, and token savings
```

```bash
# Manually test the hook
echo "line1\nline2\n..." | clipress compress "test-command"
```
