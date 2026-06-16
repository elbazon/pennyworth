"""The desktop app's Python ↔ JS bridge.

Exposed to the web UI as ``window.pywebview.api.*``. Each method runs on a
pywebview worker thread and its **return value** is delivered back to the JS
promise — so the UI just ``await``s a reply. We deliberately do *not* push
events into the page with ``evaluate_js`` from worker threads: on macOS WKWebView
that path is unreliable, and the request/response shape is simpler and robust.
"""

from __future__ import annotations

from collections.abc import Callable

from pennyworth import packs as _packs
from pennyworth import runner as _runner
from pennyworth.pack import Pack


class Bridge:
    """The js_api object for the web UI.

    Args:
        pack_provider: Returns the active pack (defaults to the installed
            store's active pack). Injectable for tests.
    """

    def __init__(
        self,
        pack_provider: Callable[[], Pack] = _packs.active_pack,
    ) -> None:
        self._pack_provider = pack_provider

    # --- methods callable from JS via window.pywebview.api.* ---

    def get_state(self) -> dict:
        """Initial app state for the UI."""
        pack = self._pack_provider()
        return {
            "app": "Pennyworth",
            "assistant": "Alfred",
            "pack": pack.name or None,
        }

    def ask(self, text: str) -> dict:
        """Run one turn and return the full reply.

        Blocks on the worker thread until the host agent finishes; the window
        stays responsive. Returns ``{"ok": bool, "text": str}``.
        """
        chunks: list[str] = []
        try:
            code = _runner.stream(
                text, self._pack_provider(), on_chunk=chunks.append
            )
        except Exception as exc:  # surface any failure to the UI, don't crash
            return {"ok": False, "text": f"Error: {exc}"}
        reply = "".join(chunks).strip()
        return {"ok": code == 0, "text": reply or "(the agent produced no output)"}
