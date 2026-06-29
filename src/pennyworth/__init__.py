"""Pennyworth — the open-source core of a butler-engineer AI companion.

The persona and the project are both **Pennyworth**, modeled after the
gentleman's butler Alfred Pennyworth. The core is
platform-agnostic: it knows *how* to serve, not *whom*. Everything specific to
a platform arrives through a :class:`~pennyworth.pack.Pack`. With no pack
attached, the assembled prompt — the "brain" — contains zero platform
specifics. That is enforced, not merely intended (see ``tests/test_clean_brain.py``).
"""

from pennyworth.pack import NULL_PACK, Pack
from pennyworth.profile import NULL_PROFILE, Profile
from pennyworth.prompt import build_system_prompt

__all__ = [
    "Pack",
    "NULL_PACK",
    "Profile",
    "NULL_PROFILE",
    "build_system_prompt",
    "__version__",
]
__version__ = "0.1.2"
