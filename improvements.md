I've analyzed your improvements document alongside my earlier review. Below is a detailed, phased upgrade plan that an AI agent can execute step-by-step to evolve `clipress` into a streaming, non-blocking proxy with interactive support, while preserving its existing safety and learning strengths.

## Upgrade Plan: From Buffering to Streaming Proxy

### Phase 0 – Preparatory Refactoring (Prerequisites)

Before adding new features, we need to decouple the current pipeline to avoid breaking core functionality. This phase makes the codebase ready for streaming.

**Task 0.1 – Dependency Injection in Engine**

- Current `Engine.compress()` instantiates `Config`, `Safety`, `Learner`, etc. directly.
- Refactor to accept these as constructor parameters or method arguments. This allows unit-testing individual components and inserting stream-aware versions later.
- *Implementation hint*: Introduce a `PipelineContext` dataclass carrying config, safety, learner, cache, registry, and a new `StreamMode` enum (`BUFFER_FULL`, `KNOWN_STREAM`, `UNKNOWN_WITH_HEARTBEAT`).

**Task 0.2 – Strategy Protocol Upgrades**

- Define a `StreamStrategy` protocol (or abstract base class) that strategies can optionally implement:
  - `def process_line(self, line: str) -> Optional[str]:` — returns the line to yield, or `None` if swallowed.
  - `def finalize(self) -> list[str]:` — returns any trailing output (like a summary).
- Refactor existing strategies (e.g., `ProgressStrategy`, `ListStrategy`) to implement this if they can operate per-line. If not, keep them as full-buffer-only and mark them as `streamable=False`.

**Task 0.3 – Extract Output Writer Abstraction**

- Currently, `compress()` returns a single string. For streaming, the engine must write to a live `stdout` / `stderr` handler.
- Create a `Writer` class that wraps `sys.stdout.write`, `sys.stderr.write`, and can be replaced by a test buffer. This will be injected into the engine.

**Task 0.4 – Thread‑Safety Audit & Fix**

- As noted in my earlier analysis, concurrent calls can corrupt the learner registry. Use a lightweight SQLite database with WAL mode instead of JSON files. This can be done early to prevent file‑locking issues when multiple `clipress` processes run simultaneously.
- *Implementation*: Replace `WorkspaceLearner` file I/O with `sqlite3` using a temporary table or a persistent database; use `PRAGMA journal_mode=WAL` for concurrent reads/writes.

### Phase 1 – Rolling Window Compression (Memory Safety)

This is the simplest streaming‑friendly change and can be implemented without altering the external interface.

**Task 1.1 – Replace List with Deque in Generic Fallback**

- Locate the code path where `head_lines` and `tail_lines` are buffered before applying truncation (likely inside a `_apply_generic_truncation` method).
- Instead of appending to a list for the entire output, use:
  ```python
  head = []
  tail = deque(maxlen=tail_lines)
  for line in input_stream:
      if len(head) < head_lines:
          head.append(line)
      else:
          tail.append(line)
  # final output = head + list(tail)
  ```
- Ensure that `always_strip` contracts are applied inline (strip ANSI before appending to head/tail) to honour safety checks without buffering full output.

**Task 1.2 – Integrate with Classifier**

- After the stream ends, the deque contains only the head + tail. Pass this combined list to the Classifier to choose the final strategy.
- If the chosen strategy is `generic`, the result is already the deque contents. For other strategies, the full output may be needed; but in those cases, the command would typically be in the seed registry and thus handled by streaming (Phase 2), so this is safe.

**Task 1.3 – Add Tests**

- Simulate a 10 GB pseudo‑command (via a generator) and verify memory stays flat (below a small threshold like 10 MB).
- Test that `always_strip` patterns are removed before the line enters the deque.

### Phase 2 – Predict & Stream Pipeline (Fast‑Path for Known Commands)

Once memory is capped, we enable real‑time streaming for commands whose output shape is already known.

**Task 2.1 – Mark Streamable Strategies**

- Extend the seed registry and learner records with a `streamable` boolean.
- For common commands (e.g., `docker build`, `npm install`, `cargo build`), set `streamable=True` and associate them with a stateful `ProgressStrategy` that yields lines incrementally.

**Task 2.2 – Implement Streaming Engine Branch**

- Modify the engine's resolution flow:
  1. Look up command in hot cache / seed registry.
  2. If `streamable==True`:
     - Instantiate the strategy as a stateful iterator (e.g., `ProgressStrategy(mode='stream')`).
     - Stream STDIN line by line, calling `strategy.process_line(line)`. Write non‑`None` results immediately to `stdout`.
     - On EOF, call `strategy.finalize()` and write any remaining output.
  3. If `streamable==False` or unknown, fall back to the buffered path (now using deque with heartbeats, Phase 3).

**Task 2.3 – Stateful Strategy Examples**

- `ProgressStrategy(stream)`:
  - Maintain a buffer for the current line; if it matches a progress regex (e.g., `\d+%`, `ETA`), swallow it and update an internal counter.
  - Every 10 seconds or on completion, emit a summary `[clipress: progress X%]` if suppressed.
