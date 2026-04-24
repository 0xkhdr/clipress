# clipress: Universal CLI Output Compressor for AI Agents

`clipress` is a Python-based CLI proxy designed to intercept and compress bash command outputs before they reach an AI agent's context window. It solves the "context overflow" problem by returning only the semantically meaningful portion of the output.

## Architecture

The project follows a layered architecture designed for speed, adaptivity, and safety.

### Core Components

- **CLI (`clipress.cli`)**: The entry point for manual interaction and the `compress` command.
- **Engine (`clipress.engine`)**: Orchestrates the compression pipeline.
- **Classifier (`clipress.classifier`)**: Heuristically determines the "shape" of the output (e.g., table, list, diff).
- **Learner (`clipress.learner`)**: An adaptive system that remembers successful compression strategies for specific commands in a workspace-local `registry.json`.
- **Strategies (`clipress.strategies`)**: Pluggable modules that implement specific compression logic for different output shapes.
- **Safety (`clipress.safety`)**: Protects against compressing sensitive information (secrets) and handles edge cases (binary data, minimal output).
- **Config (`clipress.config`)**: Manages default settings, workspace-specific overrides (`.compressor/config.yaml`), and command seeds.

### Data Flow

1. **Input**: A command string and its raw output are piped to `clipress compress`.
2. **Pre-processing**: ANSI escape codes are stripped (optional).
3. **Safety Gate**: Checks if the output contains secrets, is binary, or is too short to compress.
4. **Strategy Resolution**:
   - **Hot Cache**: Check if the command was recently processed in-memory.
   - **Seed Registry**: Check for pre-defined rules in `seeds.json` or workspace extensions.
   - **Workspace Registry**: Check `registry.json` for learned patterns.
   - **Classifier**: If no registry match, analyze the output content to detect its shape.
5. **Compression**: Apply the selected strategy (e.g., `ListStrategy`, `DiffStrategy`) using strategy-specific parameters and global/command-level contracts.
6. **Learning**: Record the result, update confidence scores in the registry, and track token savings.
7. **Output**: Return the compressed string.

---

## Core Concepts

### Shapes (Strategies)

A "Shape" is a classification of the output structure. `clipress` supports:
- **`list`**: Long lists of files or items. Keeps head and tail.
- **`progress`**: Progress bars or fetch logs. Keeps the final state or errors.
- **`test`**: Test runner outputs. Keeps failed tests and summaries.
- **`diff`**: Code diffs. Trims context lines and large hunks.
- **`table`**: Tabular data. Keeps headers and a sample of rows.
- **`keyvalue`**: Config or status blocks. Preserves keys while trimming long values.
- **`error`**: Stack traces and exception logs. Preserves frames and messages.
- **`generic`**: Fallback for unknown structures.

### Confidence & The Learning Loop

The `Learner` maintains a confidence score for each command's strategy:
- **Initial Confidence**: 0.50.
- **Reinforcement**: Each time the classifier confirms the strategy, confidence increases (+0.08).
- **Correction**: If the classifier detects a different shape, confidence drops (-0.20).
- **Hot Threshold**: At 0.85, the command is considered "hot" and uses the strategy directly from the registry, skipping classification for speed.

### Contracts

Contracts allow users to define strict rules for what must stay or go:
- **`always_keep`**: Regex patterns that, if matched in the original output, must be present in the compressed output.
- **`always_strip`**: Regex patterns to remove from the final output regardless of the strategy used.

---

## Use Cases

1. **Preventing Context Bloat**: Prevents `npm install` or `find /` from filling up the AI's 128k/200k context window.
2. **Focusing AI Attention**: By stripping redundant lines, the agent can focus on errors or the specific files it was looking for.
3. **Lowering Latency/Cost**: Fewer tokens sent to the LLM mean faster response times and lower API costs.
4. **Standardizing Output**: Provides a consistent experience across different shells and tools.

---

## Default Workflow (Processing a Command)

When a command like `ls -R` is executed through `clipress`:

1. `clipress` receives `ls -R` and the 500-line output.
2. **Safety** confirms it's not a secret and has > 15 lines.
3. **Registry** finds `ls` is a "seed" command with `ListStrategy`.
4. **ListStrategy** sees 500 lines, keeps the first 20 and last 5, adding `... [475 more items]`.
5. **Metrics** calculates that 90% of tokens were saved.
6. **Learner** updates `registry.json` with the stats.
7. The AI agent receives the 26-line summary instead of the full 500 lines.

---

## Rules & Configuration

### Configuration Hierarchy

1. **Defaults**: Hardcoded in `clipress/defaults/config.yaml`.
2. **Workspace Config**: `.compressor/config.yaml` in the current project root.
3. **Extensions**: `.compressor/extensions/*.yaml` for sharing command-specific rules across teams.

### Security Rules

`clipress` has a built-in blocklist of patterns (`.env`, `id_rsa`, `AWS_SECRET`, etc.). If a command output matches these, **compression is skipped entirely**, and the raw output is passed through to avoid accidental truncation of critical security information or leaking "summarized" secrets.

### Workspace Blocklist

Users can create `.compressor/.compressor-ignore` to list commands that `clipress` should never touch.

---

## Integration

### Shell Integration

By setting `CLIPRESS_AGENT_MODE=true` and sourcing the shell hook, `clipress` can transparently wrap bash executions.

### Claude Code Integration

A dedicated `post_tool_use.py` hook is provided for [Claude Code](https://github.com/anthropics/claude-code), allowing it to process tool results via the `Bash` tool automatically.

---

## Project Structure

```text
clipress/
├── clipress/
│   ├── classifier.py     # Heuristic shape detection
│   ├── engine.py         # Main pipeline logic
│   ├── learner.py        # Persistence & confidence tracking
│   ├── safety.py         # Secret detection & skip logic
│   ├── strategies/       # Compression implementations
│   ├── registry/         # Default command seeds
│   └── hooks/            # Agent-specific integrations
├── tests/                # Comprehensive test suite
└── pyproject.toml        # Dependencies (click, ruamel.yaml, rich)
```
