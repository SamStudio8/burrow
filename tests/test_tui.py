import pytest
from unittest.mock import patch
from burrow.tui import get_diff, parse_diff, BurrowApp


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


SAMPLE_DIFF = """\
diff --git a/foo.py b/foo.py
index 0000001..0000002 100644
--- a/foo.py
+++ b/foo.py
@@ -1,3 +1,4 @@
 line1
+line2
 line3
 line4
@@ -10,3 +11,3 @@
 lineA
-lineB
+lineC
 lineD
diff --git a/bar.py b/bar.py
index 0000003..0000004 100644
--- a/bar.py
+++ b/bar.py
@@ -5,3 +5,4 @@
 alpha
+beta
 gamma
 delta
"""


@pytest.mark.rule("diff-hunks")
def test_parse_diff_returns_hunks_grouped_by_file():
    hunks = parse_diff(SAMPLE_DIFF)
    assert len(hunks) == 3
    assert hunks[0].file == "foo.py"
    assert hunks[1].file == "foo.py"
    assert hunks[2].file == "bar.py"


@pytest.mark.rule("diff-hunks")
def test_parse_diff_hunk_contains_lines():
    hunks = parse_diff(SAMPLE_DIFF)
    assert any("+line2" in line for line in hunks[0].lines)
    assert any("-lineB" in line for line in hunks[1].lines)


@pytest.mark.rule("diff-hunks")
def test_parse_diff_hunk_has_header():
    hunks = parse_diff(SAMPLE_DIFF)
    assert hunks[0].header.startswith("@@")
    assert hunks[2].header.startswith("@@")


@pytest.mark.rule("diff-hunks")
async def test_diff_hunks_displayed_in_tui(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(repo_root=tmp_path)
        async with app.run_test() as pilot:
            text = str(app.screen.query_one("#diff-view").render())
            assert "foo.py" in text
            assert "+line2" in text
            assert "-lineB" in text
