import pytest
from unittest.mock import patch
from textual.widgets import Static
from burrow.models import Comment, Request
from textual.widgets import TextArea
from burrow.tui import get_diff, parse_diff, BurrowApp, colour_line, StaleSessionModal, SummaryModal


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


@pytest.mark.rule("diff-line-colour")
def test_colour_line():
    added = colour_line("+added line")
    removed = colour_line("-removed line")
    context = colour_line(" context line")
    assert "added line" in added.plain
    assert "removed line" in removed.plain
    assert "context line" in context.plain
    assert added.style != removed.style
    assert added.style != context.style


@pytest.mark.rule("diff-nav-line")
async def test_j_advances_line(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            assert app.selected_line == 0
            await pilot.press("j")
            assert app.selected_line == 1


@pytest.mark.rule("diff-nav-line")
async def test_k_retreats_line(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("j")
            assert app.selected_line == 2
            await pilot.press("k")
            assert app.selected_line == 1


@pytest.mark.rule("diff-nav-line")
async def test_line_nav_clamps_at_hunk_bounds(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("k")
            assert app.selected_line == 0
            for _ in range(10):
                await pilot.press("j")
            assert app.selected_line == len(app.hunks[0].lines) - 1


@pytest.mark.rule("diff-nav-line-scroll")
async def test_line_navigation_scrolls_line_into_view(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            line_widget = app.screen.query_one("#hunk-0-line-1")
            assert "selected" in line_widget.classes


@pytest.mark.rule("diff-nav-hunk-clears-line")
async def test_hunk_change_clears_previous_line_selection(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("j")
            assert "selected" in app.screen.query_one("#hunk-0-line-2").classes
            await pilot.press("]")
            assert "selected" not in app.screen.query_one("#hunk-0-line-2").classes
            assert "selected" in app.screen.query_one("#hunk-1-line-0").classes


@pytest.mark.rule("diff-nav-line")
async def test_line_resets_on_hunk_change(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("j")
            assert app.selected_line == 2
            await pilot.press("]")
            assert app.selected_line == 0


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


@pytest.mark.rule("comment-select-range")
async def test_hash_opens_compose_on_current_line(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("#")
            assert app.composing is not None
            assert app.composing.file == "foo.py"
            assert app.composing.first_line == app.composing.last_line


@pytest.mark.rule("comment-select-range-highlight")
async def test_selection_highlights_range_of_lines(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("v")
            await pilot.press("j")
            await pilot.press("j")
            assert "selected" in app.screen.query_one("#hunk-0-line-0").classes
            assert "selected" in app.screen.query_one("#hunk-0-line-1").classes
            assert "selected" in app.screen.query_one("#hunk-0-line-2").classes
            assert "selected" not in app.screen.query_one("#hunk-0-line-3").classes


@pytest.mark.rule("comment-select-range-extend")
async def test_hash_in_selection_mode_uses_range(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("v")
            await pilot.press("j")
            await pilot.press("j")
            await pilot.press("#")
            assert app.composing is not None
            assert app.composing.first_line != app.composing.last_line


@pytest.mark.rule("comment-compose")
async def test_hash_inserts_compose_widget_after_selected_line(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("#")
            compose = app.screen.query("ComposeWidget")
            assert len(compose) == 1


@pytest.mark.rule("comment-compose-expand")
async def test_compose_grows_with_content(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.press("#")
            widget = app.screen.query_one("ComposeWidget")
            initial_height = widget.size.height
            await pilot.press("a", "enter", "b", "enter", "c")
            assert widget.size.height > initial_height


@pytest.mark.rule("comment-compose-submit")
async def test_ctrl_enter_submits_and_removes_compose(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("#")
            await pilot.press("h", "i")
            await pilot.press("ctrl+j")
            assert len(app.screen.query("ComposeWidget")) == 0
            assert len(app.request.comments) == 1
            assert app.request.comments[0].body == "hi"


@pytest.mark.rule("comment-submitted-inline")
async def test_submitted_comment_renders_inline(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("#")
            await pilot.press("h", "i")
            await pilot.press("ctrl+j")
            blocks = app.screen.query("CommentBlock")
            assert len(blocks) == 1
            assert "hi" in str(blocks.first().render())
            assert "commented" in app.screen.query_one("#hunk-0-line-1").classes


@pytest.mark.rule("comment-empty-notice")
async def test_empty_submit_flashes_error_class(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("#")
            await pilot.press("ctrl+j")
            widget = app.screen.query_one("ComposeWidget")
            assert "error" in widget.classes


@pytest.mark.rule("comment-compose-cancel")
async def test_escape_cancels_compose(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("#")
            assert app.composing is not None
            assert len(app.screen.query("ComposeWidget")) == 1
            await pilot.press("escape")
            assert app.composing is None
            assert len(app.screen.query("ComposeWidget")) == 0


@pytest.mark.rule("comment-select-range-cross-hunk")
async def test_hunk_navigation_discards_selection(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("v")
            await pilot.press("j")
            assert app.selecting is not None
            await pilot.press("]")
            assert app.selecting is None


@pytest.mark.rule("comment-select-range-cancel")
async def test_v_again_cancels_selection(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("v")
            await pilot.press("j")
            assert app.selecting is not None
            await pilot.press("v")
            assert app.selecting is None
            assert "selected" not in app.screen.query_one("#hunk-0-line-0").classes
            assert "selected" in app.screen.query_one("#hunk-0-line-1").classes


@pytest.mark.rule("comment-select-range-start")
async def test_v_enters_selection_mode_at_current_line(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("j")
            assert app.selecting is None
            await pilot.press("v")
            assert app.selecting is not None
            assert app.selecting == app.selected_line


@pytest.mark.rule("tui-help")
async def test_question_mark_toggles_help_panel(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            assert len(app.screen.query("HelpOverlay")) == 0
            await pilot.press("question_mark")
            assert len(app.screen.query("HelpOverlay")) == 1
            await pilot.press("question_mark")
            assert len(app.screen.query("HelpOverlay")) == 0


@pytest.mark.rule("tui-statusbar")
async def test_statusbar_shows_review_summary(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            bar = str(app.screen.query_one("StatusBar").render())
            assert "2" in bar   # 2 files
            assert "3" in bar   # 3 hunks
            assert "1/3" in bar # hunk position
            assert "0" in bar   # 0 comments
            await pilot.press("j")
            await pilot.press("#")
            await pilot.press("h", "i")
            await pilot.press("ctrl+j")
            bar = str(app.screen.query_one("StatusBar").render())
            assert "1" in bar   # 1 comment


@pytest.mark.rule("tui-load-comments")
async def test_existing_comments_rendered_on_startup(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.add_comment(file="foo.py", first_line=2, last_line=2, body="existing comment")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            blocks = app.screen.query("CommentBlock")
            assert len(blocks) == 1
            assert "existing comment" in str(blocks.first().render())
            assert "commented" in app.screen.query_one("#hunk-0-line-1").classes


@pytest.mark.rule("tui-stale-session")
async def test_stale_session_modal_shown_when_comment_file_missing(tmp_path):
    request = Request(summary="", repo_root=tmp_path)
    request.comments.append(Comment(file="gone.py", first_line=1, last_line=1, body="orphaned"))
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            assert any(isinstance(s, StaleSessionModal) for s in app.screen_stack)
            old_id = request.id
            await pilot.press("y")
            assert not any(isinstance(s, StaleSessionModal) for s in app.screen_stack)
            assert len(app.request.comments) == 0
            assert app.request.id != old_id
            await pilot.pause()
            bar = str(app.screen.query_one("StatusBar").render())
            assert "0 comments" in bar


@pytest.mark.rule("summary-edit-tui")
async def test_at_opens_summary_modal(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="initial", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("@")
            assert any(isinstance(s, SummaryModal) for s in app.screen_stack)


@pytest.mark.rule("summary-edit-tui")
async def test_summary_modal_prefilled_with_current_summary(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="initial", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("@")
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert modal.query_one(TextArea).text == "initial"


@pytest.mark.rule("summary-edit-tui")
async def test_ctrl_enter_saves_summary(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("@")
            await pilot.press("n", "e", "w")
            await pilot.press("ctrl+j")
            assert not any(isinstance(s, SummaryModal) for s in app.screen_stack)
            assert app.request.summary == "new"


@pytest.mark.rule("summary-edit-tui")
async def test_escape_discards_summary_edit(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="old", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("@")
            await pilot.press("escape")
            assert not any(isinstance(s, SummaryModal) for s in app.screen_stack)
            assert app.request.summary == "old"


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
