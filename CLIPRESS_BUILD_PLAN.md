# CLIPRESS — Universal CLI Output Compressor for AI Agents
## Comprehensive Build Plan v1.0
### Authored for AI Agent Execution

---

> **Purpose of this document**: This is a complete, self-contained instruction set for an AI agent to build the `clipress` package from scratch. Every section is a directive. Follow the order strictly. Do not skip sections. Do not improvise architecture decisions not covered here.

---

## TABLE OF CONTENTS

1. Package Identity & Philosophy
2. Security Rules (Read Before Writing Any Code)
3. Architecture Overview
4. Folder & File Structure
5. Component Specifications
6. Integration Layer
7. Testing Requirements
8. Performance Requirements
9. Distribution & Installation
10. Agent Build Instructions (Step-by-Step)
11. Codebase Practices & Anti-Patterns
12. Definition of Done

---

## 1. PACKAGE IDENTITY & PHILOSOPHY

### Name
```
clipress
```

### Tagline
```
Universal CLI output compressor for AI agents.
Ships lean. Gets smarter with every call.
```

### Core Philosophy — Four Laws
Every decision in this codebase must satisfy all four laws:

```
Law 1 — MINIMAL CORE
  The package ships with the minimum possible code.
  No handler per command. No bloated registry.
  Seeds + strategies + classifier = the entire engine.
  Intelligence lives in the workspace, not the package.

Law 2 — ADAPTIVE
  Every command call teaches the tool.
  Built-in seeds are the starting point, not the ceiling.
  Confidence grows with usage.
  Hot path promoted from warm path automatically.

Law 3 — CONSISTENT
  Output contracts define what the user always sees.
  Strategies may vary. Contracts never change without user action.
  The agent must always get predictable, trustworthy output.

Law 4 — EXTENDIBLE
  Users shape compression through YAML only.
  No code required to add a custom command.
  No code required to override a strategy.
  The tool must never force a workflow on the user.
```

### What the Tool Is
```
A Python-based CLI proxy that intercepts bash command output
before it reaches an AI agent's context window, compresses it
using a hybrid classifier + registry system, and returns only
the semantically meaningful portion of the output.
```

### What the Tool Is NOT
```
- Not a command blocker
- Not a security scanner (it avoids secrets, it does not audit them)
- Not a per-command handler library (RTK pattern is rejected)
- Not an AI model (no LLM calls inside the compressor)
- Not a logging tool (metrics are opt-in, never sent externally)
```

---

## 2. SECURITY RULES
### ⚠️ Read every rule before writing any code. These are non-negotiable.

### Rule S-1 — Never Log Secrets
```
The compressor MUST detect and skip commands whose output
contains sensitive patterns. It must NEVER:
  - Write secret values to disk
  - Print secret values to stdout
  - Pass secret values through the compression pipeline
  - Include secret values in metrics output

If a security-sensitive command is detected, the raw output
is passed through UNTOUCHED and a warning is emitted to stderr
(not stdout) so the agent never sees the warning as content.
```

### Rule S-2 — No External Network Calls
```
The package MUST NEVER make any network call of any kind.
No telemetry. No update checks. No analytics. No pinging home.
The tool is entirely offline. Any network call is a critical bug.
```

### Rule S-3 — No Code Execution of User Input
```
The compressor reads command strings and output strings.
It MUST NEVER eval(), exec(), or subprocess() any part of
the command string or output string.
Input is text only. It is never executed.
```

### Rule S-4 — Workspace File Permissions
```
All files written to .compressor/ must be created with
mode 0600 (owner read/write only).
The .compressor/ directory must be created with mode 0700.
Never create world-readable files containing session data.
```

### Rule S-5 — Path Traversal Prevention
```
Any file path derived from command output or config values
must be sanitized before use. Never use raw user-provided
paths in os.path operations without validation.
Use pathlib.Path and resolve() then check the resolved path
stays within the expected directory.
```

### Rule S-6 — YAML Safety
```
Always use yaml.safe_load() — never yaml.load().
yaml.load() with arbitrary input is a code execution vector.
This rule has no exceptions.
```

### Rule S-7 — No Sensitive Data in learned.json
```
The learner records command names and output shapes.
It MUST NEVER record:
  - The actual output content
  - File paths from the output
  - Any values from the output
Only metadata: shape, token counts, timestamps, confidence.
```

---

## 3. ARCHITECTURE OVERVIEW

### The Three-Layer Hybrid Engine

```
INCOMING: command string + raw output string
              │
              ▼
┌─────────────────────────────────────────────┐
│  GATE: Safety Checker                       │
│                                             │
│  Checks:                                    │
│  1. Is command in blocklist?                │
│  2. Does output contain security patterns?  │
│  3. Is output binary?                       │
│  4. Is output already minimal (<15 lines)?  │
│                                             │
│  FAIL → pass through raw, emit stderr warn  │
│  PASS → continue to Layer 0                 │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  LAYER 0a: Built-in Seed Registry           │
│                                             │
│  Thin metadata entries for ~20 commands.    │
│  Maps command → strategy hint + params.     │
│  Not handlers. Just routing tags.           │
│                                             │
│  HIT  → skip to Layer 2 with hint          │
│  MISS → continue to Layer 0b               │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  LAYER 0b: Learned Workspace Registry       │
│                                             │
│  Commands seen before in this workspace.    │
│  Confidence-gated: only trusted if ≥0.85.  │
│  Loaded from .compressor/registry.json.     │
│                                             │
│  HIT + confident → skip to Layer 2         │
│  MISS or low conf → continue to Layer 1    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  LAYER 1: Shape Classifier                  │
│                                             │
│  Analyzes raw output structure.             │
│  Detects one of 7 output shapes.            │
│  Works on ANY command, known or unknown.    │
│  Returns shape name + confidence score.     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  LAYER 2: Strategy Engine                   │
│                                             │
│  Applies compression strategy.              │
│  Enforces user output contracts.            │
│  Respects always_keep / always_strip rules. │
│  Returns compressed string.                 │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  POST: Learner + Metrics                    │
│                                             │
│  Records observation to registry.json.      │
│  Updates confidence score.                  │
│  Promotes to hot cache if threshold met.    │
│  Logs token delta if metrics enabled.       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
OUTGOING: compressed output string
```

