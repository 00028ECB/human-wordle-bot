import unittest

from textual.widgets import Static

from src.wordle_lab.tui import HumanWordleBotApp


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_dashboard_renders_all_major_sections(self):
        app = HumanWordleBotApp()

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

    async def test_dashboard_uses_static_sample_content(self):
        app = HumanWordleBotApp()

        async with app.run_test(size=(100, 30)):
            screen_text = "\n".join(
                str(widget._content) for widget in app.screen.query(Static)
            )

        self.assertIn("BOUND", screen_text)
        self.assertIn("bound\nfound\nhound\nmound", screen_text)
        self.assertIn("No major trap family detected", screen_text)

    async def test_q_quits_dashboard(self):
        app = HumanWordleBotApp()

        async with app.run_test() as pilot:
            await pilot.press("q")

        self.assertIsNone(app.return_value)
