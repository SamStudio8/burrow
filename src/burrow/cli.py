import argparse
import os
import sys
from pathlib import Path
from burrow.models import Request

# did you know, you cant get these on windows
EX_CANTCREAT = 73
EX_NOINPUT = 66
EX_USAGE = 64


def cmd_init(args):
    session = Path.cwd() / ".burrow" / "request.json"
    if session.exists():
        sys.stderr.write("A session already exists at .burrow/request.json\n")
        sys.exit(EX_CANTCREAT)
    request = Request(summary=args.summary or "", repo_root=Path.cwd())
    request.save()


def cmd_add(args):
    session = Path.cwd() / ".burrow" / "request.json"
    if not session.exists():
        sys.stderr.write("error: no session found — run 'burrow init' first\n")
        sys.exit(EX_NOINPUT)
    request = Request.load(Path.cwd())
    request.add_comment(file=args.file, first_line=int(args.first_line), last_line=int(args.last_line), body=args.body)
    request.save()


class BurrowParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"error: {message}\n")
        sys.exit(EX_USAGE)


def main():
    parser = BurrowParser(prog="burrow")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("summary", nargs="?", default="")
    init_parser.set_defaults(func=cmd_init)

    add_parser = subparsers.add_parser("c")
    add_parser.add_argument("file")
    add_parser.add_argument("first_line")
    add_parser.add_argument("last_line")
    add_parser.add_argument("body")
    add_parser.set_defaults(func=cmd_add)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
