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
