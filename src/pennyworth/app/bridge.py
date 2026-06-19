"""The desktop app's Python ↔ JS bridge (production GUI contract).

Exposed to the web UI as ``window.pywebview.api.*``. The page is **push-based**:
each ``api.method(...)`` returns a value, and the bridge streams a turn's events
into the page by calling ``window.evaluate_js("window.alfredEvent(<json>)")`` —
funnelled through a single emit thread (see :meth:`Bridge.attach_window`).

This is the open-source bridge: the portable methods (chat, terminal, chats,
themes, scheduled, settings, files) run on Pennyworth's clean core; the
platform-coupled ones (batcave, usage, versions, mcp, slash) degrade gracefully
with shape-correct empty results rather than exposing any platform internals.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path

from pennyworth import packs as _packs
from pennyworth import profile as _profile
from pennyworth import runner as _runner
from pennyworth.app.terminal import TermManager
from pennyworth.pack import Pack
from pennyworth.profile import Profile

try:
    from pennyworth.version import __version__ as _VERSION
except Exception:  # version module shape is not guaranteed
    _VERSION = "0.1.0"

# --- vocabularies the picker UIs validate against --------------------------

MODELS = ["auto", "haiku", "sonnet", "opus", "opus[1m]", "fable"]
# Short picker name -> the value handed to the host agent's --model (None = let
# the agent route on its own).
_MODEL_TO_ID = {
    "auto": None,
    "haiku": "haiku",
    "sonnet": "sonnet",
    "opus": "opus",
    "opus[1m]": "opus",
    "fable": "claude-fable-5",
}
PERSONAS = ["architect", "speedster", "mentor", "hunter", "pm", "dexter", "ultron"]
PERSONA_ICONS = {
    "architect": "📐",
    "speedster": "⚡",
    "mentor": "🧭",
    "hunter": "🎯",
    "pm": "📋",
    "dexter": "🧪",
    "ultron": "🤖",
}
EFFORTS = ["low", "medium", "high"]

# Theme colour variables a custom theme may set.
_THEME_VARS = (
    "--bg",
    "--bg-side",
    "--bg-elev",
    "--bg-input",
    "--border",
    "--text",
    "--text-dim",
    "--accent",
    "--accent-soft",
    "--danger",
)

# The settings the panel edits, with defaults. Stored in app/settings.json;
# ``name`` is mirrored to the Pennyworth profile so Alfred's address works.
_SETTING_DEFAULTS = {
    "name": "",
    "email": "",
    "model": "auto",
    "persona": "",
    "mode": "auto",
    "show_thinking": True,
    "caveman": False,
    "notify_on": True,
    "voice": "",
    "max_turns": 40,
    "ui_scale": 1.0,
    "ui_font": "system",
    "ui_theme": "",
}


def _diag(msg: str) -> None:
    """Append an error line to ~/.pennyworth/app/diag.log (best-effort).

    A quiet error channel for the desktop app, whose JS console and worker-thread
    exceptions are otherwise invisible — only failures are logged, so a user can
    share the file when reporting a bug.
    """
    try:
        path = _packs.home() / "app" / "diag.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(f"{time.time():.3f} {msg}\n")
    except Exception:
        pass


def _compose(messages: list[dict]) -> str:
    """Fold a chat transcript into one request for a stateless one-shot agent.

    ``messages`` is oldest-first, each ``{"role", "text"}`` with role ``"user"``
    or ``"alfred"``; the last is the new user turn. Earlier turns are included as
    context so the conversation has memory (the host agent here is stateless).
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


