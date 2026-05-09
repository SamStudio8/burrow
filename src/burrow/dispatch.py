import asyncio
import json
from burrow.models import _serialise
from burrow.preamble import PREAMBLE


def build_payload(request):
    request_json = json.dumps(request.to_dict(), default=_serialise, indent=2)
    return PREAMBLE + "\n\n" + request_json + "\n"


async def run_agent(request):
    payload = build_payload(request).encode()
    proc = await asyncio.create_subprocess_exec(
        "claude", "--print",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=request.repo_root,
    )
    await proc.communicate(input=payload)
    return proc.returncode
