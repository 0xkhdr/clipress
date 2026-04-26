# Getting Started

## Prerequisites

| Requirement | Details |
| :--- | :--- |
| **Python** | 3.11 or newer |
| **pip or pipx** | `pipx` is recommended for isolated installs |
| **Unix / macOS** | `clipress run` (PTY mode) requires Unix — uses `pty`, `termios`, `tty`. Pipe mode works on all platforms |
| **click ≥ 8.0** | Installed automatically |
| **ruamel.yaml ≥ 0.18** | Installed automatically |
| **tiktoken** *(optional)* | `pip install tiktoken` — enables accurate token counting via `cl100k_base`. Without it, clipress estimates tokens as `len(text.split()) * 1.3` |

---

## Installation

### pipx (recommended)

Installs clipress in an isolated environment so it doesn't conflict with project dependencies:

```bash
pipx install clipress
```

### pip

```bash
pip install clipress
```

### From GitHub

```bash
pipx install "git+https://github.com/0xkhdr/clipress.git"
```

### One-liner (installs + initializes)

```bash
curl -sSL https://raw.githubusercontent.com/0xkhdr/clipress/main/install.sh | bash
```

The `install.sh` script:
- Detects whether it's running inside a cloned repo (presence of `pyproject.toml`) and installs from local source or directly from GitHub otherwise
- Finds the nearest git repository root and automatically runs `clipress init` there

### Local clone

```bash
git clone https://github.com/0xkhdr/clipress.git
cd clipress
./install.sh   # prefers pipx, falls back to pip, then runs clipress init
```

### PATH setup

If `clipress` is not found after installation:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add this to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.) to make it permanent.

---

## Verify Installation

```bash
clipress --version
# clipress, version 1.2.2
```

---

## Initialize a Workspace

Run this once per project to install hooks and create the workspace directory:

```bash
cd your-project
clipress init
```

This creates:

```
your-project/
├── .clipress/
│   ├── config.yaml            # local overrides (all keys optional)
│   ├── registry.db            # learned command patterns (SQLite)
│   ├── hook.sh                # runtime-discovery wrapper for agent hooks
│   ├── .clipress-ignore       # blocklist — one command prefix per line
│   └── extensions/
│       └── example.yaml.disabled
├── .claude/
│   └── settings.json          # PostToolUse hook for Claude Code
└── .gemini/
    └── settings.json          # AfterTool hook for Gemini CLI
```

### Global initialization

Install hooks globally so all projects are covered without per-project init:

```bash
clipress init --global
```

This writes hooks into `~/.claude/settings.json` and `~/.gemini/settings.json` and removes any existing local project hooks to prevent double compression.

> `clipress init` automatically removes any global hook if a local one is being installed. `clipress init --global` removes local project hooks. The two modes are mutually exclusive.

---

## First Use

After `clipress init`, compression is **automatic** for Claude Code and Gemini CLI — no further steps needed.

To test manually:

```bash
# Pipe mode — compress any command's output
git log --oneline -100 | clipress compress "git log"

# PTY mode — for interactive or long-running commands (Unix only)
clipress run docker build -t myapp .

# Check what's been learned and total tokens saved
clipress status
```

---

## Upgrading

```bash
pipx upgrade clipress
# or
pip install --upgrade clipress
```

You do **not** need to re-run `clipress init` after upgrading. The `hook.sh` script discovers the new binary automatically on the next hook invocation.

---

## Uninstalling

```bash
# Remove hooks, workspace data, and the package
clipress uninstall

# Skip confirmation prompt
clipress uninstall --yes

# Keep workspace data (.clipress/) but remove hooks and package
clipress uninstall --keep-data
```

---

## Next Steps

- [Integration guide](integration.md) — how hooks work for Claude Code, Gemini CLI, and shell agents
- [Configuration reference](configuration.md) — customize compression behavior
- [CLI reference](cli-reference.md) — all commands and flags
