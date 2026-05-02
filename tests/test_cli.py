import json
import pytest
from unittest.mock import patch
from burrow.cli import main, EX_CANTCREAT, EX_DATAERR, EX_NOINPUT, EX_USAGE
from burrow.models import Request


@pytest.mark.rule("init-invocation")
def test_init_is_valid_subcommand(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["burrow", "init"]):
        main()
    assert "Session initialized at .burrow/request.json" in capsys.readouterr().err


@pytest.mark.rule("init-summary-optional")
@pytest.mark.parametrize("argv", [
    ["burrow", "init", "my review summary"],
    ["burrow", "init"],
])
def test_init_accepts_optional_summary(tmp_path, monkeypatch, argv):
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", argv):
        main()


@pytest.mark.rule("add-invocation")
def test_add_is_valid_subcommand(session):
    (session / "foo.py").write_text("hello\n")
    with patch("sys.argv", ["burrow", "c", "foo.py", "1", "1", "a comment"]):
        main()


@pytest.mark.rule("add-usage")
def test_add_fails_with_missing_args(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["burrow", "c"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_USAGE


@pytest.mark.rule("add-noinput")
def test_add_fails_with_no_session(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["burrow", "c", "foo.py", "1", "1", "a comment"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_NOINPUT
    assert "No session found" in capsys.readouterr().err


@pytest.mark.rule("validate-invocation")
def test_validate_is_valid_subcommand(session):
    with patch("sys.argv", ["burrow", "validate"]):
        main()


@pytest.mark.rule("validate-response-optional")
@pytest.mark.parametrize("argv", [
    ["burrow", "validate"],
    ["burrow", "validate", "response.json"],
])
def test_validate_accepts_optional_response_path(session, argv):
    if "response.json" in argv:
        request = Request.load(session)
        (session / "response.json").write_text(json.dumps({
            "id": "a1b2c3d4-0000-0000-0000-000000000001",
            "request_id": str(request.id),
            "created_at": "2026-04-29T21:00:00+00:00",
            "summary": "",
            "agent_metadata": {"name": "test", "version": "0"},
            "comments": [],
        }))
    with patch("sys.argv", argv):
        main()


@pytest.mark.rule("validate-noinput")
def test_validate_fails_with_missing_response_file(session, capsys):
    capsys.readouterr()
    with patch("sys.argv", ["burrow", "validate", "response.json"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_NOINPUT
    assert "response.json" in capsys.readouterr().err


@pytest.mark.rule("validate-dataerr")
def test_validate_fails_with_invalid_response(session, capsys):
    capsys.readouterr()
    # response.json references a different request_id
    (session / "response.json").write_text('{"request_id": "00000000-0000-0000-0000-000000000000"}')
    with patch("sys.argv", ["burrow", "validate", "response.json"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_DATAERR


@pytest.mark.rule("validate-noinput")
def test_validate_fails_with_no_session(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["burrow", "validate"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_NOINPUT
    assert "No session found" in capsys.readouterr().err


@pytest.mark.rule("send-invocation")
def test_send_is_valid_subcommand(session, capsys):
    with patch("sys.argv", ["burrow", "send"]):
        main()


@pytest.mark.rule("send-noinput")
def test_send_fails_with_no_session(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["burrow", "send"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_NOINPUT
    assert "No session found" in capsys.readouterr().err


@pytest.mark.rule("init-excantcreat")
def test_init_fails_if_session_exists(session, capsys):
    capsys.readouterr()
    with patch("sys.argv", ["burrow", "init"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_CANTCREAT
    assert "session already exists" in capsys.readouterr().err
