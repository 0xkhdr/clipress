# clipress

Universal CLI output compressor for AI agents. Ships lean. Gets smarter with every call.

A Python-based CLI proxy that intercepts bash command output before it reaches an AI agent's context window, compresses it using a hybrid classifier + registry system, and returns only the semantically meaningful portion.

---

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Integration & Setup](#integration--setup)
- [Configuration](#configuration)
- [Compression Strategies](#compression-strategies)
- [The Learning System](#the-learning-system)
- [Output Contracts](#output-contracts)
- [Safety & Security](#safety--security)
- [CLI Reference](#cli-reference)
- [Project Structure](#project-structure)
- [Architecture Notes & Limitations](#architecture-notes--limitations)

---

## Quick Start

**Requires Python 3.11+.**

### Install

```bash
# One-liner (installs from GitHub, then runs `clipress init`)
curl -sSL https://raw.githubusercontent.com/0xkhdr/clipress/main/install.sh | bash

# Recommended — isolated install via pipx
pipx install clipress

# Or with pip
pip install clipress

# Or directly from GitHub
pipx install "git+https://github.com/0xkhdr/clipress.git"

# Or from a local clone (runs init automatically)
git clone https://github.com/0xkhdr/clipress.git
cd clipress
./install.sh            # prefers pipx, falls back to pip, then runs `clipress init`
```

> `install.sh` detects whether it is running inside the cloned repo (presence of `pyproject.toml`) and installs from local source. When run outside a repo (including the curl path) it installs directly from GitHub.

### Initialize and use

```bash
# Initialize a workspace
cd your-project
clipress init

# Compress a command's output
git log --oneline -100 | clipress compress "git log"
```

---

## How It Works

### The Compression Pipeline

Every call to `clipress compress "<cmd>"` runs through this pipeline:

```
stdin
  │
  ├─ [SIZE GUARD]       output > max_output_bytes (10 MB)? → pass through
  ├─ [ANSI STRIP]       remove escape codes (when strip_ansi=true)
  ├─ [SAFETY GATE]      blocklist / security patterns / binary / too short / error? → pass through
  │
  ├─ [STRATEGY RESOLUTION]  (in priority order)
  │     1. Hot cache         — in-memory LRU for proven commands (≥10 calls, confidence ≥0.85)
  │     2. Seed registry     — built-in rules for common commands (git, docker, pytest, …)
  │     3. Workspace learner — previously learned patterns stored in registry.json
  │     4. Classifier        — heuristic shape detection as fallback
  │
  ├─ [COMPRESS]         run the matched strategy
  ├─ [CONTRACTS]        apply always_keep / always_strip rules
  ├─ [REGRESSION GUARD] compressed > original (bytes or tokens)? → return original
  ├─ [METRICS]          count tokens saved, log to stderr if show_metrics=true
  └─ [LEARN]            update registry.json with outcome
  │
stdout (compressed output)
```

### Worked Example: `git log | clipress compress "git log"`

1. **Size guard** — 100-line log ~2 KB, well under 10 MB.
2. **ANSI strip** — no codes present, pass.
3. **Safety gate** — not blocked, not binary, 100 lines > 15 minimum.
4. **Strategy resolution** — seed registry has `"git log" → { strategy: "list", params: { max_lines: 20 } }`.
5. **Compress** — `ListStrategy` keeps head (20) + tail (5), inserts `... [75 more items]`.
6. **Contracts** — no per-command rules, no change.
7. **Regression guard** — 30 lines vs. 100 lines, pass.
8. **Metrics** — ~1950 tokens saved (75% reduction), printed to stderr if enabled.
9. **Learn** — registry entry created: `{ strategy: "list", calls: 1, confidence: 0.50 }`.

---

## Integration & Setup

### Claude Code

`clipress init` automatically registers a `PostToolUse` hook in `.claude/settings.json`. No further configuration needed — every Bash tool call is intercepted transparently.

The hook entry looks like:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "python -m clipress.hooks.post_tool_use" }]
      }
    ]
  }
}
```

The hook reads JSON from stdin (provided by Claude Code), compresses `tool_response.output`, and writes the result back as a `tool_result` JSON envelope.

### Shell-Based Agents (Gemini CLI, Codex, etc.)

Set `CLIPRESS_AGENT_MODE=true` before starting the agent to enable the shell wrapper.

```bash
export CLIPRESS_AGENT_MODE=true
gemini-cli
```

The shell hook (`clipress/hooks/shell_hook.sh`) provides a `clipress_compress()` helper but does **not** auto-intercept every command. Wire it via `PROMPT_COMMAND` / `preexec`, or call explicitly:

```bash
some_command | clipress compress "some_command"
```

---

## Configuration

### Workspace Layout

`clipress init` creates the following in your project root:

```
.clipress/
├── config.yaml           # local overrides (merged on top of defaults)
├── registry.json         # learned command patterns (auto-managed)
├── .clipress-ignore    # blocklist — one command prefix per line
└── extensions/           # custom seed rules
    └── *.yaml
```

### Config File (`.clipress/config.yaml`)

All keys are optional — unset keys fall back to the built-in defaults below.

```yaml
engine:
  show_metrics: false         # print token savings to stderr after each call
  min_lines_to_compress: 15   # skip outputs shorter than this (pass through raw)
  strip_ansi: true            # strip ANSI escape codes before processing
  pass_through_on_error: true # return raw output when error shape is detected
  max_output_bytes: 10485760  # 10 MB — larger outputs are passed through

safety:
  binary_non_ascii_ratio: 0.3 # non-ASCII chars > 30% of first 4 KB → treat as binary
  security_patterns: []       # additional regex patterns (additive to built-in list)

contracts:
  global:
    always_keep: []           # regex — matching lines are never removed
    always_strip: []          # regex — matching lines are always removed

commands:                     # per-command contract overrides
  "git status":
    always_keep:
      - "^On branch"
  "docker ps":
    always_strip:
      - "CREATED"
```

### User Extensions (`.clipress/extensions/*.yaml`)

Define custom seed rules for your own commands. User extensions override built-in seeds. Matching is longest-key-first, so `docker ps -a` takes priority over `docker ps`.

```yaml
# .clipress/extensions/mytools.yaml

"my-deploy":
  strategy: progress
  params:
    keep: errors_and_final

"kubectl get pods":
  strategy: table
  params:
    max_rows: 30
```

Rename any `.yaml` file to `.yaml.disabled` to exclude it without deleting it.

### Blocklist (`.clipress/.clipress-ignore`)

One command prefix per line. Any command starting with a listed prefix is passed through uncompressed. Lines starting with `#` are comments.

```
# .clipress/.clipress-ignore
kubectl exec
psql
mysql
```

---

## Compression Strategies

The classifier detects one of eight **shapes** and routes output to the matching strategy. Each strategy accepts optional `params` via seeds or extensions.

### Shape Detection

The classifier scores each output against all shapes and picks the highest scorer. A shape must score ≥ 0.5 to win; otherwise the output is treated as `generic`.

| Shape | Key signals |
| :--- | :--- |
| `list` | High line count, similar line lengths, few colons, no diff markers |
| `progress` | Percentage/fraction patterns, words like *downloading*, *fetching*, *step* |
| `test` | PASSED/FAILED/ERROR keywords, test names, summary lines (`====`) |
| `diff` | `+`/`-` prefix lines, `@@` hunks, `---`/`+++` headers |
| `table` | Separator line (`---`/`+++`/`\|`), consistent column count, uppercase header |
| `keyvalue` | >60% of lines match `key: value` or `key=value` |
| `error` | `Traceback`, `Exception`, `File "..."` frames, indented code snippets |
| `generic` | Fallback — basic truncation |

### Strategy Details

#### `generic` — Fallback truncation

- Deduplicates ≥3 consecutive identical lines → `[repeated Nx]`
- Keeps head + tail if output exceeds `max_lines`

| Param | Default |
| :--- | :--- |
| `max_lines` | 50 |
| `head_lines` | 20 |
| `tail_lines` | 10 |
| `dedup_min_repeats` | 3 |

#### `list` — File listings, grep results

- Optional deduplication
- Optional directory grouping (3+ files in same dir → `dir/... [N files]`)
- Keeps head + tail if over limit

| Param | Default |
| :--- | :--- |
| `max_lines` | 30 |
| `head_lines` | 20 |
| `tail_lines` | 5 |
| `group_by_directory` | `false` |
| `dedup` | `false` |

#### `progress` — Build logs, downloads, installs

- Strips percentage-only lines and ETA/speed lines
- Always keeps errors and the final line

| Param | Default |
| :--- | :--- |
| `keep` | `"final_line"` (`"errors_and_final"` also available) |
| `strip_percentage` | `true` |

#### `test` — Unit test results (pytest, jest, cargo test, …)

- Extracts failures + up to `max_traceback_lines` of traceback per failure
- Always includes summary lines (last ~5 lines matching summary pattern)

| Param | Default |
| :--- | :--- |
| `keep` | `"failed_only"` (`"all"` or `"errors_and_final"` also available) |
| `max_traceback_lines` | 8 |

#### `diff` — Git diff, patch files

- Keeps `+++`/`---` headers, `@@` hunks, changed lines with `context_lines` of context
- Falls back to per-file summary if output exceeds `max_lines`

| Param | Default |
| :--- | :--- |
| `max_lines` | 80 |
| `context_lines` | 2 |

#### `table` — `docker ps`, `kubectl get`, columnar output

- Preserves header and separator row
- Truncates rows and cell content

| Param | Default |
| :--- | :--- |
| `max_rows` | 20 |
| `max_columns` | 5 |
| `max_cell_length` | 40 |

#### `keyvalue` — Config dumps, `systemctl status`, `docker inspect`

- Strips keys matching `always_strip_keys` regex list (e.g., timestamp fields)
- Truncates to `max_lines` keeping non-timestamp pairs first

| Param | Default |
| :--- | :--- |
| `max_lines` | 20 |
| `always_strip_keys` | `[]` |

#### `error` — Stack traces, exceptions

- Keeps Traceback/Exception header + up to `max_traceback_lines` frames
- Optionally strips stdlib/venv frames (site-packages, .pyenv, .venv, frozen, …)

| Param | Default |
| :--- | :--- |
| `max_traceback_lines` | 10 |
| `strip_stdlib_frames` | `true` |

---

## The Learning System

clipress maintains a three-tier knowledge base that grows more accurate with each call.

### Tier 1 — Hot Cache (in-memory, per-process)

An LRU `OrderedDict` (max 100 entries) protected by `threading.Lock`. Commands that have been called ≥10 times with confidence ≥0.85 are promoted here. Hot-cached commands skip classification entirely — fastest possible path.

### Tier 2 — Seed Registry (built-in + user extensions)

Pre-defined strategies for common tools (`git`, `docker`, `pytest`, `kubectl`, `npm`, …) shipped with the package in `clipress/registry/seeds.json`. User extensions in `.clipress/extensions/*.yaml` are merged on top with `user_override: true`.

Seeds are sorted **longest-key-first** so `docker ps -a` matches before `docker ps`.

### Tier 3 — Workspace Learner (persistent, disk-backed)

Stored in `.clipress/registry.json`. Each command gets an entry:

```json
"git log": {
  "source": "learned",
  "strategy": "list",
  "calls": 42,
  "confidence": 0.92,
  "avg_raw_tokens": 1024,
  "avg_compressed_tokens": 256,
  "compression_ratio": 0.25,
  "hot": true,
  "user_override": false,
  "last_seen": "2026-04-25T12:34:56Z",
  "params": {}
}
```

A learner entry is only used for strategy resolution once `confidence ≥ 0.85`. Below that threshold the classifier runs and the result is compared to the stored strategy to update confidence.

### Confidence Mechanics

| Event | Delta |
| :--- | :--- |
| Strategy matches previous | `+0.08` |
| Strategy differs | `−0.20` |
| Confidence drops below `0.50` | reset to `0.50`, adopt new strategy |
| Confidence ≥ `0.85` AND calls ≥ 10 | promoted to hot (classification skipped) |
| Confidence ≥ `0.95` | locked (confidence stops updating) |

The asymmetry (−0.20 vs +0.08) means wrong predictions degrade confidence faster than correct ones restore it, preventing the learner from sticking with a mismatched strategy.

### Registry File Safety

- **File locking**: `fcntl.flock()` on `registry.lock` prevents concurrent write corruption.
- **Async saves**: A single background daemon thread coalesces bursts of `record()` calls into one disk write.
- **Backfilling**: Missing keys in older registry files are auto-filled on load to handle version skew.

---

## Output Contracts

Contracts are guarantees about what always appears (or never appears) in compressed output, regardless of which strategy ran.

```yaml
contracts:
  global:
    always_keep:
      - "CRITICAL"       # regex — line is restored even if compressed away
    always_strip:
      - "^\\[debug\\]"   # regex — line is always removed

commands:
  "make build":
    always_keep:
      - "^Build succeeded"
      - "^Build failed"
```

**Application order** (applied after strategy compression):

1. `always_keep` — matching lines from the original output are appended if not already present
2. `always_strip` — matching lines are removed from the result

Per-command contracts are merged on top of global contracts. This means a command-level `always_keep` adds to, rather than replaces, the global list.

---

## Safety & Security

### Automatic Pass-Through Conditions

clipress passes output through **without compression** when any of these conditions is met:

| Condition | Default behavior |
| :--- | :--- |
| Output > `max_output_bytes` | Pass through, warn to stderr |
| Command in blocklist | Pass through |
| Security pattern matched | Pass through |
| Binary output detected | Pass through |
| Output < `min_lines_to_compress` | Pass through |
| Error shape + `pass_through_on_error=true` | Pass through |

### Built-In Security Patterns

The following patterns are always checked (word-boundary aware):

- Credential files: `.env*`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`
- Secret keywords: `credentials`, `secret`, `password`, `api_key`, `api-key`
- Token patterns: `AWS_SECRET`, `GITHUB_TOKEN`, `bearer <token>`, `-----BEGIN`

Sensitive environment commands (`printenv`, `declare`, `env`, `set`) are unconditionally blocked.

Add project-specific patterns in config:

```yaml
safety:
  security_patterns:
    - "MY_INTERNAL_SECRET"
    - "PROD_DB_PASSWORD"
```

### Binary Detection

Outputs with null bytes (`\x00`) or a non-ASCII ratio above `binary_non_ascii_ratio` (default 0.30, sampled from first 4 KB) are treated as binary and passed through.

### Error Handling Philosophy

clipress is a compressor, not a validator. It must never crash the agent or block legitimate commands. The engine wraps the entire pipeline in a top-level `try/except` and returns the original output on any failure. Set `CLIPRESS_DEBUG=1` to surface suppressed errors to stderr.

---

## CLI Reference

| Command | Description |
| :--- | :--- |
| `clipress init` | Create `.clipress/` in the current directory with default config |
| `clipress compress "<cmd>"` | Read stdin, write compressed output to stdout |
| `clipress status` | Show workspace path, config path, and learned stats |
| `clipress validate` | Validate `.clipress/config.yaml`; exit non-zero on error |
| `clipress report` | Print full token-savings summary |
| `clipress learn show` | Dump `registry.json` as JSON |
| `clipress learn reset [cmd]` | Reset confidence for one command, or all entries |
| `clipress error-passthrough on\|off` | Toggle `pass_through_on_error` in config |
| `clipress uninstall` | Remove the PostToolUse hook from `.claude/settings.json` |

---

## Project Structure

```
clipress/
├── clipress/
│   ├── engine.py               # main pipeline orchestrator
│   ├── classifier.py           # heuristic shape detection
│   ├── learner.py              # registry management & confidence tracking
│   ├── config.py               # config loading, validation, caching
│   ├── safety.py               # security & binary detection gates
│   ├── metrics.py              # token counting & reporting
│   ├── ansi.py                 # ANSI escape code stripping
│   ├── cli.py                  # Click CLI entry point
│   ├── hooks/
│   │   └── post_tool_use.py    # Claude Code PostToolUse hook
│   ├── strategies/
│   │   ├── base.py
│   │   ├── generic_strategy.py
│   │   ├── list_strategy.py
│   │   ├── progress_strategy.py
│   │   ├── test_strategy.py
│   │   ├── diff_strategy.py
│   │   ├── table_strategy.py
│   │   ├── keyvalue_strategy.py
│   │   └── error_strategy.py
│   ├── registry/
│   │   └── seeds.json          # built-in command seeds
│   └── defaults/
│       └── config.yaml         # default configuration
└── tests/
```

### Key Interactions

```
cli.py
  └─ engine.compress()
       ├─ safety.should_skip()
       ├─ config.get_config()
       ├─ config.build_seed_registry()
       ├─ learner.Learner.lookup()
       ├─ classifier.detect()
       ├─ strategies.STRATEGIES[shape].compress()
       ├─ engine._apply_contract()
       └─ learner.Learner.record()
```

---

## Architecture Notes & Limitations

### Not a Streaming Pass-Through

clipress buffers the entire output before classifying and compressing. Long-running commands that emit output slowly will not show real-time updates — the agent sees the compressed result only after the command exits.

### Thread Safety

The compressor is **not fully thread-safe**. Concurrent calls may cause registry write conflicts despite `fcntl.flock()`. The in-memory hot cache is protected by `threading.Lock`, but agents should avoid firing multiple bash commands in parallel when possible.

### Token Counting

If `tiktoken` is installed, clipress uses the `cl100k_base` encoding for accurate token counts. Otherwise it falls back to `len(text.split()) * 1.3`. Install tiktoken for reliable savings metrics:

```bash
pip install tiktoken
```

### Cursor / Copilot (Integrated Terminal)

Coverage is partial. Only direct bash commands run in the terminal are intercepted; internal file APIs and extension-level executions are not.

### Size-Regression Guard

If the compressed output is larger than the original (by byte count or token count), clipress silently returns the original. Compression must always be net-negative in size — it never makes output bigger.

---

## Core Philosophy

- **Minimal Core** — intelligence lives in the workspace, not the package.
- **Adaptive** — learns from command outputs over time; proven commands skip classification entirely.
- **Consistent** — output contracts guarantee critical lines always appear (or never appear), regardless of compression.
- **Extensible** — users shape compression entirely through YAML; no code required.
- **Safe by default** — security-sensitive content is never compressed; any internal error returns the original output unchanged.
