# Getting started

This guide takes you from nothing to a working **Pennyworth** — the dignified
butler-engineer — running on your own machine in about five minutes.

> **Pennyworth** is the open-source project, the runtime, and the assistant you
> talk to — modeled on Alfred Pennyworth, the gentleman's butler. The clean core
> is generic; everything platform-specific attaches to it through a *pack*.

## 1. Prerequisites

| Requirement | Why | Check |
|-------------|-----|-------|
| **Python 3.11+** | Pennyworth's runtime | `python3 --version` |
| **A host coding agent** | Pennyworth drives one to do the work — the [Claude Code](https://claude.com/claude-code) CLI by default | `claude --version` |
| **The Claude CLI signed in** | Streaming, models, and the Usage panel read its auth | `claude auth status` |
| **macOS** (for the desktop app) | The app uses pywebview/WebKit; the CLI works anywhere | — |

If `claude` isn't installed, install the Claude Code CLI first (or point
`PENNYWORTH_AGENT` at another agent command — see [configuration](#5-configuration)).

## 2. Install

```bash
pipx install 'pennyworth[app]'     # Pennyworth, with the desktop app (recommended)
pipx install pennyworth            # command line only, no desktop app
```

From a clone, for development:

```bash
git clone https://github.com/elbazon/pennyworth
cd pennyworth
poetry install --extras app
poetry run pennyworth --version
```

> The `pennyworth` command is canonical; `alfred` is kept as an alias, so older
> muscle memory and any scripts still work.

## 3. First run

**The desktop app** (recommended):

```bash
pennyworth app          # or, from a clone:  poetry run pennyworth app
```

A native window opens to the welcome screen. Type a request in plain language —
*"explain this codebase"*, *"review my changes"* — and Pennyworth replies, streaming
his answer. See the [desktop app tour](desktop-app.md) for every panel.

On macOS, the first launch quietly installs **Pennyworth.app** into
`~/Applications` and adds it to the Dock, so you can open it like any other app
next time. Manage that yourself with `pennyworth app --install-shortcut` and
`pennyworth app --uninstall`.

![Pennyworth's welcome screen](images/welcome.png)

**The CLI**, for quick one-shots and scripting:

```bash
pennyworth "explain this repo"     # one-shot, answered in character
pennyworth chat                    # interactive terminal session
pennyworth prompt                  # print the assembled system prompt ("the brain")
```

## 4. Tell Pennyworth who you are

Pennyworth addresses you properly once he knows your name:

```bash
pennyworth profile set --name "Ada" --address madam   # sir / madam
pennyworth profile show
```

In the desktop app this lives under **Settings**. With no profile set, Pennyworth
falls back to the generic address rule and asks once when unsure.

## 5. Configuration

Everything installs under `PENNYWORTH_HOME` (default `~/.pennyworth`):

```
~/.pennyworth/
  profile.toml            # name + how Pennyworth addresses you
  app/
    settings.json         # app preferences (model, thinking, font, theme…)
    chats/                # saved conversations
    knowledge.json        # your domain knowledge (see docs/knowledge.md)
    repos.json            # repositories you've added
  themes/                 # custom colour themes
  packs/                  # attached platform packs
```

Useful environment variables:

- `PENNYWORTH_HOME` — relocate all of the above.
- `PENNYWORTH_AGENT` — the host agent command (default `claude`). Point it at any
  agent that speaks the Claude stream-JSON protocol, or a plain command that
  prints a reply.

## 6. Next steps

- **[Desktop app tour](desktop-app.md)** — chat, terminal, models, personas,
  the Batcave, themes, and more.
- **[Teach Pennyworth your domain](knowledge.md)** — the Knowledge panel: notes that
  get injected into his prompt every turn.
- **[Build a pack](../README.md#build-a-pack)** — make Pennyworth fluent in *your*
  platform: repositories, team, skills, MCP tools, CI.
- **[Architecture](architecture.md)** — how the brain is assembled and why the
  core stays clean.
