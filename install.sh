#!/usr/bin/env bash

set -euo pipefail

REPO="https://github.com/0xH4KU/bilimanga-downloader.git"
INSTALL_DIR="${BILIMANGA_INSTALL_DIR:-$HOME/.local/share/bilimanga-dl}"
BIN_DIR="${BILIMANGA_BIN_DIR:-$HOME/.local/bin}"
VENV_DIR="$INSTALL_DIR/.venv"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_DIR/bilimanga-dl" "$BIN_DIR/bilimanga-dl-uninstall"
    echo "Uninstalled bilimanga-dl. Config at ~/.config/bilimanga-dl/ was preserved."
    exit 0
fi

find_python() {
    for cmd in python3.14 python3.13 python3.12 python3.11 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            "$cmd" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1 && {
                echo "$cmd"
                return 0
            }
        fi
    done
    return 1
}

PYTHON_CMD="$(find_python)" || {
    echo "Python >= 3.11 is required." >&2
    exit 1
}

command -v git >/dev/null 2>&1 || {
    echo "git is required." >&2
    exit 1
}

mkdir -p "$BIN_DIR"
if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" pull --ff-only
else
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO" "$INSTALL_DIR"
fi

"$PYTHON_CMD" -m venv "$VENV_DIR" --clear
"$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
"$VENV_DIR/bin/pip" install -e "$INSTALL_DIR"
"$VENV_DIR/bin/python" -m playwright install chromium

cat > "$BIN_DIR/bilimanga-dl" << WRAPPER
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python" -m bilimanga_dl "\$@"
WRAPPER
chmod +x "$BIN_DIR/bilimanga-dl"

cat > "$BIN_DIR/bilimanga-dl-uninstall" << UNINSTALL
#!/usr/bin/env bash
rm -rf "$INSTALL_DIR"
rm -f "$BIN_DIR/bilimanga-dl" "$BIN_DIR/bilimanga-dl-uninstall"
echo "Uninstalled bilimanga-dl. Config at ~/.config/bilimanga-dl/ was preserved."
UNINSTALL
chmod +x "$BIN_DIR/bilimanga-dl-uninstall"

echo "Installed bilimanga-dl to $INSTALL_DIR"
echo "Command: $BIN_DIR/bilimanga-dl"
echo "Run: bilimanga-dl doctor"
