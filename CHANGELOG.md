# Changelog

## [1.3.1] - 2026-04-27
### Added
- `clipress restore` command family:
  - `clipress restore`
  - `clipress restore <id>`
  - `clipress restore --command "<cmd>"`
  - `clipress restore --list [--limit N]`
- Workspace history store (`.clipress/history.db`, SQLite+WAL) to retain recent raw/compressed outputs.
- Engine cost guardrails:
  - `engine.target_max_tokens`
  - `engine.min_savings_ratio`
  - `engine.min_raw_tokens_for_cost_guard`
  - adaptive generic fallback for large expensive outputs.

### Fixed
- Per-command config overrides now honor documented longest-prefix matching (`commands:`), not exact-only matching.
- Streaming seed parameter merges now use the same longest-prefix command override resolution as non-streaming compression.

### Changed
- Default config now includes `save_history` + `history_max_entries`.
- Docs updated for cost controls, history storage, and restore workflow.

## [1.2.2] - 2026-04-24
### Fixed (Critical)
- **Size-regression guard bypassed by whitespace bloat** (`engine.py`): the guard compared only
  word-based token counts, so a strategy that added pure whitespace (e.g. `"\n" * 1000`) slipped
  through unchanged. Guard now also compares byte length. (Surfaced by the previously failing
  `test_size_regression_guard`.)
- **User `security_patterns` were silently ignored** (`safety.py`, `config.py`): the safety gate
  only consulted the hardcoded module-level list. User-supplied patterns under
  `safety.security_patterns` in `config.yaml` are now compiled and applied on top of the defaults.
- **`Learner.__init__` crashed on legacy/partial `registry.json`**: if the loaded file lacked
  `stats` (or `entries`) keys, `stats.session_count += 1` raised `KeyError`, which was then
  swallowed by the engine's blanket try/except — silently degrading to raw passthrough. Missing
  top-level keys are now backfilled after load.

### Fixed (High)
- **`clipress validate` now exits non-zero** on invalid configs and reports the error on stderr.
  Previously it always exited 0 because `get_config` fell back to defaults on validation failure.
- **Version skew**: `clipress/__init__.py` hard-coded `__version__ = "0.1.0"` while `pyproject`
  was 1.2.x. `__version__` is now sourced from `importlib.metadata`.
- **Generic secret patterns tightened with word boundaries** (`\bsecret\b`, `\bpassword\b`,
  `\bcredentials\b`, `\bid_rsa\b`, `\bid_ed25519\b`, `\bapi[_-]?key\b`) so legitimate tokens
  like "secretary" no longer trip the safety gate.

### Changed
- Classifier: renamed the confusingly-named `num_diff_words` counter to `num_test_name_hits`
  (it was used for the test-shape score, not diff). Removed the redundant second KV pass; `num_kv1`
  and `num_kv2` are now computed once in the main loop.
- Engine: unused `confidence` value from `classifier.detect` is now explicitly discarded.
- `Learner._async_save` no longer spawns a thread per `record()`. A single daemon writer coalesces
  bursts into one save.
- `Learner.record` errors surface on stderr when `CLIPRESS_DEBUG=1` is set, instead of being
  unconditionally swallowed.
- `TestStrategy._SUMMARY` regex is now anchored so `--- a/file.txt` in mixed diff/test output
  doesn't get mis-flagged as a summary line.
- `ErrorStrategy` stdlib-frame stripping broadened beyond `/usr/lib/python` to cover
  `site-packages`, `dist-packages`, pyenv, venv, conda, and `<frozen …>` frames.
