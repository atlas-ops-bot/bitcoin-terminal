#!/usr/bin/env bash
# Bitcoin Terminal - Quick launcher
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Auto-install deps if needed
if ! python3 -c "import textual, rich, dotenv, yaspin" 2>/dev/null; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt
fi

# Launch
exec python3 -m bitcoin_terminal "$@"