### Hot / Warm / Cold Path

```
COLD  — first time seeing command
        classifier runs, records to registry
        slowest path, still <200ms total

WARM  — command seen before, confidence building
        registry lookup (file read), strategy applied
        faster path, ~50ms total

HOT   — command seen 10+ times, confidence ≥0.85
        in-memory dict lookup, no file I/O
        fastest path, <5ms total
```

---

## 4. FOLDER & FILE STRUCTURE

```
clipress/                          ← package root
│
├── pyproject.toml                 ← package metadata, deps, build
├── README.md                      ← user-facing documentation
├── LICENSE                        ← MIT license
├── CHANGELOG.md                   ← version history
├── install.sh                     ← one-command installer
│
├── clipress/                      ← importable package
│   ├── __init__.py                ← version, public API
│   ├── engine.py                  ← main orchestrator
│   ├── safety.py                  ← security gate (runs first)
│   ├── classifier.py              ← shape detection
│   ├── learner.py                 ← adaptive registry manager
│   ├── config.py                  ← config loader + deep merge
│   ├── metrics.py                 ← token counting + reporting
│   ├── cli.py                     ← click CLI for user commands
│   │
│   ├── registry/
│   │   ├── __init__.py
│   │   └── seeds.json             ← built-in seed entries (~20)
│   │
│   ├── strategies/
│   │   ├── __init__.py            ← strategy registry dict
│   │   ├── base.py                ← BaseStrategy abstract class
│   │   ├── list_strategy.py       ← long list compression
│   │   ├── progress_strategy.py   ← progress/noise stripping
│   │   ├── test_strategy.py       ← test runner output
│   │   ├── diff_strategy.py       ← patch/diff compression
│   │   ├── table_strategy.py      ← tabular output
│   │   ├── keyvalue_strategy.py   ← key:value block output
│   │   ├── error_strategy.py      ← error + stack trace
│   │   └── generic_strategy.py    ← universal fallback
│   │
│   ├── hooks/
│   │   ├── post_tool_use.py       ← Claude Code PostToolUse hook
│   │   ├── pre_tool_use.py        ← Claude Code PreToolUse hook
│   │   └── shell_hook.sh          ← bash/zsh shell wrapper
│   │
│   └── defaults/
│       └── config.yaml            ← default contracts (ships with pkg)
│
└── tests/
    ├── conftest.py                ← shared fixtures
    ├── test_safety.py
    ├── test_classifier.py
    ├── test_learner.py
    ├── test_engine.py
    ├── test_config.py
    ├── test_metrics.py
    ├── strategies/
    │   ├── test_list.py
    │   ├── test_progress.py
    │   ├── test_test.py
    │   ├── test_diff.py
    │   ├── test_table.py
    │   ├── test_keyvalue.py
    │   ├── test_error.py
    │   └── test_generic.py
    └── fixtures/
        ├── git_status.txt
        ├── git_diff.txt
        ├── git_log.txt
        ├── docker_ps.txt
        ├── docker_build.txt
        ├── pytest_output.txt
        ├── npm_install.txt
        ├── pip_install.txt
        └── binary_output.bin
```

### Workspace Structure (User's Project — Not Shipped)
```
user-project/
└── .compressor/
    ├── registry.json              ← learned commands (auto-managed)
    ├── config.yaml                ← user overrides (optional)
    ├── extensions/                ← user-defined command configs
    │   └── myapp.yaml
    └── .compressor-ignore         ← user blocklist
```

---

## 5. COMPONENT SPECIFICATIONS

### 5.1 — engine.py

**Purpose**: Orchestrates all layers. Single entry point for all compression.

**Public Interface**:
```python
def compress(command: str, output: str, workspace: str) -> str:
    """
    Main compression entry point.
    
    Args:
        command:   The full command string that was run
        output:    The raw stdout+stderr of the command
        workspace: Absolute path to user's project root
    
    Returns:
        Compressed output string. Never raises — on any error,
        returns original output unchanged (fail-safe).
    
    Guarantees:
        - Never returns empty string if output was non-empty
        - Never modifies output if safety gate fails
        - Always records to learner on successful compression
        - Hot path uses in-memory cache (no file I/O)
    """
```

**Internal Rules**:
- Wrap entire function body in try/except — never crash the agent
- On any exception: log to stderr, return original output
- Hot cache is a module-level dict, not a class attribute
- Config is loaded once per session, not per call
- Learner.record() is always called after compression, never before

---

### 5.2 — safety.py

**Purpose**: Security gate. Runs before any other component.

**Public Interface**:
```python
def should_skip(command: str, output: str) -> tuple[bool, str]:
    """
    Returns (should_skip: bool, reason: str)
    
    reason is empty string if should_skip is False.
    reason is used for stderr warning only, never written to stdout.
    """

def is_security_sensitive(command: str, output: str) -> bool:
    """
    Returns True if command or output contains security patterns.
    Checks command path AND output content.
    """

def is_binary(output: str) -> bool:
    """
    Returns True if output contains binary/non-printable bytes.
    Uses null byte detection + high non-ASCII ratio heuristic.
    """

def is_minimal(output: str, threshold: int = 15) -> bool:
    """
    Returns True if output line count is below threshold.
    Nothing to compress — pass through.
    """
```

