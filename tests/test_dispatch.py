import pytest
from unittest.mock import AsyncMock, patch
from burrow.dispatch import build_payload, run_agent
from burrow.models import Request
from burrow.preamble import PREAMBLE


@pytest.mark.rule("dispatch-spawn")
def test_build_payload_contains_preamble_and_request_id(tmp_path):
    request = Request(summary="hello", repo_root=tmp_path)
    payload = build_payload(request)
    assert PREAMBLE in payload
    assert str(request.id) in payload


@pytest.mark.rule("dispatch-spawn")
async def test_run_agent_spawns_claude_with_tools_and_payload_on_stdin(tmp_path):
    request = Request(summary="", repo_root=tmp_path)
    payload = build_payload(request)

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_spawn:
        await run_agent(request)

    mock_spawn.assert_called_once()
    call = mock_spawn.call_args
    assert call.args[:2] == ("claude", "-p")
    assert "--allowedTools" in call.args
    allowed = list(call.args[call.args.index("--allowedTools") + 1:])
    assert "Bash" in allowed
    assert "Read" in allowed
    assert "Edit" in allowed
    assert "Write" in allowed
    assert call.kwargs["cwd"] == request.repo_root
    stdin_data = call.kwargs["stdin"]
    import asyncio
    assert stdin_data == asyncio.subprocess.PIPE
    mock_proc.communicate.assert_called_once()
    stdin_sent = mock_proc.communicate.call_args.kwargs.get("input") or mock_proc.communicate.call_args.args[0]
    assert PREAMBLE.encode() in stdin_sent
    assert str(request.id).encode() in stdin_sent
