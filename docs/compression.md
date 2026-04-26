# Compression

## The Pipeline

Every call to `clipress compress "<cmd>"` or `clipress run <cmd>` runs through this pipeline:

```
stdin / PTY
  │
  ├─ [SIZE GUARD]         output > max_output_bytes (10 MB)? → pass through
  ├─ [ANSI STRIP]         remove escape codes (when strip_ansi=true)
  ├─ [SAFETY GATE]        blocklist / security patterns / binary / too short / error? → pass through
  │
  ├─ [STRATEGY RESOLUTION]  (checked in priority order)
  │     1. Hot cache         — in-memory LRU for proven commands (≥10 calls, confidence ≥0.85)
  │     2. Seed registry     — built-in rules for common commands (git, docker, pytest, …)
  │     3. Workspace learner — previously learned patterns stored in registry.db (SQLite+WAL)
  │     4. Classifier        — heuristic shape detection as fallback
  │
  ├─ [COMPRESS]           run the matched strategy
  ├─ [CONTRACTS]          apply always_keep / always_strip rules
  ├─ [REGRESSION GUARD]   compressed > original (bytes or tokens)? → return original
  ├─ [METRICS]            count tokens saved, log to stderr if show_metrics=true
  └─ [LEARN]              update registry.db with outcome
  │
stdout (compressed output)
```

### Worked example: `git log | clipress compress "git log"`

1. **Size guard** — 100-line log ~2 KB, well under 10 MB
2. **ANSI strip** — no codes present, skip
3. **Safety gate** — not blocked, not binary, 100 lines > 15 minimum
4. **Strategy resolution** — seed registry has `"git log" → { strategy: "list", params: { max_lines: 20 } }`
5. **Compress** — `ListStrategy` keeps head (20) + tail (5), inserts `... [75 more items]`
6. **Contracts** — no per-command rules, no change
7. **Regression guard** — 30 lines vs. 100 lines, pass
8. **Metrics** — ~1950 tokens saved (75% reduction), printed to stderr if enabled
9. **Learn** — registry entry updated: `{ strategy: "list", calls: 1, confidence: 0.50 }`

---

## Shape Detection

The classifier scores each output against all shapes and picks the highest scorer. A shape must score ≥ 0.5 to win; otherwise the output is treated as `generic`.

| Shape | Key signals |
| :--- | :--- |
| `list` | High line count, similar line lengths, few colons, no diff markers |
| `progress` | Percentage/fraction patterns, words like *downloading*, *fetching*, *step* |
| `test` | PASSED/FAILED/ERROR keywords, test names, summary lines (`====`) |
| `diff` | `+`/`-` prefix lines, `@@` hunks, `---`/`+++` headers |
| `table` | Separator line, consistent column count, uppercase header |
| `keyvalue` | >60% of lines match `key: value` or `key=value` |
| `error` | `Traceback`, `Exception`, `File "..."` frames, indented code snippets |
| `generic` | Fallback — bounded rolling-window truncation |

---

## Strategies

### `generic` — Fallback truncation

Uses a memory-bounded rolling-window (deque) that caps RAM usage to `head_lines + tail_lines` entries regardless of total output size.

- Deduplicates ≥3 consecutive identical lines → `[repeated Nx]`
- Keeps head + tail if output exceeds `max_lines`
- `always_strip` patterns applied inline during the pass (before lines enter the window)

| Param | Default |
| :--- | :--- |
| `max_lines` | 50 |
| `head_lines` | 20 |
| `tail_lines` | 10 |
| `dedup_min_repeats` | 3 |

### `list` — File listings, grep results

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

### `progress` — Build logs, downloads, installs

- Strips percentage-only lines and ETA/speed lines
- Always keeps errors and the final line

| Param | Default |
| :--- | :--- |
| `keep` | `"final_line"` (`"errors_and_final"` also available) |
| `strip_percentage` | `true` |

### `test` — Unit test results (pytest, jest, cargo test)

- Extracts failures + up to `max_traceback_lines` of traceback per failure
- Always includes summary lines (last ~5 lines matching the summary pattern)

