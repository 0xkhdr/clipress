# Changelog

## [1.2.1] - 2026-04-24
### Fixed
- **Bug: Double Learner instantiation** (`engine.py`): `Learner(workspace)` was being constructed twice per `compress()` call for non-seed, non-cached commands — once for lookup and once redundantly for `record()`. This caused `session_count` to be incremented twice and wasted a full disk read. Fixed by tracking a single `learner = None` variable and reusing it.
- **Bug: Unused `re` import** in `diff_strategy.py` and `error_strategy.py` — removed after global ANSI stripping made per-strategy regex redundant.

### Added
- **Size-regression guard**: Engine now checks if compressed output has more tokens than the original. If so, the original is returned. Prevents strategies from accidentally bloating output.
- **Improved `clipress init`**: Now scaffolds a complete workspace — `config.yaml` with commented examples, `extensions/example.yaml.disabled` with format documentation, and `.compressor-ignore` template.
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
- **Docs**: README expanded with extension YAML format, per-command contracts, `.compressor-ignore` format, `max_output_bytes`, and shell hook clarification.
- **Tests**: Added `test_max_output_bytes_passthrough`, `test_blocks_binary_beyond_512_bytes`, `test_blocks_printenv_command`.


### Fixed & Improved
- Implemented global ANSI escape code stripping.
- Fixed JSON envelope output in `post_tool_use.py` hook.
- Enforced per-command contracts via `config.yaml`.
- Implemented `dedup: true` parameter for `list_strategy` to fix `docker logs` seed.
- Support for `clipress error-passthrough` command to easily toggle pass-through behaviour.
- Allowed user extensions (`.compressor/extensions/*.yaml`) to override built-in seeds.
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
