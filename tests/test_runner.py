"""The agent runner: command building and process invocation."""

import io

import pennyworth.runner as runner
from pennyworth.pack import Hand, Pack


def test_build_command_print_mode():
    cmd = runner.build_command("do it", "SYS", agent="claude")
    assert cmd[0] == "claude"
    assert cmd[cmd.index("--append-system-prompt") + 1] == "SYS"
    assert cmd[-2:] == ["-p", "do it"]


def test_build_command_interactive_seeds_request():
    cmd = runner.build_command("hi", "SYS", agent="claude", interactive=True)
    assert "-p" not in cmd
    assert cmd[-1] == "hi"


def test_build_command_interactive_without_request_appends_no_positional():
    cmd = runner.build_command("", "SYS", agent="claude", interactive=True)
    assert "-p" not in cmd
    assert cmd == ["claude", "--append-system-prompt", "SYS"]


def test_agent_env_override(monkeypatch):
    monkeypatch.setenv("PENNYWORTH_AGENT", "my-agent")
    assert runner.agent_command() == "my-agent"
    assert runner.build_command("x", "SYS")[0] == "my-agent"


def test_allow_all_and_dirs():
    cmd = runner.build_command(
        "x", "SYS", agent="claude", add_dirs=["/a", "/b"], allow_all=True
    )
    assert "--dangerously-skip-permissions" in cmd
    assert cmd.count("--add-dir") == 2


def test_run_invokes_agent_with_brain_and_request(tmp_path, monkeypatch):
    cap = tmp_path / "argv.txt"
    stub = tmp_path / "agent.sh"
    stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAP"\n')
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))
    monkeypatch.setenv("CAP", str(cap))

    assert runner.run("hello world") == 0
    dumped = cap.read_text()
    assert "--append-system-prompt" in dumped
    assert "hello world" in dumped
    assert "You are Pennyworth" in dumped  # the assembled brain reached the agent


def test_run_reports_missing_agent(monkeypatch, capsys):
    monkeypatch.setenv("PENNYWORTH_AGENT", "definitely-not-a-real-binary-xyz")
    assert runner.run("hi") == 127
    assert "not found" in capsys.readouterr().err


def test_stream_delivers_chunks(tmp_path, monkeypatch):
    stub = tmp_path / "agent.sh"
    stub.write_text("#!/bin/sh\necho line-one\necho line-two\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    chunks: list[str] = []
    assert runner.stream("hi", on_chunk=chunks.append) == 0
    joined = "".join(chunks)
    assert "line-one" in joined
    assert "line-two" in joined


def test_stream_reports_missing_agent(monkeypatch):
    monkeypatch.setenv("PENNYWORTH_AGENT", "definitely-not-a-real-binary-xyz")
    chunks: list[str] = []
    assert runner.stream("hi", on_chunk=chunks.append) == 127
    assert any("not found" in c for c in chunks)


def test_extract_text_delta_pulls_visible_text():
    line = (
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"index":0,"delta":{"type":"text_delta","text":"good day"}}}'
    )
    assert runner.extract_text_delta(line) == "good day"


def test_extract_text_delta_ignores_envelopes_thinking_and_noise():
    assert runner.extract_text_delta('{"type":"system","subtype":"init"}') is None
    assert runner.extract_text_delta('{"type":"result","result":"hi"}') is None
    # thinking is not the visible reply
    thinking = (
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"thinking_delta","thinking":"hmm"}}}'
    )
    assert runner.extract_text_delta(thinking) is None
    assert runner.extract_text_delta("not json at all") is None
    assert runner.extract_text_delta("") is None


def test_stream_parses_claude_stream_json(tmp_path, monkeypatch):
    # A stub literally named `claude` triggers the stream-json parsing path;
    # it ignores the streaming flags and just emits canned NDJSON events.
    ndjson = tmp_path / "events.ndjson"
    ndjson.write_text(
        '{"type":"system","subtype":"init"}\n'
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"Good "}}}\n'
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"day, sir."}}}\n'
        '{"type":"result","subtype":"success","result":"Good day, sir."}\n'
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude"
    stub.write_text(f'#!/bin/sh\ncat "{ndjson}"\n')
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    chunks: list[str] = []
    assert runner.stream("hi", on_chunk=chunks.append) == 0
    # Only the two text deltas are surfaced — envelopes are dropped.
    assert "".join(chunks) == "Good day, sir."


