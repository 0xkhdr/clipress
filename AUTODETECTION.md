# Automatic Command Interception Setup

To ensure `clipress` automatically intercepts and compresses command outputs without manual piping, follow these configuration steps for your specific environment.

## 1. Claude Code

Claude Code supports a native `PostToolUse` hook that allows `clipress` to process output before it is returned to the agent.

### Requirements
- Run `clipress init` in your project root (generates `.claude/settings.json`).
- Or manually create `.claude/settings.json` with the configuration below.

### Implementation
Ensure your `.claude/settings.json` contains the following hook configuration:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "./.clipress/hook.sh"
          }
        ]
      }
    ]
  }
}
```

> **Best practice:** Use the relative path `./.clipress/hook.sh`. This keeps the configuration portable across different machines and CI environments.

---

## 2. Gemini CLI

Gemini CLI supports a native `AfterTool` hook that intercepts `run_shell_command` output before it reaches the model.

### Requirements
- Run `clipress init` in your project root (generates `.gemini/settings.json`).
- Or manually create `.gemini/settings.json` with the configuration below.

### Implementation
Ensure your `.gemini/settings.json` contains the following hook configuration:

```json
{
  "hooks": {
    "AfterTool": [
      {
        "matcher": "run_shell_command",
        "hooks": [
          {
            "type": "command",
            "command": "./.clipress/hook.sh"
          }
        ]
      }
    ]
  }
}
```

> **Best practice:** Like Claude Code, use the relative path `./.clipress/hook.sh` for portability.

---

## 3. Shell-based Agents (No Native Hooks)

For agents that execute commands in a standard shell without a native hook system (e.g., custom scripts, Cursor, or generic REPLs), use the `clipress_compress` helper.

### Requirements
- `clipress` installed and available on your `PATH`.
- `CLIPRESS_AGENT_MODE` set to `true` to suppress interactive prompts during background compression.

### Implementation
Source the helper in your shell session:

```bash
# Enable silent agent-style compression
export CLIPRESS_AGENT_MODE=true

# Source the helper (provides the clipress_compress function)
source ./.clipress/shell_hook.sh
```

Then pipe commands explicitly:
```bash
php artisan list | clipress compress "php artisan list"
```

> **Note:** The shell helper does **not** automatically intercept every command. Automatic shell-level interception is fragile, adds overhead to every command, and breaks interactive TTY programs. Always prefer native agent hooks when available.

---

## 4. Verification

Once applied, test the auto-detection by running a high-volume command without manual piping:

```bash
# No pipe needed — the native hook handles it automatically!
php artisan list
```

### Expected Result
The output should be automatically compressed, and if `engine.show_metrics` is enabled in `.clipress/config.yaml`, you should see a summary line like:
`clipress: saved 1,247 tokens (87% reduction via list)`

---

## 5. How Auto-Detection Works

When a command is intercepted by a native hook:
1. **Fast-path:** If the output is trivially small (< 200 chars, < 3 lines), the hook exits immediately with zero overhead.
2. **Lookup:** `clipress` checks if the command is already in its "learned" registry.
3. **Classification:** If unknown, the **Heuristic Classifier** analyzes the output's structure (e.g., repeating patterns, table borders, log formats).
4. **Strategy Assignment:** It assigns a "Shape" (List, Table, Progress, or Generic) and applies the corresponding compression strategy.
5. **Learning:** The decision is saved so future calls to the same command are even faster.

### Minimal Overhead Design
- **Process replacement:** The shell hook script uses `exec clipress hook`, replacing the shell process rather than forking a subshell.
- **Lazy imports:** Heavy modules (`engine`, `strategies`) are imported only when compression is actually needed.
- **Cached workspace discovery:** The workspace root lookup is LRU-cached across hook invocations.
- **Hot cache:** Frequently-seen commands are resolved from an in-memory LRU cache without touching disk.
- **Idempotent pass-through:** If `clipress` is not found, the hook script exits `0` silently so the agent is never blocked.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Double-compressed output | Both global and project hooks are active. | Run `clipress init` in the project; it auto-removes conflicting global hooks. |
| No compression at all | Hook path is absolute and points to a different machine. | Use `./.clipress/hook.sh` in `settings.json`. |
| Agent hangs on hook | `clipress` binary not in PATH. | Ensure `clipress` is installed (`pipx install clipress`) or use the Python module fallback. |
| Sensitive data compressed | Security patterns not matched. | Add custom regex to `.clipress/config.yaml` under `safety.security_patterns`. |
