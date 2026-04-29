import argparse
import sys
from pathlib import Path
from burrow.models import Request

EX_CANTCREAT = 73


def cmd_init(args):
    session = Path.cwd() / ".burrow" / "request.json"
    if session.exists():
        sys.stderr.write("A session already exists at .burrow/request.json\n")
        sys.exit(EX_CANTCREAT)
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
