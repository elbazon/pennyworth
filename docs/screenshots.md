# Screenshot capture checklist

The docs reference images under `docs/images/`. These need to be captured from a
running app on a real display (they can't be generated headlessly). Here's
exactly what to grab — about five minutes of work.

> ✅ The committed images are **current** — recaptured after the Pennyworth
> rebrand, in the generic (no-pack) state, so they show the butler UI with no
> platform internals. Two are worth a fresh grab when convenient:
> `app-overview.png` currently reuses the chat-streaming shot, and `knowledge.png`
> shows the empty state rather than a populated panel. Recapture using the
> guidance below if you want dedicated shots for those two.

On macOS, **⌘⇧4** then **Space** captures a single window cleanly. Save each into
`docs/images/` with the filename below.

| File | View | What to show |
|------|------|--------------|
| `app-overview.png` | Chat | The whole window with a short conversation in progress — sidebar, transcript, composer. |
| `chat-streaming.png` | Chat | A reply mid-stream with the **🧠 reasoning drawer** open (enable *Show thinking* first). |
| `knowledge.png` | 📚 Knowledge | Two or three entries — one inline, one file-linked — so the source badges show. |
| `batcave.png` | 🦇 Batcave | At least one configured repository with its branch + "N changed" chip. |
| `settings.png` | ⚙️ Settings | Profile + Appearance + Repositories visible. |
| `welcome.png` | New chat | The welcome screen with the suggestion chips. |

Tips for clean shots:

- **Detach any pack first** (`pennyworth pack detach`) so the shots show the
  generic butler, not a private platform. The public repo's images must not leak
  platform names, repos, or team — capture in the no-pack (generic) state.
- Set a comfortable UI scale (⌘0 resets to 100%).
- Use the default **Pennyworth** theme for consistency, or note the theme in the
  alt text if you use another.
- Crop out anything personal (paths, tokens, private repo names) before
  committing.

Once dropped in, the `📸` placeholders in [the app tour](desktop-app.md) and
[knowledge guide](knowledge.md) resolve automatically — replace the placeholder
lines with a normal image embed:

```markdown
![Pennyworth — chat in progress](images/app-overview.png)
```
