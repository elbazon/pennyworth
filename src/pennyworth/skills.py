"""Skill discovery — parse frontmatter, load a ``skills/`` directory, and the
built-in *core* skills shipped with Pennyworth.

Core skills are platform-agnostic craft (how to investigate, write a PR, judge
whether to build). They ship with the core and appear in every brain. Packs add
their own platform-specific skills on top. Both are only *indexed* in the brain —
their bodies are read on demand.
"""

from __future__ import annotations

from pathlib import Path

from pennyworth.pack import Skill

SKILLS_DIRNAME = "skills"


def parse_frontmatter(text: str) -> tuple[str, str]:
    """Return ``(name, description)`` from a Markdown file's frontmatter.

    Only the leading ``---`` … ``---`` block is inspected, and only the ``name``
    and ``description`` keys are read. Missing keys yield ``""``.
    """
    name = description = ""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return name, description
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        key = key.strip().lower()
        if key == "name":
            name = value.strip()
        elif key == "description":
            description = value.strip()
    return name, description


def load_skills(base_dir: Path | str) -> tuple[Skill, ...]:
    """Discover ``<base_dir>/skills/*.md``, in filename order."""
    skills_dir = Path(base_dir) / SKILLS_DIRNAME
    if not skills_dir.is_dir():
        return ()
    skills: list[Skill] = []
    for path in sorted(skills_dir.glob("*.md")):
        try:
            name, description = parse_frontmatter(path.read_text())
        except OSError:
            continue
        skills.append(
            Skill(
                name=name or path.stem,
                description=description or "(no description)",
                path=str(path),
            )
        )
    return tuple(skills)


def core_skills() -> tuple[Skill, ...]:
    """The built-in craft skills shipped with the core (no platform specifics)."""
    return load_skills(Path(__file__).parent)
