"""Pack discovery, loading, and the attach/detach store.

A pack on disk is a directory containing a ``pennyworth-pack.toml`` manifest.
Attaching one copies it into the per-user pack store and marks it active; the
active pack — or :data:`~pennyworth.pack.NULL_PACK` when none is active — is
what :func:`~pennyworth.prompt.build_system_prompt` serves.

The store lives under ``PENNYWORTH_HOME`` (default ``~/.pennyworth``) so tests
and sandboxes can redirect it freely.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import tomllib

from pennyworth import skills as _skills
from pennyworth.pack import NULL_PACK, Hand, Member, Pack, Repo

MANIFEST_NAME = "pennyworth-pack.toml"
TEAM_FILENAME = "team.json"


def _load_team(pack_dir: Path) -> tuple[Member, ...]:
    """Read ``team.json`` (``{"members": [{"name", "title"}, ...]}``) if present."""
    team_file = pack_dir / TEAM_FILENAME
    if not team_file.is_file():
        return ()
    try:
        data = json.loads(team_file.read_text())
    except (OSError, ValueError):
        return ()
    members: list[Member] = []
    for entry in data.get("members") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        members.append(Member(name=name, title=str(entry.get("title") or "").strip()))
    return tuple(members)


def _load_repos(data: dict) -> tuple[Repo, ...]:
    """Read the manifest's top-level ``[[repos]]`` array of ``{name, path, description}``."""
    repos: list[Repo] = []
    for entry in data.get("repos") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        repos.append(
            Repo(
                name=name,
                path=str(entry.get("path") or "").strip(),
                description=str(entry.get("description") or "").strip(),
            )
        )
    return tuple(repos)


def _load_hands(data: dict) -> tuple[Hand, ...]:
    """Read the manifest's top-level ``[[hands]]`` array.

    Each entry: ``{name, summary}`` plus optional transport — ``command``/``args``
    (stdio) or ``url``/``transport`` (remote). Transport fields are absent on a
    brain-only hand, which is valid.
    """
    hands: list[Hand] = []
    for entry in data.get("hands") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        args = tuple(
            str(a) for a in (entry.get("args") or []) if str(a).strip()
        )
        hands.append(
            Hand(
                name=name,
                summary=str(entry.get("summary") or "").strip(),
                command=str(entry.get("command") or "").strip(),
                args=args,
                url=str(entry.get("url") or "").strip(),
                transport=str(entry.get("transport") or "").strip(),
            )
        )
    return tuple(hands)


def home() -> Path:
    """The Pennyworth home directory (``PENNYWORTH_HOME`` or ``~/.pennyworth``)."""
    return Path(
        os.environ.get("PENNYWORTH_HOME", Path.home() / ".pennyworth")
    ).expanduser()


def packs_dir() -> Path:
    return home() / "packs"


def _config_path() -> Path:
    return home() / "config.toml"


def _load_ci(data: dict) -> tuple[str, str]:
    """Read the manifest's ``[ci]`` table → ``(provider, host)`` (both optional)."""
    ci = data.get("ci") or {}
    if not isinstance(ci, dict):
        return "", ""
    return (
        str(ci.get("provider") or "").strip(),
        str(ci.get("host") or "").strip(),
    )


def _load_block(src: Path, section: dict, key: str) -> str:
    """Read the Markdown file the manifest's ``[pack].<key>`` points to.

    Returns the file's stripped contents, or ``""`` when the key is unset or the
    file is missing. Used for the verbatim-block seams (principal, attribution).
    """
    filename = section.get(key)
    if not filename:
        return ""
    path = src / filename
    return path.read_text().strip() if path.is_file() else ""


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

    ci_provider, ci_host = _load_ci(data)

    return Pack(
        name=name,
        platform_name=str(section.get("platform_name") or "").strip(),
        platform_blurb=str(section.get("platform_blurb") or "").strip(),
        principal_block=_load_block(src, section, "principal_file"),
        attribution_block=_load_block(src, section, "attribution_file"),
        skills=_skills.load_skills(src),
        team=_load_team(src),
        repos=_load_repos(data),
        hands=_load_hands(data),
        ci_provider=ci_provider,
        ci_host=ci_host,
    )


def list_packs() -> list[str]:
    """Names of every installed pack in the store."""
    directory = packs_dir()
    if not directory.is_dir():
        return []
    return sorted(
        child.name for child in directory.iterdir() if (child / MANIFEST_NAME).is_file()
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
