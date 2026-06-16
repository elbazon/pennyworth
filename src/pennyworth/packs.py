"""Pack discovery, loading, and the attach/detach store.

A pack on disk is a directory containing a ``pennyworth-pack.toml`` manifest.
Attaching one copies it into the per-user pack store and marks it active; the
active pack — or :data:`~pennyworth.pack.NULL_PACK` when none is active — is
what :func:`~pennyworth.prompt.build_system_prompt` serves.

The store lives under ``PENNYWORTH_HOME`` (default ``~/.pennyworth``) so tests
and sandboxes can redirect it freely.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import tomllib

from pennyworth.pack import NULL_PACK, Pack, Skill

MANIFEST_NAME = "pennyworth-pack.toml"
SKILLS_DIRNAME = "skills"


def _parse_frontmatter(text: str) -> tuple[str, str]:
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


def _load_skills(pack_dir: Path) -> tuple[Skill, ...]:
    """Discover ``skills/*.md`` under a pack directory, in filename order."""
    skills_dir = pack_dir / SKILLS_DIRNAME
    if not skills_dir.is_dir():
        return ()
    skills: list[Skill] = []
    for path in sorted(skills_dir.glob("*.md")):
        try:
            name, description = _parse_frontmatter(path.read_text())
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


def home() -> Path:
    """The Pennyworth home directory (``PENNYWORTH_HOME`` or ``~/.pennyworth``)."""
    return Path(
        os.environ.get("PENNYWORTH_HOME", Path.home() / ".pennyworth")
    ).expanduser()


def packs_dir() -> Path:
    return home() / "packs"


def _config_path() -> Path:
    return home() / "config.toml"


def load_pack(path: str | Path) -> Pack:
    """Load a :class:`Pack` from a directory containing a manifest.

    Raises:
        FileNotFoundError: the directory has no manifest.
        ValueError: the manifest is missing a required field.
    """
    src = Path(path).expanduser()
    manifest = src / MANIFEST_NAME
    if not manifest.is_file():
        raise FileNotFoundError(f"no {MANIFEST_NAME} found in {src}")
    data = tomllib.loads(manifest.read_text())
    section = data.get("pack", {})

    name = str(section.get("name") or "").strip()
    if not name:
        raise ValueError(f"{manifest}: [pack].name is required")

    principal_block = ""
    principal_file = section.get("principal_file")
    if principal_file:
        principal_path = src / principal_file
        if principal_path.is_file():
            principal_block = principal_path.read_text().strip()

    return Pack(
        name=name,
        platform_name=str(section.get("platform_name") or "").strip(),
        platform_blurb=str(section.get("platform_blurb") or "").strip(),
        principal_block=principal_block,
        skills=_load_skills(src),
    )


def list_packs() -> list[str]:
    """Names of every installed pack in the store."""
    directory = packs_dir()
    if not directory.is_dir():
        return []
    return sorted(
        child.name
        for child in directory.iterdir()
        if (child / MANIFEST_NAME).is_file()
    )


def active_name() -> str:
    """Name of the active pack, or ``""`` if none is active."""
    config = _config_path()
    if not config.is_file():
        return ""
    return str(tomllib.loads(config.read_text()).get("active_pack") or "").strip()


def _set_active(name: str) -> None:
    home().mkdir(parents=True, exist_ok=True)
    _config_path().write_text(f'active_pack = "{name}"\n')


def active_pack() -> Pack:
    """The active pack loaded from the store, or :data:`NULL_PACK` when none."""
    name = active_name()
    if not name:
        return NULL_PACK
    target = packs_dir() / name
    if not (target / MANIFEST_NAME).is_file():
        return NULL_PACK
    return load_pack(target)


def attach(path: str | Path) -> Pack:
    """Install a pack into the store and make it active.

    The manifest is validated before anything is copied.
    """
    pack = load_pack(path)
    src = Path(path).expanduser()
    dest = packs_dir() / pack.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.resolve() != src.resolve():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    _set_active(pack.name)
    return pack


def detach() -> None:
    """Detach the active pack. Alfred falls back to the generic (no-pack) brain.

    Clears the active pointer; installed pack files are left in the store so the
    pack can be re-activated later.
    """
    _set_active("")