**Security Pattern Detection**:
```python
# These patterns trigger security skip
# Check in BOTH command string and output content
SECURITY_PATTERNS = [
    r'\.env$', r'\.env\.',          # .env files
    r'id_rsa', r'id_ed25519',       # SSH private keys
    r'\.pem$', r'\.key$',           # certificates
    r'credentials',                  # AWS credentials file
    r'secret',                       # generic secret
    r'password',                     # generic password
    r'api[_-]?key',                 # API keys
    r'AWS_SECRET',                   # AWS specific
    r'GITHUB_TOKEN',                 # GitHub tokens
    r'bearer\s+[a-zA-Z0-9]',       # Bearer tokens in output
    r'-----BEGIN',                   # PEM header
]

# Check command path for sensitive file reads
SENSITIVE_FILE_COMMANDS = ['cat', 'less', 'more', 'head', 'tail', 'bat']
```

**Critical Rules**:
- Pattern matching uses re.search with re.IGNORECASE
- Binary detection checks first 512 bytes only (performance)
- Security check emits to stderr: "clipress: skipped [reason]"
- NEVER emit the matched pattern or value to stderr

---

### 5.3 — classifier.py

**Purpose**: Detects output shape for unknown commands. The core intelligence for the cold path.

**Output Shapes** (exactly 7, maps to 7 strategies + 1 generic fallback):
```
list        — sequential items, one per line, mostly uniform
progress    — percentage lines, "step N/M", downloading, etc.
test        — PASSED/FAILED/ERROR patterns, test runner output
diff        — +/- prefixed lines, @@ hunk markers
table       — aligned columns with header separator line
keyvalue    — "key: value" or "key = value" patterns
error       — traceback, exception, stack frame patterns
generic     — fallback when no shape detected with confidence
```

**Public Interface**:
```python
def detect(output: str) -> tuple[str, float]:
    """
    Analyzes output and returns (shape_name, confidence).
    
    confidence is 0.0 to 1.0.
    shape_name is always one of the 7 shapes above.
    If confidence < 0.5 for all shapes, returns ("generic", 0.0).
    
    Detection is line-sampling based for performance:
    never reads more than 200 lines for classification.
    """
```

**Detection Logic Per Shape**:
```
list:
  Score += 0.3 if line count > 20
  Score += 0.3 if >80% lines have similar length (±20 chars)
  Score += 0.2 if no ":" patterns dominate
  Score += 0.2 if no "+"/"-" prefixes

progress:
  Score += 0.4 if any line matches r'\d+%' or r'\d+/\d+'
  Score += 0.3 if lines contain "downloading|fetching|step|layer"
  Score += 0.3 if line count > 10 and content is very repetitive

test:
  Score += 0.5 if any line matches r'PASSED|FAILED|ERROR|ok|FAIL'
  Score += 0.3 if "test" appears in >20% of lines
  Score += 0.2 if summary line pattern found

diff:
  Score += 0.6 if >10% lines start with "+" or "-"
  Score += 0.3 if "@@" appears in any line
  Score += 0.1 if "---" or "+++" appears

table:
  Score += 0.5 if line 2 matches r'^[-\s|+]+$' (separator)
  Score += 0.3 if columns align across 3+ lines
  Score += 0.2 if first line is all uppercase (header)

keyvalue:
  Score += 0.5 if >60% lines match r'^\w[\w\s]+:\s+\S'
  Score += 0.3 if >60% lines match r'^\w[\w\s]+=\s*\S'
  Score += 0.2 if no progress/test patterns present

error:
  Score += 0.5 if "Traceback" or "Exception" in output
  Score += 0.3 if "at line" or "File \"" patterns found
  Score += 0.2 if error line followed by indented lines
```

**Performance Rule**: Classifier must complete in <20ms on 1000-line output. Use line sampling, not full scan.

---

### 5.4 — learner.py

**Purpose**: Manages the adaptive workspace registry. Records, updates, and retrieves learned command patterns.

**Public Interface**:
```python
class Learner:
    def __init__(self, workspace: str): ...

    def lookup(self, command: str) -> dict | None:
        """
        Returns registry entry if confidence >= 0.85.
        Returns None if unknown or confidence too low.
        Never raises — returns None on any error.
        """

    def record(self,
               command: str,
               shape: str,
               raw_tokens: int,
               compressed_tokens: int) -> None:
        """
        Records or updates a command observation.
        Creates new entry if first time.
        Updates confidence if shape confirmed.
        Drops confidence if shape changed.
        Saves to disk atomically.
        Never raises — silently no-ops on any error.
        """

    def summary(self) -> dict:
        """
        Returns stats for session report:
        {total_learned, total_tokens_saved, hot_commands}
        """
```

**Confidence Rules**:
```python
INITIAL_CONFIDENCE = 0.50      # first observation
CONFIDENCE_GAIN    = 0.08      # per confirmed observation
CONFIDENCE_LOSS    = 0.20      # when shape changes
HOT_THRESHOLD      = 0.85      # minimum to use without classifier
LOCKED_THRESHOLD   = 0.95      # treated same as built-in seed
HOT_CALL_THRESHOLD = 10        # calls before promoted to memory cache
```

**Atomic Write Rule**:
```python
# NEVER write directly to registry.json
# Use atomic write pattern:
def _save(self):
    tmp_path = self.path.with_suffix('.tmp')
    with open(tmp_path, 'w', mode=0o600) as f:
        json.dump(self.data, f, indent=2)
    tmp_path.replace(self.path)  # atomic on POSIX
```

**Data Schema** (registry.json):
```json
{
  "version": "1.0",
  "workspace": "/absolute/path/to/project",
  "entries": {
    "git status": {
      "source": "seed|learned|user",
      "strategy": "keyvalue",
      "calls": 0,
      "confidence": 0.50,
      "avg_raw_tokens": 0,
      "avg_compressed_tokens": 0,
      "compression_ratio": 0.0,
      "hot": false,
      "user_override": false,
      "last_seen": "2026-04-24T00:00:00Z",
      "params": {}
    }
  },
  "stats": {
    "total_commands_learned": 0,
    "total_tokens_saved": 0,
    "session_count": 0
  }
}
```

