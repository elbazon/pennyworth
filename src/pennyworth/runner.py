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

import os
import subprocess
import sys

from pennyworth.pack import NULL_PACK, Pack
from pennyworth.prompt import build_system_prompt

DEFAULT_AGENT = "claude"


def agent_command() -> str:
    """The host agent executable (``PENNYWORTH_AGENT``, default ``claude``)."""
    return os.environ.get("PENNYWORTH_AGENT") or DEFAULT_AGENT


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
) -> int:
    """Assemble the brain for ``pack`` and run the host agent.

    Returns the agent's exit code, or 127 if the agent executable is missing.
    """
    system_prompt = build_system_prompt(pack, chat_mode=interactive)
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
