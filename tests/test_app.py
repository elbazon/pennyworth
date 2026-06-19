"""The desktop app: the production-contract bridge, window config, de-branding.

These exercise everything except actually opening a window. The streaming chat
path is covered with a fake window that captures the events the bridge pushes —
the same `window.alfredEvent(...)` calls the real page receives.
"""

import json
import re

from pennyworth.app import window
from pennyworth.app.bridge import EFFORTS, MODELS, PERSONAS, Bridge, _compose
from pennyworth.pack import NULL_PACK, Pack
from pennyworth.profile import NULL_PROFILE


def _bridge():
    """A bridge with both seams pinned — deterministic, never touches host disk."""
    return Bridge(
        pack_provider=lambda: NULL_PACK, profile_provider=lambda: NULL_PROFILE
    )


class _FakeWindow:
    """Captures the events the bridge pushes via evaluate_js(window.alfredEvent…)."""

    def __init__(self):
        self.events = []

    def evaluate_js(self, script):
        m = re.match(r"window\.alfredEvent\((.*)\)$", script, re.DOTALL)
        if m:
            self.events.append(json.loads(m.group(1)))


def _run_turn_sync(bridge, chat_id, text, *, timeout=5.0):
    """Send a message and block until its turn thread finishes; return events."""
    win = _FakeWindow()
    bridge._window = win  # inline delivery (no emit queue) — synchronous capture
    assert bridge.send_message(chat_id, text) is True
    thread = bridge._chats[chat_id]["thread"]
    thread.join(timeout=timeout)
    assert not thread.is_alive(), "turn did not finish in time"
    return win.events


# --- boot: state & settings ------------------------------------------------


def test_get_state_carries_the_boot_payload():
    state = _bridge().get_state()
    assert state["app"] == "Pennyworth"
    assert state["assistant"] == "Alfred"
    assert state["models"] == MODELS
    assert state["personas"] == PERSONAS
    assert state["efforts"] == EFFORTS
    assert state["model"] == "auto"
    assert "version" in state and "branch" in state and "project" in state


def test_get_state_reports_active_pack():
    bridge = Bridge(pack_provider=lambda: Pack(name="acme"))
    assert bridge.get_state()["pack"] == "acme"


def test_get_settings_shape_and_set_setting_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    from pennyworth import profile as _profile

    bridge = Bridge(
        pack_provider=lambda: NULL_PACK, profile_provider=_profile.active_profile
    )
    s = bridge.get_settings()
    for key in ("name", "email", "model", "ui_font", "ui_theme", "max_turns"):
        assert key in s
    assert s["teamcity_token_set"] is False

    updated = bridge.set_setting("ui_font", "serif")
    assert updated["ui_font"] == "serif"
    assert bridge.get_settings()["ui_font"] == "serif"


def test_set_setting_rejects_unknown_key():
    assert "error" in _bridge().set_setting("not_a_setting", 1)


def test_set_setting_name_updates_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    from pennyworth import profile as _profile

    bridge = Bridge(
        pack_provider=lambda: NULL_PACK, profile_provider=_profile.active_profile
    )
    bridge.set_setting("name", "Haim")
    assert _profile.active_profile().name == "Haim"
    assert bridge.get_settings()["name"] == "Haim"


# --- per-chat selection ----------------------------------------------------


def test_chat_settings_default_and_updates():
    bridge = _bridge()
    assert bridge.get_chat_settings("c1") == {
        "model": "auto",
        "persona": "",
        "effort": "medium",
    }
    assert bridge.set_chat_model("c1", "opus")["model"] == "opus"
    assert bridge.set_chat_persona("c1", "architect")["persona"] == "architect"
    assert bridge.set_chat_effort("c1", "high")["effort"] == "high"
    # clearing persona resolves to the default ("")
    assert bridge.set_chat_persona("c1", "clear")["persona"] == ""


def test_chat_settings_reject_unknown_values():
    bridge = _bridge()
    assert "error" in bridge.set_chat_model("c1", "gpt-5")
    assert "error" in bridge.set_chat_persona("c1", "wizard")
    assert "error" in bridge.set_chat_effort("c1", "ludicrous")


# --- the streaming turn (push) ---------------------------------------------


def test_send_message_streams_turn_events(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho streamed-reply\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    events = _run_turn_sync(_bridge(), "c1", "hello")
    types = [e["type"] for e in events]
    assert "turn_start" in types
    assert "turn_end" in types
    # every event is tagged with the chat id for pane routing
    assert all(e.get("chatId") == "c1" for e in events)
    text = "".join(
        e.get("text", "")
        for e in events
        if e["type"] == "stream" and e.get("kind") == "text"
    )
    assert "streamed-reply" in text


def test_send_message_empty_is_rejected():
    assert _bridge().send_message("c1", "   ") is False


def test_send_message_keeps_conversation_memory(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho ok\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))
    bridge = _bridge()
    _run_turn_sync(bridge, "c1", "first")
    msgs = bridge._chats["c1"]["messages"]
    # user turn + alfred reply recorded for context on the next turn
    assert msgs[0] == {"role": "user", "text": "first"}
    assert msgs[1]["role"] == "alfred"


