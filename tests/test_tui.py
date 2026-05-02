import pytest
from unittest.mock import patch
from textual.widgets import Static
from burrow.models import Request
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
def test_parse_diff_hunk_has_target_range():
    hunks = parse_diff(SAMPLE_DIFF)
    assert hunks[0].target_start == 1
    assert hunks[0].target_length == 4
    assert hunks[2].target_start == 5


@pytest.mark.rule("diff-hunks")
async def test_diff_hunks_displayed_in_tui(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    request = Request(summary="", repo_root=tmp_path)
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            widgets = app.screen.query_one("#hunk-0").query(Static)
            text = " ".join(str(w.render()) for w in widgets)
            assert "+line2" in text
            widgets1 = app.screen.query_one("#hunk-1").query(Static)
            text1 = " ".join(str(w.render()) for w in widgets1)
            assert "-lineB" in text1


@pytest.mark.rule("diff-hunk-header")
async def test_hunk_header_shows_filename_and_lines(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            header0 = str(app.screen.query_one("#hunk-0-header").render())
            assert "foo.py" in header0
            assert "@@" not in header0
            header2 = str(app.screen.query_one("#hunk-2-header").render())
            assert "bar.py" in header2


@pytest.mark.rule("diff-nav-next-hunk")
async def test_next_hunk_advances_selection(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            assert app.selected_hunk == 0
            await pilot.press("]")
            assert app.selected_hunk == 1


@pytest.mark.rule("diff-nav-prev-hunk")
async def test_prev_hunk_retreats_selection(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("]")
            await pilot.press("]")
            assert app.selected_hunk == 2
            await pilot.press("[")
            assert app.selected_hunk == 1


@pytest.mark.rule("diff-nav-next-hunk")
async def test_next_hunk_clamps_at_end(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("]")
            await pilot.press("]")
            await pilot.press("]")
            assert app.selected_hunk == 2


@pytest.mark.rule("diff-nav-prev-hunk")
async def test_prev_hunk_clamps_at_start(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("[")
            assert app.selected_hunk == 0


@pytest.mark.rule("diff-nav-hunk-highlight")
async def test_selected_hunk_is_highlighted(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            hunk0 = app.screen.query_one("#hunk-0")
            hunk1 = app.screen.query_one("#hunk-1")
            assert "selected" in hunk0.classes
            assert "selected" not in hunk1.classes
            await pilot.press("]")
            assert "selected" not in hunk0.classes
            assert "selected" in hunk1.classes
