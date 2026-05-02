from textual.app import App, ComposeResult
from textual.binding import Binding


class BurrowApp(App):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