- `post_tool_use.py` hook coerces non-string `tool_response.output` defensively.
- Shell hook comment no longer claims to use a DEBUG trap (it's a pipe helper).
- Removed leftover dev artifact `fix_lint.py`.
- README references `./install.sh`.

### Added
- `clipress.config.validate_workspace_config(workspace)` — raises on validation failure, used
  by `clipress validate`.
- Tests: `test_size_regression_guard_whitespace_bloat`,
  `test_user_security_patterns_are_applied`, `test_invalid_user_security_pattern_is_ignored`,
  `test_generic_secret_word_boundary`, `test_handles_registry_missing_stats_key`,
  `test_handles_non_dict_registry_payload`,
  `test_cli_validate_exits_nonzero_on_invalid_config`,
  `test_cli_validate_passes_on_valid_config`, `test_package_version_matches_pyproject`.

## [1.2.1] - 2026-04-24
### Fixed
- **Bug: Double Learner instantiation** (`engine.py`): `Learner(workspace)` was being constructed twice per `compress()` call for non-seed, non-cached commands — once for lookup and once redundantly for `record()`. This caused `session_count` to be incremented twice and wasted a full disk read. Fixed by tracking a single `learner = None` variable and reusing it.
- **Bug: Unused `re` import** in `diff_strategy.py` and `error_strategy.py` — removed after global ANSI stripping made per-strategy regex redundant.

### Added
- **Size-regression guard**: Engine now checks if compressed output has more tokens than the original. If so, the original is returned. Prevents strategies from accidentally bloating output.
- **Improved `clipress init`**: Now scaffolds a complete workspace — `config.yaml` with commented examples, `extensions/example.yaml.disabled` with format documentation, and `.clipress-ignore` template.
- **Tests**: `test_size_regression_guard`, `test_learner_instantiated_once_per_compress`, `test_invalid_max_output_bytes_falls_back_to_defaults`.

## [1.2.0] - 2026-04-24
### Fixed & Hardened
- **GAP-1**: Added `max_output_bytes` guard (default 10 MB) in engine to prevent OOM on large outputs.
- **GAP-2**: Added `fcntl.flock()` exclusive locking on `registry.json` writes to prevent concurrent-process corruption.
- **GAP-3**: Extended binary detection scan from 512 to 4096 bytes for more reliable non-printable detection.
- **GAP-4**: Replaced dead `SENSITIVE_FILE_COMMANDS` constant with `SENSITIVE_ENV_COMMANDS`; now blocks `printenv`, `env`, `declare`, `set` unconditionally.
- **GAP-5**: Added `threading.Lock` around all `_HOT_CACHE` reads and writes for thread-safe concurrent access.
- **GAP-6**: Documented shell hook as a helper-function (not auto-interception); clarified pipe pattern in README.
- **GAP-7**: `clipress error-passthrough` now calls `clear_cache()` after writing config so the new value is applied immediately.
- **GAP-8**: `_validate()` now validates `commands:` block structure and regex list types.
- **GAP-10**: Removed redundant per-strategy `_ANSI_ESCAPE` regex from `diff`, `error`, `table`, `keyvalue`, `test` strategies — engine handles ANSI stripping globally.
- **Docs**: README expanded with extension YAML format, per-command contracts, `.clipress-ignore` format, `max_output_bytes`, and shell hook clarification.
- **Tests**: Added `test_max_output_bytes_passthrough`, `test_blocks_binary_beyond_512_bytes`, `test_blocks_printenv_command`.


### Fixed & Improved
- Implemented global ANSI escape code stripping.
- Fixed JSON envelope output in `post_tool_use.py` hook.
- Enforced per-command contracts via `config.yaml`.
- Implemented `dedup: true` parameter for `list_strategy` to fix `docker logs` seed.
- Support for `clipress error-passthrough` command to easily toggle pass-through behaviour.
- Allowed user extensions (`.clipress/extensions/*.yaml`) to override built-in seeds.
- Added error output pass-through when `pass_through_on_error` is True.
- Refined classifier's error detection rules.
- Safe YAML loading via `ruamel.yaml`.
- Documented thread-safety limitations and streaming issues.

## [0.1.0] - 2026-04-24
### Added
- Universal CLI output compressor for AI agents.
- Hybrid 3-layer architecture: Safety gate, Seeds + Learner, Classifier.
- Support for 7 output shapes: list, progress, test, diff, table, keyvalue, error.
- PostToolUse hook for Claude Code integration.
- Shell wrapper hook for bash/zsh integration.
- CLI application for status, config management, and manual compression.
