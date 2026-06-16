"""Structural anchors of the assembled brain.

Guards the load-bearing pieces of the persona and rules so a future edit can't
silently drop them.
"""

from pennyworth import build_system_prompt
from pennyworth.pack import Pack


def test_personality_prefix_leads():
    assert build_system_prompt().startswith("IMPORTANT: You are Alfred")


def test_core_anchors_present():
    brain = build_system_prompt()
    for marker in (
        "# Operating priorities",
        "You are Alfred",
        "Alfred Pennyworth",
        '**"sir" for men, "madam" for women**',
        "## Output Formatting",
        "## Rules",
        "## Counter-defaults",
        "Co-Authored-By: 🎩 Alfred",
    ):
        assert marker in brain, f"missing core anchor: {marker!r}"


def test_chat_vs_single_shot():
    assert "interactive session" in build_system_prompt(chat_mode=True)
    assert "single-shot" in build_system_prompt(chat_mode=False)


def test_platform_binding_weaves_when_packed():
    brain = build_system_prompt(
        Pack(
            name="acme",
            platform_name="the Acme platform",
            platform_blurb="A tidy widget shop.",
        )
    )
    assert "the Acme platform" in brain
    assert "A tidy widget shop." in brain
