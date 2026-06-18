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
class Member:
    """A person on the platform's team, for the roster the brain renders.

    Attributes:
        name: The person's name.
        title: Their role/title (may be empty).
    """

    name: str
    title: str = ""


@dataclass(frozen=True)
class Repo:
    """A repository the platform works in, for the inventory the brain renders.

    Attributes:
        name: How the repository is referred to.
        path: Where it lives on disk (may use ``~``).
        description: One line on what it is (may be empty).
    """

    name: str
    path: str = ""
    description: str = ""


@dataclass(frozen=True)
class Hand:
    """An MCP tool server a pack gives Alfred — his "hands" on the platform.

    The brain only *indexes* hands — ``name`` and ``summary``: it tells Alfred
    which tool servers exist and when to reach for each. The core never imports
    platform tooling — this is the boundary it talks across (design principle
    #2); Alfred invokes the servers through the host agent's own MCP machinery.

    The transport fields below are how a hand becomes *live* rather than merely
    indexed: when present, the runner wires the server into a Claude-protocol
    host agent (via ``--mcp-config``) so its tools are callable. They are never
    rendered into the brain. A hand with only ``name`` + ``summary`` is valid and
    stays brain-only (documented but not auto-wired).

    Two transports are supported:
      * **stdio** — set ``command`` (and optional ``args``); the agent spawns it.
      * **remote** — set ``url`` (and optional ``transport`` = ``"http"`` |
        ``"sse"``, default ``"http"``).
    Secrets are not declared here: the spawned server inherits the host process
    environment, so tokens live in the host env, never in a pack manifest.

    Attributes:
        name: How the tool server is referred to (e.g. ``"teamcity"``).
        summary: One line on what it gives Alfred hands on — when to reach for it.
        command: For a stdio server, the executable to spawn (e.g. ``"npx"``).
        args: Arguments passed to ``command``.
        url: For a remote server, its endpoint URL.
        transport: Remote transport hint — ``"http"`` (default) or ``"sse"``.
    """

    name: str
    summary: str = ""
    command: str = ""
    args: tuple[str, ...] = ()
    url: str = ""
    transport: str = ""

    @property
    def is_wireable(self) -> bool:
        """True when the hand carries enough to wire a live server (not brain-only)."""
        return bool(self.command or self.url)


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
        attribution_block: An optional, verbatim Markdown block stating the
            platform's commit/PR *attribution and identity* policy — which bot
            identity to author commits as, how to credit the requester, any
            cloud-profile conventions. Injected as-is (it carries its own
            heading) and nothing when empty, exactly like ``principal_block``.
            The generic core ships a sensible default attribution rule; this
            seam lets a platform state its own on top.
        skills: The pack's on-demand reference documents. The brain renders an
            index of these (never their contents); empty means no Skill Library
            section at all.
        team: The platform's people, rendered as a roster so Alfred knows the
            team. Empty means no Team section.
        repos: The repositories the platform works in, rendered as an inventory.
            Empty means no Repositories section.
        hands: The MCP tool servers the platform operates through, rendered as an
            index of "hands". Empty means no Hands section.
    """

    name: str = ""
    platform_name: str = ""
    platform_blurb: str = ""
    principal_block: str = ""
    attribution_block: str = ""
    skills: tuple[Skill, ...] = ()
    team: tuple[Member, ...] = ()
    repos: tuple[Repo, ...] = ()
    hands: tuple[Hand, ...] = ()

    @property
    def is_attached(self) -> bool:
        """True when a real pack is in effect (it has a name)."""
        return bool(self.name)


#: The open-source default: no platform attached. The brain built around this
#: pack is, by construction, free of any platform specifics.
NULL_PACK = Pack()
