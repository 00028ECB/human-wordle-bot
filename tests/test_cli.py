import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from src.wordle_lab.__main__ import (
    CSV_COLUMNS,
    SECOND_GUESS_COLUMNS,
    STRATEGY_COLUMNS,
    TUNE_PATTERN_BRANCH_COLUMNS,
    TUNE_BRANCH_COLUMNS,
    TUNE_PATTERN_COLUMNS,
    TUNE_PATH_COLUMNS,
    TUNE_PATH_BRANCH_COLUMNS,
    WORST_GAME_COLUMNS,
    apply_second_guess_overrides,
    answer_likelihood_score,
    build_comparison_rows,
    build_comparison_row,
    build_parser,
    build_second_guess_map_rows,
    build_strategy_comparison_rows,
    build_worst_game_rows,
    build_worst_pattern_rows,
    build_worst_prefix_rows,
    build_strategy_row,
    build_top_opener_rows,
    build_final_cluster_rows,
    build_second_feedback_branch_summary,
    build_tune_branch_result,
    build_tune_branch_rows,
    build_tune_path_result,
    build_tune_path_rows,
    build_tune_pattern_result,
    build_tune_pattern_rows,
    bucket_probe_rank,
    choose_next_guess_with_optional_probe,
    choose_bucket_probe,
    choose_answer_candidate,
    choose_hybrid_guess,
    choose_small_candidate_by_likelihood,
    choose_trap_probe,
    candidates_before_guess,
    differing_letters,
    ExpectedValueOptimizer,
    feedback_bucket_sizes,
    find_final_cluster_override,
    find_path_guess_override,
    format_candidate_trace_path,
    format_comparison_row,
    filter_candidates_for_path,
    format_tune_path_label,
    format_remaining_candidates,
    is_trap_family,
    main,
    play_second_map_game,
    print_final_clusters,
    print_final_cluster_override_changes,
    print_small_order_changes,
    print_worst_prefixes,
    tune_objective_rank,
    tuned_overrides_enabled,
    worst_csv_path,
    write_worst_games_csv,
    write_second_guess_csv,
    write_comparison_csv,
    write_strategy_csv,
    write_tune_branch_csv,
    write_tune_path_csv,
    write_tune_pattern_csv,
)
from src.wordle_lab.simulator import GameResult, run_simulation


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

    def test_parser_accepts_stats_mode(self):
        args = build_parser().parse_args(["--stats"])

        self.assertTrue(args.stats)

    def test_parser_accepts_second_guess_map(self):
        args = build_parser().parse_args(["--second-guess-map", "slate"])

        self.assertEqual(args.second_guess_map, "slate")

    def test_parser_accepts_compare_strategies(self):
        args = build_parser().parse_args(["--compare-strategies"])

        self.assertTrue(args.compare_strategies)

    def test_parser_accepts_tune_pattern(self):
        args = build_parser().parse_args(["--tune-pattern", "slate", "....Y"])

        self.assertEqual(args.tune_pattern, ["slate", "....Y"])

    def test_parser_accepts_tune_branch(self):
        args = build_parser().parse_args(
            ["--tune-branch", "slate", "....Y", "rocky", "Y...."]
        )

        self.assertEqual(args.tune_branch, ["slate", "....Y", "rocky", "Y...."])

    def test_parser_accepts_tune_path(self):
        args = build_parser().parse_args(
            ["--tune-path", "slate", "....Y", "rocky", "Y....", "fiend", "..Y.."]
        )

        self.assertEqual(
            args.tune_path,
            ["slate", "....Y", "rocky", "Y....", "fiend", "..Y.."],
        )

    def test_parser_accepts_top_for_tune_pattern(self):
        args = build_parser().parse_args(
            ["--tune-pattern", "slate", "....Y", "--top", "10"]
        )

        self.assertEqual(args.top, 10)

    def test_parser_accepts_second_for_tune_pattern(self):
        args = build_parser().parse_args(
            ["--tune-pattern", "slate", "....Y", "--second", "rocky"]
        )

        self.assertEqual(args.second, "rocky")

    def test_parser_accepts_show_pattern_worst(self):
        args = build_parser().parse_args(
            [
                "--tune-pattern",
                "slate",
                "....Y",
                "--second",
                "rocky",
                "--show-pattern-worst",
                "25",
            ]
        )

        self.assertEqual(args.show_pattern_worst, 25)

    def test_parser_accepts_branch_summary(self):
        args = build_parser().parse_args(
            ["--tune-pattern", "slate", "....Y", "--branch-summary"]
        )

        self.assertTrue(args.branch_summary)

    def test_parser_accepts_tune_path_objective(self):
        args = build_parser().parse_args(
            [
                "--tune-branch",
                "slate",
                "....Y",
                "rocky",
                "Y....",
                "--tune-path-objective",
                "safe-balanced",
            ]
        )

        self.assertEqual(args.tune_path_objective, "safe-balanced")

    def test_parser_accepts_strategy(self):
        args = build_parser().parse_args(["--strategy", "second-map", "--first", "slate"])

        self.assertEqual(args.strategy, "second-map")
        self.assertEqual(args.first, "slate")

    def test_parser_accepts_trap_strategy(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-trap", "--first", "slate"]
        )

        self.assertEqual(args.strategy, "second-map-trap")

    def test_parser_accepts_bucket_strategy(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-bucket", "--first", "slate"]
        )

        self.assertEqual(args.strategy, "second-map-bucket")

    def test_parser_accepts_expected_strategy(self):
        args = build_parser().parse_args(
            [
                "--strategy",
                "second-map-expected",
                "--first",
                "slate",
                "--endgame-threshold",
                "50",
                "--max-expected-guesses",
                "7",
                "--max-expected-states",
                "1234",
                "--expected-depth",
                "3",
            ]
        )

        self.assertEqual(args.strategy, "second-map-expected")
        self.assertEqual(args.endgame_threshold, 50)
        self.assertEqual(args.max_expected_guesses, 7)
        self.assertEqual(args.max_expected_states, 1234)
        self.assertEqual(args.expected_depth, 3)

    def test_parser_accepts_hybrid_strategy(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-hybrid", "--first", "slate"]
        )

        self.assertEqual(args.strategy, "second-map-hybrid")

    def test_parser_accepts_trap_threshold(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-hybrid", "--trap-threshold", "3"]
        )

        self.assertEqual(args.trap_threshold, 3)

    def test_parser_accepts_answer_weighting(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-bucket", "--answer-weighting", "simple"]
        )

        self.assertEqual(args.answer_weighting, "simple")

    def test_parser_defaults_answer_weighting_to_off(self):
        args = build_parser().parse_args(["--strategy", "second-map-bucket"])

        self.assertEqual(args.answer_weighting, "off")

    def test_parser_accepts_small_candidate_order(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-bucket", "--small-candidate-order", "likelihood"]
        )

        self.assertEqual(args.small_candidate_order, "likelihood")

    def test_parser_defaults_small_candidate_order_to_normal(self):
        args = build_parser().parse_args(["--strategy", "second-map-bucket"])

        self.assertEqual(args.small_candidate_order, "normal")

    def test_parser_accepts_show_small_order_changes(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-bucket", "--show-small-order-changes"]
        )

        self.assertTrue(args.show_small_order_changes)

    def test_parser_accepts_final_cluster_overrides(self):
        args = build_parser().parse_args(
            [
                "--strategy",
                "second-map-bucket",
                "--final-cluster-overrides",
                "on",
                "--show-final-cluster-override-changes",
            ]
        )

        self.assertEqual(args.final_cluster_overrides, "on")
        self.assertTrue(args.show_final_cluster_override_changes)

    def test_parser_accepts_no_overrides(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-bucket", "--no-overrides"]
        )

        self.assertTrue(args.no_overrides)

    def test_parser_defaults_trap_threshold_to_two(self):
        args = build_parser().parse_args(["--strategy", "second-map-hybrid"])

        self.assertEqual(args.trap_threshold, 2)

    def test_parser_defaults_expected_guardrails(self):
        args = build_parser().parse_args(["--strategy", "second-map-expected"])

        self.assertEqual(args.endgame_threshold, 10)
        self.assertEqual(args.max_expected_guesses, 10)
        self.assertEqual(args.max_expected_states, 50000)
        self.assertEqual(args.expected_depth, 2)

    def test_parser_accepts_show_worst(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map", "--first", "slate", "--show-worst", "25"]
        )

        self.assertEqual(args.show_worst, 25)

    def test_parser_accepts_show_candidate_trace(self):
        args = build_parser().parse_args(
            [
                "--strategy",
                "second-map",
                "--first",
                "slate",
                "--show-worst",
                "25",
                "--show-candidate-trace",
            ]
        )

        self.assertTrue(args.show_candidate_trace)

    def test_parser_accepts_worst_patterns_without_limit(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map", "--first", "slate", "--worst-patterns"]
        )

        self.assertEqual(args.worst_patterns, -1)

    def test_parser_accepts_worst_patterns_limit(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map", "--first", "slate", "--worst-patterns", "20"]
        )

        self.assertEqual(args.worst_patterns, 20)

    def test_parser_accepts_worst_prefixes(self):
        args = build_parser().parse_args(
            ["--strategy", "second-map-bucket", "--first", "slate", "--worst-prefixes", "20"]
        )

        self.assertEqual(args.worst_prefixes, 20)

    def test_parser_accepts_show_final_clusters(self):
        args = build_parser().parse_args(
            [
                "--strategy",
                "second-map-bucket",
                "--first",
                "slate",
                "--show-final-clusters",
                "50",
            ]
        )

        self.assertEqual(args.show_final_clusters, 50)

    def test_parser_accepts_second_guess_pool(self):
        args = build_parser().parse_args(
            ["--second-guess-map", "slate", "--second-guess-pool", "answers"]
        )

        self.assertEqual(args.second_guess_pool, "answers")

    def test_parser_defaults_second_guess_pool_to_allowed(self):
        args = build_parser().parse_args(["--second-guess-map", "slate"])

        self.assertEqual(args.second_guess_pool, "allowed")

    def test_parser_accepts_rank_by(self):
        args = build_parser().parse_args(["--top-openers", "25", "--rank-by", "risk"])

        self.assertEqual(args.rank_by, "risk")

    def test_parser_accepts_opener_pool(self):
        args = build_parser().parse_args(
            ["--top-openers", "25", "--opener-pool", "answers"]
        )

        self.assertEqual(args.opener_pool, "answers")

    def test_parser_accepts_limit_openers(self):
        args = build_parser().parse_args(["--top-openers", "25", "--limit-openers", "100"])

        self.assertEqual(args.limit_openers, 100)

    def test_parser_defaults_opener_pool_to_allowed(self):
        args = build_parser().parse_args(["--top-openers", "25"])

        self.assertEqual(args.opener_pool, "allowed")

    def test_parser_defaults_rank_by_to_average(self):
        args = build_parser().parse_args(["--top-openers", "25"])

        self.assertEqual(args.rank_by, "average")

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

    def test_main_reports_stats(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(["--stats"])

        report = output.getvalue()
        self.assertIn("Answers: 254", report)
        self.assertIn("Allowed guesses: 1542", report)
        self.assertIn("Overlap: 254", report)
        self.assertIn("Allowed-only guesses: 1288", report)

    def test_main_reports_stats_for_custom_word_lists(self):
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
                        "--stats",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Answers: 2", report)
        self.assertIn("Allowed guesses: 3", report)
        self.assertIn("Overlap: 2", report)
        self.assertIn("Allowed-only guesses: 1", report)

    def test_main_reports_second_guess_map_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--second-guess-map",
                        "slate",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Pattern  Candidates  Best Avg  Best Balanced  Sample answers", report)
        self.assertIn("GGGGG", report)
        self.assertIn("slate", report)

    def test_main_reports_comparison_table(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(["--compare", "raise", "slate"])

        report = output.getvalue()
        self.assertIn("First   Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk", report)
        self.assertIn("raise", report)
        self.assertIn("slate", report)

    def test_main_reports_strategy_baseline_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "baseline",
                        "--first",
                        "slate",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Strategy    First  Pool", report)
        self.assertIn("baseline", report)
        self.assertIn("slate", report)

    def test_main_reports_strategy_second_map_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("second-map", report)
        self.assertIn("answers", report)

    def test_main_reports_strategy_second_map_trap_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map-trap",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("second-map-trap", report)
        self.assertIn("answers", report)

    def test_main_reports_strategy_second_map_bucket_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map-bucket",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("second-map-bucket", report)
        self.assertIn("answers", report)

    def test_main_reports_strategy_with_answer_weighting_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map-bucket",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--answer-weighting",
                        "simple",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("second-map-bucket", report)

    def test_main_reports_weighting_change_diagnostics(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(
                [
                    "--answers",
                    "data/answers.txt",
                    "--allowed",
                    "data/allowed_guesses.txt",
                    "--strategy",
                    "second-map-bucket",
                    "--first",
                    "slate",
                    "--second-guess-pool",
                    "answers",
                    "--answer-weighting",
                    "simple",
                    "--no-overrides",
                    "--show-weighting-changes",
                ]
            )

        report = output.getvalue()
        self.assertIn("Weighting changed decisions:", report)
        self.assertIn("Games affected:", report)

    def test_main_reports_small_order_change_diagnostics(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(
                [
                    "--answers",
                    "data/answers.txt",
                    "--allowed",
                    "data/allowed_guesses.txt",
                    "--strategy",
                    "baseline",
                    "--first",
                    "slate",
                    "--small-candidate-order",
                    "likelihood",
                    "--show-small-order-changes",
                ]
            )

        report = output.getvalue()
        self.assertIn("Small-order changed decisions:", report)
        self.assertIn("Games affected:", report)

    def test_main_reports_final_cluster_override_change_diagnostics(self):
        output = io.StringIO()

        with redirect_stdout(output):
            main(
                [
                    "--answers",
                    "data/answers.txt",
                    "--allowed",
                    "data/allowed_guesses.txt",
                    "--strategy",
                    "baseline",
                    "--first",
                    "slate",
                    "--final-cluster-overrides",
                    "on",
                    "--show-final-cluster-override-changes",
                ]
            )

        report = output.getvalue()
        self.assertIn("Final-cluster override changed decisions:", report)
        self.assertIn("Games affected:", report)

    def test_main_reports_strategy_second_map_hybrid_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map-hybrid",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--trap-threshold",
                        "3",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("second-map-hybrid", report)
        self.assertIn("answers", report)

    def test_main_reports_compare_strategies_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--compare-strategies",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Strategy    First  Pool", report)
        self.assertIn("baseline", report)
        self.assertIn("second-map", report)
        self.assertIn("second-map-trap", report)
        self.assertIn("second-map-bucket", report)
        self.assertIn("second-map-hybrid", report)

    def test_main_reports_tune_pattern_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-pattern",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Pattern  Second  Candidates", report)
        self.assertIn("GGGGG", report)

    def test_main_reports_tune_pattern_branch_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-pattern",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                        "--branch-summary",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Worst2", report)
        self.assertIn("WorstRisk", report)

    def test_main_tune_pattern_second_show_worst_prints_worst_games(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-pattern",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--second",
                        "slate",
                        "--show-worst",
                        "1",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Pattern  Second  Candidates", report)
        self.assertIn("Worst games:", report)
        self.assertIn("answer  guesses  path", report)

    def test_main_reports_tune_branch_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-branch",
                        "slate",
                        "GGGGG",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                    ]
                )

        report = output.getvalue()
        self.assertIn("FirstPat  Second  SecondPat", report)
        self.assertIn("GGGGG", report)

    def test_main_reports_tune_path_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-path",
                        "slate",
                        "GGGGG",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Path  Next  Candidates", report)
        self.assertIn("slate GGGGG slate GGGGG", report)

    def test_main_reports_tune_path_branch_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-path",
                        "slate",
                        "GGGGG",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                        "--branch-summary",
                    ]
                )

        report = output.getvalue()
        self.assertIn("WorstNext", report)
        self.assertIn("WorstRisk", report)

    def test_main_tune_path_selected_next_show_worst_prints_worst_games(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-path",
                        "slate",
                        "GGGGG",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--second",
                        "slate",
                        "--show-worst",
                        "1",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Worst games:", report)
        self.assertIn("answer  guesses  path", report)

    def test_main_strategy_show_worst_prints_worst_games(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--show-worst",
                        "2",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Worst games:", report)
        self.assertIn("answer  guesses  path", report)

    def test_main_strategy_show_worst_candidate_trace_prints_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "baseline",
                        "--first",
                        "slate",
                        "--show-worst",
                        "2",
                        "--show-candidate-trace",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Worst games:", report)
        self.assertIn("slate(3)", report)

    def test_main_strategy_worst_patterns_prints_pattern_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--worst-patterns",
                        "2",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Worst patterns:", report)
        self.assertIn("pattern  games  avg", report)

    def test_main_strategy_worst_prefixes_prints_prefix_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text(
                "caper\ncater\ncaver\ncower\nmower\npower\n",
                encoding="utf-8",
            )
            allowed_path.write_text(
                "slate\ncrane\ncaper\ncater\ncaver\ncower\nmower\npower\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "baseline",
                        "--first",
                        "slate",
                        "--worst-prefixes",
                        "3",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Worst prefixes:", report)
        self.assertIn("prefix  games  5s", report)

    def test_main_strategy_show_final_clusters_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text(
                "caper\ncater\ncaver\ncower\nmower\npower\n",
                encoding="utf-8",
            )
            allowed_path.write_text(
                "slate\ncrane\ncaper\ncater\ncaver\ncower\nmower\npower\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "baseline",
                        "--first",
                        "slate",
                        "--show-final-clusters",
                        "3",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Final clusters:", report)
        self.assertIn("candidates  games", report)

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
        self.assertEqual(len(lines), 6)
        self.assertIn("First   Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk", report)
        self.assertIn("Elapsed seconds:", report)
        self.assertIn("Average seconds per opener:", report)

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

    def test_build_top_opener_rows_limits_and_sorts_by_average_by_default(self):
        words = ("raise", "crane", "slate")

        rows = build_top_opener_rows(2, words, words, words)

        self.assertEqual(len(rows), 2)
        self.assertLessEqual(float(rows[0]["average"]), float(rows[1]["average"]))

    def test_build_top_opener_rows_can_rank_by_risk(self):
        words = ("raise", "crane", "slate")

        rows = build_top_opener_rows(3, words, words, words, rank_by="risk")

        risk_scores = [row["risk_score"] for row in rows]
        self.assertEqual(risk_scores, sorted(risk_scores))

    def test_build_top_opener_rows_can_rank_balanced(self):
        words = ("raise", "crane", "slate")

        rows = build_top_opener_rows(3, words, words, words, rank_by="balanced")

        ranking_values = [
            (row["risk_score"], float(row["average"]), -row["solved_3_or_less"])
            for row in rows
        ]
        self.assertEqual(ranking_values, sorted(ranking_values))

    def test_build_top_opener_rows_uses_selected_opener_pool(self):
        allowed_words = ("raise", "crane", "slate")
        answer_words = ("raise", "crane")

        rows = build_top_opener_rows(3, answer_words, allowed_words, answer_words)

        first_guesses = {row["first_guess"] for row in rows}
        self.assertEqual(first_guesses, {"raise", "crane"})

    def test_build_top_opener_rows_can_show_progress(self):
        words = ("raise", "crane", "slate")
        output = io.StringIO()

        with redirect_stdout(output):
            build_top_opener_rows(
                2,
                words,
                words,
                words,
                show_progress=True,
                progress_every=2,
            )

        self.assertIn("Tested 2/3 openers...", output.getvalue())

    def test_build_second_guess_map_rows_groups_by_feedback_pattern(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_second_guess_map_rows("slate", allowed_words, answer_words)

        patterns = {row["pattern"] for row in rows}
        solved_row = next(row for row in rows if row["pattern"] == "GGGGG")
        self.assertIn("GGGGG", patterns)
        self.assertEqual(solved_row["candidates"], 1)
        self.assertEqual(solved_row["sample_answers"], "slate")

    def test_build_second_guess_map_rows_can_use_answer_only_pool(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_second_guess_map_rows(
            "slate",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
        )

        for row in rows:
            self.assertIn(row["best_average"], answer_words)
            self.assertIn(row["best_balanced"], answer_words)

    def test_build_second_guess_map_requires_allowed_first_guess(self):
        with self.assertRaises(ValueError):
            build_second_guess_map_rows(
                "zzzzz",
                ("raise", "slate"),
                ("raise", "slate"),
            )

    def test_strategy_baseline_matches_existing_simulation_summary(self):
        words = ("raise", "crane", "slate")
        result = run_simulation(words, words, first_guess="slate")

        strategy_row = build_strategy_row("baseline", "slate", words, words)
        comparison_row = build_comparison_row("slate", result)

        for key, value in comparison_row.items():
            self.assertEqual(strategy_row[key], value)
        self.assertEqual(strategy_row["strategy"], "baseline")

    def test_strategy_second_map_reports_selected_pool(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        row = build_strategy_row(
            "second-map",
            "slate",
            allowed_words,
            answer_words,
            second_guess_pool_name="answers",
            use_overrides=False,
        )

        self.assertEqual(row["strategy"], "second-map")
        self.assertEqual(row["second_guess_pool"], "answers")
        self.assertEqual(row["tested"], 3)

    def test_strategy_second_map_trap_reports_selected_pool(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        row = build_strategy_row(
            "second-map-trap",
            "slate",
            allowed_words,
            answer_words,
            second_guess_pool_name="answers",
            use_overrides=False,
        )

        self.assertEqual(row["strategy"], "second-map-trap")
        self.assertEqual(row["second_guess_pool"], "answers")
        self.assertEqual(row["tested"], 3)

    def test_strategy_second_map_bucket_reports_selected_pool(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        row = build_strategy_row(
            "second-map-bucket",
            "slate",
            allowed_words,
            answer_words,
            second_guess_pool_name="answers",
            use_overrides=False,
        )

        self.assertEqual(row["strategy"], "second-map-bucket")
        self.assertEqual(row["second_guess_pool"], "answers")
        self.assertEqual(row["tested"], 3)

    def test_strategy_second_map_expected_reports_selected_pool(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        row = build_strategy_row(
            "second-map-expected",
            "slate",
            allowed_words,
            answer_words,
            second_guess_pool_name="answers",
            endgame_threshold=3,
            use_overrides=False,
        )

        self.assertEqual(row["strategy"], "second-map-expected")
        self.assertEqual(row["second_guess_pool"], "answers")
        self.assertEqual(row["tested"], 3)

    def test_strategy_second_map_hybrid_reports_selected_pool(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        row = build_strategy_row(
            "second-map-hybrid",
            "slate",
            allowed_words,
            answer_words,
            second_guess_pool_name="answers",
            trap_threshold=3,
            use_overrides=False,
        )

        self.assertEqual(row["strategy"], "second-map-hybrid")
        self.assertEqual(row["second_guess_pool"], "answers")
        self.assertEqual(row["tested"], 3)

    def test_apply_second_guess_overrides_uses_matching_override(self):
        second_guess_by_pattern = {
            ".....": "pound",
            "...Y.": "mount",
            "...YY": "solid",
            "....Y": "heron",
            "..G.G": "crank",
            "..Y..": "major",
            "..Y.Y": "abbey",
            "..YY.": "tacit",
            ".YY..": "brawl",
            ".Y...": "colon",
            "G..Y.": "cough",
            "..G..": "grove",
            "Y....": "mimic",
        }

        apply_second_guess_overrides(
            "slate",
            "answers",
            (
                "frond",
                "tough",
                "deter",
                "rocky",
                "brick",
                "randy",
                "march",
                "pouch",
                "rally",
                "dilly",
                "count",
                "grind",
                "missy",
            ),
            second_guess_by_pattern,
        )

        self.assertEqual(second_guess_by_pattern["....."], "frond")
        self.assertEqual(second_guess_by_pattern["...Y."], "tough")
        self.assertEqual(second_guess_by_pattern["...YY"], "deter")
        self.assertEqual(second_guess_by_pattern["....Y"], "rocky")
        self.assertEqual(second_guess_by_pattern["..G.G"], "brick")
        self.assertEqual(second_guess_by_pattern["..Y.."], "randy")
        self.assertEqual(second_guess_by_pattern["..Y.Y"], "march")
        self.assertEqual(second_guess_by_pattern["..YY."], "pouch")
        self.assertEqual(second_guess_by_pattern[".YY.."], "rally")
        self.assertEqual(second_guess_by_pattern[".Y..."], "dilly")
        self.assertEqual(second_guess_by_pattern["G..Y."], "count")
        self.assertEqual(second_guess_by_pattern["..G.."], "grind")
        self.assertEqual(second_guess_by_pattern["Y...."], "missy")

    def test_apply_second_guess_overrides_rejects_invalid_pool_word(self):
        second_guess_by_pattern = {"....Y": "heron"}

        with self.assertRaises(ValueError):
            apply_second_guess_overrides(
                "slate",
                "answers",
                ("heron",),
                second_guess_by_pattern,
            )

    def test_apply_second_guess_overrides_ignores_disabled_pool(self):
        second_guess_by_pattern = {
            ".....": "pound",
            "...Y.": "mount",
            "...YY": "solid",
            "....Y": "heron",
            "..G.G": "crank",
            "..Y..": "major",
            "..Y.Y": "abbey",
            "..YY.": "tacit",
            ".YY..": "brawl",
            ".Y...": "colon",
            "G..Y.": "cough",
            "..G..": "grove",
            "Y....": "mimic",
        }

        apply_second_guess_overrides(
            "slate",
            "allowed",
            (
                "frond",
                "tough",
                "deter",
                "heron",
                "rocky",
                "brick",
                "randy",
                "march",
                "pouch",
                "rally",
                "dilly",
                "count",
                "grind",
                "missy",
            ),
            second_guess_by_pattern,
        )

        self.assertEqual(second_guess_by_pattern["....."], "pound")
        self.assertEqual(second_guess_by_pattern["...Y."], "mount")
        self.assertEqual(second_guess_by_pattern["...YY"], "solid")
        self.assertEqual(second_guess_by_pattern["....Y"], "heron")
        self.assertEqual(second_guess_by_pattern["..G.G"], "crank")
        self.assertEqual(second_guess_by_pattern["..Y.."], "major")
        self.assertEqual(second_guess_by_pattern["..Y.Y"], "abbey")
        self.assertEqual(second_guess_by_pattern["..YY."], "tacit")
        self.assertEqual(second_guess_by_pattern[".YY.."], "brawl")
        self.assertEqual(second_guess_by_pattern[".Y..."], "colon")
        self.assertEqual(second_guess_by_pattern["G..Y."], "cough")
        self.assertEqual(second_guess_by_pattern["..G.."], "grove")
        self.assertEqual(second_guess_by_pattern["Y...."], "mimic")

    def test_find_path_guess_override_uses_matching_override(self):
        override_guess = find_path_guess_override(
            "slate",
            ".....",
            "frond",
            "..Y..",
            "answers",
            ("frond", "pouch"),
            ("slate", "frond"),
        )

        self.assertEqual(override_guess, "pouch")

    def test_find_path_guess_override_uses_all_gray_frond_override(self):
        override_guess = find_path_guess_override(
            "slate",
            ".....",
            "frond",
            ".....",
            "answers",
            ("frond", "chump"),
            ("slate", "frond"),
        )

        self.assertEqual(override_guess, "chump")

    def test_find_path_guess_override_rejects_invalid_pool_word(self):
        with self.assertRaises(ValueError):
            find_path_guess_override(
                "slate",
                ".....",
                "frond",
                "..Y..",
                "answers",
                ("frond",),
                ("slate", "frond"),
            )

    def test_play_second_map_game_uses_path_override_for_third_guess(self):
        allowed_words = ("slate", "frond", "cough", "pouch")
        answer_words = ("cough", "pouch")

        game = play_second_map_game(
            "pouch",
            allowed_words,
            answer_words,
            "slate",
            {".....": "frond"},
            probe_pool=answer_words,
            use_overrides=True,
            second_guess_pool_name="answers",
        )

        self.assertEqual(game.guesses[:3], ("slate", "frond", "pouch"))

    def test_play_second_map_game_disables_path_override(self):
        allowed_words = ("slate", "frond", "cough", "pouch")
        answer_words = ("cough", "pouch")

        game = play_second_map_game(
            "pouch",
            allowed_words,
            answer_words,
            "slate",
            {".....": "frond"},
            probe_pool=answer_words,
            use_overrides=False,
            second_guess_pool_name="answers",
        )

        self.assertEqual(game.guesses[:3], ("slate", "frond", "cough"))

    def test_tuned_overrides_default_only_for_second_map_bucket(self):
        self.assertFalse(tuned_overrides_enabled("baseline", None))
        self.assertFalse(tuned_overrides_enabled("second-map", None))
        self.assertFalse(tuned_overrides_enabled("second-map-trap", None))
        self.assertTrue(tuned_overrides_enabled("second-map-bucket", None))
        self.assertFalse(tuned_overrides_enabled("second-map-hybrid", None))

    def test_tuned_overrides_can_be_disabled_for_second_map_bucket(self):
        self.assertFalse(tuned_overrides_enabled("second-map-bucket", False))

    def test_tuned_overrides_can_be_explicitly_enabled_for_other_strategies(self):
        self.assertTrue(tuned_overrides_enabled("second-map", True))

    def test_build_strategy_comparison_rows_returns_builtin_slate_set(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_strategy_comparison_rows(
            allowed_words,
            answer_words,
            use_overrides=False,
        )

        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0]["strategy"], "baseline")
        self.assertEqual(rows[0]["first_guess"], "slate")
        self.assertEqual(rows[0]["second_guess_pool"], "-")
        self.assertEqual(rows[-1]["strategy"], "second-map-hybrid")
        self.assertEqual(rows[-1]["second_guess_pool"], "allowed")

    def test_is_trap_family_detects_shared_fixed_positions(self):
        trap_candidates = ("gaunt", "haunt", "jaunt", "taunt", "vaunt")
        mixed_candidates = ("gaunt", "breed", "cower")

        self.assertTrue(is_trap_family(trap_candidates))
        self.assertFalse(is_trap_family(mixed_candidates))

    def test_differing_letters_returns_trap_family_letters(self):
        candidates = ("gaunt", "haunt", "jaunt", "taunt", "vaunt")

        self.assertEqual(differing_letters(candidates), {"g", "h", "j", "t", "v"})

    def test_choose_trap_probe_maximizes_differing_letter_coverage(self):
        candidates = ("gaunt", "haunt", "jaunt", "taunt", "vaunt")
        probe_pool = ("slate", "fight", "ghjtv")

        self.assertEqual(choose_trap_probe(candidates, (), probe_pool), "ghjtv")

    def test_choose_next_guess_uses_probe_for_trap_family(self):
        candidates = ("gaunt", "haunt", "jaunt", "taunt", "vaunt")
        probe_pool = ("slate", "ghjtv")

        guess = choose_next_guess_with_optional_probe(
            candidates,
            previous_guesses=("slate",),
            allowed_guesses=candidates,
            probe_pool=probe_pool,
            use_trap_avoidance=True,
        )

        self.assertEqual(guess, "ghjtv")

    def test_feedback_bucket_sizes_groups_candidates_by_feedback(self):
        candidates = ("cower", "mower", "power", "rower")

        bucket_sizes = feedback_bucket_sizes("caper", candidates)

        self.assertEqual(sum(bucket_sizes), 4)
        self.assertGreaterEqual(len(bucket_sizes), 2)

    def test_bucket_probe_rank_prefers_smaller_largest_bucket(self):
        candidates = ("cower", "mower", "power", "rower")

        better_rank = bucket_probe_rank("champ", candidates)
        worse_rank = bucket_probe_rank("cower", candidates)

        self.assertLessEqual(better_rank[0], worse_rank[0])

    def test_choose_bucket_probe_minimizes_largest_bucket(self):
        candidates = ("cower", "mower", "power", "rower")
        probe_pool = ("cower", "champ", "rower")

        guess = choose_bucket_probe(candidates, previous_guesses=(), probe_pool=probe_pool)

        ranks = {probe: bucket_probe_rank(probe, candidates) for probe in probe_pool}
        self.assertEqual(ranks[guess], min(ranks.values()))

    def test_choose_next_guess_uses_bucket_strategy(self):
        candidates = ("cower", "mower", "power", "rower")
        probe_pool = ("cower", "champ", "rower")

        guess = choose_next_guess_with_optional_probe(
            candidates,
            previous_guesses=(),
            allowed_guesses=candidates,
            probe_pool=probe_pool,
            use_trap_avoidance=False,
            use_bucket_strategy=True,
        )

        self.assertEqual(guess, choose_bucket_probe(candidates, (), probe_pool))

    def test_expected_value_optimizer_prefers_answer_guess_in_tie(self):
        optimizer = ExpectedValueOptimizer(("caper", "cater"))

        guess = optimizer.choose_guess(("cater", "caper"), previous_guesses=())

        self.assertEqual(guess, "caper")

    def test_expected_value_optimizer_limits_guess_candidates(self):
        optimizer = ExpectedValueOptimizer(("caper", "cater", "caver"), max_guesses=1)

        guesses = optimizer._candidate_guesses(("caper", "cater", "caver"), ())

        self.assertEqual(len(guesses), 1)

    def test_expected_value_optimizer_falls_back_after_state_limit(self):
        optimizer = ExpectedValueOptimizer(("caper", "cater", "caver"), max_states=1)
        optimizer.state_count = 1

        guess = optimizer.choose_guess(("caper", "cater", "caver"), previous_guesses=())

        self.assertIn(guess, ("caper", "cater", "caver"))
        self.assertEqual(optimizer.fallback_count, 1)

    def test_expected_value_optimizer_depth_limit_uses_estimate(self):
        optimizer = ExpectedValueOptimizer(("caper", "cater", "caver"), max_depth=1)

        value = optimizer.expected_total(("caper", "cater", "caver"), (), 0)

        self.assertGreaterEqual(value, 1.0)

    def test_choose_next_guess_uses_expected_strategy_under_threshold(self):
        candidates = ("femur", "fewer")
        optimizer = ExpectedValueOptimizer(("fewer", "femur"))

        guess = choose_next_guess_with_optional_probe(
            candidates,
            previous_guesses=("slate", "rocky", "fever"),
            allowed_guesses=candidates,
            probe_pool=("fever", "femur", "fewer"),
            use_trap_avoidance=False,
            use_bucket_strategy=True,
            use_expected_strategy=True,
            endgame_threshold=2,
            expected_optimizer=optimizer,
        )

        self.assertEqual(guess, "femur")

    def test_small_candidate_order_applies_before_bucket_probe(self):
        candidates = ("femur", "fewer")
        probe_pool = ("fever", "femur", "fewer")
        changes = []

        guess = choose_next_guess_with_optional_probe(
            candidates,
            previous_guesses=("slate", "rocky", "fever"),
            allowed_guesses=candidates,
            probe_pool=probe_pool,
            use_trap_avoidance=False,
            use_bucket_strategy=True,
            small_candidate_order="likelihood",
            small_order_changes=changes,
            answer="fewer",
            guess_number=5,
        )

        self.assertEqual(guess, "fewer")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["normal_choice"], "femur")
        self.assertEqual(changes[0]["ordered_choice"], "fewer")

    def test_answer_likelihood_score_prefers_common_word_shape(self):
        self.assertGreater(answer_likelihood_score("crane"), answer_likelihood_score("jazzy"))
        self.assertGreater(answer_likelihood_score("caper"), answer_likelihood_score("qajaq"))

    def test_choose_small_candidate_by_likelihood_uses_pair_override(self):
        expectations = (
            (["femur", "fewer"], "fewer"),
            (["piper", "viper"], "viper"),
            (["upper", "ember"], "ember"),
            (["biddy", "giddy"], "giddy"),
            (["frank", "prank"], "prank"),
            (["pried", "weird"], "weird"),
            (["breed", "greed"], "greed"),
            (["brief", "grief"], "grief"),
        )

        for candidates, expected in expectations:
            with self.subTest(candidates=candidates):
                self.assertEqual(choose_small_candidate_by_likelihood(candidates), expected)

    def test_choose_small_candidate_by_likelihood_preserves_unmapped_order(self):
        self.assertEqual(
            choose_small_candidate_by_likelihood(["abode", "adobe", "anode"]),
            "abode",
        )

    def test_choose_answer_candidate_preserves_default_order_when_off(self):
        candidates = ("jazzy", "crane")

        guess = choose_answer_candidate(candidates, (), candidates, "off")

        self.assertEqual(guess, "jazzy")

    def test_choose_answer_candidate_uses_simple_weighting(self):
        candidates = ("jazzy", "crane")

        guess = choose_answer_candidate(candidates, (), candidates, "simple")

        self.assertEqual(guess, "crane")

    def test_choose_answer_candidate_records_weighting_change(self):
        candidates = ("jazzy", "crane")
        changes = []

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "simple",
            weighting_changes=changes,
            answer="crane",
            guess_number=3,
        )

        self.assertEqual(guess, "crane")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["unweighted_choice"], "jazzy")
        self.assertEqual(changes[0]["weighted_choice"], "crane")

    def test_choose_answer_candidate_uses_small_candidate_order_for_two_or_three(self):
        candidates = ("femur", "fewer")

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            guess_number=4,
            small_candidate_order="likelihood",
        )

        self.assertEqual(guess, "fewer")

    def test_choose_answer_candidate_small_order_ignores_larger_candidate_sets(self):
        candidates = ("jazzy", "crane", "caper", "raise")

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            guess_number=4,
            small_candidate_order="likelihood",
        )

        self.assertEqual(guess, "jazzy")

    def test_choose_answer_candidate_small_order_requires_guess_four_or_later(self):
        candidates = ("femur", "fewer")

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            guess_number=3,
            small_candidate_order="likelihood",
        )

        self.assertEqual(guess, "femur")

    def test_choose_answer_candidate_small_order_preserves_unmapped_triple(self):
        candidates = ("abode", "adobe", "anode")

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            guess_number=4,
            small_candidate_order="likelihood",
        )

        self.assertEqual(guess, "abode")

    def test_choose_answer_candidate_records_small_order_change(self):
        candidates = ("femur", "fewer")
        changes = []

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            answer="fewer",
            guess_number=4,
            small_candidate_order="likelihood",
            small_order_changes=changes,
        )

        self.assertEqual(guess, "fewer")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["normal_choice"], "femur")
        self.assertEqual(changes[0]["ordered_choice"], "fewer")

    def test_find_final_cluster_override_matches_exact_sorted_cluster(self):
        override = find_final_cluster_override(("fever", "femur", "fewer"), ())

        self.assertEqual(override, "fewer")

    def test_find_final_cluster_override_ignores_partial_cluster(self):
        override = find_final_cluster_override(("femur", "fewer"), ())

        self.assertIsNone(override)

    def test_find_final_cluster_override_ignores_already_guessed_override(self):
        override = find_final_cluster_override(
            ("fever", "femur", "fewer"),
            ("fewer",),
        )

        self.assertIsNone(override)

    def test_choose_answer_candidate_applies_final_cluster_override_only_when_on(self):
        candidates = ("femur", "fever", "fewer")
        previous_guesses = ("slate", "rocky", "fiend")
        changes = []

        normal_choice = choose_answer_candidate(
            candidates,
            previous_guesses,
            candidates,
            "off",
            answer="fewer",
            guess_number=4,
            final_cluster_overrides="off",
        )
        override_choice = choose_answer_candidate(
            candidates,
            previous_guesses,
            candidates,
            "off",
            answer="fewer",
            guess_number=4,
            final_cluster_overrides="on",
            final_cluster_override_changes=changes,
        )

        self.assertEqual(normal_choice, "femur")
        self.assertEqual(override_choice, "fewer")
        self.assertEqual(changes[0]["normal_choice"], "femur")
        self.assertEqual(changes[0]["override_choice"], "fewer")

    def test_choose_next_guess_applies_final_cluster_override_before_bucket(self):
        changes = []

        guess = choose_next_guess_with_optional_probe(
            ("femur", "fever", "fewer"),
            ("slate", "rocky", "fiend"),
            ("femur", "fever", "fewer"),
            ("femur", "fever", "fewer"),
            use_trap_avoidance=False,
            use_bucket_strategy=True,
            answer="fewer",
            guess_number=4,
            final_cluster_overrides="on",
            final_cluster_override_changes=changes,
        )

        self.assertEqual(guess, "fewer")
        self.assertEqual(changes[0]["override_choice"], "fewer")

    def test_print_final_cluster_override_changes_outputs_examples(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_final_cluster_override_changes(
                (
                    {
                        "answer": "fewer",
                        "guess_number": 4,
                        "normal_choice": "femur",
                        "override_choice": "fewer",
                        "remaining_candidates": ("femur", "fever", "fewer"),
                    },
                )
            )

        report = output.getvalue()
        self.assertIn("Final-cluster override changed decisions: 1", report)
        self.assertIn("femur, fever, fewer", report)

    def test_print_small_order_changes_outputs_examples(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_small_order_changes(
                (
                    {
                        "answer": "crane",
                        "guess_number": 4,
                        "normal_choice": "jazzy",
                        "ordered_choice": "crane",
                        "remaining_candidates": ("jazzy", "crane"),
                    },
                )
            )

        report = output.getvalue()
        self.assertIn("Small-order changed decisions: 1", report)
        self.assertIn("jazzy", report)

    def test_format_remaining_candidates_truncates_long_lists(self):
        candidates = tuple(f"word{i}" for i in range(14))

        self.assertTrue(format_remaining_candidates(candidates).endswith("..."))

    def test_choose_hybrid_guess_uses_normal_guess_below_threshold(self):
        candidates = ("cower", "mower", "power", "rower")
        probe_pool = ("champ", "cower", "mower", "power", "rower")

        guess = choose_hybrid_guess(
            candidates,
            previous_guesses=(),
            allowed_guesses=candidates,
            probe_pool=probe_pool,
            trap_threshold=4,
        )

        self.assertEqual(guess, "cower")

    def test_choose_hybrid_guess_uses_bucket_probe_above_threshold(self):
        candidates = ("cower", "mower", "power", "rower")
        probe_pool = ("champ", "cower", "mower", "power", "rower")

        guess = choose_hybrid_guess(
            candidates,
            previous_guesses=(),
            allowed_guesses=candidates,
            probe_pool=probe_pool,
            trap_threshold=1,
        )

        self.assertEqual(guess, choose_bucket_probe(candidates, (), probe_pool))

    def test_build_worst_game_rows_sorts_by_guess_count_then_answer(self):
        games = (
            GameResult(answer="slate", guesses=("slate",), solved=True),
            GameResult(answer="crane", guesses=("slate", "raise", "crane"), solved=True),
            GameResult(answer="raise", guesses=("slate", "raise"), solved=True),
            GameResult(answer="trace", guesses=("slate",), solved=False),
        )

        rows = build_worst_game_rows(games, 2)

        self.assertEqual(rows[0]["answer"], "crane")
        self.assertEqual(rows[0]["guess_count"], 3)
        self.assertIn("slate -> raise -> crane", rows[0]["path"])
        self.assertEqual(rows[1]["answer"], "raise")

    def test_format_candidate_trace_path_counts_candidates_before_each_guess(self):
        game = GameResult(
            answer="crane",
            guesses=("slate", "raise", "crane"),
            solved=True,
        )

        path = format_candidate_trace_path(game, ("raise", "crane", "slate"))

        self.assertTrue(path.startswith("slate(3)"))
        self.assertIn("crane(1)", path)

    def test_build_worst_game_rows_can_include_candidate_trace(self):
        games = (
            GameResult(answer="crane", guesses=("slate", "raise", "crane"), solved=True),
        )

        rows = build_worst_game_rows(games, 1, ("raise", "crane", "slate"))

        self.assertIn("slate(3)", rows[0]["path"])

    def test_build_worst_pattern_rows_groups_and_sorts_by_risk_then_average(self):
        games = (
            GameResult(answer="slate", guesses=("slate",), solved=True),
            GameResult(answer="crane", guesses=("slate", "raise", "crane"), solved=True),
            GameResult(
                answer="raise",
                guesses=("slate", "crane", "trace", "raise"),
                solved=True,
            ),
            GameResult(
                answer="trace",
                guesses=("slate", "crane", "raise", "trace"),
                solved=True,
            ),
        )

        rows = build_worst_pattern_rows(games)

        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("pattern", rows[0])
        self.assertIn("risk", rows[0])
        self.assertGreaterEqual(float(rows[0]["average"]), 1)

    def test_build_worst_pattern_rows_can_limit_rows(self):
        games = (
            GameResult(answer="slate", guesses=("slate",), solved=True),
            GameResult(answer="crane", guesses=("slate", "crane"), solved=True),
            GameResult(answer="raise", guesses=("slate", "raise"), solved=True),
        )

        rows = build_worst_pattern_rows(games, limit=1)

        self.assertEqual(len(rows), 1)

    def test_build_worst_prefix_rows_groups_long_games_by_prefix(self):
        games = (
            GameResult(
                answer="caper",
                guesses=("slate", "rocky", "fiend", "caper", "caper"),
                solved=True,
            ),
            GameResult(
                answer="cater",
                guesses=("slate", "rocky", "fiend", "caper", "cater"),
                solved=True,
            ),
            GameResult(
                answer="caver",
                guesses=("slate", "rocky", "fiend", "caper", "cater", "caver"),
                solved=True,
            ),
            GameResult(
                answer="crane",
                guesses=("slate", "crane", "crane"),
                solved=True,
            ),
            GameResult(
                answer="dodge",
                guesses=("slate", "rocky", "fiend", "caper", "cater", "dodge"),
                solved=False,
            ),
        )

        rows = build_worst_prefix_rows(games, limit=5)

        self.assertEqual(rows[0]["prefix"], "slate -> rocky")
        self.assertEqual(rows[0]["games"], 3)
        self.assertEqual(rows[0]["fives"], 2)
        self.assertEqual(rows[0]["sixes"], 1)
        self.assertEqual(rows[0]["risk"], 9)
        self.assertEqual(rows[0]["sample_answers"], "caper, cater, caver")

    def test_candidates_before_guess_reconstructs_remaining_answers(self):
        game = GameResult(
            answer="fewer",
            guesses=("slate", "rocky", "fiend", "femur", "fewer"),
            solved=True,
        )
        answers = ("femur", "fewer", "fever", "caper")

        candidates = candidates_before_guess(game, answers, guess_number=4)

        self.assertEqual(candidates, ("femur", "fever", "fewer"))

    def test_build_final_cluster_rows_groups_by_candidates_before_fourth_guess(self):
        games = (
            GameResult(
                answer="femur",
                guesses=("slate", "rocky", "fiend", "fewer", "femur"),
                solved=True,
            ),
            GameResult(
                answer="fewer",
                guesses=("slate", "rocky", "fiend", "femur", "fewer"),
                solved=True,
            ),
            GameResult(
                answer="caper",
                guesses=("slate", "crane", "caper"),
                solved=True,
            ),
        )
        answers = ("femur", "fewer", "fever", "caper")

        rows = build_final_cluster_rows(games, answers, limit=5)

        self.assertEqual(rows[0]["candidates"], "femur/fever/fewer")
        self.assertEqual(rows[0]["games"], 2)
        self.assertEqual(rows[0]["fives"], 2)
        self.assertEqual(rows[0]["risk"], 4)
        self.assertIn("femur", rows[0]["fourth_guess_used"])
        self.assertIn("fewer", rows[0]["sample_answers"])

    def test_print_final_clusters_outputs_table(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_final_clusters(
                (
                    {
                        "candidates": "femur/fewer/fever",
                        "games": 2,
                        "fives": 2,
                        "sixes": 0,
                        "risk": 4,
                        "fourth_guess_used": "femur",
                        "sample_answers": "femur, fewer",
                    },
                )
            )

        report = output.getvalue()
        self.assertIn("Final clusters:", report)
        self.assertIn("femur/fewer/fever", report)

    def test_print_worst_prefixes_outputs_table(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_worst_prefixes(
                (
                    {
                        "prefix": "slate -> rocky",
                        "games": 2,
                        "fives": 1,
                        "sixes": 1,
                        "risk": 7,
                        "sample_answers": "caper, cater",
                    },
                )
            )

        report = output.getvalue()
        self.assertIn("Worst prefixes:", report)
        self.assertIn("slate -> rocky", report)

    def test_build_tune_pattern_rows_ranks_second_guesses(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_tune_pattern_rows(
            "slate",
            "GGGGG",
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
            top=2,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["pattern"], "GGGGG")
        self.assertEqual(rows[0]["candidates"], 1)
        self.assertIn(rows[0]["second_guess"], answer_words)

    def test_build_tune_pattern_rows_can_include_branch_summary(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_tune_pattern_rows(
            "slate",
            "GGGGG",
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
            top=1,
            branch_summary=True,
        )

        self.assertIn("worst_branch_pattern", rows[0])
        self.assertIn("worst_branch_candidates", rows[0])
        self.assertIn("worst_branch_fives", rows[0])
        self.assertIn("worst_branch_risk", rows[0])

    def test_build_second_feedback_branch_summary_reports_worst_branch(self):
        candidates = ("raise", "crane")
        games = (
            GameResult(answer="raise", guesses=("slate", "crane", "raise"), solved=True),
            GameResult(answer="crane", guesses=("slate", "crane"), solved=True),
        )

        summary = build_second_feedback_branch_summary("crane", candidates, games)

        self.assertIn("worst_branch_pattern", summary)
        self.assertEqual(summary["worst_branch_candidates"], 1)

    def test_build_tune_pattern_result_with_second_returns_one_row_and_games(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows, games = build_tune_pattern_result(
            "slate",
            "GGGGG",
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
            second_guess="slate",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["second_guess"], "slate")
        self.assertEqual(len(games), 1)

    def test_build_tune_pattern_result_rejects_second_not_in_pool(self):
        with self.assertRaises(ValueError):
            build_tune_pattern_result(
                "slate",
                "GGGGG",
                "second-map-bucket",
                ("slate", "crane"),
                ("slate",),
                second_guess_pool=("slate",),
                second_guess="crane",
            )

    def test_build_tune_branch_rows_ranks_third_guesses(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_tune_branch_rows(
            "slate",
            "GGGGG",
            "slate",
            "GGGGG",
            "second-map-bucket",
            allowed_words,
            answer_words,
            third_guess_pool=answer_words,
            top=2,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["first_pattern"], "GGGGG")
        self.assertEqual(rows[0]["second_pattern"], "GGGGG")
        self.assertIn(rows[0]["third_guess"], answer_words)

    def test_build_tune_branch_result_with_third_returns_one_row_and_games(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows, games = build_tune_branch_result(
            "slate",
            "GGGGG",
            "slate",
            "GGGGG",
            "second-map-bucket",
            allowed_words,
            answer_words,
            third_guess_pool=answer_words,
            third_guess="slate",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["third_guess"], "slate")
        self.assertEqual(len(games), 1)

    def test_build_tune_branch_result_rejects_third_not_in_pool(self):
        with self.assertRaises(ValueError):
            build_tune_branch_result(
                "slate",
                "GGGGG",
                "slate",
                "GGGGG",
                "second-map-bucket",
                ("slate", "crane"),
                ("slate",),
                third_guess_pool=("slate",),
                third_guess="crane",
            )

    def test_tune_objective_rank_preserves_current_risk_default(self):
        row = {
            "next_guess": "bravo",
            "average": "3.00",
            "solved_4_or_less": 7,
            "fives": 2,
            "sixes": 0,
            "risk_score": 4,
        }

        self.assertEqual(tune_objective_rank(row, "next_guess"), (4, 3.0, -7, "bravo"))

    def test_tune_objective_rank_supports_safe_balanced(self):
        risky_fast = {
            "next_guess": "alpha",
            "average": "2.00",
            "solved_4_or_less": 8,
            "fives": 0,
            "sixes": 1,
            "risk_score": 1,
        }
        safer_slow = {
            "next_guess": "bravo",
            "average": "4.00",
            "solved_4_or_less": 4,
            "fives": 2,
            "sixes": 0,
            "risk_score": 4,
        }

        self.assertLess(
            tune_objective_rank(safer_slow, "next_guess", "safe-balanced"),
            tune_objective_rank(risky_fast, "next_guess", "safe-balanced"),
        )

    def test_tune_objective_rank_supports_average_and_fives(self):
        row = {
            "third_guess": "crane",
            "average": "2.50",
            "solved_4_or_less": 3,
            "fives": 1,
            "sixes": 0,
            "risk_score": 2,
        }

        self.assertEqual(
            tune_objective_rank(row, "third_guess", "average"),
            (2.5, 2, -3, "crane"),
        )
        self.assertEqual(
            tune_objective_rank(row, "third_guess", "fives"),
            (1, 0, 2, 2.5, "crane"),
        )

    def test_build_tune_path_rows_ranks_next_guesses(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_tune_path_rows(
            ("slate", "GGGGG"),
            "second-map-bucket",
            allowed_words,
            answer_words,
            next_guess_pool=answer_words,
            top=2,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["path"], "slate GGGGG")
        self.assertIn(rows[0]["next_guess"], answer_words)

    def test_build_tune_path_result_with_next_guess_returns_games(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows, games = build_tune_path_result(
            ("slate", "GGGGG"),
            "second-map-bucket",
            allowed_words,
            answer_words,
            next_guess_pool=answer_words,
            next_guess="slate",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["next_guess"], "slate")
        self.assertEqual(len(games), 1)

    def test_filter_candidates_for_path_applies_all_patterns(self):
        answers = ("raise", "slate", "crane")

        candidates = filter_candidates_for_path(answers, ("slate",), ("GGGGG",))

        self.assertEqual(candidates, ("slate",))

    def test_tune_path_requires_final_feedback_pattern(self):
        with self.assertRaises(ValueError):
            build_tune_path_rows(
                ("slate", "GGGGG", "slate"),
                "second-map-bucket",
                ("slate", "crane"),
                ("slate",),
                next_guess_pool=("slate",),
            )

    def test_format_tune_path_label_alternates_guesses_and_patterns(self):
        label = format_tune_path_label(
            ("slate", "rocky", "fiend"),
            ("....Y", "Y....", "..Y.."),
        )

        self.assertEqual(label, "slate ....Y rocky Y.... fiend ..Y..")

    def test_build_tune_pattern_rows_rejects_invalid_pattern(self):
        with self.assertRaises(ValueError):
            build_tune_pattern_rows(
                "slate",
                "bad",
                "second-map-bucket",
                ("slate",),
                ("slate",),
                second_guess_pool=("slate",),
            )

    def test_fast_top_opener_rows_match_compare_rows(self):
        words = ("raise", "crane", "slate")

        top_rows = build_top_opener_rows(3, words, words, words)
        compare_rows = {
            row["first_guess"]: row for row in build_comparison_rows(words, words, words)
        }

        for row in top_rows:
            self.assertEqual(row, compare_rows[row["first_guess"]])

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
                        "--rank-by",
                        "risk",
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

    def test_write_second_guess_csv_creates_parent_folder(self):
        rows = (
            {
                "pattern": "GGGGG",
                "candidates": 1,
                "best_average": "slate",
                "best_balanced": "slate",
                "sample_answers": "slate",
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results" / "second_guess_map_slate.csv"

            write_second_guess_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(SECOND_GUESS_COLUMNS), csv_text)
        self.assertIn("GGGGG,1,slate,slate,slate", csv_text)

    def test_main_second_guess_map_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "second_guess_map_slate.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--second-guess-map",
                        "slate",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("Pattern  Candidates  Best Avg  Best Balanced", report)
        self.assertIn("pattern,candidates,best_average,best_balanced", csv_text)

    def test_write_strategy_csv_creates_parent_folder(self):
        rows = (
            {
                "strategy": "baseline",
                "first_guess": "slate",
                "second_guess_pool": "",
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
            path = Path(temp_dir) / "results" / "strategy_slate.csv"

            write_strategy_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(STRATEGY_COLUMNS), csv_text)
        self.assertIn("baseline,slate,", csv_text)

    def test_main_strategy_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "strategy_slate.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--no-overrides",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("Strategy    First  Pool", report)
        self.assertIn("strategy,first_guess,second_guess_pool", csv_text)

    def test_main_compare_strategies_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "strategy_leaderboard.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--compare-strategies",
                        "--no-overrides",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("Strategy    First  Pool", report)
        self.assertEqual(len(csv_text.strip().splitlines()), 10)
        self.assertIn("strategy,first_guess,second_guess_pool", csv_text)

    def test_main_tune_pattern_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "tune_pattern.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-pattern",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("Pattern  Second  Candidates", report)
        self.assertIn("pattern,second_guess,candidates", csv_text)

    def test_main_tune_pattern_branch_summary_csv_writes_branch_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "tune_pattern_branch.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-pattern",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "1",
                        "--branch-summary",
                        "--csv",
                        str(csv_path),
                    ]
                )

            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn(",".join(TUNE_PATTERN_BRANCH_COLUMNS), csv_text)
        self.assertIn("worst_branch_pattern", csv_text)

    def test_main_tune_branch_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "tune_branch.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-branch",
                        "slate",
                        "GGGGG",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("FirstPat  Second  SecondPat", report)
        self.assertIn("first_pattern,second_guess,second_pattern,third_guess", csv_text)

    def test_main_tune_path_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "tune_path.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--tune-path",
                        "slate",
                        "GGGGG",
                        "slate",
                        "GGGGG",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--top",
                        "2",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("Path  Next  Candidates", report)
        self.assertIn("path,next_guess,candidates", csv_text)

    def test_main_strategy_with_csv_and_show_worst_writes_companion_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "strategy_slate.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--strategy",
                        "second-map",
                        "--first",
                        "slate",
                        "--second-guess-pool",
                        "answers",
                        "--show-worst",
                        "2",
                        "--no-overrides",
                        "--csv",
                        str(csv_path),
                    ]
                )

            worst_text = worst_csv_path(csv_path).read_text(encoding="utf-8")

        self.assertIn("answer,guess_count,path,feedback", worst_text)

    def test_write_worst_games_csv_creates_parent_folder(self):
        rows = (
            {
                "answer": "crane",
                "guess_count": 3,
                "path": "slate -> raise -> crane",
                "feedback": "....Y -> YY... -> GGGGG",
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results" / "strategy_worst.csv"

            write_worst_games_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(WORST_GAME_COLUMNS), csv_text)
        self.assertIn("crane,3", csv_text)

    def test_write_tune_pattern_csv_creates_parent_folder(self):
        rows = (
            {
                "pattern": "GGGGG",
                "second_guess": "slate",
                "candidates": 1,
                "average": "1.00",
                "solved_3_or_less": 1,
                "solved_4_or_less": 1,
                "fives": 0,
                "sixes": 0,
                "failed": 0,
                "risk_score": 0,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results" / "tune.csv"

            write_tune_pattern_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(TUNE_PATTERN_COLUMNS), csv_text)
        self.assertIn("GGGGG,slate,1", csv_text)

    def test_write_tune_branch_csv_creates_parent_folder(self):
        rows = (
            {
                "first_pattern": "GGGGG",
                "second_guess": "slate",
                "second_pattern": "GGGGG",
                "third_guess": "slate",
                "candidates": 1,
                "average": "1.00",
                "solved_3_or_less": 1,
                "solved_4_or_less": 1,
                "fives": 0,
                "sixes": 0,
                "failed": 0,
                "risk_score": 0,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results" / "branch.csv"

            write_tune_branch_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(TUNE_BRANCH_COLUMNS), csv_text)
        self.assertIn("GGGGG,slate,GGGGG,slate,1", csv_text)

    def test_write_tune_path_csv_creates_parent_folder(self):
        rows = (
            {
                "path": "slate GGGGG",
                "next_guess": "slate",
                "candidates": 1,
                "average": "1.00",
                "solved_4_or_less": 1,
                "fives": 0,
                "sixes": 0,
                "failed": 0,
                "risk_score": 0,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results" / "path.csv"

            write_tune_path_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(TUNE_PATH_COLUMNS), csv_text)
        self.assertIn("slate GGGGG,slate,1", csv_text)

    def test_write_tune_path_csv_uses_branch_columns_when_present(self):
        rows = (
            {
                "path": "slate GGGGG",
                "next_guess": "slate",
                "candidates": 1,
                "average": "1.00",
                "solved_4_or_less": 1,
                "fives": 0,
                "sixes": 0,
                "failed": 0,
                "risk_score": 0,
                "worst_branch_pattern": "GGGGG",
                "worst_branch_candidates": 1,
                "worst_branch_fives": 0,
                "worst_branch_risk": 0,
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "results" / "path_branch.csv"

            write_tune_path_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(TUNE_PATH_BRANCH_COLUMNS), csv_text)
        self.assertIn("worst_branch_pattern", csv_text)

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

    def test_limit_openers_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--top-openers", "2", "--limit-openers", "0"])

    def test_show_worst_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "baseline", "--first", "slate", "--show-worst", "0"])

    def test_show_candidate_trace_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--show-candidate-trace", "--show-worst", "1"])

    def test_show_candidate_trace_requires_show_worst(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "baseline", "--first", "slate", "--show-candidate-trace"])

    def test_worst_patterns_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--worst-patterns"])

    def test_worst_patterns_requires_positive_limit_when_provided(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "baseline", "--first", "slate", "--worst-patterns", "0"])

    def test_worst_prefixes_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--worst-prefixes", "5"])

    def test_worst_prefixes_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "baseline", "--first", "slate", "--worst-prefixes", "0"])

    def test_show_final_clusters_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--show-final-clusters", "5"])

    def test_show_final_clusters_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "baseline", "--first", "slate", "--show-final-clusters", "0"])

    def test_show_small_order_changes_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--show-small-order-changes"])

    def test_show_final_cluster_override_changes_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--show-final-cluster-override-changes"])

    def test_trap_threshold_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "second-map-hybrid", "--trap-threshold", "0"])

    def test_endgame_threshold_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "second-map-expected", "--endgame-threshold", "0"])

    def test_max_expected_guesses_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "second-map-expected", "--max-expected-guesses", "0"])

    def test_max_expected_states_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "second-map-expected", "--max-expected-states", "0"])

    def test_expected_depth_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "second-map-expected", "--expected-depth", "0"])

    def test_top_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--tune-pattern", "slate", "GGGGG", "--top", "0"])

    def test_show_pattern_worst_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--tune-pattern", "slate", "GGGGG", "--show-pattern-worst", "0"])


if __name__ == "__main__":
    unittest.main()
