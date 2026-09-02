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


def classify_risk(recommendation) -> str:
    """Translate bucket exposure into a friendly display-level risk label."""
    remaining = max(int(recommendation["remaining_count"]), 1)
    max_bucket = int(recommendation["max_bucket"])
    exposure = max_bucket / remaining
    if max_bucket <= 2 and exposure <= 0.34:
        return "Low"
    if exposure <= 0.60:
        return "Medium"
    return "High"


def format_candidates(recommendation, limit: int = 4) -> str:
    """Summarize the most likely answers without crowding the panel."""
    candidates = recommendation["candidates"]
    lines = [f"{len(candidates)} still live", *candidates[:limit]]
    if len(candidates) > limit:
        lines.append(f"+ {len(candidates) - limit} more")
    return "\n".join(lines)


def build_human_read(recommendation) -> str:
    """Add Streak Protector voice to the solver's existing explanation."""
    explanation = recommendation["explanation"].rstrip()
    if explanation and explanation[-1] not in ".!?":
        explanation += "."
    risk = classify_risk(recommendation)
    if recommendation["trap_watch"] != "No major trap family detected":
        personality_read = "This branch deserves care—coverage beats a hopeful coin flip."
    elif risk == "Low":
        personality_read = "A calm, streak-safe line with very little left to chance."
    elif risk == "Medium":
        personality_read = "A balanced line, but keep some respect for the branch risk."
    else:
        personality_read = "Protect the streak here; information matters more than speed."
    return f"{explanation} {personality_read}"


def build_trap_read(recommendation) -> str:
    """Turn trap detection into concise assistant-facing guidance."""
    trap_watch = recommendation["trap_watch"]
    if trap_watch == "No major trap family detected":
        return f"All clear\n{trap_watch}\nRisk stays {classify_risk(recommendation).lower()}."
    return f"Heads up\n{trap_watch}\nFavor letter coverage."


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
        risk = classify_risk(recommendation)

        yield Static(
            "Human Wordle Bot\n"
            f"Mode: {recommendation['mode_label']} · "
            f"Personality: {recommendation['personality_label']} · "
            f"Risk: {risk}",
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
                    "NEXT GUESS",
                    "Recommended\n\n"
                    f"[bold]{recommendation['recommended_guess'].upper()}[/]\n"
                    f"{recommendation['recommendation_type']} · {risk.lower()} risk",
                    panel_id="recommendation-panel",
                )
                yield DashboardPanel(
                    "LIKELY ANSWERS",
                    format_candidates(recommendation),
                    panel_id="candidates-panel",
                )
            with Horizontal(id="bottom-row"):
                yield DashboardPanel(
                    "HUMAN READ",
                    build_human_read(recommendation),
                    panel_id="reasoning-panel",
                )
                yield DashboardPanel(
                    "TRAP WATCH",
                    build_trap_read(recommendation),
                    panel_id="trap-panel",
                )
        yield Footer()


def main() -> None:
    """Launch the terminal dashboard."""
    HumanWordleBotApp().run()


if __name__ == "__main__":
    main()
