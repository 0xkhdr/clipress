#!/usr/bin/env bash
set -euo pipefail

echo "Installing clipress..."

# Check Python 3.11+
python3 --version | grep -E "3\.(1[1-9]|[2-9][0-9])" > /dev/null || {
    echo "Error: Python 3.11+ required"
    exit 1
}

if command -v pipx &> /dev/null; then
    pipx install .
else
    pip install .
fi

# Initialize in current directory
clipress init

echo "Done. clipress is active for this project."
echo "Run 'clipress status' to verify."
