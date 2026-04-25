#!/usr/bin/env bash
set -euo pipefail

echo "Installing clipress..."

# Check Python 3.11+
python3 --version | grep -E "3\.(1[1-9]|[2-9][0-9])" > /dev/null || {
    echo "Error: Python 3.11+ required"
    exit 1
}

SCRIPT_DIR=""
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

# Prefer local source install if running from the repo
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    if command -v pipx &>/dev/null; then
        pipx install "$SCRIPT_DIR"
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

echo "Done. Run 'clipress init' inside your project directory to set it up."
