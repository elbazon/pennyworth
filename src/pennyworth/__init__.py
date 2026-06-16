"""Pennyworth — the open-source core of Alfred, a butler-engineer AI companion.

The persona is **Alfred**; the project is **Pennyworth**. The core is
platform-agnostic: it knows *how* to serve, not *whom*. Everything specific to
a platform arrives through a :class:`~pennyworth.pack.Pack`. With no pack
attached, the assembled prompt — the "brain" — contains zero platform
specifics. That is enforced, not merely intended (see ``tests/test_clean_brain.py``).
"""

from pennyworth.pack import NULL_PACK, Pack
from pennyworth.prompt import build_system_prompt

__all__ = ["Pack", "NULL_PACK", "build_system_prompt", "__version__"]
__version__ = "0.1.0"
