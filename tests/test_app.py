"""The desktop app: bridge behaviour, window config, and de-branded UI.

These exercise everything except actually opening a window (no display needed).
"""


from pennyworth.app import window
from pennyworth.app.bridge import Bridge, _compose
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

    result = Bridge(pack_provider=lambda: NULL_PACK).ask([{"role": "user", "text": "hi"}])
    assert result["ok"] is True
    assert "hello-from-agent" in result["text"]


def test_bridge_ask_reports_missing_agent(monkeypatch):
    monkeypatch.setenv("PENNYWORTH_AGENT", "definitely-not-a-real-binary-xyz")
    result = Bridge(pack_provider=lambda: NULL_PACK).ask([{"role": "user", "text": "hi"}])
    assert result["ok"] is False
    assert "not found" in result["text"]


def test_bridge_ask_handles_empty():
    assert Bridge(pack_provider=lambda: NULL_PACK).ask([])["ok"] is False


def test_compose_single_turn_is_just_the_text():
    assert _compose([{"role": "user", "text": "deploy it"}]) == "deploy it"


def test_compose_includes_prior_turns():
    request = _compose(
        [
            {"role": "user", "text": "what is 2+2"},
            {"role": "alfred", "text": "Four, sir."},
            {"role": "user", "text": "and times three?"},
        ]
    )
    assert "Conversation so far" in request
    assert "User: what is 2+2" in request
    assert "Alfred: Four, sir." in request
    assert request.rstrip().endswith("and times three?")


def test_window_config_and_ui_asset():
    cfg = window.window_config()
    assert cfg["title"] == "Alfred"
    assert "url" not in cfg  # the page is loaded as inline html, not a file url
    assert window.index_path().is_file()
    assert "<html" in window.index_path().read_text().lower()


def test_ui_carries_no_platform_branding():
    html = window.index_path().read_text().lower()
    for token in ("morning", "greeninvoice", "ploni", "teamcity", "localstack"):
        assert token not in html, f"branding leaked into the app UI: {token!r}"


def test_ui_uses_request_response_bridge():
    """The UI awaits api.ask() rather than relying on cross-thread event pushes."""
    html = window.index_path().read_text()
    assert "api().ask(" in html
    assert "alfredEvent" not in html  # the fragile evaluate_js path is gone


def test_portrait_asset_ships():
    assert window.portrait_path().is_file()


def test_render_html_inlines_the_portrait():
    rendered = window.render_html()
    assert "{{PORTRAIT}}" not in rendered  # placeholder was substituted
    assert "data:image/png;base64," in rendered  # Alfred's face is embedded
