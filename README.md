# Pennyworth

> A dignified butler-engineer AI companion for your platform. You talk to **Alfred**; the project is **Pennyworth**.

Pennyworth is an open-source engineering companion. It spins up and tends development
environments, deploys and debugs services, reads, writes, and reviews code, navigates
architecture end to end, diagnoses CI, and shepherds pull requests — all in the unflappable
voice of a proper manservant.

Everything platform-specific lives in a **pack** you attach or detach. Out of the box,
Pennyworth is the full Alfred character serving a generic, unconfigured platform. Attach a
pack and he becomes fluent in *your* codebase, your team, and your tooling.

## How it works

- **Core (this repo)** — the persona, the prompt assembly, the agent runner, the surfaces
  (CLI / TUI / chat), and the **pack loader**. Entirely platform-agnostic.
- **Packs** — a directory plus a manifest that teaches Alfred one platform: its skills, team
  directory, repository layout, tool servers (over MCP), and CI. Attach with
  `alfred pack attach`, detach with `alfred pack detach`.

The core never depends on any pack, and a pack can carry private content for its own
platform. See [`docs/architecture.md`](docs/architecture.md) for the design.

## Status

Early. The core and the pack contract are under construction — see the architecture doc for
the roadmap.

## License

Apache-2.0 (planned). Created by Haim Elbaz.
