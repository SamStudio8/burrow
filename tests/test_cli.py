import pytest
from unittest.mock import patch
from burrow.cli import main


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


@pytest.mark.rule("init-excantcreat")
def test_init_fails_if_session_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".burrow").mkdir()
    (tmp_path / ".burrow" / "request.json").write_text("{}")
    with patch("sys.argv", ["burrow", "init"]):
        with pytest.raises(SystemExit) as exc:
            main()
    assert exc.value.code == 73
    assert "session already exists" in capsys.readouterr().err
