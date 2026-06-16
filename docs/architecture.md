# Pennyworth — Architecture

_Status: early. The core and the pack contract are under construction._

## 1. Philosophy

Pennyworth is a butler-engineer AI companion. The **persona is Alfred**; the **project is
Pennyworth**. The guiding rule is a hard separation:

- The **core** is the butler — platform-agnostic. It knows *how* to serve, not *whom*.
- A **pack** is the household — everything specific to one platform. It teaches the butler
  *whom* he serves.

The core never depends on any pack. A pack may carry private content. With no pack attached,
Pennyworth is a competent, generic engineering companion — that is the out-of-the-box
experience.

## 2. Two layers

### Core (this repo)
- **Persona & prompt assembly** — the Alfred character, the operating priorities, the rules
  scaffold, output formatting, execution modes, and persona overlays.
- **Agent runner** — drives the underlying coding agent.
- **Surfaces** — CLI, TUI, and chat.
- **Profile & identity machinery** — who the assistant is talking to.
- **Pack loader** — discovers, validates, and injects the active pack.

Every platform-specific seam in the prompt is filled from the active pack (or left in a
sensible generic default when no pack is attached).

### Packs
A pack is a directory plus a manifest. A first cut of the contract:

```
my-pack/
  pennyworth-pack.toml   # manifest: name, platform name/blurb, identity rules, principal
  persona.md             # optional persona overlay / platform binding prose
  skills/*.md            # the platform's skill library
  team.json              # the team directory (roster, roles)
  repos.toml             # repository inventory: path keys + how to scan each
  mcp.toml               # MCP tool servers that act as the assistant's "hands"
  ci.toml                # CI provider + configuration
  identity.toml          # bot commit identity, cloud profile names, principal
```

Concepts a pack can declare:
- **Platform identity** — name and blurb that bind the generic persona to a specific platform.
- **Skills** — on-demand reference content the assistant reads before acting in a domain.
- **Team & principal** — the directory of people, and optionally a *principal*: a primary user
  the assistant treats specially (with a private overlay, kept in the pack).
- **Repositories** — the layout the assistant scans to build a live inventory.
- **Hands (MCP)** — one or more MCP tool servers the assistant operates the platform through.
  This is the boundary the core talks across, so **the core never imports platform tooling**.
- **CI** — the provider and configuration for build/deploy diagnosis.

## 3. Attach / detach

```
alfred pack attach <path|git-url>   # install into the local pack store, mark active
alfred pack detach <name>
alfred pack list
```

Packs live in a per-user pack store; the active pack is recorded in the user profile. Two
mechanisms already common to companions of this kind — loading user-local skills, and
overriding the team directory locally — generalise into this single pack abstraction.

## 4. Design principles

1. **Core depends on no pack.** The dependency arrow points one way: packs depend on core.
2. **The MCP boundary is the contract for "hands."** Platform tooling is invoked, never
   imported.
3. **A pack may be private.** Open-source core, closed-source pack is a supported shape.
4. **Generic-by-default.** Every pack-filled seam has a platform-neutral fallback so the
   no-pack experience is coherent.
5. **No platform specifics in core.** Names, repos, teams, and tooling of any particular
   platform belong in a pack, never here.

## 5. Roadmap

1. **Core prompt assembly behind a `Pack` interface**, with a generic default pack.
2. **Pack manifest + loader**, and the `attach` / `detach` / `list` commands.
3. **A reference pack** demonstrating the contract end to end.
4. **Surfaces, voice, and execution modes** wired to the core.
5. **Open-source hardening** — license, contribution guide, CI, first-run onboarding.

## 6. Open items

- License copyright holder.
- Pack versioning and the core-version range a pack pins.
- Final manifest schema (section 2 is a first cut).
- The default, no-pack persona binding.
