# CLI Reference

## Commands

| Command | Description |
| :--- | :--- |
| `clipress init` | Create `.clipress/` in the current directory and install local agent hooks |
| `clipress init --global` | Install agent hooks globally in `~/.claude/` and `~/.gemini/`; remove any local project hooks |
| `clipress compress "<cmd>"` | Read stdin, compress, write to stdout |
| `clipress compress "<cmd>" --no-compress` | Read stdin, pass through unchanged |
| `clipress compress "<cmd>" --workspace <path>` | Use a specific workspace directory (default: CWD) |
| `clipress run <cmd> [args…]` | Spawn command in PTY (Unix only); compress output; auto-switch to passthrough on interactive prompt |
| `clipress run --stall-timeout <sec> <cmd>` | Custom stall timeout before interactive passthrough (default: 2s) |
| `clipress run --workspace <path> <cmd>` | Use a specific workspace directory |
| `clipress status` | Show workspace path, config path, and learned stats |
| `clipress validate` | Validate `.clipress/config.yaml`; exit non-zero on error |
| `clipress report` | Print full token-savings summary |
| `clipress restore` | Print latest raw output from workspace history |
| `clipress restore <id>` | Print raw output for a specific history entry id |
| `clipress restore --command "<cmd>"` | Print latest raw output for a command prefix |
| `clipress restore --list` | List recent history entries (id, strategy, token savings) |
| `clipress learn show` | Dump registry as JSON |
| `clipress learn reset [cmd]` | Reset confidence for one command, or all entries if no argument given |
| `clipress error-passthrough on\|off` | Toggle `pass_through_on_error` in config |
| `clipress uninstall` | Remove hooks, workspace data, and uninstall the package |
| `clipress uninstall --yes` | Skip confirmation prompt |
| `clipress uninstall --keep-data` | Remove hooks and uninstall but keep `.clipress/` workspace data |

---

## `clipress init`

```bash
# Project-local init (recommended)
cd your-project
clipress init

# Global init — covers all projects
clipress init --global
```

Creates the `.clipress/` workspace directory, installs agent hooks, and scaffolds:
- `config.yaml` with commented examples
- `extensions/example.yaml.disabled` with format documentation
- `.clipress-ignore` template

See [getting-started.md](getting-started.md) for the full workspace layout.

---

## `clipress compress`

```bash
# Basic usage
git log --oneline -100 | clipress compress "git log"

# Pass through without compressing
some_command | clipress compress "some_command" --no-compress

# Specify workspace explicitly
some_command | clipress compress "some_command" --workspace /path/to/project
```

Reads from stdin, writes compressed output to stdout. The command name argument (`"git log"`) is used for strategy lookup — it should match what you'd type in the shell.

---

## `clipress run` — PTY Mode

> **Unix only** — requires `pty`, `termios`, and `tty` modules. Use pipe mode (`cmd | clipress compress "cmd"`) on Windows.

```bash
# Long-running build
clipress run docker build -t myapp .

# Interactive program (auto-switches to passthrough)
clipress run python3

# Custom stall timeout
clipress run --stall-timeout 5 ansible-playbook site.yml

# Use -- to separate clipress flags from command flags
clipress run -- sh -c "echo hello && sleep 1 && echo world"
```

`clipress run` spawns the command inside a pseudo-terminal:

1. **TTY-aware programs** behave normally because they see a real terminal
2. **Interactive escape hatch** — if the process stops producing output for `--stall-timeout` seconds (default 2s) while still running, clipress assumes an interactive prompt:
   - Compresses and flushes whatever output has been buffered
   - Prints `[clipress: interactive prompt detected — switching to passthrough]` to stderr
   - Switches to raw bidirectional passthrough
3. **Streaming mode** — commands marked as streamable in the seed registry filter lines in real time instead of buffering until exit

The exit code of `clipress run` always matches the wrapped command's exit code.

---

## `clipress status`

```bash
clipress status
```

Prints:
- Active workspace path
- Config file path
- Number of learned commands
- Session and total token savings

---

## `clipress validate`

```bash
clipress validate
# → exits 0 on valid config
# → exits non-zero and prints error to stderr on invalid config
```

Use in CI to catch config errors early:

```bash
clipress validate && echo "Config OK"
```

---

## `clipress report`

```bash
clipress report
```

Prints a full token-savings summary across all learned commands, including compression ratios and call counts.

---

## `clipress restore`

```bash
# Show latest raw output
clipress restore

# Show latest raw output for a command
clipress restore --command "git log"

# Show compressed output instead
clipress restore --compressed

# List recent entries
clipress restore --list --limit 20

# Restore by id from --list
clipress restore 14
```

Useful when an agent needs full details after seeing compressed output. History is stored in `.clipress/history.db`.

---

## `clipress learn`

```bash
# Dump all learned entries as formatted JSON
clipress learn show

# Reset confidence for a specific command
clipress learn reset "git log"

# Reset all learned data
clipress learn reset
```

---

## `clipress error-passthrough`

```bash
clipress error-passthrough on   # pass error-shaped outputs through uncompressed
clipress error-passthrough off  # compress error-shaped outputs (default)
```

Toggles `pass_through_on_error` in `.clipress/config.yaml` and immediately clears the config cache.

---

## Environment Variables

| Variable | Effect |
| :--- | :--- |
| `CLIPRESS_NO_COMPRESS=1` | Bypass all compression; all output passes through unchanged. Useful for a single command or session where you need raw output. |
| `CLIPRESS_DEBUG=1` | Surface internal errors to stderr instead of silently falling back to raw output. Use when diagnosing unexpected pass-throughs. |

### Examples

```bash
# Skip compression for one command
CLIPRESS_NO_COMPRESS=1 some_command | clipress compress "some_command"

# Debug why a command isn't being compressed
CLIPRESS_DEBUG=1 git log --oneline -100 | clipress compress "git log"
```
