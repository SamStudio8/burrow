import subprocess
from dataclasses import dataclass

from rich.text import Text
from burrow.models import Request, Response
from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.keys import key_to_character
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static, TextArea
from textual.containers import ScrollableContainer, Vertical
from textual.worker import Worker
from unidiff import PatchSet
from watchfiles import awatch


def colour_line(line):
    if line.startswith("+"):
        return Text(line, style="green")
    if line.startswith("-"):
        return Text(line, style="red")
    return Text(line, style="dim")


@dataclass
class Anchor:
    file: str
    first_line: int
    last_line: int


@dataclass
class Hunk:
    file: str
    target_start: int
    target_length: int
    lines: list[str]


def parse_diff(raw):
    hunks = []
    for patched_file in PatchSet(raw):
        for hunk in patched_file:
            hunks.append(Hunk(
                file=patched_file.path,
                target_start=hunk.target_start,
                target_length=hunk.target_length,
                lines=[str(line) for line in hunk],
            ))
    return hunks


def get_diff(repo_root):
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.stdout


class HunkHeader(Static):
    DEFAULT_CSS = """
    HunkHeader {
        background: $surface;
        color: $text-muted;
        text-style: bold;
        padding: 0 1;
    }
    """


class DiffLine(Static):
    DEFAULT_CSS = """
    DiffLine {
        height: 1;
    }
    DiffLine.commented {
        background: white 15%;
    }
    DiffLine.selected {
        background: white 25%;
    }
    """


class ComposeHint(Static):
    DEFAULT_CSS = """
    ComposeHint {
        height: 1;
        color: $text-muted;
        padding: 0 1;
        margin-bottom: 1;
        text-align: right;
    }
    """


class HunkWidget(Static):
    DEFAULT_CSS = """
    HunkWidget {
        padding: 0 1;
        border-left: thick transparent;
        height: auto;
    }
    HunkWidget.selected {
        border-left: thick $primary;
    }
    HunkWidget.selected HunkHeader {
        background: $primary;
        color: $text;
    }
    """

    def __init__(self, hunk, index):
        super().__init__(id=f"hunk-{index}")
        self._hunk = hunk
        self._index = index

    def compose(self):
        hunk = self._hunk
        end = hunk.target_start + hunk.target_length - 1
        label = f"{hunk.file}  ·  {hunk.target_start}–{end}"
        yield HunkHeader(label, id=f"hunk-{self._index}-header")
        for i, line in enumerate(hunk.lines):
            yield DiffLine(colour_line(line.rstrip("\n")), id=f"hunk-{self._index}-line-{i}")


class ComposeWidget(TextArea):
    DEFAULT_CSS = """
    ComposeWidget {
        height: auto;
        min-height: 2;
        border: solid $accent;
    }
    ComposeWidget:focus {
        border: solid $accent;
    }
    ComposeWidget > .text-area--cursor-line {
        background: transparent;
    }
    ComposeWidget.error {
        border: solid $error;
    }
    ComposeWidget.error:focus {
        border: solid $error;
    }
    """

    def __init__(self, hunk_index, first_line_index, last_line_index):
        super().__init__()
        self._hunk_index = hunk_index
        self._first_line_index = first_line_index
        self._last_line_index = last_line_index

    def on_mount(self):
        self.show_line_numbers = False
        self.focus()

    def on_text_area_changed(self):
        lines = self.text.count("\n") + 1
        self.styles.height = lines + 2  # +2 for border

    def _on_key(self, event):
        if event.key == "ctrl+j":
            event.stop()
            self.app.action_submit_compose()
        elif event.key == "escape":
            event.stop()
            self.app.action_cancel_compose()


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, app_ref):
        super().__init__()
        self._app_ref = app_ref

    def render(self):
        app = self._app_ref
        hunks = app.hunks
        n_files = len({h.file for h in hunks})
        n_hunks = len(hunks)
        pos = f"{app.selected_hunk + 1}/{n_hunks}" if n_hunks else "0/0"
        n_comments = len(app.request.comments)
        return f"{n_files} files  {n_hunks} hunks  hunk {pos}  {n_comments} comments"