def _git(cwd: str, *args: str) -> str:
    """Run a read-only git command in ``cwd``; return stdout or '' on any error."""
    try:
        out = subprocess.run(
            ["git", "-C", cwd or ".", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


class Bridge:
    """The js_api object for the production web UI."""

    def __init__(
        self,
        pack_provider: Callable[[], Pack] = _packs.active_pack,
        profile_provider: Callable[[], Profile] = _profile.active_profile,
    ) -> None:
        self._pack_provider = pack_provider
        self._profile_provider = profile_provider
        self._lock = threading.Lock()
        self._chats: dict[str, dict] = {}
        self._session_cost = 0.0
        self._focused = True
        self._term_mgr = TermManager()
        # Live pywebview window for server-pushed events; None when headless.
        self._window = None
        self._emit_q = None

    # --- window wiring: server-pushed events -----------------------------

    def attach_window(self, window) -> None:
        """Wire the live pywebview window so the bridge can push events."""
        self._window = window
        self._start_emitter()

    def _start_emitter(self) -> None:
        """Start the single thread that owns every ``evaluate_js`` push.

        pywebview's ``evaluate_js`` blocks the calling thread on a main-thread
        round-trip; with several chats streaming at once, parallel worker
        threads contend on the one window and stall. One FIFO queue means worker
        threads only ``put()`` (instant) while this lone consumer delivers to the
        page one call at a time. Each event carries ``chatId`` so the page routes
        it to the right pane regardless of interleaving.
        """
        if self._emit_q is not None:
            return
        import queue

        self._emit_q = queue.Queue()

        def _drain() -> None:
            while True:
                event = self._emit_q.get()
                window = self._window
                if window is None:
                    continue
                try:
                    window.evaluate_js(f"window.alfredEvent({json.dumps(event)})")
                except Exception as exc:
                    _diag(f"emit failed: {exc!r}")

        threading.Thread(target=_drain, daemon=True, name="alfred-emit").start()

    def diag_js(self, msg: str) -> bool:
        """Receive a JS-side error/log line and record it (bring-up diagnostics)."""
        _diag(str(msg))
        return True

    def _emit(self, event: dict) -> None:
        """Push one event object into the page (no-op without a window)."""
        if self._window is None:
            return
        if self._emit_q is not None:
            self._emit_q.put(event)
            return
        try:
            self._window.evaluate_js(f"window.alfredEvent({json.dumps(event)})")
        except Exception:
            pass

    # --- per-chat state --------------------------------------------------

    def _chat(self, chat_id: str) -> dict:
        """Get or lazily create the mutable state for ``chat_id``."""
        with self._lock:
            chat = self._chats.get(chat_id)
            if chat is None:
                chat = {
                    "messages": [],
                    "model": "auto",
                    "persona": "",
                    "effort": "medium",
                    "cwd": str(Path.cwd()),
                    "cost": 0.0,
                    "thread": None,
                    "interrupt": None,
                    "term_open": False,
                    "session_id": None,
                    "first_turn": True,
                }
                self._chats[chat_id] = chat
            return chat

    def _chat_settings(self, chat: dict) -> dict:
        return {
            "model": chat["model"],
            "persona": chat["persona"],
            "effort": chat["effort"],
        }

    # --- app settings store ----------------------------------------------

    def _app_dir(self) -> Path:
        return _packs.home() / "app"

    def _settings_path(self) -> Path:
        return self._app_dir() / "settings.json"

    def _load_settings(self) -> dict:
        data = dict(_SETTING_DEFAULTS)
        try:
            stored = json.loads(self._settings_path().read_text())
            if isinstance(stored, dict):
                data.update({k: stored[k] for k in stored if k in _SETTING_DEFAULTS})
        except (OSError, ValueError):
            pass
        # Name is canonical on the profile so Alfred's address is consistent.
        prof = self._profile_provider()
        if prof.name:
            data["name"] = prof.name
        return data

    def _settings_payload(self) -> dict:
        return self._load_settings()

    # --- boot: state, settings -------------------------------------------

    def get_state(self) -> dict:
        pack = self._pack_provider()
        prof = self._profile_provider()
        cwd = str(Path.cwd())
        branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
        name = prof.name or ""
        return {
            "version": _VERSION,
            "app": "Pennyworth",
            "assistant": "Alfred",
            "pack": pack.name or None,
            "userName": name,
            "userFirstName": name.split()[0] if name else "",
            "persona": "",
            "personas": list(PERSONAS),
            "personaIcons": dict(PERSONA_ICONS),
            "model": "auto",
            "models": list(MODELS),
            "effort": "medium",
            "efforts": list(EFFORTS),
            "project": Path(cwd).name,
            "branch": branch,
            "sessionCost": self._session_cost,
        }

    def get_settings(self) -> dict:
        return self._settings_payload()

    def set_setting(self, key: str, value) -> dict:
        if key not in _SETTING_DEFAULTS:
            return {"error": f"unknown setting: {key}"}
        if key == "name":
            try:
                _profile.update_profile(name=str(value or ""))
            except ValueError as exc:
                return {"error": str(exc)}
        try:
            current = self._load_settings()
            current[key] = value
            self._app_dir().mkdir(parents=True, exist_ok=True)
            self._settings_path().write_text(json.dumps(current))
        except OSError as exc:
            return {"error": str(exc)}
        return self._settings_payload()

    # --- per-chat selection ----------------------------------------------

    def get_chat_settings(self, chat_id: str) -> dict:
        return self._chat_settings(self._chat(chat_id))

    def set_chat_model(self, chat_id: str, model: str) -> dict:
        if model not in MODELS:
            return {"error": f"unknown model: {model}"}
        chat = self._chat(chat_id)
        chat["model"] = model
        return self._chat_settings(chat)

    def set_chat_persona(self, chat_id: str, persona: str) -> dict:
        persona = persona or ""
        if persona in ("clear", "default"):
            persona = ""
        if persona and persona not in PERSONAS:
            return {"error": f"unknown persona: {persona}"}
        chat = self._chat(chat_id)
        chat["persona"] = persona
        return self._chat_settings(chat)

    def set_chat_effort(self, chat_id: str, effort: str) -> dict:
        if effort not in EFFORTS:
            return {"error": f"unknown effort: {effort}"}
        chat = self._chat(chat_id)
        chat["effort"] = effort
        return self._chat_settings(chat)

    # --- chat working directory ------------------------------------------

    def get_chat_cwd(self, chat_id: str) -> str:
        return self._chat(chat_id)["cwd"]

    def set_chat_cwd(self, chat_id: str, path: str) -> dict:
        p = Path(path or "").expanduser()
        if not p.is_dir():
            return {"error": f"not a directory: {path}"}
        chat = self._chat(chat_id)
        if str(p) != chat["cwd"]:
            chat["session_id"] = None  # a new dir is a new context
        chat["cwd"] = str(p)
        return {"cwd": chat["cwd"]}

    def pick_chat_cwd(self, chat_id: str) -> dict:
        picked = self._folder_dialog()
        if not picked:
            return {"error": "cancelled"}
        return self.set_chat_cwd(chat_id, picked)

    # --- the turn (push streaming) ---------------------------------------

    def send_message(self, chat_id: str, text: str) -> bool:
        """Start a turn for ``text`` in ``chat_id``; stream events via _emit."""
        text = (text or "").strip()
        if not text or not chat_id:
            return False
        chat = self._chat(chat_id)
        if chat.get("term_open"):
            return False
        with self._lock:
            if chat["thread"] is not None and chat["thread"].is_alive():
                return False
            chat["interrupt"] = threading.Event()
            chat["thread"] = threading.Thread(
                target=self._run_turn, args=(chat_id, chat, text), daemon=True
            )
            chat["thread"].start()
        return True

    def _run_turn(self, chat_id: str, chat: dict, request_text: str) -> None:
        """Worker: run one turn, streaming chatId-tagged events to the page."""

        def emit(event: dict) -> None:
            self._emit({"chatId": chat_id, **event})

        chat["messages"].append({"role": "user", "text": request_text})
        request = _compose(chat["messages"])
        model_id = _MODEL_TO_ID.get(chat["model"], None)
        # Hand the agent every configured repo as an extra working directory, so
        # Alfred can read and operate on them rather than treating them as
        # "outside the workspace". The chat's own cwd is passed separately.
        add_dirs = [
            r["path"]
            for r in self._load_extras()
            if r.get("exists") and r["path"] != chat.get("cwd")
        ]
        want_thinking = bool(self._load_settings().get("show_thinking"))
        knowledge = self._knowledge_text()
        reply: list[str] = []
        turn_model = {"id": chat["model"]}
        interrupted = chat.get("interrupt")

        emit({"type": "status", "text": "preparing…"})
        emit(
            {
                "type": "turn_start",
                "model": chat["model"],
                "routedReason": "",
                "effort": chat["effort"],
                "verb": "Pondering",
            }
        )

        def on_event(ev: dict) -> None:
            if interrupted is not None and interrupted.is_set():
                return
            kind = ev.get("kind")
            if kind == "model":
                turn_model["id"] = ev.get("model") or chat["model"]
                # Surface the actually-used model so the UI replaces "auto" with
                # the resolved id (e.g. claude-opus-4-8) for this turn.
                emit({"type": "model", "model": turn_model["id"]})
            elif kind == "text":
                reply.append(ev.get("text", ""))
                emit({"type": "stream", "kind": "text", "text": ev.get("text", "")})
            elif kind == "thinking":
                emit({"type": "stream", "kind": "thinking", "text": ev.get("text", "")})
            elif kind == "tool":
                emit(
                    {
                        "type": "stream",
                        "kind": "tool",
                        "toolName": ev.get("name", "tool"),
                        "name": ev.get("name", "tool"),
                        "toolUseId": ev.get("id", ""),
                    }
                )
            elif kind == "result":
                cost = ev.get("cost")
                if cost:
                    chat["cost"] += cost
                    self._session_cost += cost
                emit({"type": "stream", "kind": "result", "isError": ev.get("error")})

        ok = False
        try:
            code = _runner.stream_events(
                request,
                self._pack_provider(),
                on_event=on_event,
                model=model_id,
                cwd=chat.get("cwd"),
                add_dirs=add_dirs,
                profile=self._profile_provider(),
                extended_thinking=want_thinking,
                extra_knowledge=knowledge,
            )
            ok = code == 0
        except Exception as exc:  # never let a worker thread die silently
            _diag(f"turn error: {exc!r}")
            emit({"type": "error", "text": f"Error: {exc}"})

        full = "".join(reply).strip()
        if full:
            chat["messages"].append({"role": "alfred", "text": full})
        elif ok:
            emit(
                {
                    "type": "error",
                    "text": "No response was produced — the model returned "
                    "nothing. Please try again.",
                }
            )
        emit(
            {
                "type": "usage",
                "inputTokens": 0,
                "outputTokens": 0,
                "contextTokens": 0,
                "cost": None,
                "chatCost": chat["cost"],
                "sessionCost": self._session_cost,
            }
        )
        chat["first_turn"] = False
        was_interrupted = bool(interrupted is not None and interrupted.is_set())
        emit(
            {
                "type": "turn_end",
                "turnCount": sum(1 for m in chat["messages"] if m["role"] == "user"),
                "interrupted": was_interrupted,
                "sessionId": chat.get("session_id"),
            }
        )

    def interrupt(self, chat_id: str) -> bool:
        chat = self._chats.get(chat_id)
        if chat and chat.get("interrupt") is not None:
            chat["interrupt"].set()
        return True

    def close_chat(self, chat_id: str) -> bool:
        self.term_close(chat_id)
        with self._lock:
            self._chats.pop(chat_id, None)
        return True

    def set_app_focused(self, focused: bool) -> bool:
        self._focused = bool(focused)
        return True

    # --- embedded terminal (push) ----------------------------------------

    def term_open(self, chat_id: str, cols: int = 80, rows: int = 24) -> dict:
        chat = self._chat(chat_id)
        result = self._term_mgr.open(chat_id, cols=cols, rows=rows)
        if not result.get("ok"):
            return {"error": result.get("error", "failed to open terminal")}
        chat["term_open"] = True
        if result.get("reused"):
            return {"ok": True, "already": True}
        threading.Thread(target=self._term_pump, args=(chat_id,), daemon=True).start()
        return {"ok": True}

    def _term_pump(self, chat_id: str) -> None:
        """Drain PTY output and push term_output events until the shell exits."""
        while True:
            res = self._term_mgr.read(chat_id)
            if not res.get("ok"):
                break
            output = res.get("output") or ""
            if output:
                data = base64.b64encode(output.encode("utf-8")).decode("ascii")
                self._emit({"type": "term_output", "chatId": chat_id, "data": data})
            if res.get("closed"):
                self._emit({"type": "term_exit", "chatId": chat_id})
                break
            time.sleep(0.05)

    def term_input(self, chat_id: str, data: str) -> bool:
        return bool(self._term_mgr.write(chat_id, data).get("ok"))

    def term_resize(self, chat_id: str, cols: int, rows: int) -> bool:
        return bool(self._term_mgr.resize(chat_id, cols, rows).get("ok"))

    def term_close(self, chat_id: str) -> dict:
        self._term_mgr.close(chat_id)
        chat = self._chats.get(chat_id)
        cwd = chat.get("cwd") if chat else ""
        if chat:
            chat["term_open"] = False
        self._emit(
            {
                "type": "term_closed",
                "chatId": chat_id,
                "cwd": cwd or "",
                "sessionId": chat.get("session_id") if chat else None,
                "cwdChanged": False,
            }
        )
        return {"ok": True}

    # --- links, files, paths ---------------------------------------------

    def open_url(self, url: str) -> dict:
        url = str(url or "")
        if not (url.startswith("http://") or url.startswith("https://")):
            return {"error": "only http(s) urls are opened"}
        try:
            webbrowser.open(url)
            return {"ok": True}
        except Exception as exc:
            return {"error": str(exc)}

    def _open_native(self, path: str) -> bool:
        """Open ``path`` with the OS default handler. True on a launch attempt."""
        try:
            if os.name == "nt":
                os.startfile(path)  # noqa: S606 - Windows default open
            elif os.uname().sysname == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception:
            return False

    def open_path(self, path: str) -> dict:
        p = Path(path or "")
        if not p.exists():
            return {"error": f"not found: {path}"}
        return (
            {"ok": True, "via": "open"}
            if self._open_native(str(p))
            else {"error": "could not open"}
        )

    def open_terminal(self, path: str) -> dict:
        p = Path(path or ".")
        try:
            if os.uname().sysname == "Darwin":
                subprocess.Popen(["open", "-a", "Terminal", str(p)])
                return {"ok": True}
        except Exception as exc:
            return {"error": str(exc)}
        return {"error": "opening a terminal is only wired for macOS"}

    def open_in_editor(self, path: str) -> dict:
        for cmd in ("code", "cursor", "subl"):
            try:
                subprocess.Popen([cmd, str(path)])
                return {"ok": True}
            except OSError:
                continue
        return (
            {"ok": True}
            if self._open_native(str(path))
            else {"error": "no editor found"}
        )

    def focus_path(self, chat_id: str) -> dict:
        try:
            d = self._app_dir() / "focus"
            d.mkdir(parents=True, exist_ok=True)
            return {"path": str(d / f"{self._safe_id(chat_id)}.md")}
        except OSError as exc:
            return {"error": str(exc)}

    # --- native dialogs --------------------------------------------------

    @staticmethod
    def _dialog_kind(webview, which: str):
        """Resolve a dialog type, preferring the new ``FileDialog`` enum.

        pywebview deprecated the module-level ``FOLDER_DIALOG`` / ``OPEN_DIALOG``
        constants in favour of ``webview.FileDialog.FOLDER`` / ``.OPEN``; prefer
        the enum where present, fall back to the constants on older versions.
        """
        fd = getattr(webview, "FileDialog", None)
        if fd is not None and hasattr(fd, which):
            return getattr(fd, which)
        return getattr(webview, "FOLDER_DIALOG" if which == "FOLDER" else "OPEN_DIALOG")

    def _folder_dialog(self) -> str:
        try:
            import webview

            wins = webview.windows
        except (ImportError, AttributeError):
            return ""
        if not wins:
            return ""
        result = wins[0].create_file_dialog(
            dialog_type=self._dialog_kind(webview, "FOLDER")
        )
        return str(result[0]) if result else ""

    def pick_files(self) -> list[str]:
        try:
            import webview

            wins = webview.windows
        except (ImportError, AttributeError):
            return []
        if not wins:
            return []
        result = wins[0].create_file_dialog(
            dialog_type=self._dialog_kind(webview, "OPEN"), allow_multiple=True
        )
        return [str(p) for p in result] if result else []

    def pick_folder(self) -> dict:
        picked = self._folder_dialog()
        return {"path": picked} if picked else {}

    def save_pasted_image(self, b64: str, ext: str = "png") -> str:
        try:
            import tempfile

            raw = base64.b64decode(b64 or "")
            ext = "".join(c for c in (ext or "png") if c.isalnum()) or "png"
            fd, path = tempfile.mkstemp(suffix=f".{ext}", prefix="alfred-paste-")
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw)
            return path
        except Exception:
            return ""

    def read_file_text(self, path: str, max_bytes: int = 524288) -> dict:
        try:
            p = Path(path)
            size = p.stat().st_size
            raw = p.read_bytes()[:max_bytes]
            return {
                "ok": True,
                "name": p.name,
                "content": raw.decode("utf-8", errors="replace"),
                "truncated": size > max_bytes,
            }
        except OSError as exc:
            return {"error": str(exc)}

    # --- work context & diff (generic git, no gh/CI) ---------------------

    def get_work_context(self, force: bool = False, cwd: str = "") -> dict:
        cwd = cwd or str(Path.cwd())
        branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
        if not branch:
            return {"active": False, "cwd": cwd}
        numstat = _git(cwd, "diff", "--numstat")
        files = adds = dels = 0
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                files += 1
                adds += int(parts[0]) if parts[0].isdigit() else 0
                dels += int(parts[1]) if parts[1].isdigit() else 0
        return {
            "active": True,
            "repo": Path(cwd).name,
            "service": Path(cwd).name,
            "branch": branch,
            "files": files,
            "additions": adds,
            "deletions": dels,
            "pr": None,
            "ci": None,
            "cwd": cwd,
        }

    def get_diff(self, cwd: str = "") -> dict:
        cwd = cwd or str(Path.cwd())
        if not _git(cwd, "rev-parse", "--is-inside-work-tree"):
            return {"error": "not a git repository"}
        numstat = _git(cwd, "diff", "--numstat")
        files = []
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                files.append(
                    {
                        "path": parts[2],
                        "add": int(parts[0]) if parts[0].isdigit() else 0,
                        "del": int(parts[1]) if parts[1].isdigit() else 0,
                    }
                )
        return {"files": files, "text": _git(cwd, "diff")[:300000]}

    # --- skills ----------------------------------------------------------

    def list_skills(self) -> list[dict]:
        from pennyworth import skills as _skillmod

        pack = self._pack_provider()
        rows = [
            {
                "name": s.name,
                "description": s.description,
                "source": "core",
                "title": s.name,
                "local": False,
            }
            for s in _skillmod.core_skills()
        ]
        rows += [
            {
                "name": s.name,
                "description": s.description,
                "source": pack.name or "pack",
                "title": s.name,
                "local": False,
            }
            for s in pack.skills
        ]
        return rows

    def delete_local_skill(self, name: str) -> dict:
        return {"error": "the open-source build ships read-only core skills"}

    def release_skill(self, name: str) -> dict:
        return {"error": "skill release is not available in the open-source build"}

    # --- usage stats (Claude session jsonl) ------------------------------

    def get_stats(self, _home: Path | None = None) -> dict:
        import datetime

        projects = (_home or Path.home()) / ".claude" / "projects"
        sessions = messages = in_tokens = out_tokens = 0
        days: set[str] = set()
        for jsonl in projects.glob("**/*.jsonl") if projects.is_dir() else []:
            sessions += 1
            try:
                days.add(datetime.date.fromtimestamp(jsonl.stat().st_mtime).isoformat())
            except OSError:
                pass
            try:
                for raw in jsonl.read_text(errors="replace").splitlines():
                    if not raw.strip():
                        continue
                    try:
                        obj = json.loads(raw)
                    except ValueError:
                        continue
                    t = obj.get("type")
                    if t in ("user", "assistant"):
                        messages += 1
                    if t == "assistant":
                        usage = (
                            (obj.get("message") or {}).get("usage")
                            or obj.get("usage")
                            or {}
                        )
                        in_tokens += int(usage.get("input_tokens") or 0)
                        out_tokens += int(usage.get("output_tokens") or 0)
            except OSError:
                pass
        return {
            "sessions": sessions,
            "messages": messages,
            "input_tokens": in_tokens,
            "output_tokens": out_tokens,
            "total_tokens": in_tokens + out_tokens,
            "active_days": len(days),
        }

    # --- persisted GUI chats ---------------------------------------------

    def _chats_dir(self) -> Path:
        return self._app_dir() / "chats"

    @staticmethod
    def _safe_id(chat_id: str) -> str:
        kept = "".join(ch for ch in str(chat_id) if ch.isalnum() or ch in "-_")
        return kept or "chat"

    def persist_chat(self, chat_id: str, chat: dict) -> dict:
        chat = chat or {}
        try:
            directory = self._chats_dir()
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{self._safe_id(chat_id)}.json"
            pinned = False
            if path.is_file():
                try:
                    pinned = bool(json.loads(path.read_text()).get("pinned"))
                except (OSError, ValueError):
                    pinned = False
            doc = {
                "id": str(chat_id),
                "title": str(chat.get("title") or "Chat"),
                "messages": chat.get("messages") or [],
                "cost": chat.get("cost"),
                "pinned": bool(chat.get("pinned", pinned)),
                "updated": time.time(),
            }
            path.write_text(json.dumps(doc))
            return {"ok": True}
        except OSError as exc:
            return {"error": str(exc)}

    def list_app_chats(self) -> list[dict]:
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
            updated = doc.get("updated") or 0
            rows.append(
                {
                    "id": doc.get("id") or path.stem,
                    "title": doc.get("title") or "Chat",
                    "updated": updated,
                    "age": _humanize_age(updated),
                    "turns": sum(1 for m in messages if m.get("role") == "user"),
                    "cost": doc.get("cost"),
                    "pinned": bool(doc.get("pinned")),
                }
            )
        rows.sort(key=lambda r: (r["pinned"], r["updated"]), reverse=True)
        return rows[:25]

    def load_app_chat(self, chat_id: str) -> dict:
        path = self._chats_dir() / f"{self._safe_id(chat_id)}.json"
        if not path.is_file():
            return {"error": "not found"}
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}

    def rename_app_chat(self, chat_id: str, title: str) -> dict:
        doc = self.load_app_chat(chat_id)
        if doc.get("error"):
            return {"error": doc["error"]}
        doc["title"] = str(title or "Chat")
        ok = self.persist_chat(chat_id, doc)
        return {"ok": True, "title": doc["title"]} if ok.get("ok") else ok

    def delete_app_chat(self, chat_id: str) -> dict:
        path = self._chats_dir() / f"{self._safe_id(chat_id)}.json"
        try:
            if path.is_file():
                path.unlink()
            return {"ok": True}
        except OSError as exc:
            return {"error": str(exc)}

    def pin_app_chat(self, chat_id: str, pinned: bool) -> dict:
        doc = self.load_app_chat(chat_id)
        if doc.get("error"):
            return {"error": doc["error"]}
        doc["pinned"] = bool(pinned)
        ok = self.persist_chat(chat_id, doc)
        return {"ok": True, "pinned": doc["pinned"]} if ok.get("ok") else ok

    # --- custom themes (local JSON) --------------------------------------

    def _themes_dir(self) -> Path:
        return _packs.home() / "themes"

    def list_themes(self) -> list[dict]:
        directory = self._themes_dir()
        if not directory.is_dir():
            return []
        out = []
        for path in directory.glob("*.json"):
            try:
                doc = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            out.append(
                {
                    "id": doc.get("id") or path.stem,
                    "name": doc.get("name") or path.stem,
                    "vars": {
                        k: v
                        for k, v in (doc.get("vars") or {}).items()
                        if k in _THEME_VARS
                    },
                }
            )
        out.sort(key=lambda t: t["name"].lower())
        return out

    def _theme_slug(self, name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
        return slug or "theme"

    def save_theme(self, theme: dict) -> dict:
        theme = theme or {}
        name = str(theme.get("name") or "").strip()
        if not name:
            return {"error": "a theme needs a name"}
        theme_id = theme.get("id") or self._theme_slug(name)
        doc = {
            "id": theme_id,
            "name": name,
            "vars": {
                k: v for k, v in (theme.get("vars") or {}).items() if k in _THEME_VARS
            },
        }
        try:
            d = self._themes_dir()
            d.mkdir(parents=True, exist_ok=True)
            (d / f"{self._safe_id(theme_id)}.json").write_text(json.dumps(doc))
        except OSError as exc:
            return {"error": str(exc)}
        return {"ok": True, "theme": doc, "themes": self.list_themes()}

    def delete_theme(self, theme_id: str) -> dict:
        path = self._themes_dir() / f"{self._safe_id(theme_id)}.json"
        try:
            if path.is_file():
                path.unlink()
        except OSError as exc:
            return {"error": str(exc)}
        return {"ok": True, "themes": self.list_themes()}

    def import_theme(self) -> dict:
        files = self.pick_files()
        if not files:
            return {}
        try:
            doc = json.loads(Path(files[0]).read_text())
        except (OSError, ValueError) as exc:
            return {"error": str(exc)}
        return self.save_theme(doc)

    def export_theme(self, theme_id: str) -> dict:
        path = self._themes_dir() / f"{self._safe_id(theme_id)}.json"
        if not path.is_file():
            return {"error": "not found"}
        self._open_native(str(path.parent))
        return {"ok": True, "path": str(path)}

    def share_theme(self, theme_id: str) -> dict:
        path = self._themes_dir() / f"{self._safe_id(theme_id)}.json"
        if not path.is_file():
            return {"error": "not found"}
        try:
            self._clipboard_set(path.read_text())
            return {"ok": True}
        except Exception as exc:
            return {"error": str(exc)}

    def paste_theme(self) -> dict:
        try:
            doc = json.loads(self._clipboard_get())
        except Exception as exc:
            return {"error": f"clipboard has no theme JSON: {exc}"}
        return self.save_theme(doc)

    def _clipboard_set(self, text: str) -> None:
        if os.uname().sysname == "Darwin":
            subprocess.run(["pbcopy"], input=text, text=True, check=False)

    def _clipboard_get(self) -> str:
        if os.uname().sysname == "Darwin":
            return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
        return ""

    # --- scheduled prompts (local JSON) ----------------------------------

    def _sched_path(self) -> Path:
        return self._app_dir() / "schedule.json"

    def _load_sched(self) -> list[dict]:
        try:
            data = json.loads(self._sched_path().read_text())
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save_sched(self, tasks: list[dict]) -> None:
        self._app_dir().mkdir(parents=True, exist_ok=True)
        self._sched_path().write_text(json.dumps(tasks))

    def list_scheduled(self) -> list[dict]:
        return sorted(self._load_sched(), key=lambda t: t.get("when", 0))

    def add_scheduled(self, prompt: str, when_iso: str) -> dict:
        import datetime
        import uuid

        try:
            when = datetime.datetime.fromisoformat(when_iso).timestamp()
        except ValueError:
            return {"error": f"bad datetime: {when_iso}"}
        task = {
            "id": uuid.uuid4().hex[:10],
            "prompt": str(prompt or ""),
            "when": when,
            "whenIso": when_iso,
            "fired": False,
            "created": time.time(),
        }
        tasks = self._load_sched()
        tasks.append(task)
        try:
            self._save_sched(tasks)
        except OSError as exc:
            return {"error": str(exc)}
        return {"ok": True, "task": task}

    def delete_scheduled(self, task_id: str) -> dict:
        tasks = [t for t in self._load_sched() if t.get("id") != task_id]
        try:
            self._save_sched(tasks)
        except OSError:
            pass
        return {"ok": True}

    # --- repository paths (extra repos only, in the OSS build) ------------

    def get_dir_paths(self) -> dict:
        return {"rows": [], "missing": [], "extras": self._load_extras()}

    def set_dir_path(self, key: str, value: str) -> dict:
        return self.get_dir_paths()

    def pick_dir_path(self, key: str) -> dict:
        return self.get_dir_paths()

    def _extras_path(self) -> Path:
        return self._app_dir() / "repos.json"

    def _load_extras(self) -> list[dict]:
        try:
            data = json.loads(self._extras_path().read_text())
            rows = data if isinstance(data, list) else []
        except (OSError, ValueError):
            rows = []
        return [
            {
                "name": r.get("name", ""),
                "path": r.get("path", ""),
                "exists": Path(r.get("path", "")).is_dir(),
            }
            for r in rows
        ]

    def save_extra_repos(self, rows: list[dict]) -> dict:
        clean = []
        seen = set()
        for r in rows or []:
            path = str(r.get("path") or "").strip()
            if not path or path in seen:
                continue
            seen.add(path)
            clean.append({"name": str(r.get("name") or Path(path).name), "path": path})
        try:
            self._app_dir().mkdir(parents=True, exist_ok=True)
            self._extras_path().write_text(json.dumps(clean))
        except OSError as exc:
            return {"error": str(exc)}
        return self.get_dir_paths()

    # --- domain knowledge (injected into Alfred's prompt at runtime) -----

    def _knowledge_path(self) -> Path:
        return self._app_dir() / "knowledge.json"

    def _load_knowledge(self) -> list[dict]:
        try:
            data = json.loads(self._knowledge_path().read_text())
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save_knowledge(self, entries: list[dict]) -> None:
        self._app_dir().mkdir(parents=True, exist_ok=True)
        self._knowledge_path().write_text(json.dumps(entries, indent=2))

    def _entry_body(self, entry: dict) -> str:
        """The live text of an entry — read fresh from disk for file-backed ones."""
        if entry.get("path"):
            try:
                return Path(entry["path"]).read_text(errors="replace")
            except OSError:
                return ""
        return entry.get("body", "")

    def _knowledge_text(self) -> str:
        """All enabled knowledge entries composed into one prompt section."""
        parts = []
        for e in self._load_knowledge():
            if not e.get("enabled", True):
                continue
            body = self._entry_body(e).strip()
            if body:
                parts.append(f"## {e.get('title') or 'Untitled'}\n{body}")
        return "\n\n".join(parts)

    def list_knowledge(self) -> list[dict]:
        """Knowledge entries (without full bodies) for the panel list."""
        rows = []
        for e in self._load_knowledge():
            body = self._entry_body(e)
            rows.append(
                {
                    "id": e.get("id"),
                    "title": e.get("title") or "Untitled",
                    "enabled": bool(e.get("enabled", True)),
                    "source": "file" if e.get("path") else "inline",
                    "path": e.get("path", ""),
                    "chars": len(body),
                    "preview": body[:160],
                }
            )
        return rows

    def get_knowledge(self, entry_id: str) -> dict:
        for e in self._load_knowledge():
            if e.get("id") == entry_id:
                return {**e, "body": self._entry_body(e)}
        return {"error": "not found"}

    def add_knowledge(self, title: str, body: str = "", path: str = "") -> dict:
        import uuid

        entry = {
            "id": uuid.uuid4().hex[:10],
            "title": str(title or "Untitled").strip(),
            "body": "" if path else str(body or ""),
            "path": str(path or ""),
            "enabled": True,
        }
        entries = self._load_knowledge()
        entries.append(entry)
        try:
            self._save_knowledge(entries)
        except OSError as exc:
            return {"error": str(exc)}
        return {"ok": True, "entry": entry}

    def update_knowledge(
        self,
        entry_id: str,
        title: str | None = None,
        body: str | None = None,
        enabled: bool | None = None,
    ) -> dict:
        entries = self._load_knowledge()
        for e in entries:
            if e.get("id") == entry_id:
                if title is not None:
                    e["title"] = str(title).strip()
                if body is not None and not e.get("path"):
                    e["body"] = str(body)
                if enabled is not None:
                    e["enabled"] = bool(enabled)
                try:
                    self._save_knowledge(entries)
                except OSError as exc:
                    return {"error": str(exc)}
                return {"ok": True, "entry": e}
        return {"error": "not found"}

    def delete_knowledge(self, entry_id: str) -> dict:
        entries = [e for e in self._load_knowledge() if e.get("id") != entry_id]
        try:
            self._save_knowledge(entries)
        except OSError as exc:
            return {"error": str(exc)}
        return {"ok": True}

    def import_knowledge(self, link: bool = False) -> dict:
        """Pick a file and add it as a knowledge entry.

        ``link=True`` keeps it as a live file reference (re-read each turn);
        otherwise the file's text is copied inline at import time.
        """
        files = self.pick_files()
        if not files:
            return {}
        p = Path(files[0])
        if link:
            return self.add_knowledge(p.stem, path=str(p))
        try:
            text = p.read_text(errors="replace")
        except OSError as exc:
            return {"error": str(exc)}
        return self.add_knowledge(p.stem, body=text)

    def export_knowledge(self, entry_id: str) -> dict:
        """Write an entry to a markdown file under the knowledge dir and reveal it."""
        entry = self.get_knowledge(entry_id)
        if entry.get("error"):
            return entry
        try:
            d = self._app_dir() / "knowledge_export"
            d.mkdir(parents=True, exist_ok=True)
            out = d / f"{self._safe_id(entry.get('title') or entry_id)}.md"
            out.write_text(f"# {entry.get('title')}\n\n{self._entry_body(entry)}")
            self._open_native(str(d))
            return {"ok": True, "path": str(out)}
        except OSError as exc:
            return {"error": str(exc)}

    # --- platform-coupled panels: graceful, shape-correct degradation ----

    def get_batcave(self, force: bool = False) -> dict:
        """The open-source Batcave: configured repositories and their git state.

        No Docker / LocalStack / deploy / data-platform sections — those belong
        to a platform pack, not the core. Each repo row carries the keys the
        page's repo card reads: name, present, path, branch, dirty, ahead/behind.
        """
        repos = []
        for r in self._load_extras():
            path = r.get("path", "")
            present = bool(r.get("exists"))
            row = {
                "name": r.get("name") or Path(path).name,
                "path": path,
                "present": present,
                "pr": None,
            }
            if present:
                row["branch"] = _git(path, "rev-parse", "--abbrev-ref", "HEAD") or "—"
                status = _git(path, "status", "--porcelain")
                row["dirty"] = len([ln for ln in status.splitlines() if ln.strip()])
                counts = _git(
                    path, "rev-list", "--left-right", "--count", "@{u}...HEAD"
                )
                parts = counts.split()
                if len(parts) == 2:
                    row["behind"] = int(parts[0]) if parts[0].isdigit() else 0
                    row["ahead"] = int(parts[1]) if parts[1].isdigit() else 0
            repos.append(row)
        return {"repos": repos, "env": {}, "cached": False}

    def pm2_action(self, name: str, action: str) -> dict:
        return {"ok": False, "error": "process control is not in the open-source build"}

    def get_usage(self) -> dict:
        """Claude subscription quotas, read from Anthropic via the Claude Code
        keychain token. ``{tier, email, quotas[], sessionCost, extra?}`` or
        ``{error}`` when the CLI isn't signed in / the call fails."""
        from pennyworth.app import usage as _usage

        try:
            data = _usage.fetch_usage()
        except _usage.UsageError as exc:
            return {"error": str(exc)}
        status = _usage.fetch_auth_status()
        quotas = []
        labels = [
            ("five_hour", "5-hour"),
            ("seven_day", "7-day"),
            ("seven_day_opus", "7-day (Opus)"),
            ("seven_day_sonnet", "7-day (Sonnet)"),
        ]
        for key, label in labels:
            block = data.get(key) or {}
            if not block:
                continue
            quotas.append(
                {
                    "label": label,
                    "pct": float(block.get("utilization") or 0),
                    "resets": _humanize_reset(block.get("resets_at", "")),
                }
            )
        out = {
            "tier": str(status.get("subscriptionType", "") or "").lower(),
            "email": status.get("email", ""),
            "quotas": quotas,
            "sessionCost": self._session_cost,
        }
        extra = data.get("extra_usage") or {}
        if extra.get("is_enabled"):
            out["extra"] = {
                "pct": float(extra.get("utilization") or 0),
                "used": float(extra.get("used_credits") or 0),
                "limit": float(extra.get("monthly_limit") or 0),
                "currency": extra.get("currency", "USD"),
            }
        return out

    def list_mcp(self, force: bool = False) -> dict:
        return {"servers": [], "stderr": "", "cached": False}

    def add_mcp(self, name: str, target: str, transport: str = "") -> dict:
        return {"error": "MCP management is not wired in the open-source build"}

    def remove_mcp(self, name: str) -> dict:
        return {"error": "MCP management is not wired in the open-source build"}

    def list_slash_commands(self) -> list[dict]:
        return []

    def run_slash(self, text: str) -> dict:
        return {"error": "slash commands are not available in the open-source build"}

    def list_versions(self) -> dict:
        return {"versions": [], "current": _VERSION, "running": _VERSION}

    def install_version(self, tag: str) -> dict:
        return {"error": "in-app version install is not available; use pip/pipx"}

    def check_for_update(self) -> dict:
        return {"available": False, "stale": False}

    # --- dictation (macOS-only, optional) --------------------------------

    def start_dictation(self) -> bool:
        return False

    def stop_dictation(self) -> bool:
        return False


def _humanize_reset(iso: str) -> str:
    """A terse 'in 2h 14m' / 'resetting now' from an ISO reset timestamp."""
    if not iso:
        return ""
    import datetime

    try:
        when = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.timezone.utc)
        secs = (when - now).total_seconds()
    except (ValueError, TypeError):
        return ""
    if secs <= 0:
        return "resetting now"
    hours, mins = int(secs // 3600), int((secs % 3600) // 60)
    if hours:
        return f"in {hours}h {mins}m"
    return f"in {mins}m"


def _humanize_age(ts: float) -> str:
    """A terse relative age like '3m', '2h', '4d' for a unix timestamp."""
    if not ts:
        return ""
    delta = max(0, time.time() - ts)
    if delta < 90:
        return "now"
    if delta < 3600:
        return f"{int(delta // 60)}m"
    if delta < 86400:
        return f"{int(delta // 3600)}h"
    return f"{int(delta // 86400)}d"
