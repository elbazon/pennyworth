"""Pack loading and the attach/detach store."""

from pathlib import Path

import pennyworth.packs as packs
from pennyworth import NULL_PACK, build_system_prompt

EXAMPLE = Path(__file__).parents[1] / "examples" / "acme"


def test_load_example_pack():
    pack = packs.load_pack(EXAMPLE)
    assert pack.name == "acme"
    assert "Acme" in pack.platform_name
    assert pack.platform_blurb
    assert "## Principal" in pack.principal_block
    assert pack.is_attached


def test_load_example_pack_reads_attribution():
    """The [pack].attribution_file block loads and reaches the brain verbatim."""
    pack = packs.load_pack(EXAMPLE)
    assert "## Attribution & Identity" in pack.attribution_block
    assert "acme-bot" in pack.attribution_block
    brain = build_system_prompt(pack)
    assert "## Attribution & Identity" in brain
    assert "acme-bot" in brain


def test_load_example_pack_reads_hands():
    """The manifest's [[hands]] array loads into the pack and reaches the brain."""
    pack = packs.load_pack(EXAMPLE)
    names = [h.name for h in pack.hands]
    assert names == ["github", "acme-internal", "postgres"]
    assert all(h.summary for h in pack.hands)
    brain = build_system_prompt(pack)
    assert "## Hands (MCP)" in brain
    assert "**github**" in brain


def test_load_example_pack_reads_hand_transports():
    """Transport fields load: a stdio hand, a remote hand, and a brain-only hand."""
    by_name = {h.name: h for h in packs.load_pack(EXAMPLE).hands}
    assert by_name["github"].command == "npx"
    assert by_name["github"].args == ("-y", "@modelcontextprotocol/server-github")
    assert by_name["github"].is_wireable
    assert by_name["acme-internal"].url.endswith("/sse")
    assert by_name["acme-internal"].transport == "sse"
    assert by_name["acme-internal"].is_wireable
    # postgres is brain-only — documented but not auto-wired.
    assert not by_name["postgres"].is_wireable


def test_attach_list_active_detach(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))

    assert packs.list_packs() == []
    assert packs.active_pack() is NULL_PACK

    attached = packs.attach(EXAMPLE)
    assert attached.name == "acme"
    assert packs.list_packs() == ["acme"]
    assert packs.active_name() == "acme"

    active = packs.active_pack()
    assert active.name == "acme"
    assert active.platform_name in build_system_prompt(active)

    packs.detach()
    assert packs.active_name() == ""
    assert packs.active_pack() is NULL_PACK


def test_detached_brain_is_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("PENNYWORTH_HOME", str(tmp_path))
    packs.attach(EXAMPLE)
    packs.detach()
    brain = build_system_prompt(packs.active_pack())
    assert "Acme" not in brain
    assert "## Principal" not in brain
