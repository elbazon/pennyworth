# Changelog

All notable changes to Pennyworth are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims for
[Semantic Versioning](https://semver.org/).

## [0.1.1]

A maintenance release porting desktop-app fixes from local development and
sharpening behaviour when the model provider is slow.

### Added

- **Silence watchdog** — when the backend goes quiet during a provider stall
  (e.g. an HTTP 529 backoff), Pennyworth now emits `status_notice` events so a
  busy service reads as a calm, visible status rather than a frozen spinner. It
  wraps every backend, so the behaviour is identical whichever model answers.

### Changed

- **Result errors surface as notices** — the runner now turns a backend result
  error into a clear status notice instead of a silent stall.
- **Templated macOS app icon** — the desktop app renders its icon from a
  template image for a crisper dock/menubar presence.

### Fixed

- Ported assorted desktop-app fixes (bridge, bundle, window, web UI) from local
  development (#2).

### Docs

- Credited the Morning R&D team as contributors and trimmed the credits.

## [0.1.0] — first public release

The first open-source release of Pennyworth — a dignified, platform-agnostic
butler-engineer AI companion, modeled on Alfred Pennyworth.

### Added

- **Pennyworth persona + runtime** — the CLI (`pennyworth run` / `pennyworth chat` /
  `pennyworth prompt`, with `alfred` kept as an alias) and a per-user profile
  (name + how Pennyworth addresses you).
- **Desktop app** (`pennyworth app`) — a native window with:
  - streaming chat, with visible extended **thinking**, a reasoning drawer, and
    rotating butler loading phrases while a turn runs;
  - an embedded **terminal**, per-chat **model / persona / effort**, and a
    working-directory picker;
  - inline **image thumbnails** for attached/pasted images and per-reply
    **thumbs feedback**;
  - a **resizable sidebar** with **chat categories** and **cross-chat search**;
  - the **Knowledge** panel — domain notes injected into the prompt every turn
    (inline, imported, or live-linked files);
  - a repo-focused **Batcave**, **Usage** (Claude quotas), custom **themes** and
    a chat **wallpaper**, macOS **dictation**, **scheduled** prompts, saved
    chats, and **Settings**;
  - first-launch auto-install of **Pennyworth.app** into `~/Applications`
    (`pennyworth app --install-shortcut` / `--uninstall`).
- **Packs** — everything platform-specific (identity, principal, attribution,
  skills, team, repositories, MCP "hands", CI) attaches through a pack and only a
  pack. The brain is clean by construction, enforced by a test.
- **Documentation** — getting started, a desktop-app tour, the Knowledge guide,
  architecture, and contributing.

### Notes

- macOS desktop app (pywebview/WebKit); the CLI is cross-platform.
- Drives the Claude Code CLI by default (`PENNYWORTH_AGENT` to change it).

[0.1.1]: https://github.com/elbazon/pennyworth/releases/tag/v0.1.1
[0.1.0]: https://github.com/elbazon/pennyworth/releases/tag/v0.1.0
