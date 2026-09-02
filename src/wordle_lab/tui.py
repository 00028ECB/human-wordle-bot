"""Textual entry point for the Human Wordle Bot dashboard."""

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Static


class HumanWordleBotApp(App[None]):
    """Initial dashboard shell for the Human Wordle Bot."""

    TITLE = "Human Wordle Bot"

    CSS = """
    Screen {
        align: center middle;
    }

    #dashboard {
        width: 44;
        height: auto;
        padding: 1 2;
        border: round $accent;
    }

    #dashboard-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Build the initial, solver-free dashboard."""
        with Vertical(id="dashboard"):
            yield Static("Human Wordle Bot", id="dashboard-title")
            yield Static("Mode: Human Balanced")
            yield Static("Personality: Streak Protector")
            yield Static("Status: TUI shell loaded")


def main() -> None:
    """Launch the terminal dashboard."""
    HumanWordleBotApp().run()


if __name__ == "__main__":
    main()
