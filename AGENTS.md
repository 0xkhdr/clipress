# clipress: Agent Intelligence Guide

`clipress` is a CLI output compressor designed specifically to keep AI agent context windows clean and focused. It intercepts raw command output and returns a semantically compressed version.

## 🛠 Core Components

| Component | Responsibility |
| :--- | :--- |
| **Engine** | Orchestrates the entire pipeline from input to output. |
| **Safety** | Prevents compression of secrets, binary data, or small outputs. |
| **Classifier** | Heuristically detects the "shape" of the output (list, diff, etc.). |
| **Learner** | Remembers successful strategies and tracks confidence for specific commands. |
| **Strategies** | Pluggable logic for compressing different output shapes. |
| **Registry** | Storehouse for "Seed" commands and learned patterns in `registry.json`. |

## 🔄 The Compression Pipeline

1. **Safety Gate**: Checks for secrets (`.env`, `id_rsa`, etc.), binary bytes, or if output is < 15 lines.
2. **Strategy Resolution**: 
   - **Hot Cache**: LRU cache for recently processed commands.
   - **Seed Registry**: Pre-defined rules for common tools (e.g., `ls`, `npm`).
   - **Workspace Registry**: Recalls learned patterns from previous executions.
   - **Classifier**: Fallback heuristic analysis of content.
3. **Compression**: Applies the selected **Shape Strategy**.
4. **Learning**: Updates confidence scores and token savings metrics.

## 📐 Shapes (Strategies)

| Shape | Use Case | Compression Logic |
| :--- | :--- | :--- |
| `list` | File listings, generic items | Keeps Head (20) & Tail (5), adds count of skipped items. |
| `diff` | Git/SVN diffs | Trims context lines and handles large hunks. |
| `test` | Unit test results | Prioritizes Failures and Summaries; hides passed tests. |
| `progress` | Downloaders, builds | Keeps the final state or the most recent error. |
| `table` | Columnar data | Keeps header and a representive sample of rows. |
| `keyvalue` | Configs, status | Preserves keys; truncates long values. |
| `error` | Stack traces | Preserves frames and error messages; trims middle frames. |
| `generic` | Unknown structure | Fallback; basic line-based truncation if too long. |

## 📜 Configuration & Rules

- **Workspace Config**: `.clipress/config.yaml` overrides defaults.
- **Contracts**:
    - `always_keep`: Regex list of patterns that MUST remain in output.
    - `always_strip`: Regex list of patterns that MUST be removed.
- **Ignore List**: `.clipress/.clipress-ignore` to skip `clipress` for specific commands.

## 🧠 Learning Loop

- **Confidence**: Starts at `0.50`. Increases on match (`+0.08`), decreases on mismatch (`-0.20`).
- **Hot Status**: At `0.85`, a command skips classification and uses the registry directly.
- **Locked**: At `0.95`, the strategy is considered stable and stops updating confidence.

## 💻 CLI Commands

| Command | Description |
| :--- | :--- |
| `clipress status` | Shows workspace status, config path, and learned stats. |
| `clipress init` | Initializes `.clipress/` in the current directory. |
| `clipress compress "<cmd>"` | Core command. Compresses `stdin` and writes to `stdout`. |
| `clipress learn show` | Displays the `registry.json` content. |
| `clipress learn reset` | Resets confidence for a specific command or all learned data. |
| `clipress validate` | Checks if `.clipress/config.yaml` is valid. |
| `clipress report` | Prints a summary of token savings. |
| `clipress error-passthrough on/off` | Toggles whether errors should skip compression. |

## 💡 Agent Tips

- **Force Raw**: If you need the full output, look for a `--no-compress` flag or similar (if implemented in the CLI) or check the command in `.clipress-ignore`.
- **Custom Rules**: You can suggest adding regex to `always_keep` in `.clipress/config.yaml` if `clipress` is stripping vital info.
- **Metrics**: `clipress` prints token savings to `stderr` if `engine.show_metrics` is true.