def test_parse_stream_event_classifies_each_kind():
    def ev(line):
        return runner.parse_stream_event(line)

    assert ev(
        '{"type":"stream_event","event":{"type":"message_start",'
        '"message":{"model":"claude-opus-4-8"}}}'
    ) == {"kind": "model", "model": "claude-opus-4-8"}
    assert ev(
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"hi"}}}'
    ) == {"kind": "text", "text": "hi"}
    assert ev(
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"thinking_delta","thinking":"hmm"}}}'
    ) == {"kind": "thinking", "text": "hmm"}
    assert ev(
        '{"type":"stream_event","event":{"type":"content_block_start",'
        '"content_block":{"type":"tool_use","name":"Bash","id":"t1"}}}'
    ) == {"kind": "tool", "name": "Bash", "id": "t1"}
    assert ev('{"type":"result","is_error":false,"total_cost_usd":0.0123}') == {
        "kind": "result",
        "cost": 0.0123,
        "error": False,
    }


def test_parse_stream_event_ignores_noise():
    assert runner.parse_stream_event('{"type":"system","subtype":"init"}') is None
    # a text content_block_start is not a tool call
    assert (
        runner.parse_stream_event(
            '{"type":"stream_event","event":{"type":"content_block_start",'
            '"content_block":{"type":"text","text":""}}}'
        )
        is None
    )
    assert runner.parse_stream_event("not json") is None
    assert runner.parse_stream_event("") is None


def test_stream_events_passes_model_flag(monkeypatch):
    """When model= is given, --model <id> appears in the argv for claude agents."""
    captured: list[list[str]] = []

    class FakeProc:
        stdout = io.StringIO("")

        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        captured.append(list(cmd))
        return FakeProc()

    monkeypatch.setattr("pennyworth.runner.subprocess.Popen", fake_popen)
    monkeypatch.setenv("PENNYWORTH_AGENT", "claude")
    runner.stream_events("hi", on_event=lambda e: None, model="claude-opus-4-8")
    assert captured, "Popen was not called"
    assert "--model" in captured[0]
    idx = captured[0].index("--model")
    assert captured[0][idx + 1] == "claude-opus-4-8"


def test_stream_events_model_ignored_for_custom_agent(monkeypatch):
    """Non-claude agents don't receive --model (they may not understand it)."""
    captured: list[list[str]] = []

    class FakeProc:
        stdout = io.StringIO("")

        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        captured.append(list(cmd))
        return FakeProc()

    monkeypatch.setattr("pennyworth.runner.subprocess.Popen", fake_popen)
    monkeypatch.setenv("PENNYWORTH_AGENT", "my-custom-agent")
    runner.stream_events("hi", on_event=lambda e: None, model="claude-opus-4-8")
    assert captured
    assert "--model" not in captured[0]


def test_build_mcp_config_shapes_stdio_and_remote_hands():
    pack = Pack(
        name="p",
        hands=(
            Hand(name="gh", command="npx", args=("-y", "server-github")),
            Hand(name="remote", url="https://mcp.example/sse", transport="sse"),
            Hand(name="http", url="https://mcp.example/h"),  # defaults to http
        ),
    )
    config = runner.build_mcp_config(pack)
    assert config == {
        "mcpServers": {
            "gh": {"command": "npx", "args": ["-y", "server-github"]},
            "remote": {"type": "sse", "url": "https://mcp.example/sse"},
            "http": {"type": "http", "url": "https://mcp.example/h"},
        }
    }


def test_build_mcp_config_skips_brain_only_hands():
    """A hand with only name + summary contributes no server (and yields None)."""
    pack = Pack(name="p", hands=(Hand(name="doc", summary="indexed, not wired"),))
    assert runner.build_mcp_config(pack) is None


def test_build_mcp_config_none_when_no_hands():
    assert runner.build_mcp_config(Pack(name="p")) is None


