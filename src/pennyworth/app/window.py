"""Launch the Pennyworth desktop app (Alfred) in a native window.

A pywebview shell. ``pywebview`` is imported lazily inside :func:`main` so the
package (and the CLI) work without the optional ``app`` extra installed.

The web UI is the full single-page app under ``web/``. It is loaded by **file
URL** (not an inline ``html=`` string) so its relative assets — ``xterm.js``,
``xterm.css``, the avatar — resolve against the same directory. The page talks
to :class:`~pennyworth.app.bridge.Bridge` two ways: it ``await``s each
``window.pywebview.api.*`` call, and the bridge pushes streaming events back
into the page via ``window.evaluate_js("window.alfredEvent(...)")`` once
:meth:`Bridge.attach_window` has wired the live window in.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

WINDOW_TITLE = "Alfred"
BACKGROUND = "#262624"


def _purge_webkit_cache() -> None:
    """Delete WKWebView's on-disk cache before WebKit initializes (macOS).

    WKWebView serves a STALE ``file://`` index.html even across query strings,
    so an upgrade can keep showing the previous UI. Removing the cache dirs
    (which belong to the python bundle id and hold nothing else) while WebKit
    is still asleep forces a fresh load. Best-effort; a no-op off macOS.
    """
    home = Path.home()
    for cache_dir in (
        home / "Library" / "Caches" / "org.python.python" / "WebKit",
        home / "Library" / "Caches" / "com.apple.python" / "WebKit",
        home / "Library" / "WebKit" / "org.python.python",
    ):
        try:
            if cache_dir.exists():
                shutil.rmtree(cache_dir, ignore_errors=True)
        except OSError:
            pass


def _web_dir() -> Path:
    return Path(__file__).parent / "web"


def index_path() -> Path:
    """Absolute path to the bundled single-page UI."""
    return _web_dir() / "index.html"


def portrait_path() -> Path:
    """Absolute path to Alfred's portrait / app avatar."""
    return _web_dir() / "logo.png"


def index_url() -> str:
    """The ``file://``-style URL for the page, with an mtime cache-bust.

    WKWebView caches ``file://`` pages aggressively, so a wheel upgrade could
    otherwise show the previous release's UI. The ``?v=<mtime>`` query busts the
    cache whenever the file content changes. pywebview accepts a bare local path
    here and serves the directory, so relative asset links resolve.
    """
    index = index_path()
    try:
        tag = int(index.stat().st_mtime)
    except OSError:
        tag = 0
    return f"{index}?v={tag}"


def window_config() -> dict:
    """pywebview ``create_window`` kwargs (excluding ``js_api``).

    Pure, so it can be asserted in tests without a GUI. Carries ``url`` (the
    file URL) rather than inline ``html`` — the page loads its own assets.
    """
    return {
        "title": WINDOW_TITLE,
        "url": index_url(),
        "width": 1080,
        "height": 760,
        "min_size": (720, 520),
        "background_color": BACKGROUND,
    }


def _adopt_identity_pre_launch() -> None:
    """Rename the process from "Python" to "Alfred" in the menu bar (macOS).

    A bare python process inherits the interpreter's bundle identity, so the
    app menu and Cmd-Tab say "Python". Rewriting CFBundleName in the live
    bundle info dictionary before NSApplication finishes launching fixes it.
    Best-effort; a no-op without PyObjC or off macOS.
    """
    try:
        from Foundation import NSBundle

        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = "Alfred"
            info["CFBundleDisplayName"] = "Alfred"
            info["CFBundleIdentifier"] = "io.pennyworth.alfred"
    except Exception:
        pass


def _adopt_identity_post_launch() -> None:
    """Set the Dock icon to Alfred's portrait and make Alfred a foreground app.

    pywebview runs this ``webview.start(func=...)`` callback on a worker thread;
    AppKit calls must be marshalled to the main thread. ``setActivationPolicy_(0)``
    (NSApplicationActivationPolicyRegular) makes the terminal-launched process a
    proper foreground app so a single click lands. Best-effort throughout.
    """
    try:
        from PyObjCTools import AppHelper
    except Exception:
        return

    def _on_main() -> None:
        try:
            from AppKit import NSApplication, NSImage
            from Foundation import NSProcessInfo

            app = NSApplication.sharedApplication()
            icon = NSImage.alloc().initWithContentsOfFile_(str(portrait_path()))
            if icon:
                app.setApplicationIconImage_(icon)
            NSProcessInfo.processInfo().setProcessName_("Alfred")
            app.setActivationPolicy_(0)  # Regular: a real foreground app
            app.activateIgnoringOtherApps_(True)
            wins = app.windows()
            if wins:
                wins[0].makeKeyAndOrderFront_(None)
        except Exception:
            pass

    AppHelper.callAfter(_on_main)


def _ensure_shortcut() -> None:
    """Install Pennyworth.app and dock it on first run. Best-effort, silent."""
    if sys.platform != "darwin":
        return
    app_path = Path.home() / "Applications" / "Pennyworth.app"
    if app_path.exists():
        return
    try:
        from pennyworth.app.bundle import install_app_bundle
        install_app_bundle()
    except Exception:
        pass


def main() -> int:
    """Open the desktop window. Blocks until the window is closed."""
    _ensure_shortcut()
    _purge_webkit_cache()
    _adopt_identity_pre_launch()
    try:
        import webview
    except ImportError:
        print(
            "The desktop app needs pywebview. Install it with:\n"
            "    pip install 'pennyworth[app]'",
            file=sys.stderr,
        )
        return 1

    from pennyworth.app.bridge import Bridge

    if not index_path().is_file():
        print(f"UI asset missing: {index_path()}", file=sys.stderr)
        return 1

    bridge = Bridge()
    window = webview.create_window(js_api=bridge, **window_config())
    # Hand the live window to the bridge so it can push streaming events into
    # the page (window.alfredEvent). Must happen before the event loop starts.
    bridge.attach_window(window)
    # Adopt the Alfred dock icon + foreground activation once the GUI is up.
    webview.start(_adopt_identity_post_launch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
