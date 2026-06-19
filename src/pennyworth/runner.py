"""Drive a host coding agent with Alfred's assembled brain.

:func:`~pennyworth.prompt.build_system_prompt` produces the brain; this module
hands it to a coding-agent CLI — the Claude Code CLI (``claude``) by default —
via ``--append-system-prompt``, so the agent acts *as Alfred*. The brain is
*appended* to the host's own system prompt rather than replacing it, which keeps
the host's session handling intact.

The agent command is configurable via ``PENNYWORTH_AGENT``, so the core is not
hard-wired to one vendor.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from pennyworth.pack import NULL_PACK, Pack
from pennyworth.profile import NULL_PROFILE, Profile
from pennyworth.prompt import build_system_prompt

DEFAULT_AGENT = "claude"

# Flags that make the Claude CLI emit its reply as a realtime stream of
# newline-delimited JSON events (one text fragment per ``content_block_delta``),
# rather than printing the whole answer at the end. ``--verbose`` is required by
# the CLI whenever ``stream-json`` is used in print mode.
_STREAM_JSON_ARGS = [
    "--output-format",
    "stream-json",
    "--verbose",
    "--include-partial-messages",
]


def agent_command() -> str:
    """The host agent executable (``PENNYWORTH_AGENT``, default ``claude``)."""
    return os.environ.get("PENNYWORTH_AGENT") or DEFAULT_AGENT


def _speaks_claude_protocol(agent: str) -> bool:
    """Whether ``agent`` understands the Claude CLI's stream-json protocol.

    Only the bundled default (``claude``) is assumed to. A custom
    ``PENNYWORTH_AGENT`` may be any program, so for it we fall back to plain
    line-by-line streaming and don't pass the Claude-specific flags.
    """
    return Path(agent).name == DEFAULT_AGENT


def extract_text_delta(line: str) -> str | None:
    """Pull the visible reply text out of one Claude stream-json line.

    Returns the incremental text of an assistant ``text_delta`` event, or
    ``None`` for anything else — protocol envelopes (init/result/usage),
    thinking deltas, tool I/O, or non-JSON. Pure and testable.
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict) or obj.get("type") != "stream_event":
        return None
    event = obj.get("event")
    if not isinstance(event, dict) or event.get("type") != "content_block_delta":
        return None
    delta = event.get("delta")
    if not isinstance(delta, dict) or delta.get("type") != "text_delta":
        return None
    text = delta.get("text")
    return text if isinstance(text, str) else None


def parse_stream_event(line: str) -> dict | None:
    """Parse one Claude stream-json line into a structured UI event.

    Returns one of these dicts, or ``None`` for lines that carry nothing the UI
    renders (envelopes, tool-input deltas, the redundant full ``assistant``
    message):

    - ``{"kind": "model", "model": str}`` — the model answering this turn.
    - ``{"kind": "text", "text": str}`` — a visible reply fragment.
    - ``{"kind": "thinking", "text": str}`` — an extended-thinking fragment.
    - ``{"kind": "tool", "name": str, "id": str}`` — a tool call began.
    - ``{"kind": "result", "cost": float | None, "error": bool}`` — turn done.

    Pure and testable.
    """
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    kind = obj.get("type")
    if kind == "result":
        cost = obj.get("total_cost_usd")
        return {
            "kind": "result",
            "cost": cost if isinstance(cost, int | float) else None,
            "error": bool(obj.get("is_error")),
        }
    if kind != "stream_event":
        return None
    event = obj.get("event")
    if not isinstance(event, dict):
        return None
    etype = event.get("type")
    if etype == "message_start":
        model = (event.get("message") or {}).get("model")
        return {"kind": "model", "model": model} if isinstance(model, str) else None
    if etype == "content_block_start":
        block = event.get("content_block") or {}
        if block.get("type") == "tool_use":
            return {
                "kind": "tool",
                "name": str(block.get("name") or "tool"),
                "id": str(block.get("id") or ""),
            }
        return None
    if etype == "content_block_delta":
        delta = event.get("delta") or {}
        dtype = delta.get("type")
        if dtype == "text_delta" and isinstance(delta.get("text"), str):
            return {"kind": "text", "text": delta["text"]}
        if dtype == "thinking_delta" and isinstance(delta.get("thinking"), str):
            return {"kind": "thinking", "text": delta["thinking"]}
        return None
    return None


