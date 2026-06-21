"""The Pennyworth command line — ``pennyworth``.

Manage knowledge packs, render the assembled brain, and run a host coding agent
as Alfred. A bare ``pennyworth "<request>"`` is shorthand for ``pennyworth run``.
"""

from __future__ import annotations

import argparse
import sys

from pennyworth import __version__
from pennyworth import packs as _packs
from pennyworth import profile as _profile
from pennyworth import runner as _runner
from pennyworth.prompt import build_system_prompt

# Subcommands recognised before the bare-request shorthand kicks in.
_COMMANDS = {"pack", "profile", "prompt", "run", "chat", "app"}


def _cmd_pack_list(_args: argparse.Namespace) -> int:
    active = _packs.active_name()
    names = _packs.list_packs()
    if not names:
        print("No packs installed. Attach one with: alfred pack attach <path>")
        return 0
    for name in names:
        marker = "  (active)" if name == active else ""
        print(f"- {name}{marker}")
    if not active:
        print("\nNo pack is active — Alfred is running generic.")
    return 0


def _cmd_pack_attach(args: argparse.Namespace) -> int:
    pack = _packs.attach(args.path)
    print(f"Attached and activated pack: {pack.name}")
    return 0


def _cmd_pack_detach(_args: argparse.Namespace) -> int:
    _packs.detach()
    print("Detached. Alfred is now running generic (no pack).")
    return 0


def _cmd_prompt(_args: argparse.Namespace) -> int:
    print(build_system_prompt(_packs.active_pack(), profile=_profile.active_profile()))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    return _runner.run(
        " ".join(args.request),
        _packs.active_pack(),
        add_dirs=args.add_dirs,
        allow_all=args.allow_all,
        model=getattr(args, "model", None),
        cwd=getattr(args, "cwd", None),
        profile=_profile.active_profile(),
    )


def _cmd_chat(args: argparse.Namespace) -> int:
    return _runner.run(
        " ".join(args.request),
        _packs.active_pack(),
        interactive=True,
        add_dirs=args.add_dirs,
        allow_all=args.allow_all,
        model=getattr(args, "model", None),
        cwd=getattr(args, "cwd", None),
        profile=_profile.active_profile(),
    )


def _cmd_profile_show(_args: argparse.Namespace) -> int:
    prof = _profile.load_profile()
    if not prof.is_set:
        print(
            "No profile set. Configure one with:\n"
            "  alfred profile set --name <name> --address <sir|madam>"
        )
        return 0
    print(f"name:    {prof.name or '(unset)'}")
    print(f"address: {prof.address or '(unset — Alfred will ask)'}")
    print(f"\nStored at {_profile.profile_path()}")
    return 0


def _cmd_profile_set(args: argparse.Namespace) -> int:
    try:
        prof = _profile.update_profile(name=args.name, address=args.address)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    addressed = f", addressed as {prof.address}" if prof.address else ""
    print(f"Profile saved: {prof.name or '(no name)'}{addressed}.")
    return 0


def _cmd_profile_clear(_args: argparse.Namespace) -> int:
    _profile.clear_profile()
    print("Profile cleared. Alfred will use the generic address rule.")
    return 0


def _cmd_app(args: argparse.Namespace) -> int:
    if getattr(args, "install", False) or getattr(args, "install_shortcut", False):
        from pennyworth.app.bundle import install_app_bundle

        try:
            path = install_app_bundle()
            print(f"Installed: {path}")
            print("Drag Pennyworth.app to your Dock, or double-click to launch.")
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    if getattr(args, "uninstall", False):
        from pennyworth.app.bundle import remove_app_bundle

        removed = remove_app_bundle()
        print("Removed Pennyworth.app." if removed else "Pennyworth.app not found.")
        return 0

    from pennyworth.app.window import main as app_main

    return app_main()


def _add_agent_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dir",
        action="append",
        dest="add_dirs",
        metavar="PATH",
        help="extra workspace directory the agent may access (repeatable)",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL",
        help="model to use (e.g. claude-opus-4-8); defaults to the agent's own default",
    )
    parser.add_argument(
        "--cwd",
        metavar="PATH",
        help="working directory for the agent process (default: current directory)",
    )
    parser.add_argument(
        "--dangerously-allow-all",
        action="store_true",
        dest="allow_all",
        help="skip the host agent's permission prompts (use with care)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pennyworth",
        description="Pennyworth — a butler-engineer companion.",
    )
    parser.add_argument(
        "--version", action="version", version=f"pennyworth {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    pack = sub.add_parser("pack", help="manage knowledge packs")
    pack_sub = pack.add_subparsers(dest="pack_command")
    pack_sub.add_parser("list", help="list installed packs").set_defaults(
        func=_cmd_pack_list
    )
    attach = pack_sub.add_parser("attach", help="install and activate a pack directory")
    attach.add_argument("path", help="path to a directory containing a pack manifest")
    attach.set_defaults(func=_cmd_pack_attach)
    pack_sub.add_parser("detach", help="detach the active pack").set_defaults(
        func=_cmd_pack_detach
    )

    profile_cmd = sub.add_parser(
        "profile", help="manage your profile (name + how Alfred addresses you)"
    )
    profile_cmd.set_defaults(func=_cmd_profile_show)  # bare `alfred profile` shows
    profile_sub = profile_cmd.add_subparsers(dest="profile_command")
    profile_sub.add_parser("show", help="show your current profile").set_defaults(
        func=_cmd_profile_show
    )
    pset = profile_sub.add_parser("set", help="set your name and/or honorific")
    pset.add_argument("--name", help="your name")
    pset.add_argument(
        "--address",
        choices=_profile.VALID_ADDRESSES,
        help="how Alfred addresses you (sir or madam)",
    )
    pset.set_defaults(func=_cmd_profile_set)
    profile_sub.add_parser("clear", help="clear your profile").set_defaults(
        func=_cmd_profile_clear
    )

    sub.add_parser(
        "prompt", help="print the assembled system prompt for the active pack"
    ).set_defaults(func=_cmd_prompt)

    run = sub.add_parser("run", help="run a one-shot request as Alfred")
    run.add_argument("request", nargs="+", help="the request")
    _add_agent_args(run)
    run.set_defaults(func=_cmd_run)

    chat = sub.add_parser("chat", help="start an interactive Alfred session")
    chat.add_argument("request", nargs="*", help="optional opening message")
    _add_agent_args(chat)
    chat.set_defaults(func=_cmd_chat)

    app_cmd = sub.add_parser(
        "app", help="launch the desktop app (needs the 'app' extra)"
    )
    app_cmd.add_argument(
        "--install-shortcut",
        action="store_true",
        dest="install_shortcut",
        help="install Pennyworth.app to ~/Applications (macOS only)",
    )
    app_cmd.add_argument(
        "--install",
        action="store_true",
        help=argparse.SUPPRESS,  # kept for backwards compat
    )
    app_cmd.add_argument(
        "--uninstall",
        action="store_true",
        help="remove Pennyworth.app from ~/Applications (macOS only)",
    )
    app_cmd.set_defaults(func=_cmd_app)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Bare-request shorthand: `alfred "fix the bug"` -> `alfred run fix the bug`.
    if argv and not argv[0].startswith("-") and argv[0] not in _COMMANDS:
        argv = ["run", *argv]

    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
