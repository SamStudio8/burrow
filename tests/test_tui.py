import pytest
from unittest.mock import patch
from burrow.tui import get_diff


@pytest.mark.rule("diff-source")
def test_get_diff_returns_staged_and_unstaged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_diff = "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = fake_diff
        mock_run.return_value.returncode = 0
        result = get_diff(tmp_path)
    mock_run.assert_called_once()
    args = mock_run.call_args.args[0]
    assert args[:2] == ["git", "diff"]
    assert "HEAD" in args
    assert result == fake_diff
