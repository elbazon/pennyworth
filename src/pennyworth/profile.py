"""The per-user profile: who is at the keyboard, and how to address them.

This is **host-side** configuration, distinct from a pack. A pack's
``principal_block`` describes a *platform's* principal (whom that platform
serves); the profile describes the *local human* using this Pennyworth and the
honorific Pennyworth should use for them. It lives under ``PENNYWORTH_HOME`` so it
belongs to the user, not to any pack — switch packs and your profile stays.

With no profile set, the brain falls back to the persona's generic rule:
"sir"/"madam", asking once when unsure.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import tomllib

from pennyworth.packs import home

PROFILE_FILENAME = "profile.toml"

#: The honorifics a profile may store. Empty means "unset — ask once".
VALID_ADDRESSES = ("sir", "madam")


@dataclass(frozen=True)
class Profile:
    """The local user's identity for address purposes.

    Attributes:
        name: The user's name (may be empty).
        address: The honorific to use — ``"sir"``, ``"madam"``, or ``""`` when
            unset (the persona then asks once).
    """

    name: str = ""
    address: str = ""

    @property
    def is_set(self) -> bool:
        """True when the profile carries anything worth rendering."""
        return bool(self.name or self.address)


#: The default: nothing configured. The brain uses the generic address rule.
NULL_PROFILE = Profile()


def profile_path() -> Path:
    """Where the profile is stored (``$PENNYWORTH_HOME/profile.toml``)."""
    return home() / PROFILE_FILENAME


def _normalize_address(address: str) -> str:
    """Validate and canonicalize an honorific. Empty clears it."""
    address = (address or "").strip().lower()
    if address and address not in VALID_ADDRESSES:
        raise ValueError(
            f"address must be one of {', '.join(VALID_ADDRESSES)} (or empty), "
            f"not {address!r}"
        )
    return address


def _toml_escape(value: str) -> str:
    """Escape a string for a double-quoted TOML value."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def load_profile() -> Profile:
    """The stored profile, or :data:`NULL_PROFILE` when none/unreadable.

    An out-of-range honorific on disk is dropped rather than raising — a
    hand-edited file should degrade to the generic rule, not crash the brain.
    """
    path = profile_path()
    if not path.is_file():
        return NULL_PROFILE
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        return NULL_PROFILE
    name = str(data.get("name") or "").strip()
    address = str(data.get("address") or "").strip().lower()
    if address not in VALID_ADDRESSES:
        address = ""
    return Profile(name=name, address=address)


def active_profile() -> Profile:
    """The active per-user profile (alias of :func:`load_profile`)."""
    return load_profile()


def save_profile(profile: Profile) -> Profile:
    """Persist ``profile`` to disk, validating the honorific. Returns the
    normalized profile actually written."""
    profile = replace(
        profile,
        name=profile.name.strip(),
        address=_normalize_address(profile.address),
    )
    home().mkdir(parents=True, exist_ok=True)
    lines = []
    if profile.name:
        lines.append(f'name = "{_toml_escape(profile.name)}"')
    if profile.address:
        lines.append(f'address = "{profile.address}"')
    profile_path().write_text("\n".join(lines) + ("\n" if lines else ""))
    return profile


def update_profile(*, name: str | None = None, address: str | None = None) -> Profile:
    """Merge the given fields into the stored profile and persist it.

    A ``None`` field is left untouched; a string (including ``""``) replaces it.
    """
    current = load_profile()
    merged = replace(
        current,
        name=current.name if name is None else name,
        address=current.address if address is None else address,
    )
    return save_profile(merged)


def clear_profile() -> None:
    """Remove the stored profile. Pennyworth falls back to the generic address rule."""
    path = profile_path()
    if path.is_file():
        path.unlink()