def test_stream_events_wires_mcp_config_for_claude(monkeypatch):
    """Wireable hands become --mcp-config JSON in the argv for claude agents."""
    import json

    captured: list[list[str]] = []

    class FakeProc:
        stdout = io.StringIO("")

        def wait(self):
            return 0

    monkeypatch.setattr(
        "pennyworth.runner.subprocess.Popen",
        lambda cmd, **kw: captured.append(list(cmd)) or FakeProc(),
    )
    monkeypatch.setenv("PENNYWORTH_AGENT", "claude")
    pack = Pack(name="p", hands=(Hand(name="gh", command="npx", args=("server",)),))
    runner.stream_events("hi", pack, on_event=lambda e: None)
    assert captured and "--mcp-config" in captured[0]
    payload = json.loads(captured[0][captured[0].index("--mcp-config") + 1])
    assert payload["mcpServers"]["gh"] == {"command": "npx", "args": ["server"]}


def test_stream_events_no_mcp_config_for_custom_agent(monkeypatch):
    """Non-claude agents get the brain-only index, never the Claude-specific flag."""
    captured: list[list[str]] = []

    class FakeProc:
        stdout = io.StringIO("")

        def wait(self):
            return 0

    monkeypatch.setattr(
        "pennyworth.runner.subprocess.Popen",
        lambda cmd, **kw: captured.append(list(cmd)) or FakeProc(),
    )
    monkeypatch.setenv("PENNYWORTH_AGENT", "my-custom-agent")
    pack = Pack(name="p", hands=(Hand(name="gh", command="npx"),))
    runner.stream_events("hi", pack, on_event=lambda e: None)
    assert captured and "--mcp-config" not in captured[0]


def test_stream_events_passes_cwd(tmp_path, monkeypatch):
    """cwd= is forwarded to Popen so the agent process starts in that directory."""
    captured_kw: list[dict] = []

    class FakeProc:
        stdout = io.StringIO("")

        def wait(self):
            return 0

    def fake_popen(cmd, **kw):
        captured_kw.append(kw)
        return FakeProc()

    monkeypatch.setattr("pennyworth.runner.subprocess.Popen", fake_popen)
    runner.stream_events("hi", on_event=lambda e: None, cwd=str(tmp_path))
    assert captured_kw, "Popen was not called"
    assert captured_kw[0].get("cwd") == str(tmp_path)


def test_stream_events_collects_structured_events(tmp_path, monkeypatch):
    ndjson = tmp_path / "events.ndjson"
    ndjson.write_text(
        '{"type":"stream_event","event":{"type":"message_start",'
        '"message":{"model":"claude-opus-4-8"}}}\n'
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"thinking_delta","thinking":"let me see"}}}\n'
        '{"type":"stream_event","event":{"type":"content_block_start",'
        '"content_block":{"type":"tool_use","name":"Read","id":"t1"}}}\n'
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"Done, sir."}}}\n'
        '{"type":"result","is_error":false,"total_cost_usd":0.05}\n'
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "claude"
    stub.write_text(f'#!/bin/sh\ncat "{ndjson}"\n')
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    events: list[dict] = []
    assert runner.stream_events("hi", on_event=events.append) == 0
    kinds = [e["kind"] for e in events]
    assert kinds == ["model", "thinking", "tool", "text", "result"]
    assert events[0]["model"] == "claude-opus-4-8"
    assert events[2]["name"] == "Read"
    assert events[3]["text"] == "Done, sir."
    assert events[4]["cost"] == 0.05


def test_result_error_text_names_an_overload():
    line = '{"type":"result","is_error":true,"result":"API Error: 529 Overloaded"}'
    msg = runner.result_error_text(line)
    assert msg is not None
    assert "529" in msg and "charged" in msg


def test_result_error_text_passes_through_other_errors():
    line = '{"type":"result","is_error":true,"error":"disk full"}'
    assert runner.result_error_text(line) == "disk full"


def test_result_error_text_is_none_without_a_message():
    assert runner.result_error_text("not json") is None
    assert runner.result_error_text('{"type":"result","is_error":true}') is None


def test_stream_events_surfaces_an_overloaded_result(tmp_path, monkeypatch):
    # The agent prints a 529 result, then exits. The runner should surface a
    # clear error event alongside the (errored) result event.
    # The runner only parses structured stream-json when the agent is the
    # bundled "claude" CLI, so the stub must carry that name.
    stub = tmp_path / "claude"
    stub.write_text(
        "#!/bin/sh\n"
        'echo \'{"type":"result","is_error":true,"result":"529 Overloaded"}\'\n'
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))

    events = []
    runner.stream_events("hi", on_event=events.append)
    errors = [e for e in events if e.get("kind") == "error"]
    assert errors and "529" in errors[0]["text"]
