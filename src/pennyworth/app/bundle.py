"""macOS .app bundle installer for Alfred (Pennyworth).

Creates a minimal ``Alfred.app`` in ``~/Applications`` (or a custom path)
that launches ``alfred app`` when double-clicked.  No py2app or additional
tools required — the bundle is hand-assembled from a shell launcher and a
minimal ``Info.plist``.

The bundle layout::

    Alfred.app/
      Contents/
        Info.plist
        MacOS/
          alfred          ← shell launcher that exec's 'alfred app'
        Resources/
          logo.png        ← Pennyworth portrait (copied as the app icon)

Use ``install_app_bundle()`` from Python, or invoke via the CLI:
``alfred app --install``.
"""

from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path

BUNDLE_NAME = "Alfred"
BUNDLE_ID = "io.pennyworth.alfred"
BUNDLE_VERSION = "1"

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>{name}</string>
  <key>CFBundleDisplayName</key>
  <string>{name}</string>
  <key>CFBundleIdentifier</key>
  <string>{bundle_id}</string>
  <key>CFBundleVersion</key>
  <string>{version}</string>
  <key>CFBundleShortVersionString</key>
  <string>{version}</string>
  <key>CFBundleExecutable</key>
  <string>alfred</string>
  <key>CFBundleIconFile</key>
  <string>alfred</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>LSUIElement</key>
  <false/>
</dict>
</plist>
"""

_LAUNCHER_TEMPLATE = """\
#!/bin/sh
# Pennyworth / Alfred .app launcher
# Finds the 'alfred' binary on PATH (or in common install locations) and
# hands off to 'alfred app'.  Edit ALFRED_BIN to override.

ALFRED_BIN="${{ALFRED_BIN:-}}"

if [ -z "$ALFRED_BIN" ]; then
  for candidate in \
      "$HOME/.local/bin/alfred" \
      "$HOME/.pipx/venvs/pennyworth/bin/alfred" \
      "/usr/local/bin/alfred" \
      "/opt/homebrew/bin/alfred"; do
    if [ -x "$candidate" ]; then
      ALFRED_BIN="$candidate"
      break
    fi
  done
fi

if [ -z "$ALFRED_BIN" ]; then
  ALFRED_BIN="$(command -v alfred 2>/dev/null)"
fi

if [ -z "$ALFRED_BIN" ]; then
  osascript -e 'display dialog "Alfred not found. Install Pennyworth first:\\n\\n  pip install pennyworth[app]" buttons {"OK"} default button 1 with title "Alfred"'
  exit 1
fi

exec "$ALFRED_BIN" app
"""


def install_app_bundle(dest_dir: Path | None = None) -> Path:
    """Build and install ``Alfred.app`` under ``dest_dir``.

    ``dest_dir`` defaults to ``~/Applications`` (created if absent).
    Returns the path to the installed ``.app`` bundle.
    """
    if sys.platform != "darwin":
        raise RuntimeError("macOS .app bundles are only supported on macOS")

    dest_dir = dest_dir or (Path.home() / "Applications")
    dest_dir.mkdir(parents=True, exist_ok=True)

    app = dest_dir / f"{BUNDLE_NAME}.app"
    contents = app / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"

    for d in (macos_dir, resources_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Info.plist
    (contents / "Info.plist").write_text(
        _PLIST_TEMPLATE.format(
            name=BUNDLE_NAME,
            bundle_id=BUNDLE_ID,
            version=BUNDLE_VERSION,
        )
    )

    # Shell launcher
    launcher = macos_dir / "alfred"
    launcher.write_text(_LAUNCHER_TEMPLATE)
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Portrait as icon (copy; macOS will use it as a fallback .png icon)
    from pennyworth.app.window import portrait_path

    portrait = portrait_path()
    if portrait.is_file():
        shutil.copy2(portrait, resources_dir / "logo.png")

    return app


def remove_app_bundle(dest_dir: Path | None = None) -> bool:
    """Remove ``Alfred.app`` from ``dest_dir`` (default: ``~/Applications``).

    Returns ``True`` if the bundle existed and was removed, ``False`` if it
    was not found.
    """
    dest_dir = dest_dir or (Path.home() / "Applications")
    app = dest_dir / f"{BUNDLE_NAME}.app"
    if not app.exists():
        return False
    shutil.rmtree(app)
    return True
