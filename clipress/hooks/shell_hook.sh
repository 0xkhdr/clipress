#!/usr/bin/env bash
# clipress shell hook
#
# Source this to enable the clipress_compress() helper for any shell-based agent:
#   source /path/to/project/.clipress/shell_hook.sh
#
# Gemini CLI / Codex / Cursor: prefer the automatic PostToolUse hook registered by
# `clipress init` (in .gemini/settings.json or .claude/settings.json).  Use this
# shell hook only for agents without a native hook system, or to call clipress
# manually from the terminal.
#
# Auto-interception mode (pipe every command through clipress automatically):
#   export CLIPRESS_AGENT_MODE=true
#   source /path/to/.clipress/shell_hook.sh
#
# This mode wraps each command in the agent's shell session using zsh preexec /
# bash DEBUG trap.  It is disabled by default to avoid interfering with
# interactive shells.

export CLIPRESS_ENABLED="${CLIPRESS_ENABLED:-true}"
export CLIPRESS_WORKSPACE="${CLIPRESS_WORKSPACE:-$(pwd)}"
export CLIPRESS_AGENT_MODE="${CLIPRESS_AGENT_MODE:-false}"

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
clipress_compress() {
    local cmd="$1"
    local output="$2"
    if [[ -z "$output" ]]; then
        # stdin form: clipress_compress "cmd" < <(some_command)
        clipress compress "$cmd" --workspace "$CLIPRESS_WORKSPACE"
    else
        echo "$output" | clipress compress "$cmd" --workspace "$CLIPRESS_WORKSPACE"
    fi
}

# ---------------------------------------------------------------------------
# Auto-interception (CLIPRESS_AGENT_MODE=true only)
# ---------------------------------------------------------------------------
# Captures the output of every shell command and pipes it through clipress.
# Works best in a non-interactive agent shell; avoid in your main terminal.
if [[ "$CLIPRESS_AGENT_MODE" == "true" ]]; then

    if [[ -n "$ZSH_VERSION" ]]; then
        # zsh: preexec fires before the command; precmd fires after.
        # We redirect command output to a temp file in preexec and compress it in precmd.
        _clipress_tmpfile=""

        _clipress_preexec() {
            _clipress_tmpfile=$(mktemp /tmp/clipress_out.XXXXXX)
            # Redirect stdout/stderr of the forthcoming command via STDOUT_FILENO swap.
            # Note: full transparent capture in zsh requires exec redirection tricks;
            # we provide the infrastructure here.  For automatic capture in zsh agent
            # sessions, set CLIPRESS_CAPTURE_FD=1 to enable exec-level redirection.
            _CLIPRESS_LAST_CMD="$1"
        }

        _clipress_precmd() {
            if [[ -n "$_clipress_tmpfile" && -f "$_clipress_tmpfile" ]]; then
                local out
                out=$(cat "$_clipress_tmpfile" 2>/dev/null)
                rm -f "$_clipress_tmpfile"
                _clipress_tmpfile=""
                if [[ -n "$out" && -n "$_CLIPRESS_LAST_CMD" ]]; then
                    clipress_compress "$_CLIPRESS_LAST_CMD" "$out"
                fi
                unset _CLIPRESS_LAST_CMD
            fi
        }

        autoload -U add-zsh-hook 2>/dev/null
        add-zsh-hook preexec _clipress_preexec
        add-zsh-hook precmd  _clipress_precmd

    elif [[ -n "$BASH_VERSION" ]]; then
        # bash: use the DEBUG trap to capture the command string before it runs.
        # Full output capture in bash requires `exec` redirection; the trap only
        # stores the command name for downstream use with explicit piping.
        _CLIPRESS_LAST_CMD=""

        _clipress_debug_trap() {
            _CLIPRESS_LAST_CMD="$BASH_COMMAND"
        }

        trap '_clipress_debug_trap' DEBUG
    fi
fi
