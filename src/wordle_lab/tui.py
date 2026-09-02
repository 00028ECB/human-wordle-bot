"""Textual entry point for the Human Wordle Bot dashboard."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static

from .__main__ import build_human_recommendation


DEFAULT_TUI_STATE = ("slate", "....Y", "drown", "GY...")
CELL_STYLES = {
    "G": "bold white on #538d4e",
    "Y": "bold white on #b59f3b",
    ".": "bold white on #3a3a3c",
}


def format_board(state_steps: tuple[str, ...]) -> str:
    """Format guess/pattern pairs as colored Wordle cells."""
    rows = []
    for guess, pattern in zip(state_steps[::2], state_steps[1::2]):
        rows.append(
            "".join(
                f"[{CELL_STYLES[mark]}] {letter.upper()} [/]"
                for letter, mark in zip(guess, pattern)
            )
        )
    return "\n".join(rows)


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
    """Read-only dashboard for a Human Mode recommendation."""

    TITLE = "Human Wordle Bot"
    SUB_TITLE = "Human Balanced · Streak Protector"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, recommendation=None) -> None:
        super().__init__()
        self.recommendation = (
            build_human_recommendation(DEFAULT_TUI_STATE)
            if recommendation is None
            else recommendation
        )

    CSS = """
    Screen {
        background: #111318;
        color: #f4f4f4;
    }

    #app-header {
        dock: top;
        height: 4;
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
        height: 10;
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
        """Build the read-only recommendation dashboard."""
        recommendation = self.recommendation
        candidates = recommendation["candidates"]
        candidate_text = "\n".join(candidates[:5])
        if len(candidates) > 5:
            candidate_text += f"\n+ {len(candidates) - 5} more"

        yield Static(
            "Human Wordle Bot\n"
            f"{recommendation['mode_label']} · "
            f"{recommendation['personality_label']}",
            id="app-header",
        )
        with Vertical(id="dashboard"):
            with Horizontal(id="top-row"):
                yield DashboardPanel(
                    "BOARD",
                    format_board(DEFAULT_TUI_STATE),
                    panel_id="board-panel",
                )
                yield DashboardPanel(
                    "RECOMMENDATION",
                    "Next guess\n\n"
                    f"[bold]{recommendation['recommended_guess'].upper()}[/]\n"
                    f"{recommendation['recommendation_type']}",
                    panel_id="recommendation-panel",
                )
                yield DashboardPanel(
                    "CANDIDATES",
                    candidate_text,
                    panel_id="candidates-panel",
                )
            with Horizontal(id="bottom-row"):
                yield DashboardPanel(
                    "HUMAN REASONING",
                    recommendation["explanation"],
                    panel_id="reasoning-panel",
                )
                yield DashboardPanel(
                    "TRAP WATCH",
                    recommendation["trap_watch"],
                    panel_id="trap-panel",
                )
        yield Footer()


def main() -> None:
    """Launch the terminal dashboard."""
    HumanWordleBotApp().run()


if __name__ == "__main__":
    main()
