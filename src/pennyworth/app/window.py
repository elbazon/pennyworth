"""Launch the Pennyworth desktop app (Alfred) in a native window.

A thin pywebview shell. ``pywebview`` is imported lazily inside :func:`main` so
the package (and the CLI) work without the optional ``app`` extra installed.
The web UI talks to :class:`~pennyworth.app.bridge.Bridge` via ``js_api`` and
awaits each method's return value — no cross-thread event pushing.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

WINDOW_TITLE = "Alfred"
BACKGROUND = "#262624"


def _web_dir() -> Path:
    return Path(__file__).parent / "web"


def index_path() -> Path:
    """Absolute path to the bundled single-page UI."""
    return _web_dir() / "index.html"


def portrait_path() -> Path:
    """Absolute path to Alfred's portrait."""
    return _web_dir() / "alfred.png"


def _portrait_data_uri() -> str:
    """Alfred's portrait as an inline data URI, or ``""`` if missing.

    Inlined so the self-contained ``html=`` page can show it without an
    external asset URL.
    """
    png = portrait_path()
    if not png.is_file():
        return ""
    encoded = base64.b64encode(png.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_html() -> str:
    """The UI markup with Alfred's portrait inlined (``{{PORTRAIT}}`` replaced)."""
    return index_path().read_text().replace("{{PORTRAIT}}", _portrait_data_uri())


def window_config() -> dict:
    """pywebview ``create_window`` kwargs (excluding the page content itself).

    Pure, so it can be tested without a GUI.
    """
    return {
        "title": WINDOW_TITLE,
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

    if not index_path().is_file():
        print(f"UI asset missing: {index_path()}", file=sys.stderr)
        return 1

    # The page is fully self-contained (all CSS/JS inline, portrait inlined as a
    # data URI), so load its markup directly rather than via a file URL.
    webview.create_window(html=render_html(), js_api=Bridge(), **window_config())
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
