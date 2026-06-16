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
    assert {
        "investigate",
        "pr_context",
        "lean_product_reviewer",
        "worth_it",
        "aws_docs_mcp",
        "mcp_oauth",
        "testing",
    } <= names
    for skill in core.core_skills():
        assert Path(skill.path).is_file()


# Vocabulary that belongs to a specific platform, never to the OSS core. Core
# skills are platform-agnostic craft; platform specifics arrive only via a pack.
_PLATFORM_TOKENS = (
    "morning",
    "greeninvoice",
    "teamcity",
    "localstack",
    "ploni",
    "fiona",
)


def test_core_skills_carry_no_platform_vocabulary():
    """A built-in skill that named a platform would leak it into every brain."""
    for skill in core.core_skills():
        body = Path(skill.path).read_text().lower()
        for token in _PLATFORM_TOKENS:
            assert token not in body, (
                f"built-in skill {skill.name!r} leaked platform vocabulary "
                f"{token!r} — core skills must stay platform-agnostic."
            )


def test_frontmatter_parser():
    name, desc = core.parse_frontmatter("---\nname: x\ndescription: hello\n---\nbody")
    assert (name, desc) == ("x", "hello")
    assert core.parse_frontmatter("no frontmatter here") == ("", "")
