import unittest

from textual.widgets import Button, Input, Static

from src.wordle_lab.tui import (
    INITIAL_TUI_STATE,
    HumanWordleBotApp,
    build_human_read,
    build_trap_read,
    classify_risk,
    format_board,
    format_candidates,
    validate_entry,
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
    def test_entry_validation_normalizes_solver_feedback(self):
        self.assertEqual(validate_entry(" Crane ", "gbybb"), ("crane", "G.Y.."))

    def test_entry_validation_rejects_invalid_guess(self):
        for guess in ("four", "longer", "ab1de", "élate"):
            with self.subTest(guess=guess), self.assertRaisesRegex(
                ValueError,
                "Guess must be exactly 5 letters",
            ):
                validate_entry(guess, "gbybb")

    def test_entry_validation_rejects_invalid_feedback(self):
        with self.assertRaisesRegex(ValueError, "exactly 5 characters"):
            validate_entry("crane", "gybb")
        with self.assertRaisesRegex(ValueError, "only use g, y, or b"):
            validate_entry("crane", "gygbx")

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
        self.assertIn("6 still live\nberry\nbuyer\n+ 4 more", screen_text)
        self.assertIn("Chose furry using bucket safety.", screen_text)
        self.assertIn("A calm, streak-safe line", screen_text)
        self.assertIn("All clear", screen_text)
        self.assertIn("No major trap family detected", screen_text)

    def test_risk_labels_use_bucket_exposure(self):
        recommendation = recommendation_fixture()

        self.assertEqual(classify_risk(recommendation), "Low")
        self.assertEqual(
            classify_risk({**recommendation, "remaining_count": 1, "max_bucket": 1}),
            "Low",
        )
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

    def test_board_formatter_colors_sample_state(self):
        sample_state = ("slate", "....Y", "drown", "GY...")
        board = format_board(sample_state)

        self.assertIn(" S ", board)
        self.assertIn(" D ", board)
        self.assertIn("#538d4e", board)
        self.assertIn("#b59f3b", board)
        self.assertIn("#3a3a3c", board)

    async def test_dashboard_starts_with_blank_board(self):
        app = HumanWordleBotApp(recommendation_fixture())

        async with app.run_test(size=(100, 30)):
            board_text = str(app.query_one("#board-content", Static)._content)
            status_text = str(app.query_one("#entry-status", Static)._content)

            self.assertEqual(app.state_steps, INITIAL_TUI_STATE)
            self.assertEqual(board_text, "")
            self.assertIn("Guess 1 of 6", status_text)

    async def test_valid_entry_updates_board_and_recommendation(self):
        updated_recommendation = {
            **recommendation_fixture(),
            "candidates": ("cigar", "circa"),
            "recommended_guess": "cigar",
            "recommendation_type": "answer",
            "remaining_count": 2,
            "max_bucket": 1,
        }
        requested_states = []

        def recommendation_builder(state_steps):
            requested_states.append(state_steps)
            return updated_recommendation

        app = HumanWordleBotApp(
            recommendation_fixture(),
            recommendation_builder=recommendation_builder,
        )

        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one("#guess-input", Input).value = "crane"
            app.query_one("#feedback-input", Input).value = "gbybb"
            await pilot.click("#add-result")
            await pilot.pause()

            board_text = str(app.query_one("#board-content", Static)._content)
            recommendation_text = str(
                app.query_one("#recommendation-content", Static)._content
            )
            status_text = str(app.query_one("#entry-status", Static)._content)

            self.assertIn(" C ", board_text)
            self.assertEqual(requested_states[0], ("crane", "G.Y.."))
            self.assertIn("CIGAR", recommendation_text)
            self.assertIn("next is 2 of 6", status_text)
            self.assertFalse(app.query_one("#add-result", Button).disabled)
            self.assertEqual(app.query_one("#guess-input", Input).value, "")
            self.assertEqual(app.query_one("#feedback-input", Input).value, "")

            app.query_one("#guess-input", Input).value = "cigar"
            app.query_one("#feedback-input", Input).value = "bgybb"
            await pilot.press("enter")
            await pilot.pause()

            board_text = str(app.query_one("#board-content", Static)._content)
            self.assertIn(" I ", board_text)
            self.assertEqual(len(requested_states), 2)
            self.assertEqual(len(app.state_steps) // 2, 2)
            self.assertFalse(app.query_one("#add-result", Button).disabled)

    async def test_all_green_completes_session_without_requesting_next_guess(self):
        requested_states = []

        def recommendation_builder(state_steps):
            requested_states.append(state_steps)
            return recommendation_fixture()

        app = HumanWordleBotApp(
            recommendation_fixture(),
            recommendation_builder=recommendation_builder,
        )

        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one("#guess-input", Input).value = "beech"
            app.query_one("#feedback-input", Input).value = "ggggg"
            await pilot.click("#add-result")
            await pilot.pause()

            board_text = str(app.query_one("#board-content", Static)._content)
            recommendation_text = str(
                app.query_one("#recommendation-content", Static)._content
            )
            status_text = str(app.query_one("#entry-status", Static)._content)

            self.assertIn(" B ", board_text)
            self.assertIn("SOLVED", recommendation_text)
            self.assertIn("BEECH", recommendation_text)
            self.assertIn("Solved in 1 of 6", status_text)
            self.assertEqual(requested_states, [])
            self.assertTrue(app.game_over)
            self.assertTrue(app.query_one("#add-result", Button).disabled)

    async def test_sixth_guess_ends_session(self):
        app = HumanWordleBotApp(
            recommendation_fixture(),
            recommendation_builder=lambda _state: recommendation_fixture(),
        )

        async with app.run_test(size=(100, 30)) as pilot:
            for guess in ("crane", "cigar", "pound", "fever", "humph", "blaze"):
                app.query_one("#guess-input", Input).value = guess
                app.query_one("#feedback-input", Input).value = "bbbbb"
                await pilot.press("enter")
                await pilot.pause()

            recommendation_text = str(
                app.query_one("#recommendation-content", Static)._content
            )
            status_text = str(app.query_one("#entry-status", Static)._content)

            self.assertEqual(len(app.state_steps) // 2, 6)
            self.assertIn("GAME OVER", recommendation_text)
            self.assertIn("Game over", status_text)
            self.assertTrue(app.game_over)
            self.assertTrue(app.query_one("#add-result", Button).disabled)

    async def test_reset_restores_initial_session(self):
        app = HumanWordleBotApp(recommendation_fixture())

        async with app.run_test(size=(100, 30)) as pilot:
            app.query_one("#guess-input", Input).value = "beech"
            app.query_one("#feedback-input", Input).value = "ggggg"
            await pilot.click("#add-result")
            await pilot.pause()
            await pilot.click("#reset-game")
            await pilot.pause()

            board_text = str(app.query_one("#board-content", Static)._content)
            recommendation_text = str(
                app.query_one("#recommendation-content", Static)._content
            )
            status_text = str(app.query_one("#entry-status", Static)._content)

            self.assertEqual(app.state_steps, INITIAL_TUI_STATE)
            self.assertEqual(board_text, "")
            self.assertIn("FURRY", recommendation_text)
            self.assertIn("Guess 1 of 6", status_text)
            self.assertFalse(app.game_over)
            self.assertFalse(app.query_one("#add-result", Button).disabled)

    async def test_invalid_entry_shows_error_without_updating_board(self):
        app = HumanWordleBotApp(recommendation_fixture())

        async with app.run_test(size=(100, 30)) as pilot:
            original_board = str(app.query_one("#board-content", Static)._content)
            app.query_one("#guess-input", Input).value = "four"
            app.query_one("#feedback-input", Input).value = "gbybb"
            await pilot.click("#add-result")
            await pilot.pause()

            status_text = str(app.query_one("#entry-status", Static)._content)
            board_text = str(app.query_one("#board-content", Static)._content)

            self.assertIn("Guess must be exactly 5 letters", status_text)
            self.assertEqual(board_text, original_board)
            self.assertFalse(app.query_one("#add-result", Button).disabled)

    async def test_q_quits_dashboard(self):
        app = HumanWordleBotApp(recommendation_fixture())

        async with app.run_test() as pilot:
            await pilot.press("q")

        self.assertIsNone(app.return_value)
