import pytest
from unittest.mock import patch
from burrow.cli import main, EX_CANTCREAT, EX_NOINPUT, EX_USAGE


@pytest.mark.rule("init-invocation")
def test_init_is_valid_subcommand(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("sys.argv", ["burrow", "init"]):
        main()


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
def test_add_is_valid_subcommand(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "foo.py").write_text("hello\n")
    with patch("sys.argv", ["burrow", "init"]):
        main()
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
    assert "session" in capsys.readouterr().err


@pytest.mark.rule("init-excantcreat")
def test_init_fails_if_session_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".burrow").mkdir()
    (tmp_path / ".burrow" / "request.json").write_text("{}")
    with patch("sys.argv", ["burrow", "init"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == EX_CANTCREAT
    assert "session already exists" in capsys.readouterr().err
