#!/usr/bin/env bash
# local-ai-env one-line installer (Linux / macOS)
#   curl -fsSL https://raw.githubusercontent.com/DevEpoch/lai/main/install.sh | bash
# Override: LAI_REPO=https://github.com/DevEpoch/lai LAI_DIR=~/ai bash install.sh
set -euo pipefail

REPO="${LAI_REPO:-https://github.com/DevEpoch/lai}"
DEST="${LAI_DIR:-$HOME/lai}"

echo "local-ai-env installer -> $DEST"

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
    echo "Python 3.9+ is required. Install it first:" >&2
    echo "    sudo apt install -y python3   |   brew install python" >&2
    exit 1
fi

if [ -f "$DEST/lai.py" ]; then
    echo "Existing install found - updating (git pull)."
    [ -d "$DEST/.git" ] && git -C "$DEST" pull --ff-only
elif command -v git >/dev/null 2>&1; then
    git clone --depth 1 "$REPO" "$DEST"
else
    echo "git not found - downloading tarball instead."
    TMP="$(mktemp -d)"
    curl -fsSL "$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP"
    mv "$TMP"/* "$DEST"
    rm -rf "$TMP"
fi

[ -f "$DEST/lai.py" ] || { echo "Install failed - lai.py not found." >&2; exit 1; }

chmod +x "$DEST/lai.sh" 2>/dev/null || true
cd "$DEST"
echo
echo "Installed. Checking your hardware:"
echo
"$PY" "$DEST/lai.py" check
"$PY" "$DEST/lai.py" shortcut --yes   # app-menu / Applications launcher
echo
echo "Next:  cd $DEST && ./lai.sh setup   (or launch 'Local AI Env' from the app menu)"
