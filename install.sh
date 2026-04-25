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

# Prefer local source install if running from the repo
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    if command -v pipx &>/dev/null; then
        pipx install --force "$SCRIPT_DIR"
    elif command -v pip &>/dev/null; then
        pip install "$SCRIPT_DIR"
    else
        echo "Error: pip or pipx required."
        exit 1
    fi
else
    # Install directly from GitHub
    GITHUB_URL="https://github.com/0xkhdr/clipress"
    if command -v pipx &>/dev/null; then
        pipx install "git+${GITHUB_URL}.git"
    elif command -v pip &>/dev/null; then
        pip install "git+${GITHUB_URL}.git"
    else
        echo "Error: pip or pipx required."
        exit 1
    fi
fi

echo ""
echo "clipress installed successfully."

# Auto-initialize in the current directory so zero additional steps are needed.
if command -v clipress &>/dev/null; then
    echo "Initializing clipress in $(pwd)..."
    clipress init
    echo ""
    echo "Done! clipress is active. Run any command — token savings will appear in stderr."
    echo "  clipress status    — workspace stats"
    echo "  clipress report    — full session report"
    echo "  clipress run <cmd> — run interactive commands with PTY support"
    echo "  clipress uninstall — remove clipress"
else
    echo ""
    echo "NOTE: 'clipress' not found in PATH. You may need to:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo "Then run 'clipress init' inside your project directory to activate hooks."
fi
