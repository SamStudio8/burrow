import argparse
from pathlib import Path
from burrow.models import Request


def cmd_init(args):
    request = Request(summary=args.summary or "", repo_root=Path.cwd())
    request.save()


def main():
    parser = argparse.ArgumentParser(prog="burrow")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("summary", nargs="?", default="")
    init_parser.set_defaults(func=cmd_init)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