---

### 5.5 — strategies/base.py

**Purpose**: Abstract base class all strategies must inherit from.

```python
from abc import ABC, abstractmethod

class BaseStrategy(ABC):

    @abstractmethod
    def compress(self,
                 output: str,
                 params: dict,
                 contract: dict) -> str:
        """
        Compress the output string.
        
        Args:
            output:   Raw command output
            params:   Strategy-specific parameters from registry
            contract: User output contract (always_keep, always_strip)
        
        Returns:
            Compressed string. MUST be shorter than input
            OR equal to input if nothing to compress.
            MUST NEVER return empty string for non-empty input.
            MUST honor contract.always_keep patterns.
            MUST honor contract.always_strip patterns.
        
        Contract enforcement order:
            1. Apply strategy compression
            2. Re-add lines matching always_keep that were removed
            3. Remove lines matching always_strip
            4. Return result
        """

    def _apply_contract(self,
                        lines: list[str],
                        original_lines: list[str],
                        contract: dict) -> list[str]:
        """
        Shared contract enforcement.
        All strategies call this as their final step.
        """
        keep_patterns = contract.get('always_keep', [])
        strip_patterns = contract.get('always_strip', [])

        # restore any always_keep lines that were stripped
        if keep_patterns:
            kept = [l for l in original_lines
                    if any(re.search(p, l) for p in keep_patterns)]
            # add back if not already present
            for line in kept:
                if line not in lines:
                    lines.append(line)

        # strip always_strip lines
        if strip_patterns:
            lines = [l for l in lines
                     if not any(re.search(p, l) for p in strip_patterns)]

        return lines

    def name(self) -> str:
        return self.__class__.__name__.replace('Strategy', '').lower()
```

---

### 5.6 — strategies/ (All 8 Strategies)

**General Rules for All Strategies**:
- Never import from outside the strategies/ package (except base.py)
- Never call external processes
- Never read from disk
- All regex patterns are pre-compiled at class level (not per call)
- All strategies are stateless — no instance variables that change

**list_strategy.py**:
```
Input:  Long sequential lists (ls, find, pip list, etc.)
Logic:
  1. Strip blank lines and ANSI codes
  2. If lines <= max_lines: return as-is
  3. Keep head_lines from top
  4. Keep tail_lines from bottom
  5. Insert "... [X more items]" marker in middle
  6. Group by directory if group_by_directory=True
  7. Apply contract
Default params: max_lines=30, head_lines=20, tail_lines=5
```

**progress_strategy.py**:
```
Input:  Progress bars, download output, build steps
Logic:
  1. Strip ANSI escape codes entirely
  2. Strip percentage-only lines (r'^\s*\d+%')
  3. Strip ETA/speed lines (r'eta|speed|\d+\s*[kmg]b/s')
  4. Strip step lines if keep="final_line"
  5. Always keep error lines
  6. Always keep final status line (last non-empty line)
  7. Apply contract
Default params: keep="final_line", strip_percentage=True
```

**test_strategy.py**:
```
Input:  pytest, jest, cargo test, mocha, etc.
Logic:
  1. Detect test runner from content patterns
  2. Strip all passing test lines
  3. Keep all failing test lines + their traceback (max 8 lines)
  4. Keep summary line (always last meaningful line)
  5. Deduplicate repeated assertion messages
  6. Apply contract
Default params: keep="failed_only", max_traceback_lines=8
```

**diff_strategy.py**:
```
Input:  git diff, patch files, any unified diff
Logic:
  1. Keep all "+" lines (additions)
  2. Keep all "-" lines (deletions)
  3. Keep "@@" hunk headers
  4. Keep "+++" and "---" file markers
  5. Keep N context lines around each change (default: 2)
  6. Strip "index " metadata lines
  7. If total > max_lines: summarize by file with change counts
  8. Apply contract
Default params: max_lines=80, context_lines=2
```

**table_strategy.py**:
```
Input:  docker ps, kubectl get, columnar output
Logic:
  1. Detect header row (all uppercase or separator line below)
  2. Keep header always
  3. If rows > max_rows: keep first max_rows, add count marker
  4. Truncate cells longer than max_cell_length
  5. Keep always_keep_columns, drop others if > max_columns
  6. Apply contract
Default params: max_rows=20, max_columns=5, max_cell_length=40
```

**keyvalue_strategy.py**:
```
Input:  Status output, config dumps, JSON-like text
Logic:
  1. Parse key:value and key=value patterns
  2. Strip keys in always_strip_keys list
  3. If pairs > max_lines: keep most relevant (non-timestamp keys)
  4. Preserve original formatting of values
  5. Apply contract
Default params: max_lines=20
```

**error_strategy.py**:
```
Input:  Exceptions, tracebacks, stack traces
Logic:
  1. Find error/exception header line (always keep)
  2. Keep first max_traceback_lines of trace
  3. Strip duplicate frame entries
  4. Keep final "caused by" chain (max 2 levels)
  5. Strip noisy frame paths (site-packages, stdlib)
  6. Apply contract
Default params: max_traceback_lines=10, strip_stdlib_frames=True
```

**generic_strategy.py**:
```
Input:  Anything that didn't match other shapes
Logic:
  1. Strip ANSI escape codes
  2. Strip blank lines
  3. Deduplicate: collapse lines repeated >=3 times
     into "line [repeated Nx]"
  4. If lines > max_lines: truncate with head+tail
  5. Apply contract
Default params: max_lines=50, head_lines=20, tail_lines=10
  dedup_min_repeats=3
```

