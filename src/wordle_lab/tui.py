"""Textual entry point for the Human Wordle Bot dashboard."""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Input, Static

from .__main__ import build_human_recommendation


DEFAULT_TUI_STATE = ("slate", "....Y", "drown", "GY...")
MAX_GUESSES = 6
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
        f"{recommendation['recommendation_type']} · {risk}"
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
    """Human Mode dashboard with an in-memory six-guess session."""

    TITLE = "Human Wordle Bot"
    SUB_TITLE = "Human Balanced · Streak Protector"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, recommendation=None, recommendation_builder=None) -> None:
        super().__init__()
        self.initial_state = DEFAULT_TUI_STATE
        self.state_steps = self.initial_state
        self.game_over = False
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
        self.initial_recommendation = self.recommendation

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
        padding: 0 2;
    }

    #top-row {
        height: 10;
    }

    #bottom-row {
        height: 8;
    }

    #entry-row {
        height: 3;
        margin-right: 1;
    }

    #guess-input {
        width: 14;
        margin-right: 1;
    }

    #feedback-input {
        width: 18;
        margin-right: 1;
    }

    #add-result {
        width: 10;
        min-width: 10;
        margin-right: 1;
    }

    #reset-game {
        width: 10;
        min-width: 10;
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
                    placeholder="g/y/b result",
                    id="feedback-input",
                    max_length=5,
                )
                yield Button("Add", id="add-result", variant="primary")
                yield Button("Reset", id="reset-game")
                yield Static(self._next_guess_status(), id="entry-status")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle result submission and session reset actions."""
        if event.button.id == "add-result":
            self._submit_entry()
        elif event.button.id == "reset-game":
            self._reset_session()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Allow Enter in either field to submit the result."""
        self._submit_entry()

    def _submit_entry(self) -> None:
        if self.game_over:
            return
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

        if pattern == "GGGGG":
            self._complete_session(solved_guess=guess)
            return

        try:
            recommendation = self.recommendation_builder(self.state_steps)
        except (FileNotFoundError, ValueError) as error:
            self._complete_session(detail=f"No recommendation: {error}")
        else:
            self.recommendation = recommendation
            self._refresh_recommendation(recommendation)
            if self._guess_count() >= MAX_GUESSES:
                self._complete_session()
                return
            guess_input.value = ""
            feedback_input.value = ""
            status.update(
                f"[green]Guess {self._guess_count()} added[/] · "
                f"next is {self._guess_count() + 1} of {MAX_GUESSES}"
            )
            guess_input.focus()

    def _guess_count(self) -> int:
        return len(self.state_steps) // 2

    def _next_guess_status(self) -> str:
        return f"Guess {self._guess_count() + 1} of {MAX_GUESSES}"

    def _set_entry_enabled(self, enabled: bool) -> None:
        self.query_one("#guess-input", Input).disabled = not enabled
        self.query_one("#feedback-input", Input).disabled = not enabled
        self.query_one("#add-result", Button).disabled = not enabled

    def _complete_session(self, solved_guess=None, detail=None) -> None:
        """Stop entry and show a friendly solved or game-over state."""
        self.game_over = True
        self._set_entry_enabled(False)
        header = self.query_one("#app-header", Static)
        recommendation = self.query_one("#recommendation-content", Static)
        candidates = self.query_one("#candidates-content", Static)
        human_read = self.query_one("#human-read-content", Static)
        trap_watch = self.query_one("#trap-watch-content", Static)
        status = self.query_one("#entry-status", Static)

        if solved_guess:
            header.update(
                "Human Wordle Bot\nMode: Human Balanced · "
                "Personality: Streak Protector · Solved"
            )
            recommendation.update(f"SOLVED\n[bold]{solved_guess.upper()}[/]\nNice work")
            candidates.update(f"Solved answer\n{solved_guess}")
            human_read.update("That’s the one. Nicely played—the streak is safe.")
            trap_watch.update("Game complete\nNo traps left to navigate.")
            status.update(
                f"[green]Solved in {self._guess_count()} of {MAX_GUESSES}[/] · Reset"
            )
            return

        header.update(
            "Human Wordle Bot\nMode: Human Balanced · "
            "Personality: Streak Protector · Game over"
        )
        recommendation.update(
            "SESSION STOPPED\nNo matching answers\nReset to revise"
            if detail
            else "GAME OVER\nSix rows used\nReset to try again"
        )
        human_read.update(
            detail or "That’s six. Tough branch—reset when you’re ready for another run."
        )
        trap_watch.update("Session complete\nNo more guesses accepted.")
        status.update(
            "[yellow]Session stopped[/] · Reset"
            if detail
            else "[yellow]Game over[/] · Reset"
        )

    def _reset_session(self) -> None:
        """Restore the initial in-memory scenario without persistence."""
        self.state_steps = self.initial_state
        self.recommendation = self.initial_recommendation
        self.game_over = False
        self.query_one("#board-content", Static).update(format_board(self.state_steps))
        self._refresh_recommendation(self.recommendation)
        guess_input = self.query_one("#guess-input", Input)
        feedback_input = self.query_one("#feedback-input", Input)
        guess_input.value = ""
        feedback_input.value = ""
        self._set_entry_enabled(True)
        self.query_one("#entry-status", Static).update(self._next_guess_status())
        guess_input.focus()

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
