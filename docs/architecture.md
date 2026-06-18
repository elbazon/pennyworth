# Pennyworth — Architecture

_Status: v0.1.0 — runnable. The persona, the pack mechanism (identity, principal,
skills, team, repositories), the agent runner, and a desktop app are implemented;
the pack contract grows seam by seam._

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
A pack is a directory plus a manifest. The shipped contract is a single
`pennyworth-pack.toml` that carries the platform identity and the repository
inventory inline, alongside a few well-known sibling files:

```
my-pack/
  pennyworth-pack.toml   # [pack] name, platform_name, platform_blurb, principal_file
                         #   + [[repos]] inventory (name / path / description), inline
  principal.md           # optional: a primary user the assistant treats specially
                         #   (path set by [pack].principal_file; may be private)
  team.json              # optional: { "members": [{ "name", "title" }] }
  skills/*.md            # optional: the platform's skill library (frontmatter: name, description)
                         # + [[hands]] MCP tool-server index, inline in the manifest
```

Implemented seams a pack can declare today:
- **Platform identity** — `platform_name` and `platform_blurb` that bind the generic persona
  to a specific platform.
- **Repositories** — the `[[repos]]` inventory the assistant works in.
- **Skills** — on-demand reference content (`skills/*.md`) the assistant reads before acting in
  a domain; the brain renders an index, never the contents.
- **Team & principal** — the `team.json` roster, and optionally a *principal*: a primary user
  the assistant treats specially (a private overlay, kept in the pack).
- **Hands (MCP)** — the `[[hands]]` array of MCP tool servers (`name`, `summary`) the assistant
  operates the platform through. This is the boundary the core talks across, so **the core never
  imports platform tooling** — the load-bearing seam the two-layer design is named for.
  **Brain-only today:** the brain renders an *index* (which servers exist, when to reach for
  each); Alfred invokes them via the host agent's MCP tools. Wiring a declared server live into
  the host agent is a separate, later step (see §5).

Designed but **not yet built** (no manifest surface, no loader) — each gated by the clean-brain
test when it lands:
- **CI** — the provider and configuration for build/deploy diagnosis.
- **Identity** — bot commit identity and cloud profile names.

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
5. **No platform specifics in the brain.** The "brain" is the assembled system prompt —
   persona, rules, the skills the core ships, and every section the core emits. Names, repos,
   teams, and tooling of any particular platform belong in a pack, never in the brain.

## 4a. Acceptance: a clean brain

The extraction has a single, mechanical acceptance test: with **no pack** (or the generic
default pack) attached, the **fully assembled prompt** must contain **zero** tokens of any
specific platform — no platform name, no repository, no team member, no tool server, no CI
host. A guard test renders the brain and asserts it is clean; one platform token leaking into
the core is a failing build. "Looks clean" is not the bar — "greps clean" is.

## 5. Roadmap

Done in v0.1.0:
- ✅ Core prompt assembly behind a `Pack` interface, with a generic default pack.
- ✅ Pack manifest + loader, and `pack attach` / `detach` / `list`.
- ✅ Seams: persona binding, principal, skills, team, repositories.
- ✅ A reference pack (`examples/acme`) demonstrating the contract end to end.
- ✅ The agent runner (drives the host coding agent) + CLI (`run` / `chat`).
- ✅ A clean, unbranded desktop app (`alfred app`): streaming token output,
  markdown + code-copy rendering, a per-reply reasoning drawer (thinking + tool
  activity) and cost, persisted multi-chat (restore/rename/delete), and Skills /
  Settings / About panels.
- ✅ Per-user profile (name + form of address) so the no-pack butler addresses
  you correctly — host config under `PENNYWORTH_HOME`, not a pack (`alfred profile`).
- ✅ CI: ruff + the test suite on every push/PR across Python 3.11–3.13.
- ✅ The **Hands (MCP)** seam, brain-only: a pack's `[[hands]]` index reaches the
  brain (which tool servers exist, when to reach for each), gated by the
  clean-brain test. The core never imports platform tooling.

Next:
- **Wire the Hands seam live** — configure the host agent from a pack's declared
  MCP servers so their tools are callable, not just indexed. This is the seam's
  transport half; the contract surface and index already ship.
- The remaining seams (CI, identity), each gated by the clean-brain test.
- Packaging & distribution (PyPI/release wheels), contribution guide.

## 6. Open items

- License copyright holder (the LICENSE currently credits the author + contributors).
- Pack versioning and the core-version range a pack pins.
- The manifest schema is a first cut and will grow with the contract.
