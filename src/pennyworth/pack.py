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
class Skill:
    """A single on-demand reference document a pack provides.

    Skills are not inlined into the brain — only an index of them is. The brain
    tells Alfred *when* to read each one and *where* it lives, and he reads it
    via the host agent's file tools at the moment a task matches.

    Attributes:
        name: Short identifier (the file stem if the frontmatter omits one).
        description: An action-bound "when to engage this" line, shown in the
            Skill Library index.
        path: Absolute path to the Markdown file on disk.
    """

    name: str
    description: str
    path: str


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
        skills: The pack's on-demand reference documents. The brain renders an
            index of these (never their contents); empty means no Skill Library
            section at all.
    """

    name: str = ""
    platform_name: str = ""
    platform_blurb: str = ""
    principal_block: str = ""
    skills: tuple[Skill, ...] = ()

    @property
    def is_attached(self) -> bool:
        """True when a real pack is in effect (it has a name)."""
        return bool(self.name)


#: The open-source default: no platform attached. The brain built around this
#: pack is, by construction, free of any platform specifics.
NULL_PACK = Pack()
