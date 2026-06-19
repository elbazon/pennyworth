"""Claude subscription usage — read straight from Anthropic, no platform deps.

The OAuth access token is the one Claude Code itself stores in the macOS
keychain (``claude auth login``); the usage endpoint is Anthropic's public
OAuth-backed ``/api/oauth/usage``. Both are standard Claude Code surfaces, so
this works for any open-source user with the Claude CLI signed in.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request

_USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
_KEYCHAIN_SERVICE = "Claude Code-credentials"


class UsageError(Exception):
    """Raised when usage can't be read (no token, network/API failure)."""


def _read_oauth_token() -> str:
    """The Claude Code OAuth access token from the macOS keychain, or raise."""
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UsageError(f"keychain read failed: {exc}") from exc
    if out.returncode != 0 or not out.stdout.strip():
        raise UsageError(
            "Claude Code credentials not found in keychain. Run `claude auth login`."
        )
    try:
        data = json.loads(out.stdout.strip())
        token = (data.get("claudeAiOauth") or {}).get("accessToken", "")
    except (ValueError, AttributeError) as exc:
        raise UsageError(f"could not parse keychain payload: {exc}") from exc
    if not token:
        raise UsageError("no access token in keychain payload")
    return token


def fetch_usage(timeout: float = 5.0) -> dict:
    """GET Anthropic's OAuth usage endpoint with the keychain token."""
    token = _read_oauth_token()
    req = urllib.request.Request(
        _USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "pennyworth-alfred",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise UsageError(f"usage request failed: {exc}") from exc


def fetch_auth_status(timeout: float = 5.0) -> dict:
    """``claude auth status --json`` — tier + email, or {} on any failure."""
    try:
        out = subprocess.run(
            ["claude", "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return json.loads(out.stdout) if out.returncode == 0 else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}
