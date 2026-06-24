"""AI providers — let Pennyworth run on more than the Claude Code CLI.

Two backends, behind one ``stream_events`` entry point that mirrors
:func:`pennyworth.runner.stream_events`:

- ``claude-code`` (default) — the Claude Code CLI, with full agentic powers
  (tools, file edits, terminal). Delegates straight to the runner.
- ``openai`` / ``openai-compatible`` — any OpenAI-style ``/chat/completions``
  endpoint: OpenAI itself, or a local model served by Ollama / vLLM / LM Studio.
  This is a *conversational* backend — it streams replies (and reasoning, where
  the model exposes it) but does not edit files or run tools on its own.

The system prompt (Pennyworth's brain, plus any injected knowledge) is assembled the
same way for every backend, so Pennyworth stays in character whichever model answers.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable

from pennyworth import runner as _runner
from pennyworth.pack import NULL_PACK, Pack
from pennyworth.profile import NULL_PROFILE, Profile
from pennyworth.prompt import build_system_prompt

# Silence-watchdog thresholds (seconds of no events from the backend). At the
# first the user gets a calm "the service is busy" notice; at the second it
# escalates to a warning. They turn a frozen spinner during a provider stall
# (e.g. an HTTP 529 backoff) into a visible, reassuring status.
_SILENCE_INFO_S = 15
_SILENCE_WARN_S = 45

# Provider ids the Settings UI offers. "openai" and "openai-compatible" share the
# same HTTP adapter; they differ only in the default base URL.
PROVIDERS = ["claude-code", "openai", "openai-compatible"]
_DEFAULT_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "openai-compatible": "http://localhost:11434/v1",  # Ollama's default
}


def default_base_url(provider: str) -> str:
    return _DEFAULT_BASE_URL.get(provider, "")


def is_claude_code(provider: str) -> bool:
    return not provider or provider == "claude-code"


def _knowledge_section(extra_knowledge: str) -> str:
    return (
        "\n\n# User-provided domain knowledge\n"
        "The user has supplied the following knowledge about their domain. "
        "Treat it as authoritative context for this conversation.\n\n"
        + extra_knowledge.strip()
    )


def stream_events(
    request: str,
    pack: Pack = NULL_PACK,
    *,
    on_event: Callable[[dict], None],
    provider: str = "claude-code",
    base_url: str = "",
    api_key: str = "",
    provider_model: str = "",
    model: str | None = None,
    cwd: str | None = None,
    add_dirs: list[str] | None = None,
    profile: Profile = NULL_PROFILE,
    extended_thinking: bool = False,
    extra_knowledge: str = "",
) -> int:
    """Run one turn on the configured provider, delivering events via ``on_event``.

    Returns an exit code (0 on success), matching the runner's contract so the
    bridge handles every backend identically.

    A silence watchdog wraps the call so it applies to every backend: it stamps
    activity on each delivered event and, when the backend goes quiet past the
    thresholds, emits ``status_notice`` events so the user sees the service is
    busy rather than a frozen spinner.
    """
    last_activity = [time.monotonic()]
    watchdog_stop = threading.Event()
    notice_sent = {"info": False, "warn": False}

    def tracked_on_event(event: dict) -> None:
        last_activity[0] = time.monotonic()
        on_event(event)

    def _watchdog() -> None:
        while not watchdog_stop.wait(0.5):
            elapsed = time.monotonic() - last_activity[0]
            if elapsed > _SILENCE_WARN_S and not notice_sent["warn"]:
                notice_sent["warn"] = True
                on_event(
                    {
                        "kind": "status_notice",
                        "severity": "warn",
                        "text": "The model service is under heavy load. "
                        "Pennyworth is still retrying — your message is safe.",
                    }
                )
            elif elapsed > _SILENCE_INFO_S and not notice_sent["info"]:
                notice_sent["info"] = True
                on_event(
                    {
                        "kind": "status_notice",
                        "severity": "info",
                        "text": "The model service is busy and Pennyworth is "
                        "waiting. This is on the provider's side, not Pennyworth.",
                    }
                )

    watchdog = threading.Thread(target=_watchdog, daemon=True)
    watchdog.start()
    try:
        if is_claude_code(provider):
            return _runner.stream_events(
                request,
                pack,
                on_event=tracked_on_event,
                model=model,
                cwd=cwd,
                add_dirs=add_dirs,
                profile=profile,
                extended_thinking=extended_thinking,
                extra_knowledge=extra_knowledge,
            )

        # OpenAI-compatible HTTP backend.
        system_prompt = build_system_prompt(pack, chat_mode=False, profile=profile)
        if extra_knowledge.strip():
            system_prompt += _knowledge_section(extra_knowledge)
        return _openai_compatible_stream(
            request=request,
            system_prompt=system_prompt,
            base_url=base_url or default_base_url(provider),
            api_key=api_key,
            model=provider_model or "gpt-4o-mini",
            on_event=tracked_on_event,
        )
    finally:
        watchdog_stop.set()


def _openai_compatible_stream(
    *,
    request: str,
    system_prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    on_event: Callable[[dict], None],
) -> int:
    """Stream a chat completion from an OpenAI-style endpoint via SSE.

    Emits the same event kinds the UI already renders: ``text`` for visible
    reply tokens, ``thinking`` for reasoning tokens (models that expose
    ``reasoning_content``), ``error`` on failure, and a terminal ``result``.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request},
            ],
            "stream": True,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    produced = False
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    obj = json.loads(payload)
                except ValueError:
                    continue
                delta = ((obj.get("choices") or [{}])[0]).get("delta") or {}
                reasoning = delta.get("reasoning_content")
                if reasoning:
                    on_event({"kind": "thinking", "text": reasoning})
                text = delta.get("content")
                if text:
                    produced = True
                    on_event({"kind": "text", "text": text})
    except urllib.error.HTTPError as exc:
        detail = _read_http_error(exc)
        on_event({"kind": "error", "text": f"Provider error {exc.code}: {detail}"})
        on_event({"kind": "result", "cost": None, "error": True})
        return 1
    except (urllib.error.URLError, OSError) as exc:
        on_event({"kind": "error", "text": f"Could not reach the provider: {exc}"})
        on_event({"kind": "result", "cost": None, "error": True})
        return 1

    if not produced:
        on_event({"kind": "error", "text": "The provider returned no content."})
    on_event({"kind": "result", "cost": None, "error": not produced})
    return 0 if produced else 1


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        obj = json.loads(raw)
        return (obj.get("error") or {}).get("message") or raw[:300]
    except Exception:
        return str(exc)
