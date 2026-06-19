# Pennyworth

[![CI](https://github.com/greeninvoice/pennyworth/actions/workflows/ci.yml/badge.svg)](https://github.com/greeninvoice/pennyworth/actions/workflows/ci.yml)

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
  pennyworth-pack.toml   # name, platform identity, repositories, hands, CI
  principal.md           # optional: a primary user Alfred treats specially
  attribution.md         # optional: commit/PR attribution & identity policy
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
attribution_file = "attribution.md"

[ci]                       # which CI provider runs the builds, and where
provider = "GitHub Actions"
host = "https://github.com/acme/acme/actions"

[[repos]]
name = "acme-api"
path = "~/code/acme-api"
description = "The REST API service."

[[hands]]                  # an MCP tool server Alfred operates the platform through
name = "github"
summary = "Pull requests, issues, and CI status."
command = "npx"            # stdio transport (or set `url` for a remote server)
args = ["-y", "@modelcontextprotocol/server-github"]
```

Each piece fills a *seam* in the brain — persona binding, principal, attribution,
skills, team, repositories, hands (MCP), CI — and is absent when the pack omits
it. A pack may be private: open-source core, closed-source pack is a supported
shape.

## How it fits together

- **Core (this repo)** — the persona, the prompt assembly, the pack loader, the
  agent runner, and the surfaces (CLI + desktop app). Platform-agnostic; depends
  on no pack.
- **Packs** — what teach Alfred a specific platform.

See [`docs/architecture.md`](docs/architecture.md) for the design.

## Knowledge — teach Alfred your domain

The desktop app has a **Knowledge** panel: free-form notes about your platform —
glossary, conventions, architecture, do's and don'ts — injected into Alfred's
prompt at the start of every turn, with no code change and no pack. Add them
inline, **import** a file, or **link** a file (re-read live each turn, so editing
it updates Alfred immediately); enable/disable, edit, and export each entry.
Stored locally under `PENNYWORTH_HOME/app/knowledge.json`.

## Status

v0.1.0 — runnable. The persona, the per-user profile, the agent runner, and the
full desktop app all work end to end: streaming chat with visible extended
thinking, an embedded terminal, per-chat model/persona/effort, configured
repositories handed to the agent as working directories, a repo-focused Batcave,
Claude usage, custom themes, scheduled prompts, and the Knowledge panel. The
first-cut pack contract is complete: every seam — principal, attribution/identity,
skills, team, repositories, hands (MCP, with live wiring into the host agent), and
CI — is built and guarded by the clean-brain test. CI runs ruff + the test suite
on every push and pull request across Python 3.11–3.13. Next: packaging for PyPI.

## License

[Apache-2.0](LICENSE). Created by Haim Elbaz.
