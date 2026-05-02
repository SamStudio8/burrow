import subprocess
from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Footer, Static
from textual.containers import ScrollableContainer
from unidiff import PatchSet


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
        yield Static("\n".join(line.rstrip("\n") for line in hunk.lines))


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
    ]

    selected_hunk = reactive(0)

    def __init__(self, request):
        super().__init__()
        self.request = request
        self.hunks = parse_diff(get_diff(request.repo_root))

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

    def watch_selected_hunk(self, new):
        self._update_highlight(new)
        if self.hunks:
            self.query_one(f"#hunk-{new}").scroll_visible()

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
