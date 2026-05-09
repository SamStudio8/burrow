import json
import pytest
from unittest.mock import patch
from textual.widgets import Static
from burrow.models import Comment, Request
from textual.widgets import TextArea
from burrow.tui import get_diff, parse_diff, BurrowApp, colour_line, StaleSessionModal, SummaryEditModal, SummaryModal, ErrorModal


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


@pytest.mark.rule("diff-source")
def test_get_diff_falls_back_to_last_commit_when_clean(tmp_path):
    fake_diff = "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n"
    def fake_run(cmd, **kwargs):
        result = type("R", (), {})()
        if "HEAD~1" in cmd:
            result.stdout = fake_diff
        else:
            result.stdout = ""
        result.returncode = 0
        return result
    with patch("subprocess.run", side_effect=fake_run) as mock_run:
        result = get_diff(tmp_path)
    assert result == fake_diff
    calls = [c.args[0] for c in mock_run.call_args_list]
    assert any("HEAD~1" in c for c in calls)


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
            await pilot.press("l")
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
            await pilot.press("l")
            assert app.selected_line == 0


@pytest.mark.rule("diff-nav-next-hunk")
async def test_next_hunk_advances_selection(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            assert app.selected_hunk == 0
            await pilot.press("l")
            assert app.selected_hunk == 1


@pytest.mark.rule("diff-nav-prev-hunk")
async def test_prev_hunk_retreats_selection(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("l")
            await pilot.press("l")
            assert app.selected_hunk == 2
            await pilot.press("h")
            assert app.selected_hunk == 1


@pytest.mark.rule("diff-nav-next-hunk")
async def test_next_hunk_clamps_at_end(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("l")
            await pilot.press("l")
            await pilot.press("l")
            assert app.selected_hunk == 2


@pytest.mark.rule("diff-nav-prev-hunk")
async def test_prev_hunk_clamps_at_start(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("h")
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
            await pilot.press("l")
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
async def test_stale_session_modal_shown_when_comment_not_in_diff(tmp_path):
    request = Request(summary="", repo_root=tmp_path)
    # gone.py does not appear in SAMPLE_DIFF, so _locate_comment returns None
    request.comments.append(Comment(file="gone.py", first_line=1, last_line=1, body="orphaned"))
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            assert any(isinstance(s, StaleSessionModal) for s in app.screen_stack)
            old_id = request.id
            await pilot.press(StaleSessionModal.CONFIRM.key)
            assert not any(isinstance(s, StaleSessionModal) for s in app.screen_stack)
            assert len(app.request.comments) == 0
            assert app.request.id != old_id
            await pilot.pause()
            bar = str(app.screen.query_one("StatusBar").render())
            assert "0 comments" in bar


@pytest.mark.rule("tui-stale-session")
async def test_stale_session_modal_shown_when_anchor_line_not_in_diff(tmp_path):
    # foo.py is in SAMPLE_DIFF but only lines 1-4; line 99 is not in any hunk
    (tmp_path / "foo.py").write_text("".join(f"line{i}\n" for i in range(1, 200)))
    request = Request(summary="", repo_root=tmp_path)
    request.comments.append(Comment(file="foo.py", first_line=99, last_line=99, body="off-diff"))
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            assert any(isinstance(s, StaleSessionModal) for s in app.screen_stack)


@pytest.mark.rule("summary-edit-tui")
async def test_summary_modal_open_prefilled_and_saves(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="initial", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("@")
            assert any(isinstance(s, SummaryEditModal) for s in app.screen_stack)
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryEditModal))
            assert modal.query_one(TextArea).text == "initial"
            modal.query_one(TextArea).clear()
            await pilot.press("n", "e", "w")
            await pilot.press(SummaryEditModal.CONFIRM.key)
            assert not any(isinstance(s, SummaryEditModal) for s in app.screen_stack)
            assert app.request.summary == "new"


@pytest.mark.rule("summary-edit-tui")
async def test_escape_discards_summary_edit(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="old", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press("@")
            await pilot.press(SummaryEditModal.DISMISS.key)
            assert not any(isinstance(s, SummaryEditModal) for s in app.screen_stack)
            assert app.request.summary == "old"


@pytest.mark.rule("response-load-tui")
async def test_existing_response_loaded_on_startup(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.save()
    comment = request.add_comment(file="foo.py", first_line=2, last_line=2, body="a comment")
    request.save()
    response_data = {
        "id": "a1b2c3d4-0000-0000-0000-000000000001",
        "request_id": str(request.id),
        "created_at": "2026-04-29T21:00:00+00:00",
        "summary": "",
        "agent_metadata": {"name": "test", "version": "0"},
        "comments": [{
            "id": str(comment.id),
            "file": comment.file,
            "first_line": comment.first_line,
            "last_line": comment.last_line,
            "body": comment.body,
            "status": "done",
            "reply": "fixed it",
        }],
    }
    (tmp_path / ".burrow" / "response.json").write_text(json.dumps(response_data))
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            block = app.screen.query_one("CommentBlock")
            assert "fixed it" in str(block.render())
            assert "status-done" in block.classes


@pytest.mark.rule("response-load-tui")
async def test_response_watch_loads_on_file_creation(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.save()
    comment = request.add_comment(file="foo.py", first_line=2, last_line=2, body="a comment")
    request.save()
    response_data = {
        "id": "a1b2c3d4-0000-0000-0000-000000000001",
        "request_id": str(request.id),
        "created_at": "2026-04-29T21:00:00+00:00",
        "summary": "",
        "agent_metadata": {"name": "test", "version": "0"},
        "comments": [{
            "id": str(comment.id),
            "file": comment.file,
            "first_line": comment.first_line,
            "last_line": comment.last_line,
            "body": comment.body,
            "status": "done",
            "reply": "fixed it",
        }],
    }
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            (tmp_path / ".burrow" / "response.json").write_text(json.dumps(response_data))
            await pilot.pause(delay=0.5)
            block = app.screen.query_one("CommentBlock")
            assert "fixed it" in str(block.render())
            assert "status-done" in block.classes


@pytest.mark.rule("response-comment-reply")
async def test_comment_block_renders_reply_when_present(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    comment = request.add_comment(file="foo.py", first_line=2, last_line=2, body="a comment")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            block = app.screen.query_one("CommentBlock")
            assert "a comment" in str(block.render())
            assert "a reply" not in str(block.render())
            block.update_reply("a reply")
            assert "a reply" in str(block.render())


@pytest.mark.rule("response-comment-status-colour")
async def test_comment_block_border_colour_reflects_status(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.add_comment(file="foo.py", first_line=2, last_line=2, body="a comment")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            block = app.screen.query_one("CommentBlock")
            assert "status-todo" in block.classes
            block.update_status("done")
            assert "status-done" in block.classes
            assert "status-todo" not in block.classes


@pytest.mark.rule("comment-nav")
async def test_n_navigates_comments_in_visual_order(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    # Add comments in reverse visual order
    request.add_comment(file="foo.py", first_line=2, last_line=2, body="second")
    request.add_comment(file="foo.py", first_line=1, last_line=1, body="first")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            await pilot.press("n")
            # should land on visual first (foo.py line 1, index 0), not creation first (line 2)
            assert app.selected_line == 0
            await pilot.press("n")
            # second n lands on visual second (foo.py line 2, index 1)
            assert app.selected_line == 1


@pytest.mark.rule("comment-nav")
async def test_n_navigates_to_comment_hunk_and_line(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.add_comment(file="foo.py", first_line=1, last_line=1, body="first")
    request.add_comment(file="foo.py", first_line=2, last_line=2, body="second")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            assert app._comment_index == -1
            await pilot.press("n")
            assert app._comment_index == 0
            assert app.selected_hunk == 0
            assert app.selected_line == 0  # line index of foo.py line 1 in hunk 0
            await pilot.press("n")
            assert app._comment_index == 1
            assert app.selected_line == 1  # line index of foo.py line 2 in hunk 0
            await pilot.press("n")
            assert app._comment_index == 1  # clamps at end


@pytest.mark.rule("comment-nav")
async def test_p_navigates_to_comment_hunk_and_line(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.add_comment(file="foo.py", first_line=1, last_line=1, body="first")
    request.add_comment(file="foo.py", first_line=2, last_line=2, body="second")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            await pilot.press("n")
            await pilot.press("n")
            assert app._comment_index == 1
            await pilot.press("shift+n")
            assert app._comment_index == 0
            assert app.selected_hunk == 0
            assert app.selected_line == 0  # line index of foo.py line 1 in hunk 0
            await pilot.press("shift+n")
            assert app._comment_index == -1  # clamps before first


@pytest.mark.rule("comment-nav-visible")
async def test_comment_nav_scrolls_first_anchor_line_to_top(tmp_path):
    # Build a diff long enough that the comment anchor starts off-screen
    n_context = 40
    file_lines = [f"line{i}\n" for i in range(1, n_context + 10)]
    (tmp_path / "foo.py").write_text("".join(file_lines))
    context = "".join(f" line{i}\n" for i in range(1, n_context + 1))
    tall_diff = (
        "diff --git a/foo.py b/foo.py\n"
        "index 0000001..0000002 100644\n"
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        f"@@ -1,{n_context + 1} +1,{n_context + 2} @@\n"
        + context
        + f"+newline\n"
        + f" line{n_context + 1}\n"
    )
    request = Request(summary="", repo_root=tmp_path)
    # anchor is near the bottom of the hunk — will be off-screen in a small terminal
    request.add_comment(file="foo.py", first_line=n_context, last_line=n_context + 1, body="bottom comment")
    with patch("burrow.tui.get_diff", return_value=tall_diff):
        app = BurrowApp(request=request)
        async with app.run_test(size=(120, 10)) as pilot:
            await pilot.press("n")
            await pilot.pause(delay=0.2)
            diff_view = app.screen.query_one("#diff-view")
            first_line = app.screen.query_one("#hunk-0-line-39")  # line index n_context-1
            # virtual_region.y is absolute position in scroll content; scroll_y is viewport top
            # difference should be near 0 if the line is scrolled to the top of the viewport
            line_top_in_viewport = first_line.virtual_region.y - diff_view.scroll_y
            assert 0 <= line_top_in_viewport <= 4


@pytest.mark.rule("comment-nav-highlight")
async def test_comment_nav_highlights_anchor_lines(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    # range comment: foo.py lines 1-2 → hunk 0 line indices 0-1
    request.add_comment(file="foo.py", first_line=1, last_line=2, body="range comment")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            await pilot.press("n")
            assert "selected" in app.screen.query_one("#hunk-0-line-0").classes
            assert "selected" in app.screen.query_one("#hunk-0-line-1").classes
            assert "selected" not in app.screen.query_one("#hunk-0-line-2").classes


@pytest.mark.rule("dispatch-modal-summary")
async def test_dispatch_modal_has_two_columns_with_datatable(tmp_path):
    from textual.widgets import DataTable
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="my summary", repo_root=tmp_path)
    request.add_comment(file="foo.py", first_line=2, last_line=2, body="fix this")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            await pilot.press(">")
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert modal.query_one(TextArea).text == "my summary"
            table = modal.query_one(DataTable)
            assert table.row_count == 1
            # table has filename and line range columns
            assert "foo.py" in str(table.get_row_at(0))


@pytest.mark.rule("dispatch-modal-summary")
async def test_dispatch_modal_jk_navigate_table_and_update_detail(tmp_path):
    from textual.widgets import DataTable
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.add_comment(file="foo.py", first_line=1, last_line=1, body="first comment")
    request.add_comment(file="foo.py", first_line=2, last_line=2, body="second comment")
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            await pilot.press(">")
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            table = modal.query_one(DataTable)
            table.focus()
            await pilot.pause()
            detail = str(modal.query_one("#dispatch-comment-body").render())
            assert "first comment" in detail
            await pilot.press("j")
            await pilot.pause()
            detail = str(modal.query_one("#dispatch-comment-body").render())
            assert "second comment" in detail


@pytest.mark.rule("dispatch-modal-summary")
async def test_dispatch_modal_summary_is_editable_and_saved(tmp_path):
    async def fake_run_agent(request):
        return 1

    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        with patch("burrow.tui.run_agent", fake_run_agent):
            app = BurrowApp(request=Request(summary="before", repo_root=tmp_path))
            async with app.run_test() as pilot:
                await pilot.press(">")
                modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
                ta = modal.query_one(TextArea)
                ta.clear()
                await pilot.press("a", "f", "t", "e", "r")
                await pilot.press(SummaryModal.CONFIRM.key)
                await pilot.pause(delay=0.2)
                assert app.request.summary == "after"


@pytest.mark.rule("dispatch-waiting")
async def test_dispatch_modal_shows_spinner_while_waiting(tmp_path):
    from textual.widgets import LoadingIndicator

    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            spinner_seen = []
            async def fake_run_agent(request):
                modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
                spinner_seen.append(len(modal.query(LoadingIndicator)) > 0)
                return 0
            with patch("burrow.tui.run_agent", fake_run_agent):
                await pilot.press(">")
                await pilot.press(SummaryModal.CONFIRM.key)
                await pilot.pause(delay=0.2)
            # spinner was visible during agent run; gone after agent finishes
            assert spinner_seen == [True]
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert len(modal.query(LoadingIndicator)) == 0
            assert modal._state != "waiting"


@pytest.mark.rule("dispatch-success")
async def test_dispatch_success_transitions_modal_to_response_state(tmp_path):
    (tmp_path / "foo.py").write_text("line1\nline2\nline3\nline4\n")
    request = Request(summary="", repo_root=tmp_path)
    request.save()
    comment = request.add_comment(file="foo.py", first_line=2, last_line=2, body="fix this")
    request.save()
    response_data = {
        "id": "a1b2c3d4-0000-0000-0000-000000000001",
        "request_id": str(request.id),
        "created_at": "2026-04-29T21:00:00+00:00",
        "summary": "all done",
        "agent_metadata": {"name": "test", "version": "0"},
        "comments": [{
            "id": str(comment.id),
            "file": comment.file,
            "first_line": comment.first_line,
            "last_line": comment.last_line,
            "body": comment.body,
            "status": "done",
            "reply": "fixed it",
        }],
    }

    async def fake_run_agent(request):
        (tmp_path / ".burrow" / "response.json").write_text(json.dumps(response_data))
        return 0

    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            with patch("burrow.tui.run_agent", fake_run_agent):
                await pilot.press(">")
                await pilot.press(SummaryModal.CONFIRM.key)
                await pilot.pause(delay=0.2)
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert modal._state == "response"
            # left pane shows agent summary as read-only TextArea
            ta = modal.query_one("#dispatch-summary", TextArea)
            assert ta.read_only
            assert "all done" in ta.text
            # table row coloured by status
            from textual.widgets import DataTable
            table = modal.query_one(DataTable)
            assert table.row_count == 1
            # close modal and check CommentBlock updated
            await pilot.press(SummaryModal.CLOSE.key)
            assert not any(isinstance(s, SummaryModal) for s in app.screen_stack)
            block = app.screen.query_one("CommentBlock")
            assert "status-done" in block.classes
            assert "fixed it" in str(block.render())


@pytest.mark.rule("dispatch-retry")
async def test_retry_keeps_modal_open_and_redispatches(tmp_path):
    call_count = [0]

    async def fake_run_agent(request):
        call_count[0] += 1
        return 1  # always fail

    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            with patch("burrow.tui.run_agent", fake_run_agent):
                await pilot.press(">")
                await pilot.press(SummaryModal.CONFIRM.key)
                await pilot.pause(delay=0.2)
                modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
                assert modal._state == "error"
                await pilot.press(SummaryModal.RETRY.key)
                await pilot.pause(delay=0.2)
            # modal still open (in error state again), called agent twice
            assert call_count[0] == 2
            assert any(isinstance(s, SummaryModal) for s in app.screen_stack)
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert modal._state == "error"


@pytest.mark.rule("dispatch-error")
async def test_dispatch_error_transitions_modal_on_nonzero_exit(tmp_path):
    async def fake_run_agent(request):
        return 1

    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            with patch("burrow.tui.run_agent", fake_run_agent):
                await pilot.press(">")
                assert any(isinstance(s, SummaryModal) for s in app.screen_stack)
                modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
                assert modal._state == "compose"
                await pilot.press(SummaryModal.CONFIRM.key)
                await pilot.pause(delay=0.2)
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert modal._state == "error"
            hint = str(modal.query_one("#dispatch-hint", Static).render())
            assert "1" in str(modal.query_one("#dispatch-error-msg", Static).render())
            assert SummaryModal.RETRY.label in hint
            # dismiss closes the modal from error state
            await pilot.press(SummaryModal.DISMISS.key)
            assert not any(isinstance(s, SummaryModal) for s in app.screen_stack)


@pytest.mark.rule("dispatch-error")
async def test_dispatch_error_shown_when_response_missing_or_invalid(tmp_path):
    async def fake_run_no_response(request):
        return 0

    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            with patch("burrow.tui.run_agent", fake_run_no_response):
                await pilot.press(">")
                await pilot.press(SummaryModal.CONFIRM.key)
                await pilot.pause(delay=0.2)
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert modal._state == "error"

    request = Request(summary="", repo_root=tmp_path)
    request.save()

    async def fake_run_bad_response(req):
        (tmp_path / ".burrow" / "response.json").write_text('{"request_id": "00000000-0000-0000-0000-000000000000"}')
        return 0

    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=request)
        async with app.run_test() as pilot:
            with patch("burrow.tui.run_agent", fake_run_bad_response):
                await pilot.press(">")
                await pilot.press(SummaryModal.CONFIRM.key)
                await pilot.pause(delay=0.2)
            modal = next(s for s in app.screen_stack if isinstance(s, SummaryModal))
            assert modal._state == "error"


@pytest.mark.rule("dispatch-confirm")
async def test_escape_dismisses_summary_modal_in_compose_state(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            await pilot.press(">")
            assert any(isinstance(s, SummaryModal) for s in app.screen_stack)
            await pilot.press(SummaryModal.DISMISS.key)
            assert not any(isinstance(s, SummaryModal) for s in app.screen_stack)


@pytest.mark.rule("diff-nav-hunk-highlight")
async def test_selected_hunk_is_highlighted(tmp_path):
    with patch("burrow.tui.get_diff", return_value=SAMPLE_DIFF):
        app = BurrowApp(request=Request(summary="", repo_root=tmp_path))
        async with app.run_test() as pilot:
            hunk0 = app.screen.query_one("#hunk-0")
            hunk1 = app.screen.query_one("#hunk-1")
            assert "selected" in hunk0.classes
            assert "selected" not in hunk1.classes
            await pilot.press("l")
            assert "selected" not in hunk0.classes
            assert "selected" in hunk1.classes
