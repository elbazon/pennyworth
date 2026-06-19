"""The desktop app: bridge behaviour, window config, and de-branded UI.

These exercise everything except actually opening a window (no display needed).
"""

import pytest

from pennyworth import profile as _profile
from pennyworth.app import window
from pennyworth.app.bridge import Bridge, _compose
from pennyworth.pack import NULL_PACK, Pack
from pennyworth.profile import NULL_PROFILE


def _bridge():
    """A bridge with both seams pinned — deterministic, never touches host disk."""
    return Bridge(
        pack_provider=lambda: NULL_PACK, profile_provider=lambda: NULL_PROFILE
    )


# The poll snapshot for a finished/unknown turn.
_EMPTY_TURN = {
    "ok": False,
    "done": True,
    "text": "",
    "thinking": "",
    "steps": [],
    "cost": None,
    "model": None,
}


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

    result = _bridge().ask([{"role": "user", "text": "hi"}])
    assert result["ok"] is True
    assert "hello-from-agent" in result["text"]


def test_bridge_ask_reports_missing_agent(monkeypatch):
    monkeypatch.setenv("PENNYWORTH_AGENT", "definitely-not-a-real-binary-xyz")
    result = _bridge().ask([{"role": "user", "text": "hi"}])
    assert result["ok"] is False
    assert "not found" in result["text"]


def test_bridge_ask_handles_empty():
    assert Bridge(pack_provider=lambda: NULL_PACK).ask([])["ok"] is False


def _drain(bridge, turn_id, *, budget=300):
    """Poll a streaming turn to completion, returning the final poll result."""
    import time

    for _ in range(budget):
        result = bridge.poll(turn_id)
        if result["done"]:
            return result
        time.sleep(0.01)
    raise AssertionError("turn did not finish in time")


def test_bridge_start_and_poll_stream_reply(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho streamed-reply\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    bridge = _bridge()
    started = bridge.start([{"role": "user", "text": "hi"}])
    assert started["ok"] is True
    assert started["id"]

    final = _drain(bridge, started["id"])
    assert final["ok"] is True
    assert "streamed-reply" in final["text"]
    # Rich snapshot carries the structured fields too.
    assert set(final) >= {"text", "thinking", "steps", "cost", "model"}
    # The turn is forgotten once done — a second poll finds nothing.
    assert bridge.poll(started["id"]) == _EMPTY_TURN


def test_bridge_start_handles_empty():
    started = Bridge(pack_provider=lambda: NULL_PACK).start([])
    assert started["ok"] is False
    assert started["id"] is None


def test_bridge_poll_unknown_turn():
    assert _bridge().poll("no-such-turn") == _EMPTY_TURN


# --- persisted GUI chats ---


def test_persist_list_load_rename_delete_chats(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    bridge = _bridge()

    assert bridge.list_app_chats() == []
    chat = {
        "title": "Fix the bug",
        "messages": [
            {"role": "user", "text": "hi"},
            {"role": "alfred", "text": "Good day, sir."},
        ],
        "cost": 0.02,
    }
    assert bridge.persist_chat("c1", chat)["ok"] is True

    rows = bridge.list_app_chats()
    assert len(rows) == 1
    assert rows[0]["title"] == "Fix the bug"
    assert rows[0]["turns"] == 1  # one user message

    loaded = bridge.load_app_chat("c1")
    assert loaded["messages"][1]["text"] == "Good day, sir."

    assert bridge.rename_app_chat("c1", "Renamed")["ok"] is True
    assert bridge.load_app_chat("c1")["title"] == "Renamed"

    assert bridge.delete_app_chat("c1")["ok"] is True
    assert bridge.list_app_chats() == []
    assert bridge.load_app_chat("c1")["error"] == "not found"


def test_chat_id_is_sanitized_against_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    bridge = _bridge()
    bridge.persist_chat("../../evil", {"title": "x", "messages": []})
    # Nothing escaped the chats directory.
    assert not (tmp_path / "evil.json").exists()
    files = list((tmp_path / "app" / "chats").glob("*.json"))
    assert len(files) == 1


def test_open_url_rejects_non_http(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u))
    bridge = _bridge()
    assert bridge.open_url("file:///etc/passwd")["ok"] is False
    assert bridge.open_url("javascript:alert(1)")["ok"] is False
    assert opened == []  # nothing was launched


def test_open_url_opens_http(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u))
    assert _bridge().open_url("https://example.com")["ok"] is True
    assert opened == ["https://example.com"]


