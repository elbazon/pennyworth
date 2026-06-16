"""The desktop app's Python ↔ JS bridge.

Exposed to the web UI as ``window.pywebview.api.*``. The window owns emission of
events back to the page; the bridge calls an injected ``emit`` for every event,
so the whole turn lifecycle can be unit-tested without a real window.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from pennyworth import packs as _packs
from pennyworth import runner as _runner
from pennyworth.pack import Pack


class Bridge:
    """The js_api object for the web UI.

    Args:
        emit: Called with each event dict to deliver to the page.
        pack_provider: Returns the active pack (defaults to the installed
            store's active pack). Injectable for tests.
    """

    def __init__(
        self,
        emit: Callable[[dict], None],
        pack_provider: Callable[[], Pack] = _packs.active_pack,
    ) -> None:
        self._emit = emit
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

    def send_message(self, chat_id: str, text: str) -> None:
        """Start a turn on a daemon thread; reply streams back as events."""
        threading.Thread(
            target=self._run_turn, args=(chat_id, text), daemon=True
        ).start()

    # --- internals ---

    def _run_turn(self, chat_id: str, text: str) -> None:
        self._emit({"type": "start", "chat_id": chat_id})
        try:
            code = _runner.stream(
                text,
                self._pack_provider(),
                on_chunk=lambda chunk: self._emit(
                    {"type": "chunk", "chat_id": chat_id, "text": chunk}
                ),
            )
        except Exception as exc:  # never let a worker thread die silently
            self._emit({"type": "error", "chat_id": chat_id, "text": str(exc)})
            code = 1
        self._emit({"type": "end", "chat_id": chat_id, "code": code})