def test_interrupt_and_close_chat_are_safe():
    bridge = _bridge()
    assert bridge.interrupt("nope") is True  # idempotent on unknown chat
    bridge.get_chat_settings("c1")
    assert bridge.close_chat("c1") is True
    assert "c1" not in bridge._chats


def test_set_app_focused():
    assert _bridge().set_app_focused(False) is True


# --- links & files ---------------------------------------------------------


def test_open_url_rejects_non_http(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u))
    bridge = _bridge()
    assert "error" in bridge.open_url("file:///etc/passwd")
    assert "error" in bridge.open_url("javascript:alert(1)")
    assert opened == []


def test_open_url_opens_http(monkeypatch):
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda u: opened.append(u))
    assert _bridge().open_url("https://example.com")["ok"] is True
    assert opened == ["https://example.com"]


def test_pick_folder_returns_empty_without_window():
    assert _bridge().pick_folder() == {}


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
    assert "error" in _bridge().read_file_text("/no/such/file/abc.txt")


# --- skills, stats ---------------------------------------------------------


def test_list_skills_includes_core_skills():
    rows = _bridge().list_skills()
    names = {r["name"] for r in rows}
    assert {"investigate", "pr_context", "testing"} <= names
    assert all(r["source"] == "core" for r in rows)
    assert all(r["description"] for r in rows)


def test_get_stats_counts_sessions_and_tokens(tmp_path):
    proj = tmp_path / ".claude" / "projects" / "test-project"
    proj.mkdir(parents=True)
    lines = [
        json.dumps({"type": "user", "content": [{"type": "text", "text": "hi"}]}),
        json.dumps(
            {
                "type": "assistant",
                "message": {"usage": {"input_tokens": 10, "output_tokens": 5}},
            }
        ),
        json.dumps({"type": "user", "content": [{"type": "text", "text": "again"}]}),
    ]
    (proj / "session.jsonl").write_text("\n".join(lines) + "\n")
    stats = _bridge().get_stats(_home=tmp_path)
    assert stats["sessions"] == 1
    assert stats["messages"] == 3
    assert stats["total_tokens"] == 15


def test_get_stats_empty_when_no_projects(tmp_path):
    stats = _bridge().get_stats(_home=tmp_path)
    assert stats["sessions"] == 0 and stats["total_tokens"] == 0


# --- persisted GUI chats (+ pinning) ---------------------------------------


def test_persist_list_load_rename_pin_delete_chats(tmp_path, monkeypatch):
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
    assert rows[0]["turns"] == 1
    assert rows[0]["pinned"] is False

    assert bridge.load_app_chat("c1")["messages"][1]["text"] == "Good day, sir."
    assert bridge.rename_app_chat("c1", "Renamed")["title"] == "Renamed"
    assert bridge.pin_app_chat("c1", True)["pinned"] is True
    assert bridge.list_app_chats()[0]["pinned"] is True

    assert bridge.delete_app_chat("c1")["ok"] is True
    assert bridge.list_app_chats() == []
    assert "error" in bridge.load_app_chat("c1")


def test_chat_id_is_sanitized_against_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    bridge = _bridge()
    bridge.persist_chat("../../evil", {"title": "x", "messages": []})
    assert not (tmp_path / "evil.json").exists()
    files = list((tmp_path / "app" / "chats").glob("*.json"))
    assert len(files) == 1


# --- custom themes ---------------------------------------------------------


def test_theme_save_list_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    bridge = _bridge()
    assert bridge.list_themes() == []
    saved = bridge.save_theme({"name": "Sunset", "vars": {"--accent": "#ff8800"}})
    assert saved["ok"] is True
    assert saved["theme"]["name"] == "Sunset"
    assert any(t["name"] == "Sunset" for t in bridge.list_themes())
    theme_id = saved["theme"]["id"]
    assert bridge.delete_theme(theme_id)["ok"] is True
    assert bridge.list_themes() == []


def test_theme_needs_a_name():
    assert "error" in _bridge().save_theme({"vars": {}})


# --- scheduled prompts -----------------------------------------------------


