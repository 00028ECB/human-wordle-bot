import unittest

from textual.widgets import Static

from src.wordle_lab.tui import (
    DEFAULT_TUI_STATE,
    HumanWordleBotApp,
    build_human_read,
    build_trap_read,
    classify_risk,
    format_board,
    format_candidates,
)


def recommendation_fixture():
    return {
        "candidates": ("berry", "buyer", "cheer", "cyber", "ember", "every"),
        "recommended_guess": "furry",
        "recommendation_type": "probe",
        "explanation": "Chose furry using bucket safety.",
        "trap_watch": "No major trap family detected",
        "mode_label": "Human Balanced",
        "personality_label": "Streak Protector",
        "remaining_count": 6,
        "max_bucket": 2,
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
            "NEXT GUESS",
            "LIKELY ANSWERS",
            "HUMAN READ",
            "TRAP WATCH",
            "Mode: Human Balanced",
            "Personality: Streak Protector",
            "Risk: Low",
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
        self.assertIn("6 still live\nberry\nbuyer\ncheer\ncyber\n+ 2 more", screen_text)
        self.assertIn("Chose furry using bucket safety.", screen_text)
        self.assertIn("A calm, streak-safe line", screen_text)
        self.assertIn("All clear", screen_text)
        self.assertIn("No major trap family detected", screen_text)

    def test_risk_labels_use_bucket_exposure(self):
        recommendation = recommendation_fixture()

        self.assertEqual(classify_risk(recommendation), "Low")
        self.assertEqual(
            classify_risk({**recommendation, "remaining_count": 10, "max_bucket": 5}),
            "Medium",
        )
        self.assertEqual(
            classify_risk({**recommendation, "remaining_count": 10, "max_bucket": 7}),
            "High",
        )

    def test_personality_helpers_warn_on_trap_family(self):
        recommendation = {
            **recommendation_fixture(),
            "remaining_count": 4,
            "max_bucket": 3,
            "trap_watch": "Potential trap family detected",
        }

        self.assertIn("coverage beats a hopeful coin flip", build_human_read(recommendation))
        self.assertEqual(
            build_trap_read(recommendation),
            "Heads up\nPotential trap family detected\nFavor letter coverage.",
        )

    def test_candidate_summary_limits_visible_answers(self):
        self.assertEqual(
            format_candidates(recommendation_fixture(), limit=2),
            "6 still live\nberry\nbuyer\n+ 4 more",
        )

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
