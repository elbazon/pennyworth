"""The clean-brain guarantee.

The central acceptance criterion for Pennyworth: with no pack attached, the
assembled brain contains zero platform specifics. Everything a platform
contributes flows through the pack and *only* through the pack — never compiled
into the core.

This file proves the mechanism with neutral sentinels. It deliberately names no
real platform: the open-source repo must itself stay free of any specific
platform's vocabulary. Scanning a rendered brain for a *particular* platform's
words (a literal-leak grep) is a concern for that platform's pack/CI, kept out
of here on purpose.
"""

from pennyworth import NULL_PACK, build_system_prompt
from pennyworth.pack import Member, Pack, Repo, Skill

# Stand-ins for whatever a real (possibly private) pack would inject.
_SENTINELS = {
    "platform_name": "the ACME-PLATFORM-SENTINEL",
    "platform_blurb": "It runs the EXAMPLE-STACK-SENTINEL end to end.",
    "principal_block": "## Principal\nThe EXAMPLE-PRINCIPAL-SENTINEL, served specially.",
}
_SKILL = Skill(
    name="sentinel",
    description="SKILL-DESC-SENTINEL — when to engage.",
    path="/tmp/SKILL-PATH-SENTINEL.md",
)
_MEMBER = Member(name="MEMBER-NAME-SENTINEL", title="MEMBER-TITLE-SENTINEL")
_REPO = Repo(
    name="REPO-NAME-SENTINEL",
    path="/tmp/REPO-PATH-SENTINEL",
    description="REPO-DESC-SENTINEL",
)


def _loaded_pack() -> Pack:
    return Pack(
        name="sentinel",
        skills=(_SKILL,),
        team=(_MEMBER,),
        repos=(_REPO,),
        **_SENTINELS,
    )


def _all_pack_lines() -> list[str]:
    lines = [line for value in _SENTINELS.values() for line in value.splitlines()]
    lines += [_SKILL.description, _SKILL.path]
    lines += [_MEMBER.name, _MEMBER.title, _REPO.name, _REPO.path, _REPO.description]
    return lines


def test_attached_pack_content_reaches_the_brain():
    brain = build_system_prompt(_loaded_pack())
    for value in _SENTINELS.values():
        fragment = value.splitlines()[0]
        assert fragment in brain, f"pack seam did not reach the brain: {fragment!r}"
    for fragment in (
        _SKILL.description,
        _SKILL.path,
        _MEMBER.name,
        _REPO.name,
        _REPO.description,
    ):
        assert fragment in brain, f"pack seam did not reach the brain: {fragment!r}"


def test_null_brain_is_free_of_all_pack_content():
    """With no pack, none of a pack's content survives anywhere in the brain."""
    brain = build_system_prompt(NULL_PACK)
    for line in _all_pack_lines():
        assert line not in brain, (
            f"null brain leaked pack content: {line!r} — a platform seam is "
            "hard-coded into the core instead of arriving from the pack."
        )


def test_null_brain_names_no_platform():
    """A no-pack brain claims to serve a generic codebase, never a named platform,
    and carries no principal block."""
    brain = build_system_prompt(NULL_PACK)
    assert "across the developer's codebase and tooling" in brain
    assert "## Principal" not in brain
    assert "## Skill Library" not in brain
    assert "## The Team" not in brain
    assert "## Repositories" not in brain
