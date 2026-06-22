"""macOS .app bundle installer for Pennyworth.

Creates ``Pennyworth.app`` in ``~/Applications`` (or a custom path) that
launches ``pennyworth app`` when double-clicked.  No py2app or additional
tools required — the bundle is hand-assembled from a shell launcher and a
minimal ``Info.plist``, with a proper .icns icon built from ``logo.png``.

The bundle layout::

    Pennyworth.app/
      Contents/
        Info.plist
        MacOS/
          pennyworth      ← shell launcher that exec's 'pennyworth app'
        Resources/
          pennyworth.icns ← icon built from logo.png via sips + iconutil

Use ``install_app_bundle()`` from Python, or invoke via the CLI:
``pennyworth app --install-shortcut``.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

BUNDLE_NAME = "Pennyworth"
BUNDLE_ID = "io.pennyworth.app"
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
  <string>pennyworth</string>
  <key>CFBundleIconFile</key>
  <string>pennyworth</string>
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
# Pennyworth .app launcher
# Finds the 'pennyworth' binary on PATH (or in common install locations).
# Set PENNYWORTH_BIN to override.

PENNYWORTH_BIN="${{PENNYWORTH_BIN:-}}"

if [ -z "$PENNYWORTH_BIN" ]; then
  for candidate in \
      "$HOME/.local/bin/pennyworth" \
      "$HOME/.pipx/venvs/pennyworth/bin/pennyworth" \
      "/usr/local/bin/pennyworth" \
      "/opt/homebrew/bin/pennyworth"; do
    if [ -x "$candidate" ]; then
      PENNYWORTH_BIN="$candidate"
      break
    fi
  done
fi

if [ -z "$PENNYWORTH_BIN" ]; then
  PENNYWORTH_BIN="$(command -v pennyworth 2>/dev/null)"
fi

if [ -z "$PENNYWORTH_BIN" ]; then
  osascript -e 'display dialog "Pennyworth not found. Install it first:\\n\\n  pipx install \\"pennyworth[app]\\"" buttons {"OK"} default button 1 with title "Pennyworth"'
  exit 1
fi

exec "$PENNYWORTH_BIN" app
"""


def _build_icns(png: Path, dest: Path) -> bool:
    """Convert ``png`` to an ``.icns`` file at ``dest`` using sips + iconutil.

    Returns True on success, False if the tools are unavailable (non-fatal —
    macOS will fall back to the PNG).
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            iconset = Path(tmp) / "Pennyworth.iconset"
            iconset.mkdir()
            for size in (16, 32, 128, 256, 512):
                subprocess.run(
                    [
                        "sips",
                        "-z",
                        str(size),
                        str(size),
                        str(png),
                        "--out",
                        str(iconset / f"icon_{size}x{size}.png"),
                    ],
                    check=True,
                    capture_output=True,
                )
            for label, px in ((16, 32), (32, 64), (128, 256), (256, 512)):
                subprocess.run(
                    [
                        "sips",
                        "-z",
                        str(px),
                        str(px),
                        str(png),
                        "--out",
                        str(iconset / f"icon_{label}x{label}@2x.png"),
                    ],
                    check=True,
                    capture_output=True,
                )
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset), "-o", str(dest)],
                check=True,
                capture_output=True,
            )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_app_bundle(dest_dir: Path | None = None) -> Path:
    """Build and install ``Pennyworth.app`` under ``dest_dir``.

    ``dest_dir`` defaults to ``~/Applications`` (created if absent).
    Returns the path to the installed ``.app`` bundle.
    """
    if sys.platform != "darwin":
        raise RuntimeError("macOS .app bundles are only supported on macOS")

    dest_dir = dest_dir or (Path.home() / "Applications")
    dest_dir.mkdir(parents=True, exist_ok=True)

    app = dest_dir / f"{BUNDLE_NAME}.app"
    if app.exists():
        shutil.rmtree(app)

    contents = app / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"

    for d in (macos_dir, resources_dir):
        d.mkdir(parents=True, exist_ok=True)

    (contents / "Info.plist").write_text(
        _PLIST_TEMPLATE.format(
            name=BUNDLE_NAME,
            bundle_id=BUNDLE_ID,
            version=BUNDLE_VERSION,
        )
    )

    launcher = macos_dir / "pennyworth"
    launcher.write_text(_LAUNCHER_TEMPLATE)
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    from pennyworth.app.window import portrait_path

    portrait = portrait_path()
    if portrait.is_file():
        icns = resources_dir / "pennyworth.icns"
        if not _build_icns(portrait, icns):
            shutil.copy2(portrait, resources_dir / "pennyworth.png")

    app.touch()
    _dock_app(app)
    return app


def _dock_app(app_path: Path) -> None:
    """Add ``app_path`` to the macOS Dock (persistent-apps). Best-effort."""
    import subprocess

    tile = (
        "<dict><key>tile-data</key><dict>"
        "<key>file-data</key><dict>"
        f"<key>_CFURLString</key><string>{str(app_path)}</string>"
        "<key>_CFURLStringType</key><integer>0</integer>"
        "</dict></dict></dict>"
    )
    try:
        subprocess.run(
            [
                "defaults",
                "write",
                "com.apple.dock",
                "persistent-apps",
                "-array-add",
                tile,
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(["killall", "Dock"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass


def remove_app_bundle(dest_dir: Path | None = None) -> bool:
    """Remove ``Pennyworth.app`` from ``dest_dir`` (default: ``~/Applications``).

    Returns ``True`` if the bundle existed and was removed.
    """
    dest_dir = dest_dir or (Path.home() / "Applications")
    app = dest_dir / f"{BUNDLE_NAME}.app"
    if not app.exists():
        return False
    shutil.rmtree(app)
    return True
