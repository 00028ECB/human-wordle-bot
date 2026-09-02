import unittest

from textual.widgets import Static

from src.wordle_lab.tui import DEFAULT_TUI_STATE, HumanWordleBotApp, format_board


def recommendation_fixture():
    return {
        "candidates": ("berry", "buyer", "cheer", "cyber", "ember", "every"),
        "recommended_guess": "furry",
        "recommendation_type": "probe",
        "explanation": "Chose furry using bucket safety.",
        "trap_watch": "No major trap family detected",
        "mode_label": "Human Balanced",
        "personality_label": "Streak Protector",
    }


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_renders_all_major_sections(self):
        app = HumanWordleBotApp(recommendation_fixture())

        async with app.run_test(size=(100, 30)):
            screen_text = "\n".join(
                str(widget._content) for widget in app.screen.query(Static)
            )

        for expected_text in (
            "Human Wordle Bot",
            "BOARD",
            "RECOMMENDATION",
            "CANDIDATES",
            "HUMAN REASONING",
            "TRAP WATCH",
        ):
            with self.subTest(expected_text=expected_text):
                self.assertIn(expected_text, screen_text)

    async def test_dashboard_renders_recommendation_data(self):
        app = HumanWordleBotApp(recommendation_fixture())

        async with app.run_test(size=(100, 30)):
            screen_text = "\n".join(
                str(widget._content) for widget in app.screen.query(Static)
            )

        self.assertIn("FURRY", screen_text)
        self.assertIn("berry\nbuyer\ncheer\ncyber\nember\n+ 1 more", screen_text)
        self.assertIn("Chose furry using bucket safety.", screen_text)
        self.assertIn("No major trap family detected", screen_text)

    def test_board_uses_configured_recommendation_state(self):
        board = format_board(DEFAULT_TUI_STATE)

        self.assertIn(" S ", board)
        self.assertIn(" D ", board)
        self.assertIn("#538d4e", board)
        self.assertIn("#b59f3b", board)
        self.assertIn("#3a3a3c", board)

    async def test_q_quits_dashboard(self):
        app = HumanWordleBotApp(recommendation_fixture())

        async with app.run_test() as pilot:
            await pilot.press("q")

        self.assertIsNone(app.return_value)
