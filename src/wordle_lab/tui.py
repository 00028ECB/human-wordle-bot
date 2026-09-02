"""Textual entry point for the Human Wordle Bot dashboard."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static


SAMPLE_BOARD = """\
[bold white on #538d4e] S [/][bold white on #538d4e] L [/][bold white on #b59f3b] A [/][bold white on #3a3a3c] T [/][bold white on #3a3a3c] E [/]
[bold white on #3a3a3c] R [/][bold white on #b59f3b] O [/][bold white on #3a3a3c] U [/][bold white on #538d4e] N [/][bold white on #538d4e] D [/]"""


class DashboardPanel(Vertical):
    """A consistently styled dashboard section."""

    def __init__(self, title: str, content: str, *, panel_id: str) -> None:
        super().__init__(
            Static(title, classes="section-title"),
            Static(content, classes="section-content"),
            id=panel_id,
            classes="panel",
        )


class HumanWordleBotApp(App[None]):
    """Static dashboard preview for the Human Wordle Bot."""

    TITLE = "Human Wordle Bot"
    SUB_TITLE = "Human Balanced · Streak Protector"
    BINDINGS = [("q", "quit", "Quit")]

    CSS = """
    Screen {
        background: #111318;
        color: #f4f4f4;
    }

    #app-header {
        dock: top;
        height: 3;
        padding: 1 2;
        background: #243447;
        color: #ffffff;
        text-style: bold;
        text-align: center;
    }

    #dashboard {
        height: 1fr;
        padding: 1 2 0 2;
    }

    #top-row {
        height: 11;
    }

    #bottom-row {
        height: 1fr;
        min-height: 7;
    }

    .panel {
        height: 100%;
        margin: 0 1 1 0;
        padding: 0 1;
        border: round #486581;
        background: #1b2028;
    }

    .section-title {
        height: 2;
        color: #8ecae6;
        text-style: bold;
    }

    .section-content {
        height: 1fr;
    }

    #board-panel {
        width: 2fr;
    }

    #recommendation-panel, #candidates-panel, #trap-panel {
        width: 1fr;
    }

    #reasoning-panel {
        width: 2fr;
    }

    #board-panel .section-content {
        text-align: center;
        padding-top: 1;
    }

    #recommendation-panel .section-content {
        color: #a7d8a2;
        text-style: bold;
        text-align: center;
        padding-top: 1;
    }

    #trap-panel .section-content {
        color: #a7d8a2;
    }

    Footer {
        background: #243447;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the solver-free sample dashboard."""
        yield Static("Human Wordle Bot", id="app-header")
        with Vertical(id="dashboard"):
            with Horizontal(id="top-row"):
                yield DashboardPanel("BOARD", SAMPLE_BOARD, panel_id="board-panel")
                yield DashboardPanel(
                    "RECOMMENDATION",
                    "Next guess\n\n[bold]BOUND[/]",
                    panel_id="recommendation-panel",
                )
                yield DashboardPanel(
                    "CANDIDATES",
                    "bound\nfound\nhound\nmound",
                    panel_id="candidates-panel",
                )
            with Horizontal(id="bottom-row"):
                yield DashboardPanel(
                    "HUMAN REASONING",
                    "BOUND tests the uncertain B while preserving the known O, N, "
                    "and D. It balances information gain with a plausible solve.",
                    panel_id="reasoning-panel",
                )
                yield DashboardPanel(
                    "TRAP WATCH",
                    "No major trap family detected",
                    panel_id="trap-panel",
                )
        yield Footer()


def main() -> None:
    """Launch the terminal dashboard."""
    HumanWordleBotApp().run()


if __name__ == "__main__":
    main()
