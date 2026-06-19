# Porting the production Alfred GUI into Pennyworth

Status: **in progress** (branch `feat/production-gui`). This document is the
contract spec for finishing the port. It exists because the work cannot be
fully verified without a display, and must not land on `master` until it is.

## Goal

Give the open-source Pennyworth desktop app the **same GUI** as the internal
"Alfred" app (`morning_cli/ai/app`), wired to Pennyworth's clean, platform-
agnostic core instead of `morning_cli`. The visual shell should be identical;
everything platform-specific arrives through the pack or degrades gracefully.

## What is DONE on this branch

- **Visual shell ported** — the full production `index.html` (4843 lines) is now
  `src/pennyworth/app/web/index.html`, replacing the older bespoke 892-line UI.
- **Terminal assets bundled** — `xterm.js`, `xterm.css`, `xterm-addon-fit.js`,
  and the real `alfred.png` avatar copied into `web/`.
- **De-branding (the safe, done parts):**
  - Proprietary **Ploni** typeface removed entirely (commercial font — must not
    ship in an Apache-2.0 repo). Default font is now the system UI stack; the
    font picker offers System / Serif / Monospace.
  - Morning logo asset, `morning.co` link, and "Made at Morning · R&D" footer
    removed. Footer is now a "Pennyworth" wordmark linking to the repo.
  - About credits neutralised; default theme renamed "Pennyworth (default)".
- **Window serving** — `window.py` now loads the page by **file URL** (with an
  `?v=<mtime>` cache-bust) so relative assets resolve, and calls
  `Bridge.attach_window(window)` before the event loop.
- **Push machinery** — `Bridge.attach_window` / `_start_emitter` / `_emit`
  ported verbatim (coupling-free): a single FIFO thread delivers events to the
  page via `window.evaluate_js("window.alfredEvent(...)")`.
- **Tests** — the UI-shape tests were rewritten to the new (push) contract and
  pass; one `xfail` documents the platform tokens still in coupled panels.

## What REMAINS (the bridge contract)

The page is **push-based** and calls **63** `window.pywebview.api.*` methods.
Pennyworth's bridge currently implements a different, pull-based set
(`ask`/`start`/`poll`, `term_write`/`term_read`, `pick_file`/`pick_dir`). To
make the ported page actually run, the bridge must expose the production method
names and the push streaming protocol below.

### The 63 methods the page calls

```
get_state, get_settings, set_setting, get_chat_settings, set_chat_model,
set_chat_persona, set_chat_effort, get_chat_cwd, set_chat_cwd, pick_chat_cwd,
send_message, interrupt, close_chat, set_app_focused,
term_open, term_input, term_resize, term_close,
get_work_context, get_diff,
open_url, open_path, open_terminal, open_in_editor, focus_path,
pick_files, pick_folder, pick_dir_path, set_dir_path, get_dir_paths,
save_extra_repos, save_pasted_image,
list_skills, delete_local_skill, release_skill,
list_app_chats, load_app_chat, persist_chat, rename_app_chat, delete_app_chat,
pin_app_chat,
list_themes, save_theme, delete_theme, import_theme, export_theme, share_theme,
paste_theme,
list_scheduled, add_scheduled, delete_scheduled,
get_stats, get_usage, get_batcave, pm2_action,
list_mcp, add_mcp, remove_mcp,
list_slash_commands, run_slash,
list_versions, install_version, check_for_update,
start_dictation, stop_dictation
```

### Streaming protocol (push)

`send_message(chat_id, text) -> bool` starts a turn on a per-chat daemon
thread. The thread pushes `chatId`-tagged events via `_emit`. The page's
`window.alfredEvent(e)` routes by `e.chatId` + `e.type`.

Event `type`s the page handles: `status`, `turn_start`, `stream`, `usage`,
`work_context`, `batcave`, `stats`, `term_output`, `term_exit`, `term_closed`,
`scheduled_fire`, `dictation`, `dictation_state`, `update_available`.

`stream` events carry a `kind`: `agent_start`, `agent`, `text`, `thinking`,
`tool`, `tool_done`, plus interactive-prompt kinds `select` / `number` /
`password`. A turn ends with a terminal `stream` (`kind:"result"`) / `usage`.

Map the chat core onto `pennyworth.runner.stream_events(request, pack,
on_event=…, model=…, cwd=…, profile=…)` — translate its `kind` values
(`text`/`thinking`/`tool`/`model`/`result`/`error`) into the page's `stream`
events.

### Classification for the bridge rebuild

- **Portable (reuse Pennyworth core):** chat (`send_message`/`interrupt`/
  `close_chat`), terminal (`term_*` via `TermManager`), chats persistence
  (`*_app_chat`, `pin_app_chat`), skills (`list_skills`), stats (`get_stats`),
  file ops (`pick_files`/`pick_folder`/`save_pasted_image`/`open_url`),
  settings/profile (`get_settings`/`set_setting`/`get_chat_settings`/
  `set_chat_*`), themes (`*_theme` — pure local JSON), scheduled (`*_scheduled`
  — local JSON + ticker), cwd (`*_chat_cwd`).
- **Platform-coupled → degrade gracefully (return empty/unavailable, do NOT
  expose Morning internals):** `get_batcave`/`pm2_action` (LocalStack/Docker/
  pm2), `get_usage` (subscription), `list_versions`/`install_version` (morning-
  cli releases), `list_mcp`/`add_mcp`/`remove_mcp`, `list_slash_commands`/
  `run_slash`, `get_work_context`/`get_diff` (git/gh — could be a clean generic
  git impl), `release_skill`/`delete_local_skill`, `open_in_editor`/
  `open_terminal`/`open_path`, version checks.
- **macOS-only, optional:** `start_dictation`/`stop_dictation` (AVFoundation +
  Speech via pyobjc). Return "unavailable" off-darwin or without deps.

Also pending: redesign the **Batcave**, **Connectors**, and **Settings** panels
to drop the remaining `morning`/`teamcity`/`localstack` tokens (the `xfail` in
`tests/test_app.py`), and add a contract test that parses every `api().<m>` call
out of `index.html` and asserts `hasattr(Bridge, m)`.

## Deliberate deviations from "pixel-identical"

1. **Font:** system stack, not Ploni (licensing). Visually close, legally clean.
2. **Branding:** Alfred/Pennyworth, not Morning (the clean-brain rule).

## Verification note

Headless tests cover assets, de-branding, window config, the push machinery,
and bridge behaviour. They do **not** prove the GUI renders or the chat path
works end to end — that needs a desktop session (`poetry install --extras app`
then `alfred app`). That runtime check is the final acceptance step.
