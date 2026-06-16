"""The desktop app's Python ↔ JS bridge.

Exposed to the web UI as ``window.pywebview.api.*``. Each method runs on a
pywebview worker thread and its **return value** is delivered back to the JS
promise — so the UI just ``await``s a reply. We deliberately do *not* push
events into the page with ``evaluate_js`` from worker threads: on macOS WKWebView
that path is unreliable. The request/response shape is simpler and robust.
"""

from __future__ import annotations

import itertools
import threading
from collections.abc import Callable

from pennyworth import packs as _packs
from pennyworth import profile as _profile
from pennyworth import runner as _runner
from pennyworth.pack import Pack
from pennyworth.profile import Profile


def _compose(messages: list[dict]) -> str:
    """Fold a chat transcript into a single request for a one-shot agent.

    ``messages`` is the chat so far, oldest first, each ``{"role", "text"}`` with
    role ``"user"`` or ``"alfred"``; the last entry is the new user turn. With
    only that one turn, the request is just its text. Earlier turns are included
    as context so the conversation has memory across turns.
    """
    if not messages:
        return ""
    latest = str(messages[-1].get("text", ""))
    prior = messages[:-1]
    if not prior:
        return latest
    lines = ["Conversation so far (oldest first):"]
    for message in prior:
        who = "User" if message.get("role") == "user" else "Alfred"
        lines.append(f"{who}: {message.get('text', '')}")
    lines += ["", "Now respond, in character, to the user's latest message:", latest]
    return "\n".join(lines)


class Bridge:
    """The js_api object for the web UI.

    Args:
        pack_provider: Returns the active pack (defaults to the installed
            store's active pack). Injectable for tests.
    """

    def __init__(
        self,
        pack_provider: Callable[[], Pack] = _packs.active_pack,
        profile_provider: Callable[[], Profile] = _profile.active_profile,
    ) -> None:
        self._pack_provider = pack_provider
        self._profile_provider = profile_provider
        # In-flight streaming turns, keyed by id. Each is the mutable buffer a
        # worker thread appends to and ``poll`` reads from, under ``_lock``.
        self._turns: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    # --- methods callable from JS via window.pywebview.api.* ---

    def get_state(self) -> dict:
        """Initial app state for the UI."""
        pack = self._pack_provider()
        return {
            "app": "Pennyworth",
            "assistant": "Alfred",
            "pack": pack.name or None,
        }

    def ask(self, messages: list[dict]) -> dict:
        """Run one turn for a chat transcript and return the full reply.

        Blocks on the worker thread until the host agent finishes; the window
        stays responsive. Returns ``{"ok": bool, "text": str}``.
        """
        request = _compose(messages or [])
        if not request:
            return {"ok": False, "text": "(nothing to ask)"}
        chunks: list[str] = []
        try:
            code = _runner.stream(
                request,
                self._pack_provider(),
                on_chunk=chunks.append,
                profile=self._profile_provider(),
            )
        except Exception as exc:  # surface any failure to the UI, don't crash
            return {"ok": False, "text": f"Error: {exc}"}
        reply = "".join(chunks).strip()
        return {"ok": code == 0, "text": reply or "(the agent produced no output)"}

    def start(self, messages: list[dict]) -> dict:
        """Begin a streaming turn; returns ``{"ok", "id"}``.

        The agent runs on a background thread, accumulating its reply into a
        server-side buffer. The UI calls :meth:`poll` to render the reply as it
        grows — request/response only, never a cross-thread event push.
        """
        request = _compose(messages or [])
        if not request:
            return {"ok": False, "id": None}
        turn_id = f"t{next(self._ids)}"
        turn = {"chunks": [], "done": False, "ok": False}
        with self._lock:
            self._turns[turn_id] = turn
        worker = threading.Thread(
            target=self._run_turn, args=(turn, request), daemon=True
        )
        worker.start()
        return {"ok": True, "id": turn_id}

    def _run_turn(self, turn: dict, request: str) -> None:
        """Drive one streaming turn on a worker thread into ``turn``'s buffer."""

        def on_chunk(text: str) -> None:
            with self._lock:
                turn["chunks"].append(text)

        try:
            code = _runner.stream(
                request,
                self._pack_provider(),
                on_chunk=on_chunk,
                profile=self._profile_provider(),
            )
            ok = code == 0
        except Exception as exc:  # never let a worker thread die silently
            with self._lock:
                turn["chunks"].append(f"Error: {exc}")
            ok = False
        with self._lock:
            turn["ok"] = ok
            turn["done"] = True

    def poll(self, turn_id: str) -> dict:
        """Return the reply accumulated so far for ``turn_id``.

        ``{"ok", "done", "text"}``. When ``done`` is true the turn has finished
        and is forgotten after this call, so poll until ``done`` then stop.
        """
        with self._lock:
            turn = self._turns.get(turn_id)
            if turn is None:
                return {"ok": False, "done": True, "text": ""}
            text = "".join(turn["chunks"])
            done = turn["done"]
            ok = turn["ok"]
            if done:
                self._turns.pop(turn_id, None)
        return {"ok": ok, "done": done, "text": text}
