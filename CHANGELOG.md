# Changelog

All notable changes to Pennyworth are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims for
[Semantic Versioning](https://semver.org/).

## [0.1.0] — first public release

The first open-source release of Pennyworth — the clean, platform-agnostic core
of **Alfred**, a dignified butler-engineer AI companion.

### Added

- **Alfred persona + runtime** — the CLI (`alfred run` / `alfred chat` /
  `alfred prompt`) and a per-user profile (name + how Alfred addresses you).
- **Desktop app** (`alfred app`) — a native window with:
  - streaming chat, with visible extended **thinking** and a reasoning drawer;
  - an embedded **terminal**, per-chat **model / persona / effort**, and a
    working-directory picker;
  - the **Knowledge** panel — domain notes injected into the prompt every turn
    (inline, imported, or live-linked files);
  - a repo-focused **Batcave**, **Usage** (Claude quotas), custom **themes**,
    **scheduled** prompts, saved chats, and **Settings**.
- **Packs** — everything platform-specific (identity, principal, attribution,
  skills, team, repositories, MCP "hands", CI) attaches through a pack and only a
  pack. The brain is clean by construction, enforced by a test.
- **Documentation** — getting started, a desktop-app tour, the Knowledge guide,
  architecture, and contributing.

### Notes

- macOS desktop app (pywebview/WebKit); the CLI is cross-platform.
- Drives the Claude Code CLI by default (`PENNYWORTH_AGENT` to change it).

[0.1.0]: https://github.com/elbazon/pennyworth/releases/tag/v0.1.0
