# Security policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue.

Use GitHub's [private vulnerability reporting](https://github.com/elbazon/pennyworth/security/advisories/new)
on this repository, or contact the maintainer directly. Include what you found,
how to reproduce it, and the impact. You'll get an acknowledgement, and a fix or
mitigation will be worked as a priority.

## Scope and good to know

- Pennyworth drives a **host coding agent** (the Claude CLI by default) with the
  permissions you grant it. Treat it like any tool that can read and write your
  code, and review what it does.
- Your **profile, settings, chats, and knowledge** are stored locally under
  `PENNYWORTH_HOME` (default `~/.pennyworth`). They never leave your machine
  except as part of the prompts you send to your own agent/provider.
- The desktop app reads your Claude CLI's keychain token only to show usage
  quotas; it is never written to disk by Pennyworth.

## Supported versions

This is an early project; security fixes target the latest `master` and release.
