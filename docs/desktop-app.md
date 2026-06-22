# The desktop app — a tour

Launch it with `pennyworth app` (or `poetry run pennyworth app` from a clone). This
is a guided tour of every part of the window.

> On macOS the first launch quietly installs **Pennyworth.app** into `~/Applications`
> and docks it, so you can open it like any other app afterwards. Drive that yourself
> with `pennyworth app --install-shortcut` (install + dock now) and
> `pennyworth app --uninstall` (remove it).

> Screenshots are marked `📸`. To capture them yourself, see
> [the screenshot checklist](screenshots.md).

## Layout at a glance

```mermaid
flowchart LR
  subgraph Sidebar
    NC[➕ New chat]
    SR[🔍 Search chats]
    H[Chat history · grouped by category]
    subgraph Nav
      BC[🦇 Batcave]
      SK[⚡ Skills]
      KN[📚 Knowledge]
      MC[🔌 Connectors]
      US[📊 Usage]
      ST[⚙️ Settings]
      AB[ℹ️ About]
    end
    BR[Pennyworth ↗]
  end
  subgraph Main
    T[Transcript / welcome]
    BD[🧠 Reasoning drawer]
    CMP[Composer: model · persona · effort · cwd · terminal]
  end
  Sidebar --- Main
```

The sidebar is **resizable** — drag its right edge; the width persists across
launches.

![Pennyworth — the desktop app with a conversation in progress](images/app-overview.png)

## Chat

The heart of the app. Type in plain language and Pennyworth streams his reply.

- **Streaming** — text appears token by token. Tool calls and sub-agents show as
  collapsible steps; extended thinking streams into the **🧠 reasoning drawer**
  (enable *Show thinking* in Settings).
- **Loading flavour** — while a turn runs, the status line rotates through butler
  loading phrases (carrying the `model · effort` suffix), so the wait tells you
  what's running with a little personality.
- **Composer controls** (left → right): **model** picker (`auto` routes each
  request to the cheapest capable model), **persona**, **effort**
  (low/medium/high), **working directory**, and a **terminal** toggle.
- **Images** — attached or pasted images render as inline thumbnails in your
  message bubble; non-image attachments fall back to a filename chip.
- **Markdown** replies render fully — headings, lists, code blocks with copy
  buttons, and clickable links (opened in your browser, never navigating the
  app away).
- **Feedback** — each reply carries a thumbs up/down; ratings are logged locally
  for later review.
- **Multi-chat** — each conversation in the sidebar keeps its own model, persona,
  working directory, and history. Conversations are saved and survive a restart.

![A reply streaming, with the reasoning drawer open](images/chat-streaming.png)

## Sidebar: categories & search

- **Categories** — assign a chat to a label (rename or delete labels too); the
  sidebar groups chats under their category. Assign via the chat's chooser menu or
  by dragging a chat onto a category.
- **Search** — full-text search across *all* stored chats from the sidebar, with a
  hit count and snippet excerpts so you can jump straight to the right conversation.

## Embedded terminal

The **❯_ Terminal** button in the composer opens a real PTY shell, rooted at the
chat's working directory, right inside the pane — for the moments you'd rather
type a command than ask for one.

## 📚 Knowledge

Teach *this* Pennyworth about your domain. Every enabled entry is injected into his
prompt at the start of each turn — no code change, no pack. Add inline notes,
import a file, or link a file (re-read live each turn). Full guide:
**[Teach Pennyworth your domain](knowledge.md)**.

![The Knowledge panel](images/knowledge.png)

## ⚡ Skills

Pennyworth's craft knowledge — reference docs that load automatically when a request
touches their topic (debugging, git, PR-writing, testing, investigation…).
Read-only in the open-source core; a pack can add its own.

## 🦇 Batcave

Your configured repositories at a glance — each one's branch and uncommitted
changes. Add repositories under **Settings → Repositories**; every configured
repo is also handed to Pennyworth as a working directory, so he can operate in it
directly. (No Docker/CI/deploy sections — those belong to a platform pack.)

![The Batcave listing configured repositories and their git state](images/batcave.png)

## 🔌 Connectors

Manage MCP servers that give Pennyworth new "hands" (tools). Add by URL or command.

## 📊 Usage

Your Claude subscription quotas — the rolling 5-hour and 7-day windows with
percent-used and reset countdowns — read live from Anthropic via your signed-in
Claude CLI. (If `claude` isn't signed in, the panel says so.) Readings are cached
briefly so opening the tab can't hammer the endpoint.

## ⏰ Scheduled

Prompts Pennyworth runs at a chosen time while the app is open — a quick way to queue
"review the diff at 5pm".

## ⚙️ Settings

- **Profile** — your name and how Pennyworth addresses you (sir/madam).
- **Defaults** — model, persona, effort, *show thinking*, notifications.
- **AI provider** — which model answers. **Claude Code** (default) keeps Pennyworth's
  full powers — editing files, running tools, the terminal. **OpenAI** or any
  **OpenAI-compatible** endpoint (OpenAI, Ollama, vLLM, LM Studio) gives a
  conversational Pennyworth: he streams replies but won't edit files or run tools.
  Your API key is stored locally and never shown again.
- **Appearance** — UI font (system/serif/mono), scale, theme, and a chat
  **wallpaper** (pick a background image or clear it; stored with your profile).
- **Repositories** — the repos Pennyworth works in and that appear in the Batcave.

![The Settings panel](images/settings.png)

## Themes

Beyond the built-in dark themes, create your own under Appearance: pick the
colours, save, and export/share/import theme JSON. Personas (Architect,
Speedster, Mentor, Hunter, PM, Dexter, Ultron) recolour a chat's accent.

## 🎙️ Dictation

Speak instead of type: dictation records on macOS and transcribes your speech
into the composer (record-then-transcribe). The first use asks for microphone and
speech-recognition permission.

## ℹ️ About

Version, the Pennyworth persona, capabilities, and credits.

## Keyboard

- **⌘N** — new chat
- **⌘+ / ⌘- / ⌘0** — UI scale up / down / reset
- **Enter** — send · **Shift-Enter** — newline

## Troubleshooting

- **Window opens but nothing responds** — fully quit (⌘Q) and relaunch; the app
  purges the WebKit cache on launch so a pulled update takes effect.
- **A panel shows an error or a turn fails** — the desktop console isn't visible,
  so errors are logged to `~/.pennyworth/app/diag.log`; share that when reporting
  a bug.
- **"Usage" is empty** — sign in with `claude auth login`.
