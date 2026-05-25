import unittest

from src.wordle_lab.scoring import is_solved, score_guess


class ScoreGuessTests(unittest.TestCase):
    def test_all_green_when_guess_matches_answer(self):
        self.assertEqual(score_guess("crane", "crane"), "GGGGG")

    def test_yellow_for_right_letter_wrong_position(self):
        self.assertEqual(score_guess("raise", "arise"), "YYGGG")

    def test_gray_for_missing_letters(self):
        self.assertEqual(score_guess("crane", "sloth"), ".....")

    def test_duplicate_letters_do_not_overcount_yellows(self):
        self.assertEqual(score_guess("allee", "apple"), "GY..G")

    def test_duplicate_answer_letters_can_both_score(self):
        self.assertEqual(score_guess("paper", "apple"), "YYGY.")

    def test_rejects_different_word_lengths(self):
        with self.assertRaises(ValueError):
            score_guess("word", "world")

    def test_is_solved(self):
        self.assertTrue(is_solved("GGGGG"))
        self.assertFalse(is_solved("GGG.G"))


if __name__ == "__main__":
    unittest.main()