---

### 5.7 — config.py

**Purpose**: Load, validate, and merge default + user configs.

**Loading Order** (strict):
```
1. Load clipress/defaults/config.yaml (always exists, ships with pkg)
2. Check for .compressor/config.yaml in workspace
3. If user config exists: deep merge (user values override defaults)
4. If user config missing: defaults are complete and sufficient
5. Cache merged config in module-level dict per workspace path
```

**Validation Rules**:
```python
# After loading, validate these constraints:
assert config['engine']['min_lines_to_compress'] >= 5
assert config['engine']['hot_cache_threshold'] >= 1
assert all(isinstance(p, str) for p in
           config['safety']['security_patterns'])
# If validation fails: log to stderr, use defaults only
# NEVER crash on bad user config
```

**Deep Merge Rule**:
```python
def deep_merge(base: dict, override: dict) -> dict:
    """
    Lists in override REPLACE lists in base (not extend).
    Dicts in override are merged recursively.
    Scalar values in override replace base values.
    Keys in base not present in override are preserved.
    """
```

---

### 5.8 — metrics.py

**Purpose**: Token counting and session reporting. Entirely opt-in.

**Token Counting**:
```python
def count_tokens(text: str) -> int:
    """
    Approximates token count without tiktoken dependency.
    Uses word-based heuristic: tokens ≈ words * 1.3
    Fast, dependency-free, accurate enough for reporting.
    
    If tiktoken is installed: use cl100k_base encoding.
    If not installed: use word heuristic.
    tiktoken is OPTIONAL, never a hard dependency.
    """
```

**Session Report Format**:
```
clipress session report
───────────────────────────────────────────
compressed   : 47 commands
skipped      : 8 commands
tokens saved : 48,200 → 3,100 (93% reduction)

top savers:
  pytest -v          96% │ 8400 → 312 tokens
  docker build .     97% │ 3200 → 89 tokens
  git log --oneline  91% │ 1500 → 135 tokens

learned this session:
  ✅ datadog-agent status  (keyvalue, ×3)
  ✅ myapp export          (progress, ×5)
  🔄 internal-ci run       (learning, ×1)
───────────────────────────────────────────
```

**Rules**:
- Metrics are only printed if `engine.show_metrics: true` in config
- Metrics go to stderr, never stdout (stdout is for compressed output)
- No metrics are written to disk by default
- No metrics are ever sent externally

---

### 5.9 — seeds.json

**Purpose**: Built-in seed entries. Ships with package. Never edited at runtime.

**Format**:
```json
{
  "version": "1.0",
  "seeds": {
    "git status":    { "strategy": "keyvalue",  "params": { "max_lines": 15 }},
    "git diff":      { "strategy": "diff",      "params": { "max_lines": 80, "context_lines": 2 }},
    "git log":       { "strategy": "list",      "params": { "max_lines": 20 }},
    "git push":      { "strategy": "progress",  "params": { "keep": "final_line" }},
    "git pull":      { "strategy": "progress",  "params": { "keep": "final_line" }},
    "git stash":     { "strategy": "list",      "params": { "max_lines": 10 }},
    "docker ps":     { "strategy": "table",     "params": { "max_rows": 15 }},
    "docker build":  { "strategy": "progress",  "params": { "keep": "errors_and_final" }},
    "docker logs":   { "strategy": "list",      "params": { "dedup": true, "tail_lines": 30 }},
    "docker images": { "strategy": "table",     "params": { "max_rows": 20 }},
    "pytest":        { "strategy": "test",      "params": { "keep": "failed_only" }},
    "jest":          { "strategy": "test",      "params": { "keep": "failed_only" }},
    "cargo test":    { "strategy": "test",      "params": { "keep": "failed_only" }},
    "npm install":   { "strategy": "progress",  "params": { "keep": "final_line" }},
    "pip install":   { "strategy": "progress",  "params": { "keep": "final_line" }},
    "cargo build":   { "strategy": "progress",  "params": { "keep": "errors_and_final" }},
    "npm run build": { "strategy": "progress",  "params": { "keep": "errors_and_final" }},
    "ls":            { "strategy": "list",      "params": { "max_lines": 30 }},
    "find":          { "strategy": "list",      "params": { "group_by_directory": true }},
    "cat":           { "strategy": "list",      "params": { "max_lines": 50 }}
  }
}
```

**Matching Rules**:
```python
# Command matching is prefix-based on the normalized command
# Normalization: strip leading whitespace, collapse multiple spaces
# Match order:
#   1. Exact match (full command string)
#   2. Command + first subcommand ("git status" matches "git status -s")
#   3. Root command only ("pytest" matches "pytest tests/ -v --tb=short")
# First match wins. No ambiguity allowed.
```

---

### 5.10 — hooks/post_tool_use.py

**Purpose**: Claude Code PostToolUse hook. The primary integration point.

```python
#!/usr/bin/env python3
"""
Claude Code PostToolUse hook for clipress.
Registered in .claude/settings.json.
Receives hook data via stdin as JSON.
Writes compressed output to stdout as JSON.

Hook input schema (from Claude Code):
{
  "tool_name": "Bash",
  "tool_input": { "command": "git status" },
  "tool_response": { "output": "..." }
}

Hook output schema (to Claude Code):
{
  "type": "tool_result",
  "content": "compressed output here"
}
"""
import sys
import json
import os

def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # malformed input — pass through
        sys.exit(0)

    # only handle Bash tool
    if data.get('tool_name') != 'Bash':
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')
    output  = data.get('tool_response', {}).get('output', '')

    if not command or not output:
        sys.exit(0)

    # find workspace root (walk up from cwd looking for .git)
    workspace = find_workspace_root(os.getcwd())

    from clipress.engine import compress
    compressed = compress(command, output, workspace)

    # output ONLY the compressed content to stdout
    print(compressed, end='')
    sys.exit(0)


def find_workspace_root(start: str) -> str:
    """Walk up directory tree to find .git root."""
    path = os.path.abspath(start)
    while path != os.path.dirname(path):
        if os.path.exists(os.path.join(path, '.git')):
            return path
        path = os.path.dirname(path)
    return start  # fallback to cwd if no .git found


if __name__ == '__main__':
    main()
```