STATUS_COLOURS = {
    "todo": "#808080",
    "done": "#00aa00",
    "partial": "#aa00aa",
    "refused": "#aa0000",
    "blocked": "#aaaa00",
}


class CommentBlock(Static):
    DEFAULT_CSS = """
    CommentBlock {
        padding: 0 1;
        color: $text-muted;
        height: auto;
        margin-bottom: 1;
    }
    CommentBlock.status-todo    { border-left: thick #808080; }
    CommentBlock.status-done    { border-left: thick #00aa00; }
    CommentBlock.status-partial { border-left: thick #aa00aa; }
    CommentBlock.status-refused { border-left: thick #aa0000; }
    CommentBlock.status-blocked { border-left: thick #aaaa00; }
    """

    def __init__(self, comment):
        super().__init__()
        self._comment = comment
        self._reply = comment.reply

    def on_mount(self):
        self.update_status(self._comment.status)

    def update_status(self, status):
        for s in STATUS_COLOURS:
            self.remove_class(f"status-{s}")
        self.add_class(f"status-{status}")

    def update_reply(self, reply):
        self._reply = reply
        self.refresh()

    def render(self):
        if self._reply:
            return f"{self._comment.body}\n\n{self._reply}"
        return self._comment.body



class HelpOverlay(Widget):
    can_focus = True
    DEFAULT_CSS = """
    HelpOverlay {
        layer: overlay;
        background: $surface;
        border: solid $accent;
        padding: 1 2;
        height: auto;
        width: auto;
        offset: 2 2;
    }
    """

    def on_mount(self):
        self.focus()

    def render(self):
        groups = {}
        for b in self.app.BINDINGS:
            if isinstance(b, Binding) and b.show and b.description:
                key = key_to_character(b.key) or b.key
                if b.action in groups:
                    groups[b.action][0].append(key)
                else:
                    groups[b.action] = ([key], b.description)
        lines = []
        for keys, description in groups.values():
            lines.append(f"  {', '.join(keys):<12} {description}")
        return "\n".join(lines)

    def _on_key(self, event):
        event.stop()
        self.remove()


class SummaryModal(ModalScreen):
    DEFAULT_CSS = """
    SummaryModal {
        align: center middle;
    }
    SummaryModal #summary-container {
        width: 80;
        height: auto;
        border: solid $accent;
        background: $surface;
    }
    SummaryModal #summary-title {
        background: $accent;
        color: $text;
        padding: 0 1;
        height: 1;
    }
    SummaryModal #summary-hint {
        color: $text-muted;
        padding: 0 1;
        height: 1;
        text-align: right;
    }
    SummaryModal TextArea {
        height: 16;
        border: none;
    }
    SummaryModal TextArea:focus {
        border: none;
    }
    """

    def __init__(self, summary):
        super().__init__()
        self._summary = summary

    def compose(self):
        with Vertical(id="summary-container"):
            yield Static("Edit session summary", id="summary-title")
            yield TextArea(self._summary)
            #todo use the hint
            yield Static("ctrl+enter  save    esc  cancel", id="summary-hint")

    def on_mount(self):
        self.query_one(TextArea).focus()

    def _on_key(self, event):
        if event.key == "ctrl+j":  # ctrl+enter in most terminals
            event.stop()
            self.dismiss(self.query_one(TextArea).text)
        elif event.key == "escape":
            event.stop()
            self.dismiss(None)


