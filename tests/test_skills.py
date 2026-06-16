"""The skills seam: a pack's skills are discovered and indexed in the brain."""

from pathlib import Path

import pennyworth.packs as packs
from pennyworth import NULL_PACK, build_system_prompt

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


def test_no_skill_section_without_skills():
    assert "## Skill Library" not in build_system_prompt(NULL_PACK)


def test_frontmatter_parser():
    name, desc = packs._parse_frontmatter("---\nname: x\ndescription: hello\n---\nbody")
    assert (name, desc) == ("x", "hello")
    assert packs._parse_frontmatter("no frontmatter here") == ("", "")
