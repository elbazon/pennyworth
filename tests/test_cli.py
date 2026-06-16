"""CLI smoke tests: attach → prompt → detach round trip."""

from pathlib import Path

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
