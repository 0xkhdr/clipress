# Changelog

## [1.1.0] - 2026-04-24
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
