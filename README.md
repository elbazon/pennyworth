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

## Quickstart

Pennyworth drives a host coding agent (the Claude Code CLI, `claude`, by default)
with Alfred's assembled prompt.

```bash
alfred run "explain this repo"     # one-shot request, answered as Alfred
alfred chat                        # interactive session
alfred prompt                      # print the assembled system prompt

alfred pack attach examples/acme   # teach Alfred a platform
alfred pack list
alfred pack detach                 # back to the generic butler
```

Set `PENNYWORTH_AGENT` to point at a different agent CLI. Packs install under
`PENNYWORTH_HOME` (default `~/.pennyworth`).

## Status

Early but runnable: the persona, the pack mechanism, and the agent runner work
end to end. The pack contract grows seam by seam — see the architecture doc for
the roadmap.

## License

Apache-2.0 (planned). Created by Haim Elbaz.
