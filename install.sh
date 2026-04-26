#!/usr/bin/env bash
set -euo pipefail

echo "Installing clipress..."

# Check Python 3.11+
python3 --version | grep -qE "3\.(1[1-9]|[2-9][0-9])" || {
    echo "Error: Python 3.11+ required (found: $(python3 --version 2>&1))"
    exit 1
}

SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

# Determine install source
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    INSTALL_FROM="$SCRIPT_DIR"
else
    INSTALL_FROM="git+https://github.com/0xkhdr/clipress.git"
fi

# Prefer pipx (isolated), fall back to pip
if command -v pipx &>/dev/null; then
    pipx install --force "$INSTALL_FROM"
    INSTALL_METHOD="pipx"
elif command -v pip &>/dev/null; then
    pip install --force-reinstall "$INSTALL_FROM"
    INSTALL_METHOD="pip"
else
    echo "Error: pip or pipx required."
    exit 1
fi

echo ""
echo "clipress installed successfully."

# Ensure ~/.local/bin is in PATH for the current session
USER_BIN="$HOME/.local/bin"
if [[ -d "$USER_BIN" && ":$PATH:" != *":$USER_BIN:"* ]]; then
    export PATH="$USER_BIN:$PATH"
fi

# Small delay to ensure shell wrappers are written
sleep 1

# Determine init target: git root if available, otherwise CWD
INIT_TARGET=""
if command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null; then
    INIT_TARGET="$(git rev-parse --show-toplevel)"
    echo "Detected git repository root: $INIT_TARGET"
else
    INIT_TARGET="$(pwd)"
    echo "No git repository detected — initializing in current directory."
fi

# Try to run clipress init. Prefer the binary, fallback to python module.
CLIPRESS_INIT_CMD=""
if command -v clipress &>/dev/null; then
    CLIPRESS_INIT_CMD="clipress init"
elif python3 -m clipress --help &>/dev/null; then
    CLIPRESS_INIT_CMD="python3 -m clipress init"
fi

if [[ -n "$CLIPRESS_INIT_CMD" ]]; then
    (
        cd "$INIT_TARGET"
        echo "Initializing clipress in $(pwd)..."
        eval "$CLIPRESS_INIT_CMD"
    )
    echo ""
    echo "Done! clipress is active."
    echo "  clipress status    — workspace stats"
    echo "  clipress report    — full session report"
    echo "  clipress run <cmd> — run interactive commands with PTY support"
    echo "  clipress uninstall — remove clipress"
else
    echo ""
    echo "WARNING: 'clipress' command not found in PATH."
    echo "If you installed with pip, you may need to add the following to your shell profile:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "Then run 'clipress init' inside your project directory to activate hooks."
fi