| Param | Default |
| :--- | :--- |
| `keep` | `"failed_only"` (`"all"` or `"errors_and_final"` also available) |
| `max_traceback_lines` | 8 |

### `diff` — Git diff, patch files

- Keeps `+++`/`---` headers, `@@` hunks, changed lines with surrounding context
- Falls back to per-file summary if output exceeds `max_lines`

| Param | Default |
| :--- | :--- |
| `max_lines` | 80 |
| `context_lines` | 2 |

### `table` — `docker ps`, `kubectl get`, columnar output

- Preserves header and separator row
- Truncates rows and cell content

| Param | Default |
| :--- | :--- |
| `max_rows` | 20 |
| `max_columns` | 5 |
| `max_cell_length` | 40 |

### `keyvalue` — Config dumps, `systemctl status`, `docker inspect`

- Strips keys matching `always_strip_keys` regex list
- Truncates to `max_lines` keeping non-timestamp pairs first

| Param | Default |
| :--- | :--- |
| `max_lines` | 20 |
| `always_strip_keys` | `[]` |

### `error` — Stack traces, exceptions

- Keeps Traceback/Exception header + up to `max_traceback_lines` frames
- Strips stdlib/venv frames (site-packages, .pyenv, .venv, frozen, conda, …)

| Param | Default |
| :--- | :--- |
| `max_traceback_lines` | 10 |
| `strip_stdlib_frames` | `true` |

---

## Built-In Seed Commands

These commands are recognized out of the box with no configuration. Commands marked **Streaming** use real-time line filtering in `clipress run`.

| Command | Strategy | Streaming |
| :--- | :--- | :---: |
| `git status` | keyvalue | — |
| `git diff` | diff | — |
| `git log` | list | — |
| `git push` | progress | — |
| `git pull` | progress | — |
| `git stash` | list | — |
| `docker ps` | table | — |
| `docker build` | progress | ✓ |
| `docker logs` | list | — |
| `docker images` | table | — |
| `pytest` | test | — |
| `jest` | test | — |
| `cargo test` | test | — |
| `npm install` | progress | ✓ |
| `pip install` | progress | ✓ |
| `cargo build` | progress | ✓ |
| `npm run build` | progress | ✓ |
| `ls` | list | — |
| `find` | list (grouped) | — |
| `cat` | list | — |

Override any seed by adding an entry with the same key to `.clipress/extensions/*.yaml`. See [configuration.md](configuration.md) for the format.

---

## Streaming Mode

Commands marked with ✓ in the seed table support **real-time line filtering** when run with `clipress run` (PTY mode only).

| Mode | Behavior |
| :--- | :--- |
| **Buffered** | All output collected, then compressed at exit |
| **Streaming** | Lines filtered in real time as they arrive |

**Real-time filtering behavior:**
- Progress lines (%, ETA, speed) → dropped immediately
- Errors and warnings → emitted immediately
- Final summary → always included

```bash
# Buffered (pipe mode) — waits for build to complete, then compresses
docker build -t app . | clipress compress "docker build"

# Streaming (PTY mode) — filters live as output arrives
clipress run docker build -t app .
```

To mark a custom command as streamable:

```yaml
# .clipress/extensions/custom.yaml
"my-long-build":
  streamable: true
  strategy: progress
  params:
    keep: "errors_and_final"
```

---

## Regression Guard

If the compressed output is **larger than the original** (by byte count or token count), clipress silently returns the original:

```python
if len(compressed) > len(original):
    return original
```

This guarantees compression is always net-negative. No configuration needed.

---

## Practical Examples

### Git log

```bash
git log --oneline -100 | clipress compress "git log"
```

Input: 100 lines, ~2 KB → Output: 25 lines, ~500 B (**75% reduction**)

### Docker build with streaming

```bash
clipress run docker build -t myapp .
# Progress lines dropped in real time
# Errors emitted immediately
# Final layer summary always shown
```

Input: 500 lines, ~40 KB → Output: 75 lines, ~6 KB (**85% reduction**)

### Pytest failures

```bash
pytest tests/ -v 2>&1 | clipress compress "pytest"
```

Input: 1000 lines (50 passing, 3 failing) → Output: ~50 lines (failures + tracebacks + summary) (**95% reduction**)
