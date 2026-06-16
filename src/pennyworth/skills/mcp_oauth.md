---
name: mcp_oauth
description: Use when running an MCP server's OAuth flow — a remote MCP whose authenticate tool returns an authorize URL with a localhost redirect_uri — to capture the browser's loopback callback yourself instead of making the user paste it back. NOT for MCP installs that don't use OAuth.
---

# MCP OAuth redirect capture

Some MCP servers drive an OAuth 2.1 browser flow. Their `authenticate` tool
returns a URL like:

```
https://<server>/authorize?...&redirect_uri=http%3A%2F%2Flocalhost%3A53679%2Fcallback&state=...
```

The naive flow — share the URL, then ask the user to paste back the
`http://localhost:53679/callback?...` URL their browser landed on — is brittle:
the server may discard in-flight OAuth state between tool calls in a headless
session, and even when it works it costs a round-trip and a copy-paste. Capture
the callback yourself with a one-shot loopback listener.

## Flow

1. Parse `redirect_uri` out of the authorize URL. You need the **port** and the
   **path** (above: `53679` and `/callback`). Reuse the exact port the server
   baked in — never invent one.

2. Start a one-shot loopback listener **before** showing the user the URL, with
   `run_in_background: true` so the tool call returns immediately:

   ```bash
   python3 - <<'PY'
   import http.server
   class H(http.server.BaseHTTPRequestHandler):
       def do_GET(self):
           print(self.path, flush=True)
           self.send_response(200); self.end_headers()
           self.wfile.write(b"Authorised - you may close this tab.")
       def log_message(self, *a): pass
   srv = http.server.HTTPServer(("127.0.0.1", 53679), H)
   srv.timeout = 120
   srv.handle_request()   # serves exactly one request, or returns after timeout
   PY
   ```

   It binds `127.0.0.1` only, serves exactly one request, and prints the
   captured path (`/callback?code=…&state=…`) on stdout. Capture the job id.

3. Send the authorize URL to the user — one short message, no preamble.

4. When the background job finishes (the moment the browser hits the listener),
   read its stdout: a single line like `/callback?code=abc123&state=xyz`.

5. Rebuild the full callback URL — `http://localhost:PORT` + that line — and
   pass it to the server's `complete_authentication` tool.

6. If the listener times out, the port is already bound, or the path is wrong,
   fall back to asking the user to paste the callback URL manually.

## Why background, not foreground

The listener blocks until the GET arrives. Run it foreground and your tool call
hangs waiting for the user to click "allow" — and they can't reply to you in
the meantime, because you're still inside the call. Background it.

## Loopback only

Bind `127.0.0.1`, never `0.0.0.0`. The browser is the only legitimate caller; a
stray request from elsewhere on the network would burn the one-shot.
