import argparse
import json
import sys
from pathlib import Path
from burrow.models import Request, Response, _serialise
from burrow.preamble import PREAMBLE
from burrow.tui import BurrowApp

# did you know, you cant get these on windows
EX_CANTCREAT = 73
EX_DATAERR = 65
EX_NOINPUT = 66
EX_USAGE = 64


def _current_request(ex_on_noinput=False):
    session = Path.cwd() / ".burrow" / "request.json"
    if not session.exists():
        if ex_on_noinput:
            sys.stderr.write("No session found — run 'burrow start' first\n")
            sys.exit(EX_NOINPUT)
        return None
    return Request.load(Path.cwd())


def cmd_start(args):
    if _current_request() is not None:
        sys.stderr.write("A session already exists at .burrow/request.json\n")
        sys.exit(EX_CANTCREAT)
    request = Request(summary=args.summary or "", repo_root=Path.cwd())
    request.save()
    sys.stderr.write("Session started at .burrow/request.json\n")


def cmd_validate(args):
    request = _current_request(ex_on_noinput=True)
    if args.response is None:
        return
    try:
        Response.load(Path(args.response), request)
    except FileNotFoundError:
        sys.stderr.write(f"response file not found: {args.response}\n")
        sys.exit(EX_NOINPUT)
    except ValueError as e:
        sys.stderr.write(f"validation failed: {e}\n")
        sys.exit(EX_DATAERR)


def cmd_add(args):
    request = _current_request(ex_on_noinput=True)
    request.add_comment(file=args.file, first_line=int(args.first_line), last_line=int(args.last_line), body=args.body)
    request.save()


def cmd_end(args):
    _current_request(ex_on_noinput=True)
    burrow_dir = Path.cwd() / ".burrow"
    (burrow_dir / "request.json").unlink()
    response = burrow_dir / "response.json"
    if response.exists():
        response.unlink()


def cmd_send(args):
    request = _current_request(ex_on_noinput=True)
    request_json = json.dumps(request.to_dict(), default=_serialise, indent=2)
    sys.stdout.write(PREAMBLE + "\n\n" + request_json + "\n")


class BurrowParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"error: {message}\n")
        sys.exit(EX_USAGE)


def main():
    parser = BurrowParser(prog="burrow")
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start")
    start_parser.add_argument("summary", nargs="?", default="")
    start_parser.set_defaults(func=cmd_start)

    add_parser = subparsers.add_parser("c")
    add_parser.add_argument("file")
    add_parser.add_argument("first_line")
    add_parser.add_argument("last_line")
    add_parser.add_argument("body")
    add_parser.set_defaults(func=cmd_add)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("response", nargs="?", default=None)
    validate_parser.set_defaults(func=cmd_validate)

    send_parser = subparsers.add_parser("send")
    send_parser.set_defaults(func=cmd_send)

    end_parser = subparsers.add_parser("end")
    end_parser.set_defaults(func=cmd_end)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        if _current_request() is None:
            Request(summary="", repo_root=Path.cwd()).save()
        BurrowApp().run()
