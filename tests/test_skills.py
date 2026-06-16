"""The skills seam: a pack's skills are discovered and indexed in the brain."""

from pathlib import Path

import pennyworth.packs as packs
from pennyworth import NULL_PACK, build_system_prompt
from pennyworth import skills as core

EXAMPLE = Path(__file__).parents[1] / "examples" / "acme"


def test_example_pack_discovers_skills():
    pack = packs.load_pack(EXAMPLE)
    names = [s.name for s in pack.skills]
    assert "deploy" in names
    deploy = next(s for s in pack.skills if s.name == "deploy")
    assert deploy.description.startswith("Use before deploying")
    assert deploy.path.endswith("deploy.md")
    assert Path(deploy.path).is_file()


def test_skill_index_renders_in_brain():
    brain = build_system_prompt(packs.load_pack(EXAMPLE))
    assert "## Skill Library" in brain
    assert "Use before deploying" in brain
    assert "deploy.md" in brain


def test_core_skills_present_without_a_pack():
    """The built-in craft skills ship with the core and appear with no pack —
    but a pack's own skills do not."""
    brain = build_system_prompt(NULL_PACK)
    assert "## Skill Library" in brain
    assert "investigate.md" in brain
    assert "deploy.md" not in brain  # that one belongs to the acme pack


def test_core_skills_are_discovered_and_exist_on_disk():
    names = {s.name for s in core.core_skills()}
    assert {"investigate", "pr_context", "lean_product_reviewer", "worth_it"} <= names
    for skill in core.core_skills():
        assert Path(skill.path).is_file()


def test_frontmatter_parser():
    name, desc = core.parse_frontmatter("---\nname: x\ndescription: hello\n---\nbody")
    assert (name, desc) == ("x", "hello")
    assert core.parse_frontmatter("no frontmatter here") == ("", "")
