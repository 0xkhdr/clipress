# clipress
Universal CLI output compressor for AI agents.

Ships lean. Gets smarter with every call.

## Description
A Python-based CLI proxy that intercepts bash command output before it reaches an AI agent's context window, compresses it using a hybrid classifier + registry system, and returns only the semantically meaningful portion of the output.

## Quick Start

```bash
pip install clipress
# Or, from a source checkout:
./install.sh            # prefers pipx, falls back to pip, then runs `clipress init`

# Initialize a workspace (only if you didn't use install.sh)
cd your-project
clipress init

# Compress a command's output
git log --oneline -100 | clipress compress "git log"
```

## Integration & Setup

### For Claude Code
Uses `.claude/settings.json` PostToolUse hook automatically. No env setup required.

### For Shell-Based Agents (Gemini CLI, Codex, Pi)
Must set `CLIPRESS_AGENT_MODE=true` before starting the agent to enable the shell wrapper.
```bash
export CLIPRESS_AGENT_MODE=true
# start your agent
gemini-cli
```

> **Note on the shell hook:** `clipress/hooks/shell_hook.sh` provides a `clipress_compress()` helper function
> for use in shell scripts. It does **not** auto-intercept every command — it must be called explicitly
> or wired via a `PROMPT_COMMAND`/`preexec` hook in your shell config. The recommended pattern for
> shell-based agents is the pipe:
> ```bash
> some_command | clipress compress "some_command"
> ```

## Configuration

### Workspace Initialization
```bash
clipress init   # creates .compressor/config.yaml in the current directory
```

### Config File (`.compressor/config.yaml`)
```yaml
engine:
  show_metrics: true          # print token savings to stderr
  min_lines_to_compress: 15   # skip outputs shorter than this
  strip_ansi: true            # strip ANSI escape codes before processing
  pass_through_on_error: true # return raw output when an error is detected
  max_output_bytes: 10485760  # 10 MB limit — larger outputs are passed through

# Global output contracts
contracts:
  global:
    always_keep:
      - "CRITICAL"          # any line matching this regex is never removed
    always_strip:
      - "^\\[debug\\]"      # any line matching this regex is always removed

# Per-command overrides (merged on top of global contracts)
commands:
  "git status":
    always_keep:
      - "^On branch"
  "docker ps":
    always_strip:
      - "CREATED"
```

### User Extensions (`.compressor/extensions/*.yaml`)
Add custom seed rules for your own commands. User extensions override built-in seeds.
Matching uses longest command key first (e.g., `docker ps -a` takes priority over `docker ps`).

```yaml
# .compressor/extensions/mytools.yaml
"my-deploy":
  strategy: progress
  params:
    keep: errors_and_final

"kubectl get pods":
  strategy: table
  params:
    max_rows: 30
```

### Blocklist (`.compressor/.compressor-ignore`)
One command prefix per line. Any command starting with a listed prefix is passed through uncompressed.
Lines starting with `#` are comments.

```
# Skip compression for these commands
kubectl exec
psql
mysql
```

## CLI Reference

| Command | Description |
| :--- | :--- |
| `clipress init` | Initializes `.compressor/` in the current directory |
| `clipress status` | Shows workspace status, config path, and learned stats |
| `clipress compress "<cmd>"` | Core command. Reads stdin, writes compressed output to stdout |
| `clipress validate` | Checks if `.compressor/config.yaml` is valid |
| `clipress report` | Prints a summary of token savings |
| `clipress learn show` | Displays the `registry.json` content |
| `clipress learn reset [cmd]` | Resets confidence for a specific command or all learned data |
| `clipress error-passthrough on\|off` | Toggles whether errors should skip compression |

## Known Limitations & Architecture Notes

### Streaming Pass-Through
`clipress` is **not a streaming pass-through**. It requires the full stdout/stderr of a command before it can classify, analyze, and compress the output. For very long-running commands that yield output slowly, you will not see real-time output updates.

### Thread Safety
The compressor is **NOT thread‑safe**. Concurrent calls from an agent running multiple bash commands simultaneously may corrupt the learned registry (`registry.json`) or the in-memory hot cache. File locking (`fcntl.flock`) is used for the registry, but agents should still await command completion before executing the next command when possible.

### Output Size Limit
Outputs exceeding `max_output_bytes` (default: 10 MB) are passed through without compression to prevent out-of-memory errors. A warning is printed to stderr.

### Cursor / Copilot (Integrated Terminal)
Coverage is partial — it only intercepts direct bash commands run in the terminal, not internal file APIs or custom executions via their extensions.

## Core Philosophy
- **Minimal Core**: Intelligence lives in the workspace, not the package.
- **Adaptive**: Learns from the command outputs over time.
- **Consistent**: Output contracts define what the user always sees.
- **Extendible**: Users shape compression through YAML only.
