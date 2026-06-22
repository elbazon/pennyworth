"""AI providers: Claude-Code delegation + the OpenAI-compatible HTTP backend."""

import io
import json

from pennyworth import providers
from pennyworth.pack import NULL_PACK


def _collect(**kwargs):
    events = []
    code = providers.stream_events(
        "say hi", NULL_PACK, on_event=events.append, **kwargs
    )
    return code, events


def test_claude_code_is_the_default_and_delegates(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho hi-from-claude\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    code, events = _collect(provider="claude-code")
    assert code == 0
    text = "".join(e.get("text", "") for e in events if e.get("kind") == "text")
    assert "hi-from-claude" in text


def _fake_sse(*chunks, reasoning=None):
    """Build an OpenAI-style streaming SSE body from content chunks."""
    lines = []
    if reasoning:
        lines.append(
            "data: "
            + json.dumps({"choices": [{"delta": {"reasoning_content": reasoning}}]})
        )
    for c in chunks:
        lines.append("data: " + json.dumps({"choices": [{"delta": {"content": c}}]}))
    lines.append("data: [DONE]")
    return io.BytesIO(("\n".join(lines) + "\n").encode("utf-8"))


def test_openai_compatible_streams_text_and_thinking(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data)
        captured["auth"] = req.headers.get("Authorization")
        return _fake_sse("Good ", "day, ", "sir.", reasoning="pondering…")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    code, events = _collect(
        provider="openai",
        api_key="sk-test",
        provider_model="gpt-4o-mini",
    )
    assert code == 0
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["body"]["model"] == "gpt-4o-mini"
    assert captured["body"]["stream"] is True
    # system prompt (Pennyworth's brain) + the user request are both sent
    roles = [m["role"] for m in captured["body"]["messages"]]
    assert roles == ["system", "user"]

    text = "".join(e.get("text", "") for e in events if e.get("kind") == "text")
    thinking = "".join(e.get("text", "") for e in events if e.get("kind") == "thinking")
    assert text == "Good day, sir."
    assert "pondering" in thinking
    assert events[-1]["kind"] == "result" and events[-1]["error"] is False


def test_openai_compatible_uses_custom_base_url(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=0):
        captured["url"] = req.full_url
        return _fake_sse("ok")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    _collect(
        provider="openai-compatible",
        base_url="http://localhost:1234/v1",
        provider_model="llama3.1",
    )
    assert captured["url"] == "http://localhost:1234/v1/chat/completions"


def test_openai_compatible_surfaces_errors(monkeypatch):
    import urllib.error

    def boom(req, timeout=0):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    code, events = _collect(provider="openai", api_key="x", provider_model="m")
    assert code == 1
    assert any(e.get("kind") == "error" for e in events)
    assert events[-1]["kind"] == "result" and events[-1]["error"] is True


def test_default_base_url_and_is_claude_code():
    assert providers.is_claude_code("claude-code") is True
    assert providers.is_claude_code("") is True
    assert providers.is_claude_code("openai") is False
    assert providers.default_base_url("openai").startswith("https://api.openai.com")