# --- panels: skills, profile, about ---


def test_list_skills_includes_core_skills():
    rows = _bridge().list_skills()
    names = {r["name"] for r in rows}
    assert {"investigate", "pr_context", "testing"} <= names
    assert all(r["source"] == "core" for r in rows)  # no pack attached
    assert all(r["description"] for r in rows)


def test_get_and_set_profile_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    bridge = Bridge(
        pack_provider=lambda: NULL_PACK, profile_provider=_profile.active_profile
    )
    assert bridge.get_profile() == {
        "name": "",
        "address": "",
        "addresses": ["sir", "madam"],
    }
    assert bridge.set_profile(name="Haim", address="sir")["ok"] is True
    got = bridge.get_profile()
    assert got["name"] == "Haim" and got["address"] == "sir"


def test_set_profile_rejects_bad_address(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    result = _bridge().set_profile(address="captain")
    assert result["ok"] is False
    assert "address" in result["error"]


def test_list_models_returns_curated_set():
    models = _bridge().list_models()
    assert isinstance(models, list) and len(models) >= 3
    ids = {m["id"] for m in models}
    assert "claude-sonnet-4-6" in ids
    assert all("id" in m and "label" in m for m in models)


def test_get_stats_counts_sessions_and_tokens(tmp_path):
    import json as _json

    proj = tmp_path / ".claude" / "projects" / "test-project"
    proj.mkdir(parents=True)
    lines = [
        _json.dumps({"type": "user", "content": [{"type": "text", "text": "hi"}]}),
        _json.dumps(
            {
                "type": "assistant",
                "message": {"usage": {"input_tokens": 10, "output_tokens": 5}},
            }
        ),
        _json.dumps({"type": "user", "content": [{"type": "text", "text": "again"}]}),
    ]
    (proj / "session.jsonl").write_text("\n".join(lines) + "\n")

    stats = _bridge().get_stats(_home=tmp_path)
    assert stats["sessions"] == 1
    assert stats["messages"] == 3
    assert stats["input_tokens"] == 10
    assert stats["output_tokens"] == 5
    assert stats["total_tokens"] == 15
    assert stats["active_days"] >= 1


def test_get_stats_empty_when_no_projects(tmp_path):
    stats = _bridge().get_stats(_home=tmp_path)
    assert stats == {
        "sessions": 0,
        "messages": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "active_days": 0,
    }


def test_start_accepts_model_param(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho hi\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))
    started = _bridge().start(
        [{"role": "user", "text": "hi"}], model="claude-sonnet-4-6"
    )
    assert started["ok"] is True and started["id"]


def test_start_accepts_cwd_param(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho hi\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))
    started = _bridge().start(
        [{"role": "user", "text": "hi"}], cwd=str(tmp_path)
    )
    assert started["ok"] is True and started["id"]


def test_pick_dir_returns_error_without_window():
    r = _bridge().pick_dir()
    assert r["ok"] is False
    assert r.get("error")  # cancelled / no window / headless mode — all are errors


def test_about_names_alfred_and_pennyworth():
    about = _bridge().about()
    assert about["assistant"] == "Alfred"
    assert about["project"] == "Pennyworth"
    assert about["pack"] is None


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
    # The production-GUI shell loads by file URL so its relative assets
    # (xterm.js/css, avatar) resolve; it is no longer an inline html= page.
    assert "url" in cfg
    assert str(window.index_path()) in cfg["url"]
    assert window.index_path().is_file()
    assert "<html" in window.index_path().read_text().lower()


