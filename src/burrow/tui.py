import subprocess
from dataclasses import dataclass

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Static
from textual.containers import ScrollableContainer
from unidiff import PatchSet


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
    DiffLine.selected {
        background: $accent 30%;
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
        border-left: thick $accent;
    }
    HunkWidget.selected HunkHeader {
        background: $accent;
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
    ]

    selected_hunk = reactive(0)
    selected_line = reactive(0)

    def __init__(self, request):
        super().__init__()
        self.request = request
        self.hunks = parse_diff(get_diff(request.repo_root))
        self.composing = None
        self.selecting = None

    def compose(self):
        yield BurrowHeader()
        with ScrollableContainer(id="diff-view"):
            if not self.hunks:
                yield Static("No uncommitted changes.")
            else:
                for i, hunk in enumerate(self.hunks):
                    yield HunkWidget(hunk, i)
        yield Footer()

    def on_mount(self):
        self._update_highlight(0)
        self._update_line_highlight(0)

    def watch_selected_hunk(self, old, new):
        if self.hunks:
            for i in range(len(self.hunks[old].lines)):
                self.query_one(f"#hunk-{old}-line-{i}").remove_class("selected")
        self.selected_line = 0
        self._update_highlight(new)
        if self.hunks:
            self.query_one(f"#hunk-{new}").scroll_visible()

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
            self.selecting = None
        else:
            first = self._target_line_for(hunk, self.selected_line)
            last = first
        self.composing = Anchor(file=hunk.file, first_line=first, last_line=last)
