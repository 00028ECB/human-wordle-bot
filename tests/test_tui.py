import unittest

from textual.widgets import Static

from src.wordle_lab.tui import HumanWordleBotApp


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_screen_shows_dashboard_shell(self):
        app = HumanWordleBotApp()

        async with app.run_test():
            screen_text = "\n".join(
                str(widget._content) for widget in app.screen.query(Static)
            )

        self.assertIn("Human Wordle Bot", screen_text)
        self.assertIn("Mode: Human Balanced", screen_text)
        self.assertIn("Personality: Streak Protector", screen_text)
        self.assertIn("Status: TUI shell loaded", screen_text)