def test_index_url_carries_cache_bust():
    # WKWebView caches file:// pages; the ?v=<mtime> query busts it on upgrade.
    assert "?v=" in window.index_url()


def test_ui_proprietary_font_and_brand_chrome_removed():
    """De-branding that IS done: no proprietary Ploni font, no Morning logo asset,
    no morning.co link, no 'Made at Morning' footer."""
    html = window.index_path().read_text().lower()
    assert "ploni" not in html  # proprietary typeface removed (licensing)
    assert "morning-logo.svg" not in html  # logo asset removed
    assert "morning.co" not in html  # company link removed
    assert "made at morning" not in html  # footer credit removed
    # The bundled web/ ships no proprietary font files.
    web = window.index_path().parent
    assert not list(web.glob("ploni*.woff2"))


@pytest.mark.xfail(
    reason="Platform-coupled panels (Batcave LocalStack/Docker view, Connectors "
    "TeamCity examples, Settings TeamCity rows + morning-cli repo paths) still "
    "carry Morning tokens; they await OSS redesign — see docs/PORTING_GUI.md.",
    strict=False,
)
def test_ui_fully_free_of_platform_tokens():
    html = window.index_path().read_text().lower()
    for token in ("morning", "teamcity", "localstack"):
        assert token not in html, f"platform token still in app UI: {token!r}"


def test_ui_uses_push_bridge():
    """The production shell is push-based: send_message() + window.alfredEvent."""
    html = window.index_path().read_text()
    assert "send_message(" in html  # a turn is started, then streamed via push
    assert "window.alfredEvent" in html  # Python pushes events into the page
    assert "get_state(" in html  # boot pulls initial state


def test_ui_has_chat_persistence_and_links():
    """Chat history persistence and safe link handling are wired."""
    html = window.index_path().read_text()
    for call in ("persist_chat(", "list_app_chats(", "load_app_chat(", "open_url("):
        assert call in html, f"UI never calls {call}"


def test_ui_has_panels():
    """The production shell wires the side-panel navigation."""
    html = window.index_path().read_text()
    for call in ("list_skills(", "get_settings(", "get_stats("):
        assert call in html, f"UI never calls {call}"
    for nav in ("navSkills", "navSettings", "navAbout"):
        assert nav in html, f"nav missing {nav}"


def test_read_file_text_returns_content(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("Good day, sir.\n")
    r = _bridge().read_file_text(str(f))
    assert r["ok"] is True
    assert r["name"] == "notes.txt"
    assert r["content"] == "Good day, sir.\n"
    assert r["truncated"] is False


def test_read_file_text_truncates_large_files(tmp_path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"x" * 600_000)
    r = _bridge().read_file_text(str(f), max_bytes=100)
    assert r["ok"] is True
    assert len(r["content"]) == 100
    assert r["truncated"] is True


def test_read_file_text_missing_file():
    assert _bridge().read_file_text("/no/such/file/abc.txt")["ok"] is False


def test_ui_has_model_picker():
    """Per-chat model selection in the composer, wired to the bridge."""
    html = window.index_path().read_text()
    assert "modelSel" in html  # the select element exists
    assert "set_chat_model(" in html  # selection routes to the bridge


def test_ui_has_file_attachments():
    html = window.index_path().read_text()
    assert "pick_files(" in html  # production picker name (plural)


def test_ui_has_terminal():
    """The embedded xterm terminal, wired to the production PTY method names."""
    html = window.index_path().read_text()
    for call in ("term_open(", "term_input(", "term_close(", "term_resize("):
        assert call in html, f"UI never calls {call}"


def test_terminal_assets_ship():
    """xterm.js / css / fit addon are bundled so the terminal renders offline."""
    web = window.index_path().parent
    for asset in ("xterm.js", "xterm.css", "xterm-addon-fit.js"):
        assert (web / asset).is_file(), f"missing terminal asset: {asset}"
    assert '<link rel="stylesheet" href="xterm.css"' in window.index_path().read_text()


def test_portrait_asset_ships():
    assert window.portrait_path().is_file()
