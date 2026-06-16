"""The desktop app: bridge lifecycle, window config, and de-branded UI.

These exercise everything except actually opening a window (no pywebview, no
display needed).
"""

from pathlib import Path

from pennyworth.app import window
from pennyworth.app.bridge import Bridge
from pennyworth.pack import NULL_PACK, Pack


def test_bridge_get_state():
    bridge = Bridge(emit=lambda e: None, pack_provider=lambda: NULL_PACK)
    state = bridge.get_state()
    assert state == {"app": "Pennyworth", "assistant": "Alfred", "pack": None}


def test_bridge_get_state_reports_active_pack():
    bridge = Bridge(emit=lambda e: None, pack_provider=lambda: Pack(name="acme"))
    assert bridge.get_state()["pack"] == "acme"


def test_bridge_run_turn_emits_start_chunks_end(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho hello-from-agent\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    events: list[dict] = []
    bridge = Bridge(emit=events.append, pack_provider=lambda: NULL_PACK)
    bridge._run_turn("c1", "hi")  # run synchronously (no thread) for the test

    assert events[0]["type"] == "start"
    assert events[-1]["type"] == "end"
    assert events[-1]["code"] == 0
    assert any(
        e["type"] == "chunk" and "hello-from-agent" in e["text"] for e in events
    )


def test_window_config_points_at_real_html():
    cfg = window.window_config()
    assert cfg["title"] == "Alfred"
    assert Path(cfg["url"]).is_file()


def test_ui_carries_no_platform_branding():
    html = window.index_path().read_text().lower()
    for token in ("morning", "greeninvoice", "ploni", "teamcity", "localstack"):
        assert token not in html, f"branding leaked into the app UI: {token!r}"
