#!/usr/bin/env bash
# Linux/macOS wrapper for lai.py - usage: ./lai.sh <command>
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
    exec python3 "$DIR/lai.py" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$DIR/lai.py" "$@"
else
    echo "Python 3.9+ not found. Install it with: sudo apt install -y python3 python3-pip" >&2
    exit 1
fi
