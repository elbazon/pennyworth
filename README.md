# Pennyworth

[![CI](https://github.com/elbazon/pennyworth/actions/workflows/ci.yml/badge.svg)](https://github.com/elbazon/pennyworth/actions/workflows/ci.yml)
&nbsp;[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
&nbsp;[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

> **Pennyworth** — a dignified butler-engineer for your codebase. He reads, writes, and
> reviews code, navigates architecture, runs your terminal, and learns your domain —
> in the unflappable voice of a proper manservant.

![Pennyworth — the open-source desktop app](docs/images/app-overview.png)

**Pennyworth** is the open-source project, the Python package, and the assistant you
talk to. His full name is Alfred Pennyworth, the gentleman's butler — but he goes by
Pennyworth. You install the package and run the `pennyworth` command (`alfred` still
works as an alias).

Under the hood, Pennyworth drives a host coding agent (the
[Claude Code](https://claude.com/claude-code) CLI by default) with a carefully
assembled system prompt — his "brain". Your code, chats, and knowledge stay on your
machine.

## Why Pennyworth

- 🗣️ **A plain-language pair.** Ask in English — he explains, writes, reviews, and
  fixes across your repositories, streaming his reasoning as he goes.
- 🧠 **He learns your domain.** The **Knowledge** panel injects your glossary,
  conventions, and architecture into every turn — no fine-tuning, no code change.
- 🖥️ **A real desktop app.** A native window with streaming chat, visible extended
  thinking, an embedded terminal, multi-chat, per-chat model / persona / effort,
  and custom themes.
- 🦇 **He knows your repos.** Point him at your repositories; he works in them
  directly and shows each one's git state at a glance.
- 🧩 **Yours to extend.** Teachable skills, personas, and MCP tools — and a *pack*
  makes him fluent in an entire platform (team, CI, tooling, and all).
- 🔒 **Local and private.** Your profile, chats, settings, and knowledge live on
  your machine; nothing is sent anywhere except your own agent.

## Quickstart

You need **Python 3.11+** and the **Claude CLI signed in** (`claude auth login`).
The desktop app is **macOS**; the command line runs anywhere.

```bash
pipx install 'pennyworth-ai[app]'  # install Pennyworth, with the desktop app
pennyworth app                     # launch the app (command is still `pennyworth`)
```

A window opens to the welcome screen — type a request like *"explain this codebase"*
or *"review my changes"*, and Pennyworth replies. New here?
→ **[Getting started](docs/getting-started.md)**.

**Prefer the terminal?** The command line ships in the same package:

```bash
pennyworth "explain this repo"     # one-shot, answered in character
pennyworth chat                    # interactive session
```

## Documentation

- **[Getting started](docs/getting-started.md)** — prerequisites, install, first run.
- **[Desktop app tour](docs/desktop-app.md)** — every panel, the terminal, models, themes.
- **[Teach Pennyworth your domain](docs/knowledge.md)** — the Knowledge panel.
- **[Build a pack](#build-a-pack)** — make Pennyworth fluent in your whole platform.
- **[Architecture](docs/architecture.md)** — how the brain is assembled, and the one rule.
- **[Contributing](CONTRIBUTING.md)** — how to help.

## The one rule

**The brain is clean by construction.** With no pack attached, the assembled prompt
contains zero platform specifics — no platform name, no repository, no teammate, no
tool. Everything a platform contributes flows through its pack and *only* through its
pack. A test (`tests/test_clean_brain.py`) enforces it. This is what lets the project
be open while a company's specifics stay in a private pack.

## Build a pack

A pack teaches Pennyworth a whole platform — its identity, repositories, team, CI, and
tools. It's a directory with a manifest; see [`examples/acme`](examples/acme) for a
complete one.

```toml
# pennyworth-pack.toml
[pack]
name = "acme"
platform_name = "the Acme platform"
platform_blurb = "A Python + React monorepo with a REST API and a Postgres store."

[ci]
provider = "GitHub Actions"
host = "https://github.com/acme/acme/actions"

[[repos]]
name = "acme-api"
path = "~/code/acme-api"
description = "The REST API service."

[[hands]]                  # an MCP tool server Pennyworth operates the platform through
name = "github"
summary = "Pull requests, issues, and CI status."
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
```

Attach it from the CLI, and detach to return to the generic butler:

```bash
pennyworth pack attach ./my-pack
pennyworth pack list
pennyworth pack detach
```

Each piece fills a *seam* in the brain — persona, principal, attribution, skills,
team, repositories, hands (MCP), CI — and is simply absent when the pack omits it.
A pack may be private: **open-source core, closed-source pack** is a supported shape.

## How it fits together

- **Core (this repo)** — the persona, the prompt assembly, the pack loader, the
  agent runner, and the surfaces (desktop app + CLI). Platform-agnostic; depends on
  no pack.
- **Packs** — what teach Pennyworth a specific platform.

See [`docs/architecture.md`](docs/architecture.md) for the design.

## Status & roadmap

**v0.1.0 — runnable today.** The desktop app works end to end: streaming chat with
visible thinking, the embedded terminal, per-chat model/persona/effort, configured
repositories, the repo-focused Batcave, Claude usage, custom themes, saved chats, and
the Knowledge panel. The first-cut pack contract is complete and guarded by the
clean-brain test; CI runs lint, format, and the test suite across Python 3.11–3.13.

Honest about the edges: a few panels are graceful stubs — **Connectors** (MCP
management), **Scheduled** firing, and **slash commands** — and the desktop app is
macOS-only for now. On the roadmap: those stubs and **multi-provider support**
(OpenAI and local LLMs behind the runner seam, alongside Claude).

## Contributing

Contributions are very welcome — see **[CONTRIBUTING.md](CONTRIBUTING.md)**. Fork,
branch, and open a pull request; sign off your commits (`git commit -s`) to certify
you wrote the change (a one-line [DCO](https://developercertificate.org/), **no CLA**).
Good first steps: try the app, file what feels rough, or pick up a roadmap item.

## License & credits

**Created by Haim Elbaz**, with development assistance from Claude (Anthropic).

Licensed under the **[Apache License 2.0](LICENSE)** — free to use, modify, and
redistribute, including commercially, provided you keep the copyright notice and the
[`NOTICE`](NOTICE) attribution. The names "Pennyworth" and "Alfred" and the branding
are reserved — see **[TRADEMARK.md](TRADEMARK.md)**.

Pennyworth is written in admiration of the classic gentleman's-butler tradition.
"Batman", "Alfred Pennyworth", and "Batcave" are trademarks of DC Comics /
Warner Bros., referenced here purely as an affectionate homage — this project is
independent and not affiliated with or endorsed by them. See **[TRADEMARK.md](TRADEMARK.md)**.

Copyright © 2026 Haim Elbaz.
