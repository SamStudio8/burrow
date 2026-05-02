import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static


def get_diff(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.stdout


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

    def render(self) -> str:
        return "🐇 burrow"


class BurrowApp(App):
    TITLE = "burrow"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield BurrowHeader()
        yield Footer()
