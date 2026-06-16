"""The team and repository seams render from the pack."""

from pathlib import Path

import pennyworth.packs as packs
from pennyworth import NULL_PACK, build_system_prompt

EXAMPLE = Path(__file__).parents[1] / "examples" / "acme"


def test_example_pack_loads_team_and_repos():
    pack = packs.load_pack(EXAMPLE)
    assert [m.name for m in pack.team] == ["Ada Lovelace", "Alan Turing", "Grace Hopper"]
    assert pack.team[0].title == "Lead Engineer"
    assert [r.name for r in pack.repos] == ["acme-api", "acme-web"]
    assert pack.repos[0].path == "~/code/acme-api"


def test_team_and_repos_render_in_brain():
    brain = build_system_prompt(packs.load_pack(EXAMPLE))
    assert "## The Team" in brain
    assert "Ada Lovelace" in brain
    assert "Lead Engineer" in brain
    assert "## Repositories" in brain
    assert "acme-api" in brain
    assert "The REST API service (Python)." in brain


def test_no_team_or_repos_without_pack():
    brain = build_system_prompt(NULL_PACK)
    assert "## The Team" not in brain
    assert "## Repositories" not in brain
