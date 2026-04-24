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

# Helper function for shell-based agents. NOT an auto-interceptor — call it explicitly:
#   output=$(some_command)
#   clipress_compress "some_command" "$output"
# Or pipe directly: `some_command | clipress compress "some_command"`.
clipress_compress() {
    local cmd="$1"
    local output="$2"
    echo "$output" | clipress compress "$cmd" --workspace "$CLIPRESS_WORKSPACE"
}