**Claude Code Settings Registration**:
```json
// .claude/settings.json — placed in user's project by installer
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -m clipress.hooks.post_tool_use"
          }
        ]
      }
    ]
  }
}
```

---

### 5.11 — hooks/shell_hook.sh

**Purpose**: Shell-level wrapper for Gemini CLI, Codex, and any terminal-based agent.

```bash
#!/usr/bin/env bash
# clipress shell hook
# Source this in ~/.bashrc or ~/.zshrc:
#   source ~/.clipress/shell_hook.sh
#
# This wraps bash command output for ANY terminal-based AI agent.
# Works with: Gemini CLI, Codex, Cursor terminal, any agent using bash.

export CLIPRESS_ENABLED="${CLIPRESS_ENABLED:-true}"
export CLIPRESS_WORKSPACE="${CLIPRESS_WORKSPACE:-$(pwd)}"

# Only activate if clipress is installed and enabled
if [[ "$CLIPRESS_ENABLED" != "true" ]]; then
    return 0
fi

if ! command -v python3 &>/dev/null; then
    return 0
fi

if ! python3 -c "import clipress" &>/dev/null 2>&1; then
    return 0
fi

# Override the command output for AI agent contexts
# Uses DEBUG trap to intercept command output
# Only active when CLIPRESS_AGENT_MODE=true is set
clipress_compress() {
    local cmd="$1"
    local output="$2"
    echo "$output" | python3 -m clipress.compress \
        --command "$cmd" \
        --workspace "$CLIPRESS_WORKSPACE"
}
```

---

### 5.12 — cli.py

**Purpose**: User-facing CLI commands via click.

```
Commands:

clipress status
  Shows current session stats, learned commands, config path

clipress init
  Initializes .compressor/ in current directory
  Creates .compressor/config.yaml from template
  Safe to run multiple times (idempotent)

clipress learn show
  Displays learned.json in human-readable format
  Shows confidence, call counts, token savings per command

clipress learn reset [command]
  Resets confidence for a specific command
  Or resets all learned data if no command given
  Asks for confirmation before reset

clipress compress <command> [--workspace PATH]
  Stdin: raw command output
  Stdout: compressed output
  Used by shell_hook.sh

clipress config validate
  Validates .compressor/config.yaml against schema
  Reports any invalid keys or values

clipress report
  Prints full session report (same as show_metrics output)
```

---

## 6. INTEGRATION LAYER

### Claude Code (Primary)
```
Method:    PostToolUse hook (native)
File:      .claude/settings.json in user project
Coverage:  100% of bash commands run by agent
Install:   clipress init (run in project root)
```

### Gemini CLI / Codex / Pi
```
Method:    Shell wrapper (shell_hook.sh)
File:      Sourced from ~/.bashrc or ~/.zshrc
Coverage:  All terminal commands during agent session
Install:   echo 'source ~/.clipress/shell_hook.sh' >> ~/.bashrc
```

### Cursor / Copilot (Integrated Terminal)
```
Method:    Shell wrapper (same as above)
Coverage:  Bash commands in integrated terminal only
           Does NOT cover Cursor's native file APIs
           Does NOT cover Copilot Chat operations
Document:  README must clearly state partial coverage
```

---

## 7. TESTING REQUIREMENTS

### Coverage Target
```
Minimum: 85% line coverage across all modules
Target:  90%+ for engine.py, safety.py, classifier.py
```

### Required Test Categories

**Unit Tests** — each component in isolation:
```python
# test_safety.py
test_blocks_env_file_command()
test_blocks_ssh_key_read()
test_blocks_binary_output()
test_passes_clean_git_status()
test_passes_minimal_output_flag()
test_detects_bearer_token_in_output()
test_emits_to_stderr_not_stdout()

# test_classifier.py
test_detects_list_shape()
test_detects_progress_shape()
test_detects_test_shape_pytest()
test_detects_test_shape_jest()
test_detects_diff_shape()
test_detects_table_shape()
test_detects_keyvalue_shape()
test_detects_error_shape()
test_falls_back_to_generic()
test_completes_in_under_20ms()  # performance assertion

# test_learner.py
test_records_new_command()
test_updates_confidence_on_confirmation()
test_drops_confidence_on_shape_change()
test_promotes_to_hot_at_threshold()
test_does_not_record_output_content()
test_atomic_write_on_save()
test_returns_none_on_low_confidence()
test_handles_corrupt_registry_gracefully()

# test_engine.py
test_hot_path_uses_no_file_io()
test_returns_original_on_exception()
test_never_returns_empty_for_nonempty_input()
test_safety_gate_runs_before_compression()
test_contract_always_keep_survives_compression()
test_contract_always_strip_applied_last()
```

**Integration Tests** — real fixture files:
```python
# tests/strategies/test_*.py
# Each strategy test loads real fixture output
# and asserts compression ratio > 0.70

def test_git_status_saves_70_percent():
    raw = load_fixture("git_status.txt")
    result = GitStatusStrategy().compress(raw, {}, {})
    assert compression_ratio(raw, result) > 0.70
    assert "modified" in result  # meaningful content preserved

def test_pytest_keeps_failures_only():
    raw = load_fixture("pytest_output.txt")
    result = TestStrategy().compress(raw, {"keep": "failed_only"}, {})
    assert "FAILED" in result
    assert "PASSED" not in result
```

