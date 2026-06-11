#!/usr/bin/env bash
# local-ai-env one-line installer (Linux / macOS)
#   curl -fsSL https://raw.githubusercontent.com/DevEpoch/lai/main/install.sh | bash
# Override: LAI_REPO=https://github.com/DevEpoch/lai LAI_DIR=~/ai bash install.sh
set -euo pipefail

REPO="${LAI_REPO:-https://github.com/DevEpoch/lai}"
DEST="${LAI_DIR:-$HOME/.local/share/lai}"

echo "local-ai-env installer -> $DEST"

# -- prerequisites: install them instead of just warning ---------------------
pm_install() {  # install packages with whatever package manager exists
    if command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y "$@"
    elif command -v dnf    >/dev/null 2>&1; then sudo dnf install -y "$@"
    elif command -v pacman >/dev/null 2>&1; then sudo pacman -S --noconfirm "$@"
    elif command -v zypper >/dev/null 2>&1; then sudo zypper install -y "$@"
    elif command -v brew   >/dev/null 2>&1; then brew install "$@"
    else
        echo "No known package manager found - install $* manually." >&2
        return 1
    fi
}

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo "Python 3 is not installed. Installing it now..."
    pm_install python3 || exit 1
fi
if ! command -v git >/dev/null 2>&1; then
    echo "Git is not installed (needed for installs and 'lai update'). Installing..."
    pm_install git || true
fi
PY="$(command -v python3 || command -v python)"

# -- fetch / update the program ----------------------------------------------
if [ -f "$DEST/lai.py" ]; then
    echo "Existing install found - updating (git pull)."
    [ -d "$DEST/.git" ] && git -C "$DEST" pull --ff-only
elif command -v git >/dev/null 2>&1; then
    git clone --depth 1 "$REPO" "$DEST"
else
    echo "git not found - downloading tarball instead."
    TMP="$(mktemp -d)"
    mkdir -p "$DEST"
    curl -fsSL "$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP"
    mv "$TMP"/*/* "$DEST"
    rm -rf "$TMP"
fi

[ -f "$DEST/lai.py" ] || { echo "Install failed - lai.py not found." >&2; exit 1; }

chmod +x "$DEST/lai.sh" 2>/dev/null || true
cd "$DEST"
echo
echo "Installed. Checking your hardware:"
echo
"$PY" "$DEST/lai.py" check
"$PY" "$DEST/lai.py" path --yes       # `lai` command in any terminal
"$PY" "$DEST/lai.py" shortcut --yes   # app-menu / Applications launcher

echo
echo "================= lai is installed ================="
echo "  1. Open a NEW terminal."
echo "  2. Type:   lai go        <- sets everything up, then opens the dashboard"
echo
echo "  The dashboard (UI) lives at:  http://localhost:8090"
echo "  Open it anytime with:  lai ui   - or the 'Local AI Env' app launcher."
echo "===================================================="
