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


def build_command(
    request: str,
    system_prompt: str,
    *,
    agent: str | None = None,
    interactive: bool = False,
    add_dirs: list[str] | None = None,
    allow_all: bool = False,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build the host-agent argv. Pure and testable.

    One-shot requests use print mode (``-p``); interactive sessions seed the
    conversation with the request when one is given. ``allow_all`` opts into the
    host's "skip permission prompts" mode — off by default, since the core
    should not silently grant a coding agent unfettered access.
    """
    cmd = [agent or agent_command(), "--append-system-prompt", system_prompt]
    for directory in add_dirs or []:
        cmd += ["--add-dir", directory]
    if allow_all:
        cmd.append("--dangerously-skip-permissions")
    if extra_args:
        cmd += list(extra_args)
    if interactive:
        if request:
            cmd.append(request)
    else:
        cmd += ["-p", request]
    return cmd


def run(
    request: str = "",
    pack: Pack = NULL_PACK,
    *,
    interactive: bool = False,
    add_dirs: list[str] | None = None,
    allow_all: bool = False,
    extra_args: list[str] | None = None,
    profile: Profile = NULL_PROFILE,
) -> int:
    """Assemble the brain for ``pack`` and run the host agent.

    Returns the agent's exit code, or 127 if the agent executable is missing.
    """
    system_prompt = build_system_prompt(pack, chat_mode=interactive, profile=profile)
    cmd = build_command(
        request,
        system_prompt,
        interactive=interactive,
        add_dirs=add_dirs,
        allow_all=allow_all,
        extra_args=extra_args,
    )
    try:
        return subprocess.run(cmd).returncode
    except FileNotFoundError:
        print(
            f"Host agent not found: {cmd[0]!r}. Install the Claude CLI, or set "
            "PENNYWORTH_AGENT to your agent's command.",
            file=sys.stderr,
        )
        return 127


def stream(
    request: str,
    pack: Pack = NULL_PACK,
    *,
    on_chunk: Callable[[str], None],
    add_dirs: list[str] | None = None,
    allow_all: bool = False,
    profile: Profile = NULL_PROFILE,
) -> int:
    """Run the host agent and deliver its reply incrementally via ``on_chunk``.

    Used by the desktop app to render a reply as it arrives. With the default
    Claude CLI the reply streams token-by-token (stream-json text deltas); with
    a custom ``PENNYWORTH_AGENT`` it falls back to plain line streaming (stderr
    folded into stdout). Returns the agent's exit code, or 127 if the agent
    executable is missing.
    """
    system_prompt = build_system_prompt(pack, chat_mode=False, profile=profile)
    agent = agent_command()
    structured = _speaks_claude_protocol(agent)
    cmd = build_command(
        request,
        system_prompt,
        agent=agent,
        add_dirs=add_dirs,
        allow_all=allow_all,
        extra_args=list(_STREAM_JSON_ARGS) if structured else None,
    )
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        on_chunk(f"[host agent not found: {cmd[0]} — set PENNYWORTH_AGENT]")
        return 127
    assert proc.stdout is not None
    for line in proc.stdout:
        if not structured:
            on_chunk(line)
            continue
        text = extract_text_delta(line)
        if text is not None:
            on_chunk(text)
        elif line.strip() and not line.lstrip().startswith(("{", "[")):
            # A plain-text line in structured mode is almost certainly an error
            # the CLI printed instead of a JSON event — surface it, don't swallow.
            on_chunk(line)
    return proc.wait()
