#!/usr/bin/env bash
# clipress shell helper
#
# ⚠️  PREFERRED: Use native agent hooks instead of this shell script.
#    Run `clipress init` to register PostToolUse (Claude Code) and
#    AfterTool (Gemini CLI) hooks automatically.  Native hooks have
#    zero shell overhead and cannot break interactive programs.
#
# Source this file ONLY for agents without a native hook system, or
# to call clipress manually from the terminal:
#   source /path/to/project/.clipress/shell_hook.sh
#
# ---------------------------------------------------------------------------

export CLIPRESS_ENABLED="${CLIPRESS_ENABLED:-true}"
export CLIPRESS_WORKSPACE="${CLIPRESS_WORKSPACE:-$(pwd)}"

if [[ "$CLIPRESS_ENABLED" != "true" ]]; then
    return 0
fi

if ! command -v python3 &>/dev/null; then
    return 0
fi

if ! python3 -c "import clipress" &>/dev/null 2>&1; then
    return 0
fi

# ---------------------------------------------------------------------------
# clipress_compress — explicit helper for manual use or scripted agents
# ---------------------------------------------------------------------------
# Usage:
#   some_command | clipress compress "some_command"          # preferred pipe form
#   clipress_compress "some_command" "$(some_command)"       # capture form
#   clipress_compress "some_command" < <(some_command)       # process-substitution form
clipress_compress() {
    local cmd="$1"
    local output="$2"
    if [[ -z "$output" ]]; then
        # stdin form
        clipress compress "$cmd" --workspace "$CLIPRESS_WORKSPACE"
    else
        echo "$output" | clipress compress "$cmd" --workspace "$CLIPRESS_WORKSPACE"
    fi
}
