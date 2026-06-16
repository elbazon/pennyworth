"""Launch the Pennyworth desktop app (Alfred) in a native window.

A thin pywebview shell. ``pywebview`` is imported lazily inside :func:`main` so
the package (and the CLI) work without the optional ``app`` extra installed.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

WINDOW_TITLE = "Alfred"
BACKGROUND = "#262624"


def _web_dir() -> Path:
    return Path(__file__).parent / "web"


def index_path() -> Path:
    """Absolute path to the bundled single-page UI."""
    return _web_dir() / "index.html"


def window_config() -> dict:
    """pywebview ``create_window`` kwargs. Pure, so it can be tested without a GUI."""
    return {
        "title": WINDOW_TITLE,
        "url": str(index_path()),
        "width": 1040,
        "height": 720,
        "min_size": (640, 480),
        "background_color": BACKGROUND,
    }


def main() -> int:
    """Open the desktop window. Blocks until the window is closed."""
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

    holder: dict = {}
    emit_lock = threading.Lock()

    def emit(event: dict) -> None:
        window = holder.get("window")
        if window is None:
            return
        payload = json.dumps(event)
        # Serialise evaluate_js calls: concurrent ones from worker threads stall.
        with emit_lock:
            window.evaluate_js(f"window.alfredEvent({json.dumps(payload)})")

    bridge = Bridge(emit=emit)
    holder["window"] = webview.create_window(js_api=bridge, **window_config())
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
