"""The agent runner: command building and process invocation."""

import pennyworth.runner as runner


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
    assert "You are Alfred" in dumped  # the assembled brain reached the agent


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
