# clipress

![Version](https://img.shields.io/badge/version-1.2.2-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.11%2B-blue)

Universal CLI output compressor for AI agents. Intercepts bash command output before it reaches the agent's context window and returns only the semantically meaningful portion.

---

## Why clipress?

| Command | Input | Output | Reduction |
| :--- | :--- | :--- | :---: |
| `git log --oneline -100` | 100 lines / 2 KB | 25 lines / 500 B | **75%** |
| `docker build -t app .` | 500 lines / 40 KB | 75 lines / 6 KB | **85%** |
| `pytest tests/ 2>&1` | 1000 lines / 80 KB | 50 lines / 4 KB | **95%** |
| `docker ps -a` | 50 containers / 10 KB | 20 rows + header / 2 KB | **80%** |
| `ls -R large_dir/` | 200 lines / 8 KB | 60 lines / 2.4 KB | **70%** |

---

## Quick Install

```bash
# Recommended — isolated install
pipx install clipress

# Or with pip
pip install clipress

# One-liner (installs from GitHub and runs clipress init)
curl -sSL https://raw.githubusercontent.com/0xkhdr/clipress/main/install.sh | bash
```

> If `clipress` is not found after installation: `export PATH="$HOME/.local/bin:$PATH"`

---

## Quick Start

```bash
# Initialize a workspace (writes hooks into .claude/ and .gemini/)
cd your-project
clipress init

# Compress a command's output manually
git log --oneline -100 | clipress compress "git log"

# Run a long-running command with PTY support (Unix only)
clipress run docker build -t myapp .

# Check workspace status and token savings
clipress status
```

After `clipress init`, compression is **automatic** — every bash command run by Claude Code or Gemini CLI is intercepted by the installed hook with no further setup.

---

## How It Works

clipress sits between the shell and the AI agent. On every bash tool call:

1. **Safety gate** — secrets, binary data, and short outputs pass through unchanged
2. **Strategy resolution** — checks hot cache → seed registry → learned patterns → heuristic classifier
3. **Compression** — applies the matched strategy (list, diff, test, progress, table, key-value, error, generic)
4. **Contracts** — enforces `always_keep` / `always_strip` rules from config
5. **Regression guard** — if compressed output is larger than the original, the original is returned
6. **Learning** — updates the workspace registry with the outcome

Full pipeline details: [docs/compression.md](docs/compression.md)

---

## Documentation

| Topic | File |
| :--- | :--- |
| Installation, prerequisites, first init | [docs/getting-started.md](docs/getting-started.md) |
| Claude Code, Gemini CLI, shell agent hooks | [docs/integration.md](docs/integration.md) |
| Config file, workspace layout, extensions, contracts | [docs/configuration.md](docs/configuration.md) |
| Compression pipeline, strategies, shapes, streaming | [docs/compression.md](docs/compression.md) |
| Three-tier learning, confidence, fuzzy matching | [docs/learning-system.md](docs/learning-system.md) |
| All CLI commands, flags, environment variables | [docs/cli-reference.md](docs/cli-reference.md) |
| Safety gates, security patterns, pass-through rules | [docs/security.md](docs/security.md) |
| Project structure, architecture, limitations | [docs/architecture.md](docs/architecture.md) |

---

## Integration at a Glance

**Claude Code** — `clipress init` writes a `PostToolUse` hook into `.claude/settings.json`. Every `Bash` tool call is automatically compressed.

**Gemini CLI** — `clipress init` writes an `AfterTool` hook into `.gemini/settings.json`. Every `run_shell_command` call is automatically compressed.

**Shell agents** (Codex, Cursor terminal, etc.) — source `.clipress/shell_hook.sh` and set `CLIPRESS_AGENT_MODE=true`.

See [docs/integration.md](docs/integration.md) for full hook details.

---

## Core Philosophy

- **Minimal core** — intelligence lives in the workspace, not the package
- **Adaptive** — learns from command outputs; proven commands skip classification entirely
- **Consistent** — contracts guarantee critical lines always appear or never appear
- **Extensible** — shaped entirely through YAML, no code required
- **Safe by default** — security-sensitive content is never compressed; any internal error returns the original output unchanged
- **Memory-bounded** — rolling deque caps memory use regardless of output size
- **Concurrency-safe** — SQLite WAL mode supports parallel agent processes on the same workspace
