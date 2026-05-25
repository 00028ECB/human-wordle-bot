import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from src.wordle_lab.__main__ import (
    CSV_COLUMNS,
    build_comparison_row,
    build_parser,
    build_top_opener_rows,
    format_comparison_row,
    main,
    write_comparison_csv,
)
from src.wordle_lab.simulator import run_simulation


class CliTests(unittest.TestCase):
    def test_parser_uses_default_first_guess(self):
        args = build_parser().parse_args([])

        self.assertEqual(args.first, "raise")

    def test_parser_accepts_custom_first_guess(self):
        args = build_parser().parse_args(["--first", "slate"])

        self.assertEqual(args.first, "slate")

    def test_parser_accepts_compare_first_guesses(self):
        args = build_parser().parse_args(["--compare", "raise", "slate", "crane"])

        self.assertEqual(args.compare, ["raise", "slate", "crane"])

    def test_parser_accepts_top_openers_limit(self):
        args = build_parser().parse_args(["--top-openers", "25"])

        self.assertEqual(args.top_openers, 25)

    def test_parser_accepts_csv_path(self):
        args = build_parser().parse_args(
            ["--compare", "raise", "slate", "--csv", "results/out.csv"]
        )

        self.assertEqual(args.csv, "results/out.csv")

    def test_parser_accepts_word_list_paths(self):
        args = build_parser().parse_args(
            [
                "--answers",
                "data/answers.txt",
                "--allowed",
                "data/allowed_guesses.txt",
                "--first",
                "raise",
            ]
        )

        self.assertEqual(args.answers, "data/answers.txt")
        self.assertEqual(args.allowed, "data/allowed_guesses.txt")

    def test_main_reports_custom_first_guess(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(["--first", "crane"])

        self.assertIn("First guess: crane", output.getvalue())

    def test_main_reports_guess_distribution(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(["--first", "raise"])

        report = output.getvalue()
        self.assertIn("Guess distribution:", report)
        self.assertIn("  1 guesses:", report)
        self.assertIn("  6 guesses:", report)
        self.assertIn("  Failed:", report)

    def test_main_reports_comparison_table(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(["--compare", "raise", "slate"])

        report = output.getvalue()
        self.assertIn("First   Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk", report)
        self.assertIn("raise", report)
        self.assertIn("slate", report)

    def test_main_reports_top_openers_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--top-openers",
                        "3",
                    ]
                )

        report = output.getvalue()
        lines = report.strip().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertIn("First   Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk", report)

    def test_format_comparison_row_includes_summary_counts(self):
        words = ("raise", "crane", "slate")
        result = run_simulation(words, words, first_guess="raise")
        row_data = build_comparison_row("raise", result)

        row = format_comparison_row(row_data)

        self.assertIn("raise", row)
        self.assertIn("3", row)
        self.assertTrue(row.endswith("0"))

    def test_build_comparison_row_includes_risk_score(self):
        words = ("raise", "crane", "slate")
        result = run_simulation(words, words, first_guess="raise")

        row = build_comparison_row("raise", result)

        expected_risk = row["fives"] * 2 + row["sixes"] * 5 + row["failed"] * 20
        self.assertEqual(row["risk_score"], expected_risk)

    def test_build_top_opener_rows_limits_and_sorts_by_average(self):
        words = ("raise", "crane", "slate")

        rows = build_top_opener_rows(2, words, words)

        self.assertEqual(len(rows), 2)
        self.assertLessEqual(float(rows[0]["average"]), float(rows[1]["average"]))

    def test_write_comparison_csv_creates_parent_folder(self):
        rows = (
            {
                "first_guess": "raise",
                "tested": 3,
                "solved": 3,
                "average": "1.67",
                "solved_3_or_less": 3,
                "solved_4_or_less": 3,
                "fives": 0,
                "sixes": 0,
                "failed": 0,
                "risk_score": 0,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results" / "starter_compare.csv"

            write_comparison_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(CSV_COLUMNS), csv_text)
        self.assertIn("raise,3,3,1.67,3,3,0,0,0,0", csv_text)

    def test_main_with_csv_still_prints_comparison_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "results" / "starter_compare.csv"
            output = io.StringIO()

            with redirect_stdout(output):
                main(["--compare", "raise", "slate", "--csv", str(csv_path)])

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("First   Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk", report)
        self.assertIn("raise", report)
        self.assertIn("first_guess,tested,solved,average", csv_text)
        self.assertIn("risk_score", csv_text)

    def test_main_top_openers_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "top_openers.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--top-openers",
                        "2",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("First   Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk", report)
        self.assertEqual(len(csv_text.strip().splitlines()), 3)
        self.assertIn("first_guess,tested,solved,average", csv_text)
        self.assertIn("risk_score", csv_text)

    def test_main_uses_custom_word_list_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--first",
                        "raise",
                    ]
                )

        self.assertIn("Answers tested: 2", output.getvalue())

    def test_main_exits_cleanly_for_missing_word_file(self):
        error_output = io.StringIO()

        with redirect_stderr(error_output), self.assertRaises(SystemExit):
            main(["--answers", "missing.txt", "--first", "raise"])

        self.assertIn("Word list file not found", error_output.getvalue())

    def test_csv_without_compare_exits(self):
        with self.assertRaises(SystemExit):
            main(["--csv", "results/out.csv"])

    def test_top_openers_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--top-openers", "0"])


if __name__ == "__main__":
    unittest.main()
