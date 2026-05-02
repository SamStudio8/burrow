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
    header: str
    lines: list[str]


def parse_diff(raw):
    hunks = []
    for patched_file in PatchSet(raw):
        for hunk in patched_file:
            header = (
                f"@@ -{hunk.source_start},{hunk.source_length}"
                f" +{hunk.target_start},{hunk.target_length} @@"
                f" {hunk.section_header}".rstrip()
            )
            hunks.append(Hunk(
                file=patched_file.path,
                header=header,
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


class HunkWidget(Static):
    DEFAULT_CSS = """
    HunkWidget {
        padding: 0 1;
        border-left: thick transparent;
    }
    HunkWidget.selected {
        border-left: thick $accent;
    }
    """

    def __init__(self, hunk, index, show_filename):
        parts = []
        if show_filename:
            parts.append(f"--- {hunk.file}")
        parts.append(hunk.header)
        parts.extend(line.rstrip("\n") for line in hunk.lines)
        super().__init__("\n".join(parts), id=f"hunk-{index}")


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
                current_file = None
                for i, hunk in enumerate(self.hunks):
                    show_filename = hunk.file != current_file
                    current_file = hunk.file
                    yield HunkWidget(hunk, i, show_filename)
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
