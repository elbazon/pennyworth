"""The Pennyworth command line — ``alfred``.

Minimal for now: manage knowledge packs and render the assembled brain. Driving
a live coding agent with that prompt is a later increment.
"""

from __future__ import annotations

import argparse
import sys

from pennyworth import __version__
from pennyworth import packs as _packs
from pennyworth.prompt import build_system_prompt


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
    print(build_system_prompt(_packs.active_pack()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alfred",
        description="Alfred — a butler-engineer companion (Pennyworth).",
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
    attach = pack_sub.add_parser(
        "attach", help="install and activate a pack directory"
    )
    attach.add_argument("path", help="path to a directory containing a pack manifest")
    attach.set_defaults(func=_cmd_pack_attach)
    pack_sub.add_parser("detach", help="detach the active pack").set_defaults(
        func=_cmd_pack_detach
    )

    sub.add_parser(
        "prompt", help="print the assembled system prompt for the active pack"
    ).set_defaults(func=_cmd_prompt)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
