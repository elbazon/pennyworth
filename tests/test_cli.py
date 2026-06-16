"""CLI smoke tests: attach → prompt → detach round trip."""

from pathlib import Path

import pytest

import pennyworth.cli as cli

EXAMPLE = Path(__file__).parents[1] / "examples" / "acme"


def test_attach_prompt_detach_roundtrip(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))

    assert cli.main(["pack", "attach", str(EXAMPLE)]) == 0
    assert "acme" in capsys.readouterr().out

    assert cli.main(["pack", "list"]) == 0
    assert "acme" in capsys.readouterr().out

    assert cli.main(["prompt"]) == 0
    assert "the Acme platform" in capsys.readouterr().out

    assert cli.main(["pack", "detach"]) == 0
    capsys.readouterr()

    assert cli.main(["prompt"]) == 0
    assert "Acme" not in capsys.readouterr().out


def test_no_args_prints_help(capsys):
    assert cli.main([]) == 0
    assert "Alfred" in capsys.readouterr().out


def test_profile_set_show_clear_roundtrip(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))

    assert cli.main(["profile", "show"]) == 0
    assert "No profile set" in capsys.readouterr().out

    assert cli.main(["profile", "set", "--name", "Haim", "--address", "sir"]) == 0
    assert "Haim" in capsys.readouterr().out

    # The profile flows into the assembled brain.
    assert cli.main(["prompt"]) == 0
    out = capsys.readouterr().out
    assert "## Your User" in out and "Haim" in out

    assert cli.main(["profile", "clear"]) == 0
    capsys.readouterr()
    assert cli.main(["prompt"]) == 0
    assert "## Your User" not in capsys.readouterr().out


def test_profile_set_rejects_bad_address(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    # argparse rejects an out-of-choice value before our handler runs.
    with pytest.raises(SystemExit):
        cli.main(["profile", "set", "--address", "captain"])


def test_bare_request_routes_to_run(tmp_path, monkeypatch):
    cap = tmp_path / "argv.txt"
    stub = tmp_path / "agent.sh"
    stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$CAP"\n')
    stub.chmod(0o755)
    monkeypatch.setenv("PENNYWORTH_AGENT", str(stub))
    monkeypatch.setenv("CAP", str(cap))
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path / "home"))

    assert cli.main(["fix", "the", "bug"]) == 0
    dumped = cap.read_text()
    assert "-p" in dumped
    assert "fix the bug" in dumped
