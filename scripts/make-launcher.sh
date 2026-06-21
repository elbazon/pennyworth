#!/usr/bin/env bash
# Creates ~/Applications/Pennyworth.app — a macOS launcher for `pennyworth app`.
# Run once after `pipx install 'pennyworth[app]'`. Re-run to update.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="Pennyworth"
APP_PATH="$HOME/Applications/${APP_NAME}.app"
ICON_SRC="$REPO_DIR/src/pennyworth/app/web/alfred.png"

echo "Building ${APP_NAME}.app..."

# 1 ── Compile the AppleScript launcher
#      /bin/zsh -lc loads .zshrc / .zprofile so pipx's PATH is available.
mkdir -p "$HOME/Applications"
osacompile -o "$APP_PATH" -e \
  'do shell script "nohup /bin/zsh -lc '"'"'pennyworth app'"'"' >/tmp/pennyworth.log 2>&1 &"'

# 2 ── Build a .icns from the repo's PNG
ICONSET_DIR="$(mktemp -d)/Pennyworth.iconset"
mkdir -p "$ICONSET_DIR"

# Standard macOS iconset sizes
for size in 16 32 128 256 512; do
    sips -z $size $size "$ICON_SRC" \
        --out "$ICONSET_DIR/icon_${size}x${size}.png" > /dev/null
done
# @2x variants (same file, double resolution label)
for pair in "16:32" "32:64" "128:256" "256:512"; do
    label="${pair%%:*}"
    px="${pair##*:}"
    sips -z $px $px "$ICON_SRC" \
        --out "$ICONSET_DIR/icon_${label}x${label}@2x.png" > /dev/null
done

iconutil -c icns "$ICONSET_DIR" \
    -o "$APP_PATH/Contents/Resources/applet.icns"

rm -rf "$(dirname "$ICONSET_DIR")"

# 3 ── Force Finder / Dock to pick up the new icon
touch "$APP_PATH"

echo "Done. Pennyworth.app is at $APP_PATH"
echo "Drag it to your Dock or double-click from Finder to launch."
