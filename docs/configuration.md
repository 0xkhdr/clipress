# Configuration

## Workspace Layout

`clipress init` creates the following structure in your project root:

```
.clipress/
├── config.yaml                    # local overrides — merged on top of built-in defaults
├── registry.db                    # learned command patterns (SQLite, WAL mode)
├── hook.sh                        # runtime-discovery wrapper referenced by agent settings
├── .clipress-ignore               # blocklist — one command prefix per line
└── extensions/                    # custom seed rules
    ├── example.yaml.disabled      # rename to .yaml to activate
    └── *.yaml

.claude/
└── settings.json                  # Claude Code PostToolUse hook

.gemini/
└── settings.json                  # Gemini CLI AfterTool hook
```

Both `.claude/settings.json` and `.gemini/settings.json` are project-scoped. Each project gets its own isolated workspace.

> **Migration**: `registry.json` from older versions is automatically migrated to `registry.db` on first run and renamed to `registry.json.migrated`.

---

## Config File (`.clipress/config.yaml`)

All keys are optional. Unset keys fall back to the built-in defaults shown below.

```yaml
engine:
  show_metrics: false         # print token savings to stderr after each call
  min_lines_to_compress: 15   # skip outputs shorter than this (pass through raw)
  hot_cache_threshold: 10     # calls before a command is promoted to in-memory hot cache
  strip_ansi: true            # strip ANSI escape codes before processing
  pass_through_on_error: false # return raw output when error shape is detected
  max_output_bytes: 10485760  # 10 MB — outputs larger than this pass through

  heartbeat_enabled: true
  heartbeat_interval_seconds: 5
  heartbeat_line_threshold: 500

safety:
  binary_non_ascii_ratio: 0.3 # non-ASCII ratio > 30% of first 4 KB → treat as binary
  security_patterns: []       # additional regex patterns (additive to built-in list)

contracts:
  global:
    always_keep: []           # regex — matching lines are never removed
    always_strip: []          # regex — matching lines are always removed

commands:                     # per-command overrides
  "git status":
    always_keep:
      - "^On branch"
    params:
      max_lines: 20
  "docker ps":
    always_strip:
      - "CREATED"
    params:
      max_rows: 10
```

### `engine` options

| Key | Default | Description |
| :--- | :--- | :--- |
| `show_metrics` | `false` | Print token savings to stderr after each compression |
| `min_lines_to_compress` | `15` | Outputs with fewer lines pass through uncompressed |
| `hot_cache_threshold` | `10` | Calls required before promoting a command to in-memory hot cache |
| `strip_ansi` | `true` | Strip ANSI escape codes before processing |
| `pass_through_on_error` | `false` | Return raw output when the classifier detects an error shape |
| `max_output_bytes` | `10485760` | Outputs larger than 10 MB pass through unchanged |
| `heartbeat_enabled` | `true` | Enable heartbeat messages during slow classification |
| `heartbeat_interval_seconds` | `5` | Seconds between heartbeat messages |
| `heartbeat_line_threshold` | `500` | Only enable heartbeat if buffering more than N lines |

### `commands` section

Each entry is keyed by command prefix (longest match wins):

| Key | Purpose |
| :--- | :--- |
| `always_keep` | Regex list — matching lines from the original are always included |
| `always_strip` | Regex list — matching lines are always removed |
| `params` | Strategy params — merged on top of seed/learned params (user wins) |

---

## Heartbeat

The heartbeat prevents AI agent timeouts during slow classification of unknown commands.

**When it activates:**
- An unknown command is being classified (not in hot/warm/seed cache)
- Buffering more than `heartbeat_line_threshold` lines
- At least `heartbeat_interval_seconds` have elapsed since the last message

**Example output (on stderr):**
```
[clipress: still running (elapsed 15s, 2300 lines buffered, shape pending)]
[clipress: still running (elapsed 20s, 3800 lines buffered, shape pending)]
```

**Common adjustments:**

```yaml
engine:
  heartbeat_enabled: false          # disable for tests
  heartbeat_interval_seconds: 10   # less frequent for verbose agents
  heartbeat_line_threshold: 100    # start heartbeat sooner
```

---

## Output Contracts

Contracts guarantee that specific lines always appear (or never appear) in compressed output, regardless of which strategy ran.

```yaml
contracts:
  global:
    always_keep:
      - "CRITICAL"        # regex — restored even if compressed away
    always_strip:
      - "^\\[debug\\]"    # regex — always removed

commands:
  "make build":
    always_keep:
      - "^Build succeeded"
      - "^Build failed"
```

**Application order** (applied after strategy compression):

1. `always_strip` — removes matching lines from the result
2. `always_keep` — appends matching lines from the original if not already present

Per-command contracts **add to** global contracts — they don't replace them.

---

## User Extensions (`.clipress/extensions/*.yaml`)

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

"my-long-build":
  streamable: true
  strategy: progress
  params:
    keep: "errors_and_final"
```

Rename a `.yaml` file to `.yaml.disabled` to exclude it without deleting it.

### Overriding built-in seeds

```yaml
# Override the built-in git log seed
"git log":
  strategy: list
  params:
    max_lines: 40
    head_lines: 30
    tail_lines: 10
```

Any key matching a built-in seed takes priority when `user_override: true` is set (automatic for extension files).

---

## Blocklist (`.clipress/.clipress-ignore`)

Commands whose output should never be compressed. One command prefix per line. Any command starting with a listed prefix is passed through unchanged.

```
# .clipress/.clipress-ignore

# Interactive tools — output should pass through raw
kubectl exec
psql
mysql

# Already-compact commands
echo
pwd
```

Lines starting with `#` are comments. Blank lines are ignored.

---

## Environment Variables

| Variable | Effect |
| :--- | :--- |
| `CLIPRESS_NO_COMPRESS=1` | Bypass all compression for the current session — all output passes through |
| `CLIPRESS_DEBUG=1` | Surface internal errors to stderr instead of silently falling back to raw output |

See [cli-reference.md](cli-reference.md) for all CLI commands and flags.
