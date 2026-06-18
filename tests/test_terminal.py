"""TermManager: PTY-backed shell sessions (macOS / Linux only)."""

from __future__ import annotations

import sys
import time

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="pty not available on Windows"
)

from pennyworth.app.terminal import TermManager  # noqa: E402


@pytest.fixture()
def mgr():
    m = TermManager()
    yield m
    for tid in list(m.list_ids()):
        m.close(tid)


def _poll(fn, *, timeout: float = 3.0, interval: float = 0.1):
    """Retry fn() until it returns truthy, or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    return None


# --- lifecycle ---


def test_open_starts_a_shell(mgr):
    r = mgr.open("t1")
    assert r["ok"] is True
    assert r["id"] == "t1"
    assert "t1" in mgr.list_ids()


def test_reopen_is_idempotent(mgr):
    mgr.open("t1")
    r2 = mgr.open("t1")
    assert r2["ok"] is True
    assert r2.get("reused") is True
    assert mgr.list_ids().count("t1") == 1


def test_close_removes_session(mgr):
    mgr.open("t1")
    r = mgr.close("t1")
    assert r["ok"] is True
    assert "t1" not in mgr.list_ids()


def test_close_unknown_returns_error(mgr):
    assert mgr.close("nope")["ok"] is False


# --- I/O ---


def test_write_and_read_round_trip(mgr):
    mgr.open("t1")
    # Drain the initial shell prompt before our command.
    _poll(lambda: mgr.read("t1")["output"])
    mgr.write("t1", "echo pennyworth-test\n")
    output = _poll(
        lambda: (lambda r: r["output"] if "pennyworth-test" in r["output"] else None)(
            mgr.read("t1")
        )
    )
    assert output is not None, "expected output never arrived"
    assert "pennyworth-test" in output


def test_read_on_unknown_term(mgr):
    assert mgr.read("nope")["ok"] is False


def test_write_on_unknown_term(mgr):
    assert mgr.write("nope", "hi\n")["ok"] is False


# --- resize ---


def test_resize_succeeds(mgr):
    mgr.open("t1")
    assert mgr.resize("t1", 200, 50)["ok"] is True


def test_resize_unknown_term(mgr):
    assert mgr.resize("nope", 80, 24)["ok"] is False


# --- read returns closed flag when shell exits ---


def test_read_reports_closed_after_exit(mgr):
    mgr.open("t1")
    _poll(lambda: mgr.read("t1")["output"])  # drain prompt
    mgr.write("t1", "exit\n")
    # This waits on a real interactive shell to exit and the drain thread to
    # observe EOF — genuinely asynchronous. Under full-suite load (many PTY
    # threads scheduling at once) that can take several seconds, so the deadline
    # is deliberately generous; it polls every 0.1s and returns the instant the
    # flag flips, so a healthy run still finishes quickly.
    result = _poll(
        lambda: (lambda r: r if r.get("closed") else None)(mgr.read("t1")),
        timeout=15.0,
    )
    assert result is not None, "session never reported closed"
    assert result["closed"] is True
