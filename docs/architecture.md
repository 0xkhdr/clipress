# Architecture

## Project Structure

```
clipress/
├── clipress/
│   ├── engine.py               # main pipeline orchestrator (+ _Heartbeat, CLIPRESS_DIAGNOSTIC)
│   ├── classifier.py           # single-pass heuristic shape detection
│   ├── learner.py              # SQLite-backed registry & confidence tracking
│   ├── config.py               # config loading, validation, extension YAML validation
│   ├── safety.py               # 27 built-in security patterns, binary detection gates
│   ├── metrics.py              # token counting & reporting
│   ├── ansi.py                 # ANSI escape code stripping
│   ├── archive.py              # SQLite-backed history store for `clipress restore`
│   ├── cli.py                  # Click CLI entry point
│   ├── py.typed                # PEP 561 typed package marker
│   ├── hooks/
│   │   └── post_tool_use.py    # Claude Code PostToolUse / Gemini CLI AfterTool handler
│   ├── strategies/
│   │   ├── base.py
│   │   ├── generic_strategy.py   # rolling-window deque
│   │   ├── list_strategy.py
│   │   ├── progress_strategy.py
│   │   ├── test_strategy.py
│   │   ├── diff_strategy.py
│   │   ├── table_strategy.py
│   │   ├── keyvalue_strategy.py
│   │   └── error_strategy.py
│   ├── registry/
│   │   └── seeds.json          # built-in command seeds (with streamable flag)
│   └── defaults/
│       └── config.yaml         # built-in default configuration
└── tests/
    ├── conftest.py
    ├── fixtures/
    ├── hooks/
    ├── strategies/
    ├── test_classifier.py
    ├── test_cli.py
    ├── test_config.py
    ├── test_engine.py
    ├── test_integration.py
    ├── test_learner.py
    ├── test_metrics.py
    └── test_safety.py
```

---

## Key Interactions

```
cli.py (compress_cmd / run_cmd)
  └─ engine.compress()
       ├─ safety.should_skip()
       ├─ config.get_config()
       ├─ config.build_seed_registry()
       ├─ learner.Learner.lookup()         ← SQLite read
       ├─ classifier.detect()             ← with _Heartbeat on unknown commands
       ├─ strategies.STRATEGIES[shape].compress()   ← rolling-window deque
       └─ learner.Learner.record()        ← SQLite write (WAL, mutex-protected)
```

The engine is the only orchestrator. Each component has a single responsibility and no cross-dependencies except through the engine.

---

## Design Decisions

### Pipe mode vs PTY mode

**Pipe mode** (`cmd | clipress compress "cmd"`) buffers all output before compressing. The agent sees the compressed result only after the command exits. Use this for short-lived commands.

**PTY mode** (`clipress run <cmd>`) reads output in chunks as it arrives. Stall detection triggers passthrough when the process stops emitting for `--stall-timeout` seconds. Use this for long-running or potentially interactive commands.

### Memory safety

The `generic` strategy uses `collections.deque` with bounded `maxlen=tail_lines`. Memory usage is capped to `head_lines + tail_lines` lines regardless of output size. No single command can exhaust agent memory.

### Thread safety

- **In-memory hot cache** — protected by `threading.Lock`
- **SQLite learner** — WAL mode allows multiple concurrent readers and one writer without locking corruption
- Multiple simultaneous clipress processes (parallel bash calls from an agent) are safe

### Async writes

`Learner._async_save` does not spawn a thread per `record()` call. A single daemon writer coalesces bursts of writes into one save, reducing disk I/O.

### Config caching

`config.get_config()` caches the parsed config per workspace path. The cache is cleared when `clipress error-passthrough` writes a new value, ensuring changes are applied immediately.

---

## Limitations

### Cursor / Copilot (integrated terminal)

Coverage is partial. Only direct bash commands run in the terminal are intercepted. Internal file APIs and extension-level executions are not.

### Windows

`clipress run` (PTY mode) requires `pty`, `termios`, and `tty` — Unix-only modules. On Windows, use pipe mode:

```bash
some_command | clipress compress "some_command"
```

### Large outputs

Outputs larger than `max_output_bytes` (default 10 MB) pass through unchanged with a warning to stderr. Adjust the threshold in `config.yaml` if needed.

### Classification accuracy

The classifier is heuristic — it scores outputs against shape signatures and picks the highest scorer. For unusual output formats, it falls back to `generic` truncation. The learning system improves accuracy over repeated calls to the same command.

### Streaming

Real-time line filtering is only available in PTY mode (`clipress run`). Pipe mode always buffers the full output before compressing.
