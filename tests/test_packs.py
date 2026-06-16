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
