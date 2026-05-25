import tempfile
import unittest
from pathlib import Path

from src.wordle_lab.simulator import (
    filter_candidates,
    load_words,
    play_game,
    run_simulation,
)


class SimulatorTests(unittest.TestCase):
    def test_load_words_skips_blanks_comments_and_duplicates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "words.txt"
            path.write_text("\n# comment\ncrane\ncrane\nslate\n", encoding="utf-8")

            self.assertEqual(load_words(path), ("crane", "slate"))

    def test_load_words_rejects_invalid_words(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "words.txt"
            path.write_text("valid\nbad!\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_words(path)

    def test_load_words_rejects_uppercase_words(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "words.txt"
            path.write_text("CRANE\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_words(path)

    def test_load_words_reports_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_words("missing.txt")

    def test_filter_candidates_uses_exact_feedback(self):
        candidates = ("crane", "slate", "raise")

        self.assertEqual(
            filter_candidates(candidates, "raise", "GGGGG"),
            ("raise",),
        )

    def test_play_game_solves_known_answer(self):
        words = ("raise", "crane", "slate")
        result = play_game("slate", words, words, first_guess="raise")

        self.assertEqual(result.answer, "slate")
        self.assertTrue(result.solved)
        self.assertEqual(result.guesses[-1], "slate")

    def test_run_simulation_reports_average(self):
        words = ("raise", "crane", "slate")
        result = run_simulation(words, words, first_guess="raise")

        self.assertEqual(result.solved_count, 3)
        self.assertGreaterEqual(result.average_guesses, 1)

    def test_run_simulation_reports_guess_distribution(self):
        words = ("raise", "crane", "slate")
        result = run_simulation(words, words, first_guess="raise")

        self.assertEqual(result.failed_count, 0)
        self.assertEqual(sum(result.guess_distribution.values()), result.solved_count)
        self.assertEqual(result.guess_distribution[1], 1)


if __name__ == "__main__":
    unittest.main()
