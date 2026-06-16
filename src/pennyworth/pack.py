"""The pack contract: how a platform teaches Alfred whom he serves.

A :class:`Pack` supplies the platform-specific *seams* that the core weaves
into the assembled prompt. The core depends on this interface and never on any
concrete pack — the dependency arrow points one way (packs depend on core).

The default, :data:`NULL_PACK`, leaves every seam empty. A brain assembled
around it is generic and contains **no** platform specifics whatsoever — the
out-of-the-box Pennyworth experience, and the thing the clean-brain test
guards. A real platform ships its own pack (which may be private) with these
fields populated, or subclasses :class:`Pack` to compute them dynamically.

Today the contract covers only the persona-binding seams. It grows seam by
seam as content is migrated out of a host's brain and into its pack
(skills, team directory, repository inventory, MCP "hands", CI). Each new
seam follows the same rule: empty default in the core, real value in the pack.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pack:
    """A platform knowledge pack.

    Every field defaults to empty — that default *is* the generic, platform-free
    behaviour. A field left empty tells the core "use your neutral default for
    this seam"; a populated field is woven into the prompt in its place.

    Attributes:
        name: Short identifier for the pack (e.g. ``"acme"``). Empty means no
            pack is attached.
        platform_name: How the platform is referred to in prose, e.g.
            ``"the Acme platform"``. Woven into the persona binding.
        platform_blurb: One sentence describing what the platform is — the
            stack, the surfaces, what Alfred tends. Woven into the persona
            binding when present.
        principal_block: An optional, verbatim Markdown block describing a
            *principal* — a primary user Alfred treats specially. Packs may
            keep this private; the core only injects whatever string it is
            given, and injects nothing when it is empty.
    """

    name: str = ""
    platform_name: str = ""
    platform_blurb: str = ""
    principal_block: str = ""

    @property
    def is_attached(self) -> bool:
        """True when a real pack is in effect (it has a name)."""
        return bool(self.name)


#: The open-source default: no platform attached. The brain built around this
#: pack is, by construction, free of any platform specifics.
NULL_PACK = Pack()
