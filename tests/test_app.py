"""The desktop app: bridge behaviour, window config, and de-branded UI.

These exercise everything except actually opening a window (no display needed).
"""

from pathlib import Path

from pennyworth.app import window
from pennyworth.app.bridge import Bridge
from pennyworth.pack import NULL_PACK, Pack


def test_bridge_get_state():
    bridge = Bridge(pack_provider=lambda: NULL_PACK)
    assert bridge.get_state() == {
        "app": "Pennyworth",
        "assistant": "Alfred",
        "pack": None,
    }


def test_bridge_get_state_reports_active_pack():
    bridge = Bridge(pack_provider=lambda: Pack(name="acme"))
    assert bridge.get_state()["pack"] == "acme"


def test_bridge_ask_returns_reply(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho hello-from-agent\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    result = Bridge(pack_provider=lambda: NULL_PACK).ask("hi")
    assert result["ok"] is True
    assert "hello-from-agent" in result["text"]


def test_bridge_ask_reports_missing_agent(monkeypatch):
    monkeypatch.setenv("PENNYWORTH_AGENT", "definitely-not-a-real-binary-xyz")
    result = Bridge(pack_provider=lambda: NULL_PACK).ask("hi")
    assert result["ok"] is False
    assert "not found" in result["text"]


def test_window_config_points_at_real_html():
    cfg = window.window_config()
    assert cfg["title"] == "Alfred"
    assert Path(cfg["url"]).is_file()


def test_ui_carries_no_platform_branding():
    html = window.index_path().read_text().lower()
    for token in ("morning", "greeninvoice", "ploni", "teamcity", "localstack"):
        assert token not in html, f"branding leaked into the app UI: {token!r}"


def test_ui_uses_request_response_bridge():
    """The UI awaits api.ask() rather than relying on cross-thread event pushes."""
    html = window.index_path().read_text()
    assert "api().ask(" in html
    assert "alfredEvent" not in html  # the fragile evaluate_js path is gone