def build_mcp_config(pack: Pack) -> dict | None:
    """Shape a pack's *wireable* hands into the Claude ``--mcp-config`` payload.

    Returns ``{"mcpServers": {name: spec, ...}}`` for every hand that carries
    transport (stdio ``command`` or remote ``url``), or ``None`` when the pack
    has no wireable hands — brain-only hands (name + summary) contribute nothing
    here, only to the prompt index. Pure and testable.

    The server spec follows the Claude CLI's MCP schema: a stdio server is
    ``{"command", "args"?}``; a remote server is ``{"type", "url"}`` where type
    is the hand's ``transport`` or ``"http"`` by default.
    """
    servers: dict[str, dict] = {}
    for hand in pack.hands:
        if hand.command:
            spec: dict = {"command": hand.command}
            if hand.args:
                spec["args"] = list(hand.args)
            servers[hand.name] = spec
        elif hand.url:
            servers[hand.name] = {"type": hand.transport or "http", "url": hand.url}
    return {"mcpServers": servers} if servers else None


def build_command(
    request: str,
    system_prompt: str,
    *,
    agent: str | None = None,
    interactive: bool = False,
    add_dirs: list[str] | None = None,
    allow_all: bool = False,
    mcp_config: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build the host-agent argv. Pure and testable.

    One-shot requests use print mode (``-p``); interactive sessions seed the
    conversation with the request when one is given. ``allow_all`` opts into the
    host's "skip permission prompts" mode — off by default, since the core
    should not silently grant a coding agent unfettered access. ``mcp_config``,
    when given, is passed verbatim as ``--mcp-config`` (a JSON string) to add the
    pack's MCP "hands" to the agent's existing servers (not replace them).
    """
    cmd = [agent or agent_command(), "--append-system-prompt", system_prompt]
    for directory in add_dirs or []:
        cmd += ["--add-dir", directory]
    if allow_all:
        cmd.append("--dangerously-skip-permissions")
    if mcp_config:
        cmd += ["--mcp-config", mcp_config]
    if extra_args:
        cmd += list(extra_args)
    if interactive:
        if request:
            cmd.append(request)
    else:
        cmd += ["-p", request]
    return cmd


def _mcp_config_arg(pack: Pack, structured: bool) -> str | None:
    """The ``--mcp-config`` JSON string for ``pack``'s hands, or ``None``.

    Gated on ``structured`` (the host speaks the Claude protocol): MCP wiring is
    Claude-CLI-specific, so a custom ``PENNYWORTH_AGENT`` gets the brain-only
    index without the flag, exactly as ``--model`` and the stream flags are gated.
    """
    if not structured:
        return None
    config = build_mcp_config(pack)
    return json.dumps(config) if config else None


def run(
    request: str = "",
    pack: Pack = NULL_PACK,
    *,
    interactive: bool = False,
    add_dirs: list[str] | None = None,
    allow_all: bool = False,
    extra_args: list[str] | None = None,
    model: str | None = None,
    cwd: str | None = None,
    profile: Profile = NULL_PROFILE,
) -> int:
    """Assemble the brain for ``pack`` and run the host agent.

    Returns the agent's exit code, or 127 if the agent executable is missing.
    """
    system_prompt = build_system_prompt(pack, chat_mode=interactive, profile=profile)
    structured = _speaks_claude_protocol(agent_command())
    model_args: list[str] = ["--model", model] if model and structured else []
    cmd = build_command(
        request,
        system_prompt,
        interactive=interactive,
        add_dirs=add_dirs,
        allow_all=allow_all,
        mcp_config=_mcp_config_arg(pack, structured),
        extra_args=(list(extra_args or []) + model_args) or None,
    )
    try:
        return subprocess.run(cmd, cwd=cwd or None).returncode
    except FileNotFoundError:
        print(
            f"Host agent not found: {cmd[0]!r}. Install the Claude CLI, or set "
            "PENNYWORTH_AGENT to your agent's command.",
            file=sys.stderr,
        )
        return 127


def stream_events(
    request: str,
    pack: Pack = NULL_PACK,
    *,
    on_event: Callable[[dict], None],
    add_dirs: list[str] | None = None,
    allow_all: bool = False,
    model: str | None = None,
    cwd: str | None = None,
    profile: Profile = NULL_PROFILE,
    extended_thinking: bool = False,
    extra_knowledge: str = "",
) -> int:
    """Run the host agent and deliver structured events via ``on_event``.

    The richer sibling of :func:`stream`: each call to ``on_event`` is one of the
    dicts described by :func:`parse_stream_event` (``text`` / ``thinking`` /
    ``tool`` / ``model`` / ``result``), plus ``{"kind": "error", "text": str}``
    for failures. With the default Claude CLI this gives token-by-token text, the
    extended-thinking stream, and tool activity; a custom ``PENNYWORTH_AGENT``
    falls back to whole-line ``text`` events. Returns the agent's exit code, or
    127 if the agent executable is missing.
    """
    system_prompt = build_system_prompt(pack, chat_mode=False, profile=profile)
    if extra_knowledge.strip():
        system_prompt += (
            "\n\n# User-provided domain knowledge\n"
            "The user has supplied the following knowledge about their domain. "
            "Treat it as authoritative context for this conversation.\n\n"
            + extra_knowledge.strip()
        )
    agent = agent_command()
    structured = _speaks_claude_protocol(agent)
    extra: list[str] = list(_STREAM_JSON_ARGS) if structured else []
    if model and structured:
        extra += ["--model", model]
    if extended_thinking and structured:
        # Visible extended thinking. `summarized` is what flips the model from
        # signature-only to real thinking content — `--thinking adaptive` alone
        # returns zero thinking text. Both are stock claude-CLI flags.
        extra += ["--thinking", "adaptive", "--thinking-display", "summarized"]
    cmd = build_command(
        request,
        system_prompt,
        agent=agent,
        add_dirs=add_dirs,
        allow_all=allow_all,
        mcp_config=_mcp_config_arg(pack, structured),
        extra_args=extra or None,
    )
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd or None,
        )
    except FileNotFoundError:
        on_event(
            {
                "kind": "error",
                "text": f"[host agent not found: {cmd[0]} — set PENNYWORTH_AGENT]",
            }
        )
        return 127
    assert proc.stdout is not None
    for line in proc.stdout:
        if not structured:
            if line.strip():
                on_event({"kind": "text", "text": line})
            continue
        event = parse_stream_event(line)
        if event is not None:
            on_event(event)
        elif line.strip() and not line.lstrip().startswith(("{", "[")):
            # A plain-text line in structured mode is almost certainly an error
            # the CLI printed instead of a JSON event — surface it, don't swallow.
            on_event({"kind": "error", "text": line})
    return proc.wait()


def stream(
    request: str,
    pack: Pack = NULL_PACK,
    *,
    on_chunk: Callable[[str], None],
    add_dirs: list[str] | None = None,
    allow_all: bool = False,
    model: str | None = None,
    cwd: str | None = None,
    profile: Profile = NULL_PROFILE,
) -> int:
    """Run the host agent and deliver visible reply text via ``on_chunk``.

    A thin text-only view over :func:`stream_events` — ``text`` and ``error``
    events become chunks; ``thinking`` / ``tool`` / ``model`` / ``result`` are
    dropped. Returns the agent's exit code.
    """

    def on_event(event: dict) -> None:
        if event.get("kind") in ("text", "error"):
            on_chunk(event.get("text", ""))

    return stream_events(
        request,
        pack,
        on_event=on_event,
        add_dirs=add_dirs,
        allow_all=allow_all,
        model=model,
        cwd=cwd,
        profile=profile,
    )
