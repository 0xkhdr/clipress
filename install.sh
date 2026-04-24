#!/usr/bin/env bash
set -euo pipefail

echo "Installing clipress..."

# Check Python 3.11+
python3 --version | grep -E "3\.(1[1-9]|[2-9][0-9])" > /dev/null || {
    echo "Error: Python 3.11+ required"
    exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Prefer local source install if running from the repo
if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    if command -v pipx &>/dev/null; then
        pipx install "$SCRIPT_DIR"
    elif command -v pip &>/dev/null; then
        pip install "$SCRIPT_DIR"
    else
        echo "Error: pip or pipx required."
        exit 1
    fi
else
    # Fallback to PyPI (requires package publication)
    if command -v pipx &>/dev/null; then
        pipx install clipress
    elif command -v pip &>/dev/null; then
        pip install clipress
    else
        echo "Error: pip or pipx required."
        exit 1
    fi
fi

# Initialize in current directory
clipress init

echo "Done. clipress is active for this project."
echo "Run 'clipress status' to verify."