- `ListStrategy(stream)`:
  - Count lines; after the output ends, emit only a `head_lines` and `tail_lines` snippet, but that requires the full output. For streaming, we can emit lines as they come but detect when the total exceeds a threshold and then switch to a “summary mode”—this needs careful design.
  - A simpler approach: for list‑like commands, we can still buffer tail with a deque, but we’ll yield head lines immediately and keep the rest in a rolling buffer. That’s a hybrid, but it still streams the head.

**Task 2.4 – Update Hot Cache & Workspace Learner**

- When a command succeeds via the non‑streaming path, the learner may now record that the strategy *could* be streamable if it matches a pattern. Add a background task (or post‑execution analysis) that, after full buffering, checks whether the output could have been handled line‑by‑line and updates the `streamable` flag in the workspace DB.

### Phase 3 – Heartbeat Chunking (Prevent AI Agent Timeouts)

Now that unbuffered commands are handled, long‑running unknown commands must still buffer, but we need to inform the agent they haven't hung.

**Task 3.1 – Threaded Buffer Monitor**

- While buffering into the deque (unknown path), spawn a light daemon thread that wakes every 5 seconds (or after 500 lines, whichever comes first).
- On each wake, write a status line to `stderr` (or a special `stdout` channel marked with a non‑interfering prefix):
  ```
  [clipress: still running (elapsed 15s, 2300 lines buffered, shape pending)]
  ```
- Ensure this thread is joined at buffer end, so no heartbeats leak after the command finishes.

**Task 3.2 – Configurable Heartbeat Settings**

- Add config keys: `heartbeat_interval_seconds` (default 5), `heartbeat_line_threshold` (500), `heartbeat_to_stderr` (true). Allow users to disable heartbeats entirely.

**Task 3.3 – Restore Original STDOUT/STDERR After Compression**

- When the buffer completes and final output is ready, the heartbeat messages must not corrupt the final compressed output. If heartbeats go to `stderr`, they are naturally separate. If they go to `stdout` with a prefix, the final output must strip that prefix. I strongly recommend using `stderr` to avoid parsing complexity.

### Phase 4 – PTY Wrapping & Interactive Escape Hatch

This is the largest change, as it introduces a new command `clipress run` that replaces shell piping. It must be opt‑in to maintain backward compatibility.

**Task 4.1 – Implement `clipress run <command>` Subcommand**

- Add a new entrypoint `run` that uses Python's `pty` module (or `pexpect` if more complex interaction is needed) to spawn the command inside a pseudo‑terminal.
- The subprocess should still be wrapped by the engine, but now the engine reads from the PTY master file descriptor, not from `stdin`.

**Task 4.2 – Stall Detection Logic**

- Use `select.select` with a timeout on the PTY master fd.
- Whenever no data is received for a configurable period (e.g., 2 seconds), and the child process is still alive, assume an interactive prompt.
- **Escape hatch**:
  1. Flush any remaining buffered output to `stdout`.
  2. Detach the engine’s compression pipeline and switch to raw passthrough mode, forwarding `stdin` from the parent directly to the PTY slave, and the child's output directly to parent's `stdout`.
  3. The agent can now interact naturally with the prompt.

**Task 4.3 – Non‑Interactive Fallback for PTY**

- For known commands that are *not* interactive, `clipress run` should behave exactly like the streaming pipeline (Phase 2) but using the PTY for input/output. This ensures consistent behaviour between `cmd | clipress` and `clipress run`.

**Task 4.4 – Exit Code Propagation**

- When the child process ends, the `run` command must return the same exit code as the original command, so the AI agent can correctly detect failures.

### Phase 5 – Integration & Safety Verification

All new features must not break existing safety guarantees.

**Task 5.1 – Safety Checks During Streaming**

- For the streaming path, run each line through the safety checker before emitting it. If a sensitive pattern is detected, either strip the line or abort streaming and fall back to the safe buffered path (which might redact the whole output). This maintains the “never leak sensitive info” promise.

**Task 5.2 – Regression Test Suite**

- Create automated tests that simulate AI agent usage:
  - Run `clipress run` with interactive prompts; verify that after the prompt, raw I/O works.
  - Run a long‑running task (e.g., `sleep 10 && echo done`) with streaming disabled and check that heartbeats appear in `stderr`.
  - Verify that the rolling window never consumes more than a fixed memory budget.
  - Test concurrent execution of multiple `clipress run` processes with the SQLite‑backed workspace learner.

**Task 5.3 – Documentation & Migration Guide**

- Update README to explain the new `run` subcommand, heartbeat configurations, and the difference between piped and PTY execution.
- Provide a migration path for agents that currently pipe into `clipress compress`: they can continue doing so, but for interactive commands they should switch to `clipress run`.

## Summary of Implementation Order

| Phase | Milestone | Dependencies |
|-------|-----------|--------------|
| 0     | Refactoring (DI, protocols, SQLite) | None |
| 1     | Rolling window (deque) & memory safety | Phase 0 |
| 2     | Stream fast‑path for known commands | Phase 1 |
| 3     | Heartbeat emission | Phase 1 (buffered path) |
| 4     | PTY wrapper & interactive escape | Phase 0,1,3 |
| 5     | Safety integration & testing | All phases |

Each phase can be implemented, tested, and merged independently, gradually delivering value without destabilizing the production tool.

