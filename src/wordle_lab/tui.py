"""Textual entry point for the Human Wordle Bot dashboard."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Input, Static

from .__main__ import build_human_recommendation


DEFAULT_TUI_STATE = ("slate", "....Y", "drown", "GY...")
CELL_STYLES = {
    "G": "bold white on #538d4e",
    "Y": "bold white on #b59f3b",
    ".": "bold white on #3a3a3c",
}


def validate_entry(guess_text: str, feedback_text: str) -> tuple[str, str]:
    """Validate user input and return solver-ready guess and feedback values."""
    guess = guess_text.strip().lower()
    feedback = feedback_text.strip().lower()
    if len(guess) != 5 or not guess.isascii() or not guess.isalpha():
        raise ValueError("Guess must be exactly 5 letters.")
    if len(feedback) != 5:
        raise ValueError("Feedback must be exactly 5 characters.")
    if any(mark not in "gyb" for mark in feedback):
        raise ValueError("Feedback may only use g, y, or b.")
    return guess, feedback.translate(str.maketrans({"g": "G", "y": "Y", "b": "."}))


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
    if remaining == 1:
        return "Low"
    exposure = max_bucket / remaining
    if max_bucket <= 2 and exposure <= 0.34:
        return "Low"
    if exposure <= 0.60:
        return "Medium"
    return "High"


def format_candidates(recommendation, limit: int = 2) -> str:
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


def format_header(recommendation) -> str:
    """Format the dashboard identity and current risk summary."""
    return (
        "Human Wordle Bot\n"
        f"Mode: {recommendation['mode_label']} · "
        f"Personality: {recommendation['personality_label']} · "
        f"Risk: {classify_risk(recommendation)}"
    )


def format_next_guess(recommendation) -> str:
    """Format the recommendation panel content."""
    risk = classify_risk(recommendation)
    return (
        "Recommended\n"
        f"[bold]{recommendation['recommended_guess'].upper()}[/]\n"
        f"{recommendation['recommendation_type']} · {risk.lower()} risk"
    )


class DashboardPanel(Vertical):
    """A consistently styled dashboard section."""

    def __init__(
        self,
        title: str,
        content: str,
        *,
        panel_id: str,
        content_id: str,
    ) -> None:
        super().__init__(
            Static(title, classes="section-title"),
            Static(content, id=content_id, classes="section-content"),
            id=panel_id,
            classes="panel",
        )


class HumanWordleBotApp(App[None]):
    """Human Mode dashboard with one-result entry support."""

    TITLE = "Human Wordle Bot"
    SUB_TITLE = "Human Balanced · Streak Protector"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, recommendation=None, recommendation_builder=None) -> None:
        super().__init__()
        self.state_steps = DEFAULT_TUI_STATE
        self.recommendation_builder = (
            build_human_recommendation
            if recommendation_builder is None
            else recommendation_builder
        )
        self.recommendation = (
            self.recommendation_builder(self.state_steps)
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
        height: 3;
        padding: 0 2;
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
        height: 8;
    }

    #bottom-row {
        height: 8;
    }

    #entry-row {
        height: 3;
        margin-right: 1;
    }

    #guess-input {
        width: 18;
        margin-right: 1;
    }

    #feedback-input {
        width: 22;
        margin-right: 1;
    }

    #add-result {
        width: 14;
        margin-right: 1;
    }

    #entry-status {
        width: 1fr;
        height: 3;
        padding: 1;
    }

    .panel {
        height: 100%;
        margin: 0 1 1 0;
        padding: 0 1;
        border: round #486581;
        background: #1b2028;
    }

    .section-title {
        height: 1;
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
        """Build the recommendation dashboard and one-result entry bar."""
        recommendation = self.recommendation

        yield Static(format_header(recommendation), id="app-header")
        with Vertical(id="dashboard"):
            with Horizontal(id="top-row"):
                yield DashboardPanel(
                    "BOARD",
                    format_board(self.state_steps),
                    panel_id="board-panel",
                    content_id="board-content",
                )
                yield DashboardPanel(
                    "NEXT GUESS",
                    format_next_guess(recommendation),
                    panel_id="recommendation-panel",
                    content_id="recommendation-content",
                )
                yield DashboardPanel(
                    "LIKELY ANSWERS",
                    format_candidates(recommendation),
                    panel_id="candidates-panel",
                    content_id="candidates-content",
                )
            with Horizontal(id="bottom-row"):
                yield DashboardPanel(
                    "HUMAN READ",
                    build_human_read(recommendation),
                    panel_id="reasoning-panel",
                    content_id="human-read-content",
                )
                yield DashboardPanel(
                    "TRAP WATCH",
                    build_trap_read(recommendation),
                    panel_id="trap-panel",
                    content_id="trap-watch-content",
                )
            with Horizontal(id="entry-row"):
                yield Input(placeholder="Guess", id="guess-input", max_length=5)
                yield Input(
                    placeholder="Feedback: g/y/b",
                    id="feedback-input",
                    max_length=5,
                )
                yield Button("Add result", id="add-result", variant="primary")
                yield Static("Ready", id="entry-status")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Add the entered result when the submit button is pressed."""
        if event.button.id == "add-result":
            self._submit_entry()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Allow Enter in either field to submit the result."""
        self._submit_entry()

    def _submit_entry(self) -> None:
        guess_input = self.query_one("#guess-input", Input)
        feedback_input = self.query_one("#feedback-input", Input)
        status = self.query_one("#entry-status", Static)
        try:
            guess, pattern = validate_entry(guess_input.value, feedback_input.value)
        except ValueError as error:
            status.update(f"[red]{error}[/]")
            return

        self.state_steps = (*self.state_steps, guess, pattern)
        self.query_one("#board-content", Static).update(format_board(self.state_steps))
        try:
            recommendation = self.recommendation_builder(self.state_steps)
        except (FileNotFoundError, ValueError) as error:
            self.query_one("#recommendation-content", Static).update(
                "Recommendation unavailable"
            )
            status.update(f"[yellow]Board updated: {error}[/]")
        else:
            self.recommendation = recommendation
            self._refresh_recommendation(recommendation)
            status.update("[green]Result added[/]")

        guess_input.disabled = True
        feedback_input.disabled = True
        self.query_one("#add-result", Button).disabled = True

    def _refresh_recommendation(self, recommendation) -> None:
        """Refresh recommendation-backed display panels after valid entry."""
        self.query_one("#app-header", Static).update(format_header(recommendation))
        self.query_one("#recommendation-content", Static).update(
            format_next_guess(recommendation)
        )
        self.query_one("#candidates-content", Static).update(
            format_candidates(recommendation)
        )
        self.query_one("#human-read-content", Static).update(
            build_human_read(recommendation)
        )
        self.query_one("#trap-watch-content", Static).update(
            build_trap_read(recommendation)
        )


def main() -> None:
    """Launch the terminal dashboard."""
    HumanWordleBotApp().run()


if __name__ == "__main__":
    main()