**Security Tests**:
```python
def test_never_logs_secret_value():
    output = "DATABASE_URL=postgres://user:P4ssw0rd@host/db"
    should_skip, reason = safety.should_skip("cat .env", output)
    assert should_skip is True
    assert "P4ssw0rd" not in reason  # reason must not contain secret

def test_no_network_calls():
    import socket
    original_connect = socket.socket.connect
    calls = []
    socket.socket.connect = lambda *a: calls.append(a)
    compress("git status", "On branch main", "/tmp")
    assert len(calls) == 0
    socket.socket.connect = original_connect
```

**Performance Tests**:
```python
def test_hot_path_under_5ms():
    # warm up hot cache first
    for _ in range(15):
        compress("git status", GIT_STATUS_OUTPUT, WORKSPACE)
    # now measure hot path
    start = time.perf_counter()
    compress("git status", GIT_STATUS_OUTPUT, WORKSPACE)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.005  # 5ms

def test_classifier_under_20ms():
    large_output = "\n".join([f"file_{i}.txt" for i in range(1000)])
    start = time.perf_counter()
    classifier.detect(large_output)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.020  # 20ms
```

### Test Fixtures
Every fixture file must be a REAL captured output from the actual command. No fabricated outputs. Fixture sources documented in conftest.py.

---

## 8. PERFORMANCE REQUIREMENTS

### Latency Targets
```
Safety check:         < 2ms
Registry lookup:      < 1ms (hot), < 10ms (warm/file)
Classification:       < 20ms on 1000-line output
Compression:          < 10ms on 1000-line output
Total (hot path):     < 5ms
Total (warm path):    < 50ms
Total (cold path):    < 200ms
```

### Memory Targets
```
Hot cache:            < 5MB (evict LRU after 100 entries)
Config cache:         < 1MB
Per-call allocation:  < 512KB (no large string copies)
```

### Optimization Rules
```
1. Pre-compile all regex patterns at class/module level
   Never compile inside a function that is called per-command

2. Use line sampling in classifier (max 200 lines)
   Never scan the full output for shape detection

3. Hot cache is a module-level dict with maxlen=100
   Use collections.OrderedDict for LRU eviction

4. Config loaded once per process, cached in module global
   Never re-read config.yaml on every compress() call

5. Learner saves to disk asynchronously when possible
   Use threading.Thread(daemon=True) for disk writes
   Never block the compression return on disk I/O

6. Binary detection reads only first 512 bytes
   Never load full binary output into memory
```

---

## 9. DISTRIBUTION & INSTALLATION

### Package Metadata (pyproject.toml)
```toml
[project]
name = "clipress"
version = "0.1.0"
description = "Universal CLI output compressor for AI agents"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "ruamel.yaml>=0.18",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "tiktoken>=0.5",
]

[project.scripts]
clipress = "clipress.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Install Methods
```bash
# Recommended — isolated environment
pipx install clipress

# Alternative — pip
pip install clipress

# Development
git clone https://github.com/user/clipress
cd clipress
pip install -e ".[dev]"
```

### install.sh (One-Command Setup for Claude Code)
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Installing clipress..."

# Check Python 3.11+
python3 --version | grep -E "3\.(1[1-9]|[2-9][0-9])" || {
    echo "Error: Python 3.11+ required"
    exit 1
}

# Install package
pipx install clipress || pip install clipress

# Initialize in current directory
clipress init

echo "Done. clipress is active for this project."
echo "Run 'clipress status' to verify."
```

---

## 10. AGENT BUILD INSTRUCTIONS

### ⚠️ READ BEFORE WRITING ANY CODE

```
You are building a production Python package.
Every file you write will be used by real users
in AI agent workflows where reliability is critical.

Treat this as you would treat code going into
a production system used by thousands of developers.
```

### Build Order (STRICT — Do Not Reorder)

```
PHASE 1 — Foundation (build in this exact order)
─────────────────────────────────────────────────
Step 1:  Create pyproject.toml
Step 2:  Create clipress/__init__.py (version only)
Step 3:  Create clipress/defaults/config.yaml (full default config)
Step 4:  Create clipress/registry/seeds.json (all 20 seeds)
Step 5:  Create clipress/strategies/base.py (abstract class)
Step 6:  Create clipress/strategies/generic_strategy.py (fallback first)
Step 7:  Create clipress/safety.py
Step 8:  Write tests/test_safety.py — run tests — must pass
Step 9:  Create clipress/classifier.py
Step 10: Write tests/test_classifier.py — run tests — must pass

PHASE 2 — Strategies (build in this exact order)
─────────────────────────────────────────────────
Step 11: list_strategy.py + test
Step 12: progress_strategy.py + test
Step 13: test_strategy.py + test
Step 14: diff_strategy.py + test
Step 15: table_strategy.py + test
Step 16: keyvalue_strategy.py + test
Step 17: error_strategy.py + test
Step 18: clipress/strategies/__init__.py (registry dict)

PHASE 3 — Core Engine
─────────────────────────────────────────────────
Step 19: Create clipress/config.py
Step 20: Write tests/test_config.py — run tests — must pass
Step 21: Create clipress/learner.py
Step 22: Write tests/test_learner.py — run tests — must pass
Step 23: Create clipress/metrics.py
Step 24: Create clipress/engine.py
Step 25: Write tests/test_engine.py — run tests — must pass

PHASE 4 — Integration
─────────────────────────────────────────────────
Step 26: Create clipress/hooks/post_tool_use.py
Step 27: Create clipress/hooks/shell_hook.sh
Step 28: Create clipress/cli.py
Step 29: Create install.sh
Step 30: Write integration tests with real fixtures
Step 31: Run full test suite — coverage must be ≥85%

PHASE 5 — Documentation
─────────────────────────────────────────────────
Step 32: Write README.md
Step 33: Write CHANGELOG.md
Step 34: Final security audit (checklist below)
```

