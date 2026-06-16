"""The desktop app's Python ↔ JS bridge.

Exposed to the web UI as ``window.pywebview.api.*``. Each method runs on a
pywebview worker thread and its **return value** is delivered back to the JS
promise — so the UI just ``await``s a reply. We deliberately do *not* push
events into the page with ``evaluate_js`` from worker threads: on macOS WKWebView
that path is unreliable. The request/response shape is simpler and robust.
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

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


def _new_turn() -> dict:
    """A fresh in-flight turn buffer for the rich streaming snapshot."""
    return {
        "text": [],
        "thinking": [],
        "steps": [],
        "cost": None,
        "model": None,
        "done": False,
        "ok": False,
    }


def _turn_snapshot(turn: dict | None) -> dict:
    """The poll payload for ``turn`` (or an empty, done payload for ``None``)."""
    if turn is None:
        return {
            "ok": False,
            "done": True,
            "text": "",
            "thinking": "",
            "steps": [],
            "cost": None,
            "model": None,
        }
    return {
        "ok": turn["ok"],
        "done": turn["done"],
        "text": "".join(turn["text"]),
        "thinking": "".join(turn["thinking"]),
        "steps": list(turn["steps"]),
        "cost": turn["cost"],
        "model": turn["model"],
    }


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
        turn = _new_turn()
        with self._lock:
            self._turns[turn_id] = turn
        worker = threading.Thread(
            target=self._run_turn, args=(turn, request), daemon=True
        )
        worker.start()
        return {"ok": True, "id": turn_id}

    def _run_turn(self, turn: dict, request: str) -> None:
        """Drive one streaming turn on a worker thread into ``turn``'s buffer.

        Accumulates the structured event stream — visible text, extended
        thinking, tool activity, the model, and the final cost — so :meth:`poll`
        can render a rich snapshot, not just plain text.
        """

        def on_event(event: dict) -> None:
            kind = event.get("kind")
            with self._lock:
                if kind in ("text", "error"):
                    turn["text"].append(event.get("text", ""))
                elif kind == "thinking":
                    turn["thinking"].append(event.get("text", ""))
                elif kind == "tool":
                    turn["steps"].append(event.get("name", "tool"))
                elif kind == "model":
                    turn["model"] = event.get("model")
                elif kind == "result" and event.get("cost") is not None:
                    turn["cost"] = event.get("cost")

        try:
            code = _runner.stream_events(
                request,
                self._pack_provider(),
                on_event=on_event,
                profile=self._profile_provider(),
            )
            ok = code == 0
        except Exception as exc:  # never let a worker thread die silently
            with self._lock:
                turn["text"].append(f"Error: {exc}")
            ok = False
        with self._lock:
            turn["ok"] = ok
            turn["done"] = True

    def poll(self, turn_id: str) -> dict:
        """Return the rich snapshot of ``turn_id`` accumulated so far.

        ``{"ok", "done", "text", "thinking", "steps", "cost", "model"}``. When
        ``done`` is true the turn has finished and is forgotten after this call,
        so poll until ``done`` then stop.
        """
        with self._lock:
            turn = self._turns.get(turn_id)
            if turn is None:
                return _turn_snapshot(None)
            snapshot = _turn_snapshot(turn)
            if turn["done"]:
                self._turns.pop(turn_id, None)
        return snapshot

    # --- persisted GUI chats (survive a restart) ---

    def _chats_dir(self) -> Path:
        return _packs.home() / "app" / "chats"

    @staticmethod
    def _safe_id(chat_id: str) -> str:
        kept = "".join(ch for ch in str(chat_id) if ch.isalnum() or ch in "-_")
        return kept or "chat"

    def persist_chat(self, chat_id: str, chat: dict) -> dict:
        """Write a chat snapshot to disk. ``chat`` carries title/messages/cost."""
        chat = chat or {}
        try:
            directory = self._chats_dir()
            directory.mkdir(parents=True, exist_ok=True)
            doc = {
                "id": str(chat_id),
                "title": str(chat.get("title") or "Chat"),
                "messages": chat.get("messages") or [],
                "cost": chat.get("cost"),
                "updated": time.time(),
            }
            (directory / f"{self._safe_id(chat_id)}.json").write_text(json.dumps(doc))
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def list_app_chats(self) -> list[dict]:
        """Stored chats, newest first (max 25), as lightweight index rows."""
        directory = self._chats_dir()
        if not directory.is_dir():
            return []
        rows: list[dict] = []
        for path in directory.glob("*.json"):
            try:
                doc = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            messages = doc.get("messages") or []
            rows.append(
                {
                    "id": doc.get("id") or path.stem,
                    "title": doc.get("title") or "Chat",
                    "updated": doc.get("updated") or 0,
                    "turns": sum(1 for m in messages if m.get("role") == "user"),
                    "cost": doc.get("cost"),
                }
            )
        rows.sort(key=lambda row: row["updated"], reverse=True)
        return rows[:25]

    def load_app_chat(self, chat_id: str) -> dict:
        """The full stored transcript for ``chat_id``, or ``{"error": ...}``."""
        path = self._chats_dir() / f"{self._safe_id(chat_id)}.json"
        if not path.is_file():
            return {"error": "not found"}
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}

    def rename_app_chat(self, chat_id: str, title: str) -> dict:
        """Rename a stored chat in place."""
        doc = self.load_app_chat(chat_id)
        if doc.get("error"):
            return {"ok": False, "error": doc["error"]}
        doc["title"] = str(title or "Chat")
        return self.persist_chat(chat_id, doc)

    def delete_app_chat(self, chat_id: str) -> dict:
        """Delete a stored chat."""
        path = self._chats_dir() / f"{self._safe_id(chat_id)}.json"
        try:
            if path.is_file():
                path.unlink()
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
