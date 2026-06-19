"""PTY-backed terminal sessions for the desktop app.

Each session is identified by a caller-supplied string id (typically the chat
id). A background drain thread keeps the master-fd read so the OS buffer does
not fill; callers collect output on demand via :meth:`TermManager.read`.

ANSI escape sequences are left in the byte stream — the UI strips them with a
client-side regex rather than pulling in a full terminal emulator.

macOS / Linux only (uses ``pty``, ``fcntl``, ``termios`` from the stdlib).
"""

from __future__ import annotations

import fcntl
import os
import pty
import select
import signal
import struct
import termios
import threading


class TermManager:
    """Owns a collection of PTY-backed shell sessions, keyed by string id."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self, term_id: str, cols: int = 120, rows: int = 30) -> dict:
        """Spawn an interactive shell in a new PTY and register it as ``term_id``.

        If ``term_id`` is already open, returns ``{ok, id, reused: True}``
        without spawning a second shell.
        """
        with self._lock:
            if term_id in self._sessions:
                return {"ok": True, "id": term_id, "reused": True}
        shell = _pick_shell()
        try:
            pid, master_fd = pty.fork()
        except OSError as exc:
            return {"ok": False, "error": str(exc)}
        if pid == 0:
            # Child process — exec the shell; this path never returns. Fall back
            # to /bin/sh if the chosen shell can't exec, so a missing $SHELL (or
            # a zsh-less CI box) still gets a working terminal instead of silence.
            try:
                os.execvp(shell, [shell, "-i"])
            except OSError:
                try:
                    os.execvp("/bin/sh", ["/bin/sh", "-i"])
                except OSError:
                    os._exit(1)
        # Parent: set the initial window size, then register the session.
        try:
            _set_winsize(master_fd, cols, rows)
        except OSError:
            pass
        session: dict = {"fd": master_fd, "pid": pid, "buf": b"", "closed": False}
        with self._lock:
            self._sessions[term_id] = session
        threading.Thread(target=self._drain_loop, args=(term_id,), daemon=True).start()
        return {"ok": True, "id": term_id, "reused": False}

    def close(self, term_id: str) -> dict:
        """Kill and remove the session for ``term_id``."""
        with self._lock:
            session = self._sessions.pop(term_id, None)
        if session is None:
            return {"ok": False, "error": "not found"}
        _kill(session["pid"])
        _close_fd(session["fd"])
        return {"ok": True}

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def read(self, term_id: str) -> dict:
        """Drain the accumulated output buffer for ``term_id``.

        Returns ``{ok, output, closed}`` — ``closed`` is True once the shell
        process exits (output may still contain trailing bytes before it).
        """
        with self._lock:
            session = self._sessions.get(term_id)
            if session is None:
                return {"ok": False, "error": "not found"}
            data, session["buf"] = session["buf"], b""
            closed = session["closed"]
        return {
            "ok": True,
            "output": data.decode("utf-8", errors="replace"),
            "closed": closed,
        }

    def write(self, term_id: str, data: str) -> dict:
        """Write ``data`` to the PTY stdin of ``term_id``."""
        with self._lock:
            session = self._sessions.get(term_id)
        if session is None:
            return {"ok": False, "error": "not found"}
        try:
            os.write(session["fd"], data.encode("utf-8"))
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def resize(self, term_id: str, cols: int, rows: int) -> dict:
        """Send ``TIOCSWINSZ`` to the PTY of ``term_id``."""
        with self._lock:
            session = self._sessions.get(term_id)
        if session is None:
            return {"ok": False, "error": "not found"}
        try:
            _set_winsize(session["fd"], cols, rows)
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Introspection (tests)
    # ------------------------------------------------------------------

    def list_ids(self) -> list[str]:
        """Active session IDs."""
        with self._lock:
            return list(self._sessions)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _drain_loop(self, term_id: str) -> None:
        """Background thread: read from the PTY master fd into the session buffer.

        Exit is detected two ways, whichever comes first: reading EOF off the
        master fd, or :func:`os.waitpid` reporting the shell process has gone.
        The latter is the authoritative signal — relying on PTY EOF alone can lag
        badly under load — and it reaps the child so no zombie is left behind.
        """
        while True:
            with self._lock:
                session = self._sessions.get(term_id)
            if session is None:
                return
            fd = session["fd"]
            try:
                ready, _, _ = select.select([fd], [], [], 0.2)
                if ready:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        break
                    with self._lock:
                        session["buf"] += chunk
                    continue
                # Idle cycle: ask the OS directly whether the shell has exited,
                # rather than waiting for the PTY to surface EOF.
                if _reaped(session["pid"]):
                    break
            except OSError:
                break
        # Shell exited — mark the session closed but leave it readable.
        with self._lock:
            if term_id in self._sessions:
                self._sessions[term_id]["closed"] = True


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _pick_shell() -> str:
    """The user's ``$SHELL`` if it exists, else the first available common shell.

    A bare ``$SHELL`` default of ``/bin/zsh`` is wrong on boxes without zsh (many
    CI runners), where the PTY child would fail to exec and produce no output.
    """
    shell = os.environ.get("SHELL", "")
    candidates = [shell, "/bin/zsh", "/bin/bash", "/bin/sh"]
    for cand in candidates:
        if cand and os.path.exists(cand) and os.access(cand, os.X_OK):
            return cand
    return "/bin/sh"


def _set_winsize(fd: int, cols: int, rows: int) -> None:
    packed = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)


def _reaped(pid: int) -> bool:
    """True if the shell ``pid`` has exited (reaping it if so).

    ``waitpid(WNOHANG)`` returns ``(0, 0)`` while the child still runs and
    ``(pid, status)`` once it has exited; a child already reaped elsewhere raises,
    which we also treat as gone.
    """
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError):
        return True
    return done != 0


def _kill(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
        os.waitpid(pid, os.WNOHANG)
    except (ProcessLookupError, ChildProcessError, OSError):
        pass


def _close_fd(fd: int) -> None:
    try:
        os.close(fd)
    except OSError:
        pass
