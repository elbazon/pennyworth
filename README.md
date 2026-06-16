# Pennyworth

> A dignified butler-engineer AI companion for your platform. You talk to **Alfred**; the project is **Pennyworth**.

Pennyworth is an open-source engineering companion. It reads, writes, and reviews
code, navigates architecture, diagnoses CI, and shepherds changes — in the
unflappable voice of a proper manservant. It drives a host coding agent (the
[Claude Code](https://claude.com/claude-code) CLI by default) with a carefully
assembled system prompt — Alfred's "brain".

Everything platform-specific lives in a **pack** you attach or detach. Out of the
box, Pennyworth is the full Alfred character serving a generic, unconfigured
platform. Attach a pack and he becomes fluent in *your* codebase, your team, and
your tooling — and `detach` returns him to clean.

## The one rule

**The brain is clean by construction.** With no pack attached, the assembled
prompt contains zero platform specifics — no platform name, no repository, no
teammate, no tool. Everything a platform contributes flows through its pack and
*only* through its pack. A test (`tests/test_clean_brain.py`) enforces it.

## Install

```bash
pipx install pennyworth            # the CLI
pipx install 'pennyworth[app]'     # CLI + the desktop app (pywebview)
```

From a clone, for development:

```bash
poetry install --extras app
poetry run alfred --version
```

The agent runner shells out to `claude` by default; install the Claude Code CLI,
or point `PENNYWORTH_AGENT` at another agent command.

## Use

```bash
alfred run "explain this repo"     # one-shot, answered as Alfred
alfred chat                        # interactive session
alfred app                         # the desktop app (needs the 'app' extra)
alfred prompt                      # print the assembled brain for the active pack

alfred pack attach examples/acme   # teach Alfred a platform
alfred pack list
alfred pack detach                 # back to the generic butler

alfred profile set --name Haim --address sir   # how Alfred addresses you
alfred profile show
alfred profile clear
```

Packs and your profile install under `PENNYWORTH_HOME` (default `~/.pennyworth`).
A bare `alfred "<request>"` is shorthand for `alfred run`. With no profile set,
Alfred falls back to the generic address rule (sir/madam, asking once when
unsure).

## Build a pack

A pack is a directory with a manifest. See [`examples/acme`](examples/acme) for a
complete one.

```
my-pack/
  pennyworth-pack.toml   # name, platform identity, repositories
  principal.md           # optional: a primary user Alfred treats specially
  team.json              # optional: { "members": [{ "name", "title" }] }
  skills/*.md            # optional: on-demand reference docs (frontmatter: name, description)
```

```toml
# pennyworth-pack.toml
[pack]
name = "acme"
platform_name = "the Acme platform"
platform_blurb = "A Python + React monorepo with a REST API and a Postgres store."
principal_file = "principal.md"

[[repos]]
name = "acme-api"
path = "~/code/acme-api"
description = "The REST API service."
```

Each piece fills a *seam* in the brain — persona binding, principal, skills,
team, repositories — and is absent when the pack omits it. A pack may be private:
open-source core, closed-source pack is a supported shape.

## How it fits together

- **Core (this repo)** — the persona, the prompt assembly, the pack loader, the
  agent runner, and the surfaces (CLI + desktop app). Platform-agnostic; depends
  on no pack.
- **Packs** — what teach Alfred a specific platform.

See [`docs/architecture.md`](docs/architecture.md) for the design.

## Status

v0.1.0 — runnable. The persona, the pack mechanism (identity, principal, skills,
team, repositories), the agent runner, and a desktop app all work end to end. The
pack contract grows seam by seam.

## License

[Apache-2.0](LICENSE). Created by Haim Elbaz.
