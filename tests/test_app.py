"""The desktop app: bridge behaviour, window config, and de-branded UI.

These exercise everything except actually opening a window (no display needed).
"""

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
    assert "url" not in cfg  # the page is loaded as inline html, not a file url
    assert window.index_path().is_file()
    assert "<html" in window.index_path().read_text().lower()


def test_ui_carries_no_platform_branding():
    html = window.index_path().read_text().lower()
    for token in ("morning", "greeninvoice", "ploni", "teamcity", "localstack"):
        assert token not in html, f"branding leaked into the app UI: {token!r}"


def test_ui_uses_request_response_bridge():
    """The UI polls api.start()/api.poll() — request/response, no cross-thread push."""
    html = window.index_path().read_text()
    assert "api().start(" in html
    assert "api().poll(" in html
    assert "alfredEvent" not in html  # the fragile evaluate_js path is gone
    assert "evaluate_js" not in html


def test_ui_has_rich_features():
    """The UI wires the Layer-1 features: markdown, persistence, links, shortcuts."""
    html = window.index_path().read_text()
    assert "renderMarkdown(" in html  # rendered replies, not plain text
    assert "cbcopy" in html  # code-block copy buttons
    assert "paintReason(" in html  # thinking + tool-step reasoning drawer
    for call in ("persist_chat(", "list_app_chats(", "load_app_chat(", "open_url("):
        assert call in html, f"UI never calls {call}"
    assert 'ev.key === "n"' in html  # the ⌘N new-chat shortcut


def test_ui_has_panels():
    """The UI wires the Layer-2 side panels (Skills, Settings, About)."""
    html = window.index_path().read_text()
    assert "showView(" in html
    for call in ("list_skills(", "get_profile(", "set_profile(", "about("):
        assert call in html, f"UI never calls {call}"
    for view in ('data-view="skills"', 'data-view="settings"', 'data-view="about"'):
        assert view in html, f"nav missing {view}"


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


def test_ui_has_model_picker_and_stats():
    """Layer-3 additions: model picker in the composer + Stats panel."""
    html = window.index_path().read_text()
    assert "list_models(" in html  # model picker populated from bridge
    assert "modelSel" in html  # the select element exists
    assert "get_stats(" in html  # Stats panel calls bridge
    assert 'data-view="stats"' in html  # Stats nav button present
    assert "renderStats(" in html  # the renderer is wired


def test_ui_has_slash_commands():
    html = window.index_path().read_text()
    assert "SLASH_COMMANDS" in html
    assert "slashMenu" in html
    assert "updateSlashMenu(" in html


def test_ui_has_file_attachments():
    html = window.index_path().read_text()
    assert "pick_file(" in html
    assert "read_file_text(" in html
    assert "chips" in html  # chip row for pending attachments
    assert "pendingFiles" in html


def test_ui_has_terminal():
    html = window.index_path().read_text()
    assert "term_open(" in html
    assert "term_write(" in html
    assert "term_read(" in html
    assert "term_close(" in html
    assert "termPane" in html
    assert "stripAnsi(" in html


def test_ui_has_working_dir_picker():
    html = window.index_path().read_text()
    assert "pick_dir(" in html
    assert "cwdPick" in html
    assert "setCwd(" in html


def test_portrait_asset_ships():
    assert window.portrait_path().is_file()


def test_render_html_inlines_the_portrait():
    rendered = window.render_html()
    assert "{{PORTRAIT}}" not in rendered  # placeholder was substituted
    assert "data:image/png;base64," in rendered  # Alfred's face is embedded
