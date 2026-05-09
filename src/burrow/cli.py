import argparse
import subprocess
import sys
from pathlib import Path
from burrow.dispatch import build_payload
from burrow.models import Request, Response
from burrow.tui import BurrowApp

# did you know, you cant get these on windows
EX_CANTCREAT = 73
EX_DATAERR = 65
EX_NOINPUT = 66
EX_USAGE = 64


def get_repo_root(cwd=None):
    if cwd is None:
        cwd = Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stderr.write("Not inside a git repository\n")
        sys.exit(EX_NOINPUT)
    return Path(result.stdout.strip()).resolve()


def _current_request(ex_on_noinput=False):
    repo_root = get_repo_root()
    session = repo_root / ".burrow" / "request.json"
    if not session.exists():
        if ex_on_noinput:
            sys.stderr.write("No session found — run 'burrow start' first\n")
            sys.exit(EX_NOINPUT)
        return None
    return Request.load(repo_root)


def cmd_start(args):
    if _current_request() is not None:
        sys.stderr.write("A session already exists at .burrow/request.json\n")
        sys.exit(EX_CANTCREAT)
    request = Request(summary=args.summary or "", repo_root=get_repo_root())
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
    repo_root = get_repo_root()
    _current_request(ex_on_noinput=True)
    burrow_dir = repo_root / ".burrow"
    (burrow_dir / "request.json").unlink()
    response = burrow_dir / "response.json"
    if response.exists():
        response.unlink()


def cmd_send(args):
    request = _current_request(ex_on_noinput=True)
    sys.stdout.write(build_payload(request))


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
        request = _current_request()
        if request is None:
            request = Request(summary="", repo_root=get_repo_root())
            request.save()
        BurrowApp(request=request).run()