class StaleSessionModal(ModalScreen):
    DEFAULT_CSS = """
    StaleSessionModal {
        align: center middle;
    }
    StaleSessionModal > Static {
        background: $surface;
        border: solid $error;
        padding: 1 2;
        height: auto;
        width: auto;
    }
    """

    def compose(self):
        yield Static(
            "Session has comments that no longer map to valid file locations.\n"
            "Discard existing request and start new session?\n\n"
            "  y  Start new session\n"
            "  n  Quit"
        )

    def _on_key(self, event):
        event.stop()
        self.dismiss(event.key == "y")


class BurrowHeader(Static):
    DEFAULT_CSS = """
    BurrowHeader {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
        content-align: left middle;
    }
    """

    def render(self):
        return "🐇 burrow"


class BurrowApp(App):
    TITLE = "burrow"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("]", "next_hunk", "Next hunk"),
        Binding("[", "prev_hunk", "Prev hunk"),
        Binding("j", "next_line", "Next line"),
        Binding("k", "prev_line", "Prev line"),
        Binding("v", "select", "Select"),
        Binding("#", "comment", "Comment"),
        Binding("n", "next_comment", "Next comment"),
        Binding("shift+n", "prev_comment", "Prev comment"),
        Binding("question_mark", "help", "Help"),
        Binding("at", "summary", "Summary"),
    ]

    selected_hunk = reactive(0)
    selected_line = reactive(0)

    def __init__(self, request):
        super().__init__()
        self.request = request
        self.hunks = parse_diff(get_diff(request.repo_root))
        self.composing = None
        self.selecting = None
        self._comment_blocks = {}  # comment id -> CommentBlock
        self._comment_index = -1

    def compose(self):
        yield BurrowHeader()
        with ScrollableContainer(id="diff-view"):
            if not self.hunks:
                yield Static("No uncommitted changes.")
            else:
                for i, hunk in enumerate(self.hunks):
                    yield HunkWidget(hunk, i)
        yield StatusBar(self)

    def _locate_comment(self, comment):
        for hunk_idx, hunk in enumerate(self.hunks):
            if hunk.file != comment.file:
                continue
            target_line = hunk.target_start
            for line_idx, line in enumerate(hunk.lines):
                if target_line == comment.last_line:
                    first_line_idx = line_idx - (comment.last_line - comment.first_line)
                    return hunk_idx, max(first_line_idx, 0), line_idx
                if not line.startswith("-"):
                    target_line += 1
        return None

    def _comment_is_valid(self, comment):
        path = self.request.repo_root / comment.file
        if not path.is_file():
            return False
        line_count = len(path.read_text().splitlines())
        return comment.last_line <= line_count

    def _load_existing_comments(self, response=None):
        response_by_id = {c.id: c for c in response.comments} if response else {}
        for comment in self.request.comments:
            location = self._locate_comment(comment)
            if location is None:
                continue
            hunk_idx, first_line_idx, last_line_idx = location
            for i in range(first_line_idx, last_line_idx + 1):
                self.query_one(f"#hunk-{hunk_idx}-line-{i}").add_class("commented")
            anchor = self.query_one(f"#hunk-{hunk_idx}-line-{last_line_idx}")
            responded = response_by_id.get(comment.id, comment)
            block = CommentBlock(responded)
            self._comment_blocks[comment.id] = block
            self.mount(block, after=anchor)

    def load_response(self, response):
        for comment in response.comments:
            block = self._comment_blocks[comment.id]
            block.update_status(comment.status)
            if comment.reply:
                block.update_reply(comment.reply)

    def on_mount(self):
        self._update_highlight(0)
        self._update_line_highlight(0)
        stale = any(not self._comment_is_valid(c) for c in self.request.comments)
        if stale:
            self.push_screen(StaleSessionModal(), self._on_stale_result)
            return
        response = self._try_load_response()
        self._load_existing_comments(response)
        self.run_worker(self._watch_response(), exclusive=True)

    def _try_load_response(self):
        response_path = self.request.repo_root / ".burrow" / "response.json"
        if not response_path.exists():
            return None
        try:
            return Response.load(response_path, self.request)
        except (ValueError, KeyError):
            return None

    async def _watch_response(self):
        burrow_dir = self.request.repo_root / ".burrow"
        if not burrow_dir.is_dir():
            return
        async for _ in awatch(burrow_dir):
            response_path = burrow_dir / "response.json"
            if not response_path.exists():
                continue
            try:
                response = Response.load(response_path, self.request)
            except (ValueError, KeyError):
                continue
            self.load_response(response)

    def watch_selected_hunk(self, old, new):
        if self.hunks:
            for i in range(len(self.hunks[old].lines)):
                self.query_one(f"#hunk-{old}-line-{i}").remove_class("selected")
        self.selecting = None
        self.selected_line = 0
        self._update_highlight(new)
        if self.hunks:
            self.query_one(f"#hunk-{new}").scroll_visible()
        self.query_one(StatusBar).refresh()

    def watch_selected_line(self, new):
        self._update_line_highlight(new)
        self._update_selection_highlight()

    def _update_line_highlight(self, index):
        h = self.selected_hunk
        if not self.hunks:
            return
        for i in range(len(self.hunks[h].lines)):
            widget = self.query_one(f"#hunk-{h}-line-{i}")
            widget.set_class(i == index, "selected")
        self.query_one(f"#hunk-{h}-line-{index}").scroll_visible()

    def _update_selection_highlight(self):
        h = self.selected_hunk
        if not self.hunks:
            return
        if self.selecting is None:
            return
        lo = min(self.selecting, self.selected_line)
        hi = max(self.selecting, self.selected_line)
        for i in range(len(self.hunks[h].lines)):
            self.query_one(f"#hunk-{h}-line-{i}").set_class(lo <= i <= hi, "selected")

    def action_next_line(self):
        if self.hunks:
            max_line = len(self.hunks[self.selected_hunk].lines) - 1
            self.selected_line = min(self.selected_line + 1, max_line)

    def action_prev_line(self):
        if self.hunks:
            self.selected_line = max(self.selected_line - 1, 0)

    def _update_highlight(self, index):
        for i in range(len(self.hunks)):
            widget = self.query_one(f"#hunk-{i}")
            widget.set_class(i == index, "selected")

    def action_next_hunk(self):
        if self.hunks:
            self.selected_hunk = min(self.selected_hunk + 1, len(self.hunks) - 1)

    def action_prev_hunk(self):
        if self.hunks:
            self.selected_hunk = max(self.selected_hunk - 1, 0)

    def action_select(self):
        if not self.hunks:
            return
        if self.selecting is not None:
            self.selecting = None
            self._update_line_highlight(self.selected_line)
        else:
            self.selecting = self.selected_line
            self._update_selection_highlight()

    def _target_line_for(self, hunk, line_index):
        target_line = hunk.target_start
        for i, line in enumerate(hunk.lines):
            if i == line_index:
                break
            if not line.startswith("-"):
                target_line += 1
        return target_line

    def action_comment(self):
        if not self.hunks:
            return
        hunk = self.hunks[self.selected_hunk]
        if self.selecting is not None:
            anchor_index = self.selecting
            end_index = self.selected_line
            first = self._target_line_for(hunk, min(anchor_index, end_index))
            last = self._target_line_for(hunk, max(anchor_index, end_index))
            last_line_index = max(anchor_index, end_index)
            self.selecting = None
        else:
            first = self._target_line_for(hunk, self.selected_line)
            last = first
            last_line_index = self.selected_line
        self.composing = Anchor(file=hunk.file, first_line=first, last_line=last)
        anchor_widget = self.query_one(f"#hunk-{self.selected_hunk}-line-{last_line_index}")
        compose = ComposeWidget(
            hunk_index=self.selected_hunk,
            first_line_index=min(self.selected_line, last_line_index),
            last_line_index=last_line_index,
        )
        hint = ComposeHint("ctrl+enter  submit    esc  cancel")
        self.mount(compose, after=anchor_widget)
        self.mount(hint, after=compose)

    def action_cancel_compose(self):
        self.screen.query(ComposeHint).remove()
        widgets = self.screen.query(ComposeWidget)
        if widgets:
            widgets.first().remove()
            self.composing = None
            self.query_one("#diff-view").focus()

    def action_submit_compose(self):
        widgets = self.screen.query(ComposeWidget)
        if not widgets:
            return
        compose = widgets.first()
        body = compose.text.strip()
        if not body:
            compose.add_class("error")
            self.set_timer(0.4, lambda: compose.remove_class("error"))
            return
        if self.composing is not None:
            comment = self.request.add_comment(
                file=self.composing.file,
                first_line=self.composing.first_line,
                last_line=self.composing.last_line,
                body=body,
            )
            self.request.save()
            for i in range(compose._first_line_index, compose._last_line_index + 1):
                self.query_one(f"#hunk-{compose._hunk_index}-line-{i}").add_class("commented")
            block = CommentBlock(comment)
            self._comment_blocks[comment.id] = block
            self.mount(block, after=compose)
            self.query_one(StatusBar).refresh()
        self.screen.query(ComposeHint).remove()
        compose.remove()
        self.composing = None
        self.query_one("#diff-view").focus()

    def _on_stale_result(self, start_new):
        if start_new:
            burrow_dir = self.request.repo_root / ".burrow"
            (burrow_dir / "request.json").unlink(missing_ok=True)
            response = burrow_dir / "response.json"
            if response.exists():
                response.unlink()
            self.request = Request(summary=self.request.summary, repo_root=self.request.repo_root)
            self.request.save()
            self._load_existing_comments()
            self.query_one(StatusBar).refresh()
        else:
            self.exit()

    def _sorted_comment_ids(self):
        def sort_key(comment_id):
            comment = next(c for c in self.request.comments if c.id == comment_id)
            location = self._locate_comment(comment)
            return location[:2] if location else (999999, 999999)
        return sorted(self._comment_blocks.keys(), key=sort_key)

    def _navigate_to_comment(self, index):
        comment_ids = self._sorted_comment_ids()
        comment_id = comment_ids[index]
        comment = next(c for c in self.request.comments if c.id == comment_id)
        location = self._locate_comment(comment)
        if location is None:
            return
        hunk_idx, first_line_idx, last_line_idx = location
        # Update hunk highlight without triggering the watcher's scroll side-effect
        self._update_highlight(hunk_idx)
        self.set_reactive(BurrowApp.selected_hunk, hunk_idx)
        self.query_one(StatusBar).refresh()
        # Set selection range covering the full anchor
        self.set_reactive(BurrowApp.selected_line, last_line_idx)
        self.selecting = first_line_idx
        self._update_selection_highlight()
        # Scroll so first anchor line is at top, revealing anchor + block below
        first_line = self.query_one(f"#hunk-{hunk_idx}-line-{first_line_idx}")
        self.call_after_refresh(
            self.query_one("#diff-view").scroll_to_widget, first_line, top=True
        )

    def action_next_comment(self):
        if not self._comment_blocks:
            return
        self._comment_index = min(self._comment_index + 1, len(self._comment_blocks) - 1)
        self._navigate_to_comment(self._comment_index)

    def action_prev_comment(self):
        if not self._comment_blocks:
            return
        self._comment_index = max(self._comment_index - 1, -1)
        if self._comment_index >= 0:
            self._navigate_to_comment(self._comment_index)


    def action_summary(self):
        self.push_screen(SummaryModal(self.request.summary), self._on_summary_result)

    def _on_summary_result(self, summary):
        if summary is not None:
            self.request.summary = summary.strip()
            self.request.save()

    def action_help(self):
        overlays = self.screen.query(HelpOverlay)
        if overlays:
            overlays.first().remove()
        else:
            self.mount(HelpOverlay())

