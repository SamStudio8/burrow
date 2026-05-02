import subprocess
from dataclasses import dataclass
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static
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
    ]

    def compose(self):
        yield BurrowHeader()
        yield Footer()