### Per-Step Rules

```
After every step:
  □ Run existing tests — they must still pass
  □ No new warnings introduced
  □ No commented-out code left in files
  □ All functions have docstrings

After Phase 1:
  □ Safety gate correctly blocks all security patterns
  □ Classifier detects all 7 shapes with >50% confidence

After Phase 2:
  □ Every strategy saves >70% tokens on its fixture file
  □ Every strategy honors always_keep contract rules
  □ Every strategy honors always_strip contract rules

After Phase 3:
  □ Hot path under 5ms (verified by timing test)
  □ Learner never records output content
  □ Config merge works correctly

After Phase 4:
  □ End-to-end test: real git status → compressed output
  □ Claude Code hook receives correct JSON format
  □ Shell hook sources without errors on bash + zsh

After Phase 5:
  □ Full security checklist passed
  □ Coverage ≥85%
  □ No failing tests
```

---

## 11. CODEBASE PRACTICES & ANTI-PATTERNS

### Required Practices

```python
# ✅ All regex pre-compiled at class level
class ProgressStrategy(BaseStrategy):
    _PCT_PATTERN = re.compile(r'^\s*\d+%')
    _ETA_PATTERN = re.compile(r'eta|remaining', re.IGNORECASE)

# ✅ Type hints on all public functions
def compress(command: str, output: str, workspace: str) -> str:

# ✅ Docstrings on all public functions and classes

# ✅ Fail-safe in engine
def compress(command, output, workspace):
    try:
        # ... compression logic
    except Exception as e:
        print(f"clipress error: {e}", file=sys.stderr)
        return output  # always return something

# ✅ Atomic file writes
tmp = path.with_suffix('.tmp')
tmp.write_text(content)
tmp.replace(path)

# ✅ Pathlib for all file operations
from pathlib import Path
config_path = Path(workspace) / '.compressor' / 'config.yaml'

# ✅ yaml.safe_load always
config = yaml.safe_load(config_file)  # never yaml.load()

# ✅ Stderr for all tool messages
print("clipress: skipped binary output", file=sys.stderr)
```

### Forbidden Anti-Patterns

```python
# ❌ NEVER — execute user input
eval(command)
exec(output)
subprocess.run(command_from_output)

# ❌ NEVER — yaml.load without Loader
yaml.load(f)  # code execution vector

# ❌ NEVER — compile regex inside per-call function
def compress(output):
    pattern = re.compile(r'PASSED')  # compiled every call

# ❌ NEVER — catch and swallow all exceptions silently
try:
    compress(...)
except:
    pass  # no logging, no fallback return

# ❌ NEVER — write output content to disk
learner.record(command, shape, output_content=output)

# ❌ NEVER — network calls of any kind
import requests
import urllib
import socket  # except in tests

# ❌ NEVER — global mutable state outside of explicitly
#            documented hot cache and config cache
GLOBAL_STATE = {}  # unless it's _hot_cache or _config_cache

# ❌ NEVER — print to stdout from anywhere except engine output
print("debug info")  # use sys.stderr

# ❌ NEVER — hardcode workspace paths
path = "/home/user/.compressor"  # always use workspace param

# ❌ NEVER — skip test after writing a component
# Write the test. Run the test. Fix until it passes. Move on.
```

### Code Style Rules

```
Line length:      88 characters (black default)
Formatter:        black
Linter:           ruff
Import order:     isort
Type checker:     mypy (warn-only, not blocking)

Naming:
  Classes:        PascalCase
  Functions:      snake_case
  Constants:      UPPER_SNAKE_CASE
  Private:        _leading_underscore

File structure (every .py file):
  1. Module docstring
  2. Standard library imports
  3. Third-party imports
  4. Local imports
  5. Constants
  6. Classes/functions
  7. if __name__ == '__main__': (only for hooks)
```

---

## 12. DEFINITION OF DONE

The package is complete when ALL of the following are true:

### Functional
```
□ clipress init runs in a project and creates .compressor/
□ git status output is compressed to <15 lines
□ pytest -v output shows only failures + summary
□ docker build output shows only errors + final status
□ Unknown commands are classified and compressed generically
□ Same unknown command on second call uses learned registry
□ Hot cache is active after 10 calls to same command
□ .env file read is blocked by safety gate
□ Binary command output is passed through untouched
□ User config.yaml overrides default contracts
□ Custom command in extensions/myapp.yaml is respected
□ clipress status shows learned commands and token savings
```

### Quality
```
□ Test coverage ≥ 85% (verified by pytest --cov)
□ All tests pass on Python 3.11, 3.12
□ All tests pass on Ubuntu 22.04 and macOS 14
□ No warnings from ruff linter
□ No errors from mypy type checker
□ black formatter passes with zero changes
```

### Security
```
□ yaml.safe_load used everywhere (grep verified)
□ No eval() or exec() in codebase (grep verified)
□ No network calls in codebase (grep verified)
□ .compressor/ created with mode 0700
□ registry.json created with mode 0600
□ Security patterns tested with real-world secret formats
□ No secret values appear in any error messages
```

### Performance
```
□ Hot path measured < 5ms (timing test passes)
□ Classifier measured < 20ms on 1000-line output
□ Memory profiled < 5MB for hot cache at 100 entries
□ No regex compiled inside per-call functions
```

### Distribution
```
□ pipx install clipress works on clean Ubuntu 22.04
□ pipx install clipress works on clean macOS 14
□ install.sh runs end-to-end without errors
□ clipress --help shows all commands
□ README.md covers install, usage, and config
□ CHANGELOG.md has v0.1.0 entry
```

---

*End of Build Plan — clipress v1.0*
*All requirements above are mandatory for v1.0 release.*
*No partial implementations. No deferred security items.*
*Build in order. Test at every step. Ship clean.*