def test_scheduled_add_list_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    bridge = _bridge()
    assert bridge.list_scheduled() == []
    added = bridge.add_scheduled("deploy it", "2030-01-01T09:00")
    assert added["ok"] is True
    task_id = added["task"]["id"]
    assert len(bridge.list_scheduled()) == 1
    assert bridge.delete_scheduled(task_id)["ok"] is True
    assert bridge.list_scheduled() == []


def test_scheduled_rejects_bad_datetime():
    assert "error" in _bridge().add_scheduled("x", "not-a-date")


# --- platform-coupled panels degrade gracefully (shape-correct) ------------


def test_batcave_surfaces_configured_repos(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    repo = tmp_path / "myrepo"
    repo.mkdir()
    b = _bridge()
    b.save_extra_repos([{"name": "myrepo", "path": str(repo)}])
    repos = b.get_batcave()["repos"]
    assert len(repos) == 1
    assert repos[0]["name"] == "myrepo"
    assert repos[0]["present"] is True


def test_platform_panels_return_safe_shapes(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    b = _bridge()
    assert b.get_batcave()["repos"] == []  # no platform env sections in OSS
    assert b.list_mcp()["servers"] == []
    assert b.list_slash_commands() == []
    assert b.list_versions()["running"]
    assert b.check_for_update()["available"] is False
    assert "error" in b.get_usage()
    assert "error" in b.run_slash("/whatever")
    assert b.start_dictation() is False


# --- compose ---------------------------------------------------------------


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


# --- window config & assets ------------------------------------------------


def test_window_config_and_ui_asset():
    cfg = window.window_config()
    assert cfg["title"] == "Alfred"
    assert "url" in cfg
    assert str(window.index_path()) in cfg["url"]
    assert window.index_path().is_file()
    assert "<html" in window.index_path().read_text().lower()


def test_index_url_carries_cache_bust():
    assert "?v=" in window.index_url()


# --- UI contract (the ported production shell) -----------------------------


def test_bridge_implements_every_method_the_ui_calls():
    """Every window.pywebview.api.<m>() the page calls exists on Bridge."""
    html = window.index_path().read_text()
    called = set(re.findall(r"api\(\)\.([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", html))
    missing = sorted(m for m in called if not hasattr(Bridge, m))
    assert not missing, f"Bridge is missing {len(missing)} UI methods: {missing}"


def test_ui_uses_push_bridge():
    html = window.index_path().read_text()
    assert "send_message(" in html
    assert "window.alfredEvent" in html
    assert "get_state(" in html


def test_ui_has_chat_persistence_and_links():
    html = window.index_path().read_text()
    for call in ("persist_chat(", "list_app_chats(", "load_app_chat(", "open_url("):
        assert call in html, f"UI never calls {call}"


def test_ui_has_panels():
    html = window.index_path().read_text()
    for call in ("list_skills(", "get_settings(", "get_stats("):
        assert call in html, f"UI never calls {call}"
    for nav in ("navSkills", "navSettings", "navAbout"):
        assert nav in html, f"nav missing {nav}"


def test_ui_has_model_picker():
    html = window.index_path().read_text()
    assert "modelSel" in html
    assert "set_chat_model(" in html


def test_ui_has_file_attachments():
    assert "pick_files(" in window.index_path().read_text()


def test_ui_has_terminal():
    html = window.index_path().read_text()
    for call in ("term_open(", "term_input(", "term_close(", "term_resize("):
        assert call in html, f"UI never calls {call}"


def test_terminal_assets_ship():
    web = window.index_path().parent
    for asset in ("xterm.js", "xterm.css", "xterm-addon-fit.js"):
        assert (web / asset).is_file(), f"missing terminal asset: {asset}"
    assert '<link rel="stylesheet" href="xterm.css"' in window.index_path().read_text()


def test_portrait_asset_ships():
    assert window.portrait_path().is_file()


def test_inline_script_parses(tmp_path):
    """The page's inline JS must parse — a syntax error aborts the whole script
    and leaves the UI rendered but inert. Skips cleanly where node is absent."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node not available to syntax-check the inline script")
    html = window.index_path().read_text().splitlines()
    start = next(i for i, ln in enumerate(html) if ln.strip() == "<script>" and i > 50)
    end = next(i for i in range(start + 1, len(html)) if "</script>" in html[i])
    script = tmp_path / "inline.js"
    script.write_text("\n".join(html[start + 1 : end]))
    result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, f"inline script has a syntax error:\n{result.stderr}"


def test_ui_proprietary_font_and_brand_chrome_removed():
    """De-branding that IS done: no Ploni font, no Morning logo/link/footer."""
    html = window.index_path().read_text().lower()
    assert "ploni" not in html
    assert "morning-logo.svg" not in html
    assert "morning.co" not in html
    assert "made at morning" not in html
    web = window.index_path().parent
    assert not list(web.glob("ploni*.woff2"))
