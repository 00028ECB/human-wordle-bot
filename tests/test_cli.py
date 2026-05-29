import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

from src.wordle_lab.__main__ import (
    BUILT_SECOND_MAP_COLUMNS,
    CSV_COLUMNS,
    SECOND_GUESS_COLUMNS,
    STRATEGY_COLUMNS,
    OPENER_STRATEGY_COLUMNS,
    TUNE_PATTERN_BRANCH_COLUMNS,
    TUNE_BRANCH_COLUMNS,
    TUNE_PATTERN_COLUMNS,
    TUNE_PATTERN_WEIGHTED_COLUMNS,
    TUNE_PATH_COLUMNS,
    TUNE_PATH_BRANCH_COLUMNS,
    WORST_GAME_COLUMNS,
    apply_second_guess_overrides,
    answer_likelihood_score,
    apply_prior_policy_to_candidates,
    apply_prior_policy_to_test_answers,
    build_comparison_rows,
    build_comparison_row,
    build_prior_dated_stats,
    build_prior_answer_weights,
    build_prior_weight_stats,
    build_recommendation,
    build_weighted_score_row,
    build_weighted_worst_pattern_rows,
    build_parser,
    build_full_second_map_rows,
    build_second_map_row_for_pattern,
    build_second_guess_map_rows,
    build_opener_strategy_comparison_rows,
    build_strategy_comparison_rows,
    build_strategy_result,
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
    choose_bucket_probe_with_prior_diagnostics,
    choose_bucket_probe,
    choose_answer_candidate,
    choose_hybrid_guess,
    choose_prior_weighted_endgame_candidate,
    choose_small_candidate_by_likelihood,
    choose_trap_probe,
    clean_prior_source,
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
    load_dated_prior_answers,
    load_built_second_map,
    open_incremental_built_second_map_csv,
    main,
    play_baseline_game,
    play_second_map_game,
    print_built_second_map,
    print_clean_prior_source_report,
    print_final_clusters,
    print_final_cluster_override_changes,
    print_opener_strategy_report,
    print_prior_stats_report,
    print_prior_dated_stats_report,
    print_prior_weight_stats_report,
    print_prior_weighting_changes,
    print_recommendation,
    print_weighted_score_report,
    print_weighted_worst_patterns,
    print_small_candidate_events,
    print_small_order_changes,
    record_small_candidate_event,
    tune_pattern_objective_rank,
    print_worst_prefixes,
    prior_answer_weight_for_age,
    prior_safe_answer_rank,
    prior_weight_for_word,
    resolve_as_of_date,
    read_completed_built_second_map_patterns,
    run_build_second_map,
    second_guess_candidate_rank,
    select_second_map_patterns,
    select_second_guess_candidates,
    tune_objective_rank,
    tuned_overrides_enabled,
    worst_csv_path,
    write_worst_games_csv,
    write_second_guess_csv,
    write_comparison_csv,
    write_built_second_map_csv,
    write_strategy_csv,
    write_opener_strategy_csv,
    write_tune_branch_csv,
    write_tune_path_csv,
    write_tune_pattern_csv,
)
from src.wordle_lab.scoring import score_guess
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

    def test_parser_accepts_compare_openers_with_strategy(self):
        args = build_parser().parse_args(
            [
                "--compare-openers-with-strategy",
                "slate",
                "crane",
                "raise",
                "--strategy",
                "second-map-bucket",
                "--second-guess-pool",
                "answers",
            ]
        )

        self.assertEqual(args.compare_openers_with_strategy, ["slate", "crane", "raise"])
        self.assertEqual(args.strategy, "second-map-bucket")
        self.assertEqual(args.second_guess_pool, "answers")

    def test_parser_accepts_top_openers_limit(self):
        args = build_parser().parse_args(["--top-openers", "25"])

        self.assertEqual(args.top_openers, 25)

    def test_parser_accepts_stats_mode(self):
        args = build_parser().parse_args(["--stats"])

        self.assertTrue(args.stats)

    def test_parser_accepts_prior_stats_mode(self):
        args = build_parser().parse_args(["--prior-stats"])

        self.assertTrue(args.prior_stats)

    def test_parser_accepts_prior_dated_stats_mode(self):
        args = build_parser().parse_args(["--prior-dated-stats"])

        self.assertTrue(args.prior_dated_stats)

    def test_parser_accepts_prior_answer_options(self):
        args = build_parser().parse_args(
            [
                "--prior-answers",
                "data/prior_answers.txt",
                "--prior-policy",
                "exclude",
                "--prior-answers-dated",
                "data/prior_answers_dated.csv",
            ]
        )

        self.assertEqual(args.prior_answers, "data/prior_answers.txt")
        self.assertEqual(args.prior_policy, "exclude")
        self.assertEqual(args.prior_answers_dated, "data/prior_answers_dated.csv")

    def test_parser_accepts_prior_weighting_options(self):
        args = build_parser().parse_args(
            [
                "--strategy",
                "baseline",
                "--prior-policy",
                "downweight",
                "--as-of-date",
                "2025-09-01",
                "--show-prior-weighting-changes",
                "--prior-weight-stats",
            ]
        )

        self.assertEqual(args.prior_policy, "downweight")
        self.assertEqual(args.as_of_date, "2025-09-01")
        self.assertTrue(args.show_prior_weighting_changes)
        self.assertTrue(args.prior_weight_stats)

    def test_parser_accepts_show_weighted_score(self):
        args = build_parser().parse_args(["--strategy", "baseline", "--show-weighted-score"])

        self.assertTrue(args.show_weighted_score)

    def test_parser_accepts_show_small_candidate_events(self):
        args = build_parser().parse_args(
            ["--strategy", "baseline", "--show-small-candidate-events", "50"]
        )

        self.assertEqual(args.show_small_candidate_events, 50)

    def test_parser_accepts_clean_prior_source(self):
        args = build_parser().parse_args(
            ["--clean-prior-source", "raw.txt", "data/prior_answers.txt"]
        )

        self.assertEqual(args.clean_prior_source, ["raw.txt", "data/prior_answers.txt"])

    def test_parser_accepts_second_guess_map(self):
        args = build_parser().parse_args(["--second-guess-map", "slate"])

        self.assertEqual(args.second_guess_map, "slate")

    def test_parser_accepts_build_second_map(self):
        args = build_parser().parse_args(
            [
                "--build-second-map",
                "slate",
                "--strategy",
                "second-map-bucket",
                "--second-guess-pool",
                "answers",
                "--tune-pattern-objective",
                "safe-balanced",
            ]
        )

        self.assertEqual(args.build_second_map, "slate")
        self.assertEqual(args.strategy, "second-map-bucket")
        self.assertEqual(args.tune_pattern_objective, "safe-balanced")

    def test_parser_accepts_resumable_build_second_map_options(self):
        args = build_parser().parse_args(
            [
                "--build-second-map",
                "slate",
                "--force",
                "--only-pattern",
                "....Y",
                "--only-pattern",
                ".....",
                "--max-patterns",
                "2",
                "--only-worst-patterns",
                "3",
                "--min-candidates",
                "4",
                "--max-second-guesses",
                "50",
                "--second-guess-candidates",
                "top",
            ]
        )

        self.assertTrue(args.force)
        self.assertEqual(args.only_pattern, ["....Y", "....."])
        self.assertEqual(args.max_patterns, 2)
        self.assertEqual(args.only_worst_patterns, 3)
        self.assertEqual(args.min_candidates, 4)
        self.assertEqual(args.max_second_guesses, 50)
        self.assertEqual(args.second_guess_candidates, "top")

    def test_parser_accepts_use_built_second_map(self):
        args = build_parser().parse_args(
            [
                "--strategy",
                "second-map-bucket",
                "--first",
                "slate",
                "--use-built-second-map",
                "results/map.csv",
            ]
        )

        self.assertEqual(args.use_built_second_map, "results/map.csv")

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

    def test_parser_accepts_recommend_state(self):
        args = build_parser().parse_args(
            ["--recommend", "--state", "slate", "....Y", "drown", ".Y..."]
        )

        self.assertTrue(args.recommend)
        self.assertEqual(args.state, ["slate", "....Y", "drown", ".Y..."])

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

    def test_parser_accepts_tune_pattern_objective(self):
        args = build_parser().parse_args(
            [
                "--tune-pattern",
                "slate",
                "....Y",
                "--tune-pattern-objective",
                "branch-safe",
            ]
        )

        self.assertEqual(args.tune_pattern_objective, "branch-safe")

    def test_parser_accepts_tune_pattern_weighted_risk_objective(self):
        args = build_parser().parse_args(
            [
                "--tune-pattern",
                "slate",
                ".....",
                "--tune-pattern-objective",
                "weighted-risk",
            ]
        )

        self.assertEqual(args.tune_pattern_objective, "weighted-risk")

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

    def test_parser_accepts_weighted_worst_patterns_limit(self):
        args = build_parser().parse_args(
            [
                "--strategy",
                "second-map-bucket",
                "--first",
                "slate",
                "--weighted-worst-patterns",
                "25",
            ]
        )

        self.assertEqual(args.weighted_worst_patterns, 25)

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

    def test_main_reports_prior_stats_for_custom_word_lists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_path = temp_path / "prior.txt"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            prior_path.write_text("slate\ncigar\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--prior-answers",
                        str(prior_path),
                        "--prior-stats",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Answers: 3", report)
        self.assertIn("Prior answers: 2", report)
        self.assertIn("Prior answers found in answer list: 1", report)
        self.assertIn("Remaining non-prior answers: 2", report)

    def test_load_dated_prior_answers_validates_csv_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prior_dated.csv"
            path.write_text(
                "date,word\n2025-08-31,petal\n2021-06-19,cigar\n",
                encoding="utf-8",
            )

            rows = load_dated_prior_answers(path)

        self.assertEqual(rows[0][0].isoformat(), "2025-08-31")
        self.assertEqual(rows[0][1], "petal")
        self.assertEqual(rows[1][1], "cigar")

    def test_load_dated_prior_answers_rejects_invalid_word(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prior_dated.csv"
            path.write_text("date,word\n2025-08-31,PETAL\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_dated_prior_answers(path)

    def test_load_dated_prior_answers_rejects_invalid_date(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prior_dated.csv"
            path.write_text("date,word\nnot-date,petal\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_dated_prior_answers(path)

    def test_build_prior_dated_stats_counts_repeats_and_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prior_dated.csv"
            path.write_text(
                "date,word\n"
                "2025-08-31,petal\n"
                "2021-06-19,cigar\n"
                "2022-01-01,cigar\n",
                encoding="utf-8",
            )
            rows = load_dated_prior_answers(path)

        stats = build_prior_dated_stats(rows)

        self.assertEqual(stats["dated_prior_rows"], 3)
        self.assertEqual(stats["valid_dated_prior_words"], 3)
        self.assertEqual(stats["unique_prior_words"], 2)
        self.assertEqual(stats["duplicates_repeats"], 1)
        self.assertEqual(stats["oldest_date"], "2021-06-19")
        self.assertEqual(stats["newest_date"], "2025-08-31")
        self.assertEqual(stats["words_repeated_more_than_once"], (("cigar", 2),))

    def test_resolve_as_of_date_uses_latest_dated_prior_by_default(self):
        dated_rows = ((date(2025, 8, 31), "petal"), (date(2021, 6, 19), "cigar"))

        as_of = resolve_as_of_date(None, dated_rows)

        self.assertEqual(as_of, date(2025, 8, 31))

    def test_resolve_as_of_date_accepts_explicit_date(self):
        as_of = resolve_as_of_date("2025-09-01", ())

        self.assertEqual(as_of, date(2025, 9, 1))

    def test_prior_answer_weight_for_age_uses_schedule(self):
        self.assertEqual(prior_answer_weight_for_age(90), 0.05)
        self.assertEqual(prior_answer_weight_for_age(365), 0.15)
        self.assertEqual(prior_answer_weight_for_age(730), 0.35)
        self.assertEqual(prior_answer_weight_for_age(731), 0.60)

    def test_build_prior_answer_weights_uses_most_recent_date(self):
        dated_rows = (
            (date(2024, 1, 1), "cigar"),
            (date(2025, 8, 1), "cigar"),
            (date(2023, 1, 1), "petal"),
        )

        weights = build_prior_answer_weights(
            dated_rows,
            date(2025, 9, 1),
            fallback_prior_answers=("raise",),
        )

        self.assertEqual(weights["cigar"], 0.05)
        self.assertEqual(weights["petal"], 0.60)
        self.assertEqual(weights["raise"], 0.60)
        self.assertEqual(prior_weight_for_word("slate", weights), 1.0)

    def test_build_prior_weight_stats_counts_answer_buckets(self):
        weights = {"cigar": 0.05, "petal": 0.60}

        rows = build_prior_weight_stats(("cigar", "petal", "slate"), weights)
        counts = {row["weight"]: row["count"] for row in rows}

        self.assertEqual(counts["1.00"], 1)
        self.assertEqual(counts["0.05"], 1)
        self.assertEqual(counts["0.60"], 1)

    def test_print_prior_weight_stats_report_outputs_table(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_prior_weight_stats_report(
                ("cigar", "petal", "slate"),
                {"cigar": 0.05, "petal": 0.60},
            )

        report = output.getvalue()
        self.assertIn("Prior weight stats:", report)
        self.assertIn("0.05", report)
        self.assertIn("used within last 90 days", report)

    def test_build_weighted_score_row_uses_prior_weights(self):
        games = (
            GameResult(answer="cigar", guesses=("slate", "cigar"), solved=True),
            GameResult(answer="petal", guesses=("slate", "crane", "petal"), solved=True),
            GameResult(answer="raise", guesses=("slate", "crane", "raise"), solved=False),
        )

        row = build_weighted_score_row(
            games,
            {"cigar": 0.05, "petal": 0.60},
        )

        self.assertAlmostEqual(row["total_weight"], 1.65)
        self.assertAlmostEqual(row["weighted_average"], (0.05 * 2 + 0.60 * 3 + 1.0 * 3) / 1.65)
        self.assertAlmostEqual(row["weighted_solved_3_or_less"], 0.65)
        self.assertAlmostEqual(row["weighted_solved_4_or_less"], 0.65)
        self.assertAlmostEqual(row["weighted_failed"], 1.0)

    def test_print_weighted_score_report_outputs_summary(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_weighted_score_report(
                {
                    "total_weight": 1.65,
                    "weighted_average": 2.97,
                    "weighted_solved_3_or_less": 0.65,
                    "weighted_solved_4_or_less": 0.65,
                    "weighted_fives": 0.0,
                    "weighted_sixes": 0.0,
                    "weighted_failed": 1.0,
                }
            )

        report = output.getvalue()
        self.assertIn("Weighted human-mode score:", report)
        self.assertIn("Total weight: 1.65", report)
        self.assertIn("Weighted average guesses: 2.97", report)

    def test_print_prior_dated_stats_report_outputs_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prior_dated.csv"
            path.write_text(
                "date,word\n2025-08-31,petal\n2021-06-19,cigar\n2022-01-01,cigar\n",
                encoding="utf-8",
            )
            rows = load_dated_prior_answers(path)
            output = io.StringIO()

            with redirect_stdout(output):
                print_prior_dated_stats_report(rows)

        report = output.getvalue()
        self.assertIn("dated prior rows: 3", report)
        self.assertIn("valid dated prior words: 3", report)
        self.assertIn("unique prior words: 2", report)
        self.assertIn("duplicates/repeats: 1", report)
        self.assertIn("oldest date: 2021-06-19", report)
        self.assertIn("newest date: 2025-08-31", report)
        self.assertIn("words repeated more than once: cigar (2)", report)

    def test_main_reports_prior_dated_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prior_dated_path = Path(temp_dir) / "prior_dated.csv"
            prior_dated_path.write_text(
                "date,word\n2025-08-31,petal\n2021-06-19,cigar\n",
                encoding="utf-8",
            )
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--prior-dated-stats",
                    ]
                )

        report = output.getvalue()
        self.assertIn("dated prior rows: 2", report)
        self.assertIn("words repeated more than once: none", report)

    def test_main_reports_prior_weight_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("cigar\npetal\nslate\n", encoding="utf-8")
            allowed_path.write_text("cigar\npetal\nslate\n", encoding="utf-8")
            prior_dated_path.write_text(
                "date,word\n2025-08-31,petal\n2025-06-01,cigar\n",
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
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--as-of-date",
                        "2025-09-01",
                        "--prior-weight-stats",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Prior weight stats:", report)
        self.assertIn("0.05", report)
        self.assertIn("0.15", report)

    def test_main_strategy_reports_small_candidate_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("raise\ncrane\n", encoding="utf-8")
            allowed_path.write_text("zzzzz\nraise\ncrane\n", encoding="utf-8")
            prior_dated_path.write_text("date,word\n2025-08-31,raise\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--as-of-date",
                        "2025-09-01",
                        "--prior-policy",
                        "downweight",
                        "--strategy",
                        "baseline",
                        "--first",
                        "zzzzz",
                        "--show-small-candidate-events",
                        "5",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Small candidate events:", report)
        self.assertIn("raise:0.05", report)

    def test_main_strategy_reports_small_candidate_events_with_prior_ignore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_path = temp_path / "prior.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("raise\ncrane\n", encoding="utf-8")
            allowed_path.write_text("zzzzz\nraise\ncrane\n", encoding="utf-8")
            prior_path.write_text("", encoding="utf-8")
            prior_dated_path.write_text("date,word\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--prior-answers",
                        str(prior_path),
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--strategy",
                        "baseline",
                        "--first",
                        "zzzzz",
                        "--show-small-candidate-events",
                        "5",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Small candidate events:", report)
        self.assertIn("raise, crane", report)
        self.assertIn("raise:1.00", report)

    def test_main_prior_weighting_changes_reports_actual_bucket_decisions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("raise\nslate\n", encoding="utf-8")
            allowed_path.write_text("couch\nraise\nslate\n", encoding="utf-8")
            prior_dated_path.write_text("date,word\n2025-08-01,raise\n", encoding="utf-8")
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
                        "couch",
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--prior-policy",
                        "downweight",
                        "--as-of-date",
                        "2025-09-01",
                        "--show-prior-weighting-changes",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Prior-weighting changed decisions:", report)
        self.assertNotIn("Prior-weighting changed decisions: 0", report)
        self.assertIn("normal", report)
        self.assertIn("weighted", report)
        self.assertIn("raise:0.05", report)

    def test_main_rejects_invalid_prior_answer_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_path = temp_path / "prior.txt"
            answers_path.write_text("raise\nslate\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\n", encoding="utf-8")
            prior_path.write_text("SLATE\n", encoding="utf-8")
            error_output = io.StringIO()

            with redirect_stderr(error_output), self.assertRaises(SystemExit):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--prior-answers",
                        str(prior_path),
                        "--prior-stats",
                    ]
                )

        self.assertIn("Invalid word", error_output.getvalue())

    def test_clean_prior_source_writes_answer_words_in_first_seen_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / "raw.txt"
            output_path = temp_path / "prior.txt"
            source_path.write_text(
                "crane CRANE slate crane xyzzz raise raise sixletters\n",
                encoding="utf-8",
            )

            stats = clean_prior_source(
                source_path,
                output_path,
                possible_answers=("raise", "slate", "crane"),
            )
            cleaned_text = output_path.read_text(encoding="utf-8")

        self.assertEqual(cleaned_text, "crane\nslate\nraise\n")
        self.assertEqual(stats["source_words_found"], 6)
        self.assertEqual(stats["valid_wordle_answers_written"], 3)
        self.assertEqual(stats["duplicates_skipped"], 2)
        self.assertEqual(stats["non_answer_words_skipped"], 1)

    def test_print_clean_prior_source_report_outputs_counts(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_clean_prior_source_report(
                {
                    "source_words_found": 4,
                    "valid_wordle_answers_written": 2,
                    "duplicates_skipped": 1,
                    "non_answer_words_skipped": 1,
                }
            )

        report = output.getvalue()
        self.assertIn("source words found: 4", report)
        self.assertIn("valid Wordle answers written: 2", report)
        self.assertIn("duplicates skipped: 1", report)
        self.assertIn("non-answer words skipped: 1", report)

    def test_main_clean_prior_source_uses_configured_answers_without_allowed_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            source_path = temp_path / "raw.txt"
            output_path = temp_path / "data" / "prior_answers.txt"
            answers_path.write_text("crane\nslate\n", encoding="utf-8")
            source_path.write_text("crane slate raise\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--clean-prior-source",
                        str(source_path),
                        str(output_path),
                    ]
                )

            cleaned_text = output_path.read_text(encoding="utf-8")

        self.assertEqual(cleaned_text, "crane\nslate\n")
        self.assertIn("source words found: 3", output.getvalue())
        self.assertIn("valid Wordle answers written: 2", output.getvalue())

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

    def test_main_reports_compare_openers_with_strategy_for_custom_word_lists(self):
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
                        "--compare-openers-with-strategy",
                        "slate",
                        "crane",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("First   Strategy", report)
        self.assertIn("slate", report)
        self.assertIn("crane", report)
        self.assertIn("second-map-bucket", report)

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
        self.assertIn("evaluated", report)

    def test_main_tune_pattern_supports_second_guess_limits_and_incremental_csv(self):
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
                        "--second-guess-candidates",
                        "top",
                        "--max-second-guesses",
                        "1",
                        "--top",
                        "1",
                        "--csv",
                        str(csv_path),
                    ]
                )

            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("evaluated 1/1 second guesses", output.getvalue())
        self.assertEqual(len(csv_text.strip().splitlines()), 2)
        self.assertIn("pattern,second_guess,candidates", csv_text)

    def test_main_recommend_prints_pure_recommendation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("cider\ndiner\npoker\nrocky\ndrown\n", encoding="utf-8")
            allowed_path.write_text("slate\ncider\ndiner\npoker\nrocky\ndrown\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--recommend",
                        "--strategy",
                        "second-map-bucket",
                        "--state",
                        "slate",
                        "....Y",
                        "--second-guess-pool",
                        "answers",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Recommendation:", report)
        self.assertIn("Remaining candidates: 3", report)
        self.assertIn("Recommended next guess: rocky", report)
        self.assertIn("Explanation: Used Pure Mode override for slate ....Y.", report)
        self.assertNotIn("Prior weights:", report)

    def test_main_recommend_prints_human_weights(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("cider\ndiner\npoker\nrocky\ndrown\n", encoding="utf-8")
            allowed_path.write_text("slate\ncider\ndiner\npoker\nrocky\ndrown\n", encoding="utf-8")
            prior_dated_path.write_text("date,word\n2025-08-01,cider\n", encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--recommend",
                        "--strategy",
                        "second-map-bucket",
                        "--state",
                        "slate",
                        "....Y",
                        "--second-guess-pool",
                        "answers",
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--prior-policy",
                        "downweight",
                        "--as-of-date",
                        "2025-09-01",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Recommended next guess: drown", report)
        self.assertIn("Explanation: Used Human Mode override for slate ....Y.", report)
        self.assertIn("Prior weights:", report)
        self.assertIn("cider:0.05", report)

    def test_main_reports_tune_pattern_weighted_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            prior_dated_path.write_text("date,word\n2025-08-01,slate\n", encoding="utf-8")
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
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--prior-policy",
                        "downweight",
                        "--as-of-date",
                        "2025-09-01",
                        "--show-weighted-score",
                        "--top",
                        "1",
                    ]
                )

        report = output.getvalue()
        self.assertIn("WAvg", report)
        self.assertIn("WRisk", report)

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

    def test_main_strategy_weighted_worst_patterns_prints_pattern_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            prior_dated_path.write_text("date,word\n2025-08-01,raise\n", encoding="utf-8")
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
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--prior-policy",
                        "downweight",
                        "--as-of-date",
                        "2025-09-01",
                        "--weighted-worst-patterns",
                        "2",
                        "--no-overrides",
                    ]
                )

        report = output.getvalue()
        self.assertIn("Weighted worst patterns:", report)
        self.assertIn("pattern  games  total_weight", report)

    def test_main_strategy_worst_patterns_allows_non_slate_first_guess(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            answers_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
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
                        "trace",
                        "--second-guess-pool",
                        "answers",
                        "--worst-patterns",
                        "2",
                    ]
                )

        report = output.getvalue()
        self.assertIn("second-map-bucket", report)
        self.assertIn("trace", report)
        self.assertIn("Worst patterns:", report)

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

    def test_apply_second_guess_overrides_uses_human_mode_override_with_weights(self):
        second_guess_by_pattern = {
            "....Y": "heron",
            "..YY.": "tacit",
            "..Y.Y": "abbey",
        }

        apply_second_guess_overrides(
            "slate",
            "answers",
            ("rocky", "drown", "pouch", "hound", "march", "began"),
            second_guess_by_pattern,
            prior_policy="downweight",
            prior_answer_weights={"cigar": 0.05},
        )

        self.assertEqual(second_guess_by_pattern["....Y"], "drown")
        self.assertEqual(second_guess_by_pattern["..YY."], "hound")
        self.assertEqual(second_guess_by_pattern["..Y.Y"], "began")

    def test_apply_second_guess_overrides_keeps_pure_override_without_weights(self):
        second_guess_by_pattern = {
            "....Y": "heron",
            "..YY.": "tacit",
            "..Y.Y": "abbey",
        }

        apply_second_guess_overrides(
            "slate",
            "answers",
            ("rocky", "drown", "pouch", "hound", "march", "began"),
            second_guess_by_pattern,
            prior_policy="downweight",
            prior_answer_weights={},
        )

        self.assertEqual(second_guess_by_pattern["....Y"], "rocky")
        self.assertEqual(second_guess_by_pattern["..YY."], "pouch")
        self.assertEqual(second_guess_by_pattern["..Y.Y"], "march")

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

    def test_build_strategy_result_keeps_pure_slate_override(self):
        words = (
            "slate",
            "cider",
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
            "drown",
        )

        _row, games = build_strategy_result(
            "second-map-bucket",
            "slate",
            words,
            words,
            second_guess_pool_name="answers",
            prior_policy="ignore",
        )

        cider_game = next(game for game in games if game.answer == "cider")
        self.assertEqual(cider_game.guesses[1], "rocky")

    def test_build_strategy_result_uses_human_mode_slate_override(self):
        words = (
            "slate",
            "cider",
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
            "drown",
        )

        _row, games = build_strategy_result(
            "second-map-bucket",
            "slate",
            words,
            words,
            second_guess_pool_name="answers",
            prior_policy="downweight",
            prior_answer_weights={"cider": 0.05},
        )

        cider_game = next(game for game in games if game.answer == "cider")
        self.assertEqual(cider_game.guesses[1], "drown")

    def test_build_strategy_result_no_overrides_disables_human_mode_override(self):
        words = ("slate", "cider", "rocky", "drown")

        _row, games = build_strategy_result(
            "second-map-bucket",
            "slate",
            words,
            words,
            second_guess_pool_name="answers",
            use_overrides=False,
            prior_policy="downweight",
            prior_answer_weights={"cider": 0.05},
        )

        cider_game = next(game for game in games if game.answer == "cider")
        self.assertNotEqual(cider_game.guesses[1], "drown")

    def test_build_strategy_result_does_not_apply_slate_overrides_to_other_openers(self):
        allowed_words = ("trace", "frond", "pound", "cough", "pouch")
        answer_words = ("cough", "pouch")

        _row, games = build_strategy_result(
            "second-map-bucket",
            "trace",
            allowed_words,
            answer_words,
            second_guess_pool_name="answers",
        )

        self.assertNotEqual(games[1].guesses[:3], ("trace", "frond", "pouch"))

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

    def test_build_opener_strategy_comparison_rows_returns_requested_openers(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_opener_strategy_comparison_rows(
            ("slate", "crane"),
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool_name="answers",
            use_overrides=False,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["first"], "slate")
        self.assertEqual(rows[0]["strategy"], "second-map-bucket")
        self.assertEqual(rows[0]["pool"], "answers")
        self.assertEqual(rows[1]["first"], "crane")

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

    def test_apply_prior_policy_excludes_prior_answers_when_possible(self):
        candidates = ("raise", "slate", "crane")

        filtered = apply_prior_policy_to_candidates(
            candidates,
            prior_answers=("raise", "slate"),
            prior_policy="exclude",
        )

        self.assertEqual(filtered, ("crane",))

    def test_apply_prior_policy_keeps_candidates_when_exclude_would_empty(self):
        candidates = ("raise", "slate")

        filtered = apply_prior_policy_to_candidates(
            candidates,
            prior_answers=("raise", "slate"),
            prior_policy="exclude",
        )

        self.assertEqual(filtered, candidates)

    def test_apply_prior_policy_excludes_prior_answers_from_test_set(self):
        answers = ("raise", "slate", "crane")

        tested_answers = apply_prior_policy_to_test_answers(
            answers,
            prior_answers=("raise",),
            prior_policy="exclude",
        )

        self.assertEqual(tested_answers, ("slate", "crane"))

    def test_choose_answer_candidate_downweight_requires_dated_weights(self):
        candidates = ("raise", "slate", "crane")

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            prior_answers=("raise", "slate"),
            prior_policy="downweight",
        )

        self.assertEqual(guess, "raise")

    def test_choose_answer_candidate_downweights_by_dated_prior_weight(self):
        candidates = ("raise", "slate", "crane")
        changes = []

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            answer="crane",
            guess_number=3,
            prior_policy="downweight",
            prior_answer_weights={"raise": 0.05, "slate": 0.15},
            prior_weighting_changes=changes,
        )

        self.assertEqual(guess, "crane")
        self.assertEqual(changes[0]["normal_guess"], "raise")
        self.assertEqual(changes[0]["weighted_guess"], "crane")
        self.assertEqual(changes[0]["normal_weight"], 0.05)
        self.assertEqual(changes[0]["weighted_weight"], 1.0)

    def test_choose_answer_candidate_prior_weighting_only_small_clusters(self):
        candidates = ("raise", "slate", "crane", "trace", "irate", "stare")

        guess = choose_answer_candidate(
            candidates,
            (),
            candidates,
            "off",
            prior_policy="downweight",
            prior_answer_weights={"raise": 0.05},
        )

        self.assertEqual(guess, "raise")

    def test_choose_prior_weighted_endgame_candidate_keeps_bucket_safety_primary(self):
        candidates = ("raise", "slate", "crane")

        choice = choose_prior_weighted_endgame_candidate(
            "raise",
            candidates,
            candidates,
            {"raise": 0.05},
        )

        self.assertEqual(prior_safe_answer_rank(choice, candidates), prior_safe_answer_rank("raise", candidates))

    def test_bucket_probe_rank_uses_prior_weight_as_tie_breaker(self):
        candidates = ("raise", "slate")

        raise_rank = bucket_probe_rank("raise", candidates, prior_answer_weights={"raise": 0.05})
        slate_rank = bucket_probe_rank("slate", candidates, prior_answer_weights={"raise": 0.05})

        self.assertLess(slate_rank, raise_rank)

    def test_bucket_probe_records_prior_weighting_change(self):
        changes = []

        guess = choose_bucket_probe_with_prior_diagnostics(
            ("raise", "slate"),
            previous_guesses=(),
            probe_pool=("raise", "slate"),
            prior_policy="downweight",
            prior_answer_weights={"raise": 0.05},
            prior_weighting_changes=changes,
            answer="slate",
            guess_number=4,
        )

        self.assertEqual(guess, "slate")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["normal_guess"], "raise")
        self.assertEqual(changes[0]["weighted_guess"], "slate")
        self.assertEqual(changes[0]["prior_weights"], (("raise", 0.05), ("slate", 1.0)))

    def test_print_prior_weighting_changes_outputs_examples(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_prior_weighting_changes(
                (
                    {
                        "answer": "crane",
                        "guess_number": 3,
                        "normal_guess": "raise",
                        "weighted_guess": "crane",
                        "remaining_candidates": ("raise", "crane"),
                        "normal_weight": 0.05,
                        "weighted_weight": 1.0,
                        "normal_max_bucket": 1,
                        "weighted_max_bucket": 1,
                        "prior_weights": (("raise", 0.05), ("crane", 1.0)),
                    },
                )
            )

        report = output.getvalue()
        self.assertIn("Prior-weighting changed decisions: 1", report)
        self.assertIn("normal_w", report)
        self.assertIn("weighted_w", report)
        self.assertIn("Prior-weighting max-bucket increases: 0", report)
        self.assertIn("raise", report)
        self.assertIn("crane", report)
        self.assertIn("raise:0.05", report)

    def test_record_small_candidate_event_records_weights_and_candidate_flag(self):
        events = []

        record_small_candidate_event(
            events,
            "crane",
            4,
            "crane",
            ("raise", "crane"),
            {"raise": 0.05},
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["answer"], "crane")
        self.assertEqual(events[0]["guess_number"], 4)
        self.assertEqual(events[0]["normal_guess"], "crane")
        self.assertTrue(events[0]["chosen_is_candidate"])
        self.assertEqual(events[0]["prior_weights"], (("raise", 0.05), ("crane", 1.0)))

    def test_choose_answer_candidate_records_small_candidate_event(self):
        events = []

        guess = choose_answer_candidate(
            ("raise", "crane"),
            (),
            ("raise", "crane"),
            "off",
            answer="crane",
            guess_number=4,
            prior_answer_weights={"raise": 0.05},
            small_candidate_events=events,
        )

        self.assertEqual(guess, "raise")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["remaining_candidates"], ("raise", "crane"))

    def test_print_small_candidate_events_outputs_rows(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_small_candidate_events(
                (
                    {
                        "answer": "crane",
                        "guess_number": 4,
                        "normal_guess": "raise",
                        "remaining_candidates": ("raise", "crane"),
                        "prior_weights": (("raise", 0.05), ("crane", 1.0)),
                        "chosen_is_candidate": True,
                    },
                ),
                limit=1,
            )

        report = output.getvalue()
        self.assertIn("Small candidate events:", report)
        self.assertIn("raise:0.05", report)
        self.assertIn("crane:1.00", report)

    def test_play_baseline_game_excludes_prior_candidates(self):
        words = ("raise", "slate", "crane")

        game = play_baseline_game(
            "crane",
            words,
            words,
            "slate",
            prior_answers=("raise", "slate"),
            prior_policy="exclude",
        )

        self.assertEqual(game.guesses, ("slate", "crane"))

    def test_build_strategy_result_exclude_prior_reduces_tested_without_failure(self):
        words = ("raise", "slate", "crane")

        row, games = build_strategy_result(
            "baseline",
            "slate",
            words,
            words,
            prior_answers=("raise",),
            prior_policy="exclude",
        )

        self.assertEqual(row["tested"], 2)
        self.assertEqual(row["failed"], 0)
        self.assertEqual({game.answer for game in games}, {"slate", "crane"})

    def test_prior_exclude_keeps_prior_answers_available_as_answer_pool_guesses(self):
        words = ("slate", "frond", "cough", "pouch")

        row, games = build_strategy_result(
            "second-map-bucket",
            "slate",
            words,
            words,
            second_guess_pool_name="answers",
            prior_answers=("frond", "slate"),
            prior_policy="exclude",
        )

        self.assertEqual(row["tested"], 2)
        self.assertEqual(row["failed"], 0)
        self.assertEqual({game.answer for game in games}, {"cough", "pouch"})
        self.assertTrue(all(game.guesses[1] == "frond" for game in games))

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

    def test_build_weighted_worst_pattern_rows_uses_prior_weights(self):
        games = (
            GameResult(
                answer="cigar",
                guesses=("slate", "crane", "raise", "trace", "cigar"),
                solved=True,
            ),
            GameResult(
                answer="petal",
                guesses=("slate", "crane", "raise", "trace", "petal", "petal"),
                solved=True,
            ),
            GameResult(
                answer="raise",
                guesses=("slate", "crane", "raise", "trace", "petal", "cigar"),
                solved=False,
            ),
        )

        rows = build_weighted_worst_pattern_rows(
            games,
            {"cigar": 0.05, "petal": 0.60},
            limit=3,
        )
        rows_by_pattern = {row["pattern"]: row for row in rows}

        self.assertEqual(rows_by_pattern["..Y.."]["total_weight"], "0.05")
        self.assertEqual(rows_by_pattern["..Y.."]["weighted_5s"], "0.05")
        self.assertEqual(rows_by_pattern["..Y.."]["weighted_risk"], "0.10")
        self.assertEqual(rows_by_pattern[".YYYY"]["weighted_6s"], "0.60")
        self.assertEqual(rows_by_pattern[".YYYY"]["weighted_risk"], "3.00")
        self.assertEqual(rows_by_pattern["Y.Y.G"]["weighted_risk"], "20.00")

    def test_print_weighted_worst_patterns_outputs_table(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_weighted_worst_patterns(
                (
                    {
                        "pattern": "..Y..",
                        "games": 2,
                        "total_weight": "1.05",
                        "weighted_avg": "4.95",
                        "weighted_5s": "1.05",
                        "weighted_6s": "0.00",
                        "weighted_risk": "2.10",
                        "max_guesses": 5,
                    },
                )
            )

        report = output.getvalue()
        self.assertIn("Weighted worst patterns:", report)
        self.assertIn("weighted_risk", report)
        self.assertIn("..Y..", report)

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

    def test_build_tune_pattern_rows_can_limit_second_guesses(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_tune_pattern_rows(
            "slate",
            "GGGGG",
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
            top=25,
            max_second_guesses=1,
        )

        self.assertEqual(len(rows), 1)

    def test_build_tune_pattern_rows_supports_top_second_guess_candidates(self):
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
            max_second_guesses=1,
            second_guess_candidates="top",
        )

        expected = select_second_guess_candidates(
            answer_words,
            ("slate",),
            max_second_guesses=1,
            mode="top",
        )[0]
        self.assertEqual(rows[0]["second_guess"], expected)

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

    def test_tune_pattern_objective_rank_preserves_risk_default(self):
        row = {
            "second_guess": "crane",
            "average": "3.00",
            "solved_4_or_less": 7,
            "fives": 2,
            "sixes": 0,
            "risk_score": 4,
        }

        self.assertEqual(
            tune_pattern_objective_rank(row),
            (4, 3.0, -7, "crane"),
        )

    def test_tune_pattern_objective_rank_supports_branch_safe(self):
        branchy = {
            "second_guess": "alpha",
            "average": "2.50",
            "solved_4_or_less": 9,
            "fives": 1,
            "sixes": 1,
            "risk_score": 7,
            "worst_branch_risk": 7,
            "worst_branch_fives": 1,
        }
        safer = {
            "second_guess": "bravo",
            "average": "3.50",
            "solved_4_or_less": 6,
            "fives": 2,
            "sixes": 0,
            "risk_score": 10,
            "worst_branch_risk": 4,
            "worst_branch_fives": 1,
        }

        self.assertLess(
            tune_pattern_objective_rank(safer, "branch-safe"),
            tune_pattern_objective_rank(branchy, "branch-safe"),
        )

    def test_tune_pattern_objective_rank_supports_weighted_risk(self):
        normal_safe = {
            "second_guess": "alpha",
            "average": "3.00",
            "fives": 0,
            "sixes": 0,
            "risk_score": 0,
            "weighted_avg": "3.20",
            "weighted_5s": "0.00",
            "weighted_6s": "0.05",
            "weighted_risk": "0.25",
        }
        weighted_safe = {
            "second_guess": "bravo",
            "average": "3.50",
            "fives": 2,
            "sixes": 1,
            "risk_score": 9,
            "weighted_avg": "3.40",
            "weighted_5s": "0.20",
            "weighted_6s": "0.00",
            "weighted_risk": "0.40",
        }

        self.assertLess(
            tune_pattern_objective_rank(weighted_safe, "weighted-risk"),
            tune_pattern_objective_rank(normal_safe, "weighted-risk"),
        )

    def test_build_tune_pattern_rows_can_include_weighted_columns(self):
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
            prior_answer_weights={"slate": 0.05},
            include_weighted_columns=True,
        )

        self.assertIn("weighted_avg", rows[0])
        self.assertIn("weighted_5s", rows[0])
        self.assertIn("weighted_6s", rows[0])
        self.assertIn("weighted_risk", rows[0])

    def test_tune_pattern_branch_safe_can_rank_without_printing_branch_columns(self):
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
            objective="branch-safe",
        )

        self.assertNotIn("worst_branch_pattern", rows[0])

    def test_build_full_second_map_rows_returns_one_row_per_pattern(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        rows = build_full_second_map_rows(
            "slate",
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
            objective="branch-safe",
        )

        expected_patterns = {score_guess("slate", answer) for answer in answer_words}
        self.assertEqual({row["pattern"] for row in rows}, expected_patterns)
        self.assertIn("best_second", rows[0])
        self.assertIn("worst_branch_risk", rows[0])

    def test_build_second_map_row_for_pattern_returns_best_row(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")
        pattern = score_guess("slate", "slate")

        row = build_second_map_row_for_pattern(
            "slate",
            pattern,
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
        )

        self.assertEqual(row["first"], "slate")
        self.assertEqual(row["pattern"], "GGGGG")
        self.assertIn(row["best_second"], answer_words)

    def test_build_second_map_row_for_pattern_limits_second_guesses(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")
        pattern = score_guess("slate", "slate")
        output = io.StringIO()

        with redirect_stdout(output):
            row = build_second_map_row_for_pattern(
                "slate",
                pattern,
                "second-map-bucket",
                allowed_words,
                answer_words,
                second_guess_pool=answer_words,
                max_second_guesses=1,
                show_progress=True,
            )

        self.assertEqual(row["best_second"], "raise")
        self.assertIn("evaluated 1/1 second guesses", output.getvalue())

    def test_build_second_map_row_metrics_match_tune_pattern_for_same_second(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")
        pattern = score_guess("slate", "slate")

        built_row = build_second_map_row_for_pattern(
            "slate",
            pattern,
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
            max_second_guesses=1,
        )
        tune_rows, _games = build_tune_pattern_result(
            "slate",
            pattern,
            "second-map-bucket",
            allowed_words,
            answer_words,
            second_guess_pool=answer_words,
            second_guess=built_row["best_second"],
            branch_summary=True,
        )
        tune_row = tune_rows[0]

        self.assertEqual(built_row["average"], tune_row["average"])
        self.assertEqual(built_row["solved_3_or_less"], tune_row["solved_3_or_less"])
        self.assertEqual(built_row["solved_4_or_less"], tune_row["solved_4_or_less"])
        self.assertEqual(built_row["fives"], tune_row["fives"])
        self.assertEqual(built_row["sixes"], tune_row["sixes"])
        self.assertEqual(built_row["failed"], tune_row["failed"])
        self.assertEqual(built_row["risk_score"], tune_row["risk_score"])
        self.assertEqual(
            built_row["worst_branch_pattern"],
            tune_row["worst_branch_pattern"],
        )
        self.assertEqual(
            built_row["worst_branch_candidates"],
            tune_row["worst_branch_candidates"],
        )
        self.assertEqual(
            built_row["worst_branch_fives"],
            tune_row["worst_branch_fives"],
        )
        self.assertEqual(
            built_row["worst_branch_risk"],
            tune_row["worst_branch_risk"],
        )

    def test_select_second_guess_candidates_can_limit_all_mode(self):
        selected = select_second_guess_candidates(
            ("raise", "slate", "crane"),
            ("slate",),
            max_second_guesses=2,
            mode="all",
        )

        self.assertEqual(selected, ("raise", "slate"))

    def test_select_second_guess_candidates_top_is_deterministic(self):
        selected = select_second_guess_candidates(
            ("buzzy", "crane", "slate"),
            ("raise", "slate"),
            max_second_guesses=2,
            mode="top",
        )

        self.assertEqual(selected, ("slate", "crane"))

    def test_second_guess_candidate_rank_prefers_coverage(self):
        candidates = ("raise", "slate")

        self.assertLess(
            second_guess_candidate_rank("slate", candidates),
            second_guess_candidate_rank("buzzy", candidates),
        )

    def test_select_second_map_patterns_filters_patterns_and_candidates(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")
        slate_pattern = score_guess("slate", "slate")

        selected = select_second_map_patterns(
            "slate",
            "second-map-bucket",
            allowed_words,
            answer_words,
            "answers",
            trap_threshold=2,
            answer_weighting="off",
            small_candidate_order="normal",
            only_patterns=(slate_pattern,),
            min_candidates=1,
        )

        self.assertEqual(selected, ((slate_pattern, ("slate",)),))

    def test_select_second_map_patterns_supports_max_patterns(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        selected = select_second_map_patterns(
            "trace",
            "second-map-bucket",
            allowed_words,
            answer_words,
            "answers",
            trap_threshold=2,
            answer_weighting="off",
            small_candidate_order="normal",
            max_patterns=1,
        )

        self.assertEqual(len(selected), 1)

    def test_select_second_map_patterns_supports_only_worst_patterns(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        selected = select_second_map_patterns(
            "trace",
            "second-map-bucket",
            allowed_words,
            answer_words,
            "answers",
            trap_threshold=2,
            answer_weighting="off",
            small_candidate_order="normal",
            only_worst_patterns=1,
        )

        self.assertEqual(len(selected), 1)

    def test_run_build_second_map_writes_incremental_csv_and_resumes(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "built.csv"
            output = io.StringIO()
            with redirect_stdout(output):
                first_rows = run_build_second_map(
                    "slate",
                    "second-map-bucket",
                    allowed_words,
                    answer_words,
                    second_guess_pool=answer_words,
                    second_guess_pool_name="answers",
                    csv_path=csv_path,
                    max_patterns=1,
                    max_second_guesses=1,
                )
            csv_text = csv_path.read_text(encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                second_rows = run_build_second_map(
                    "slate",
                    "second-map-bucket",
                    allowed_words,
                    answer_words,
                    second_guess_pool=answer_words,
                    second_guess_pool_name="answers",
                    csv_path=csv_path,
                    max_patterns=1,
                    max_second_guesses=1,
                )

        self.assertEqual(len(first_rows), 1)
        self.assertEqual(second_rows, ())
        self.assertIn(",".join(BUILT_SECOND_MAP_COLUMNS), csv_text)
        self.assertIn("Built 1/1 pattern", output.getvalue())

    def test_run_build_second_map_force_rebuilds_existing_csv(self):
        allowed_words = ("raise", "slate", "crane", "trace")
        answer_words = ("raise", "slate", "crane")

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "built.csv"
            with redirect_stdout(io.StringIO()):
                run_build_second_map(
                    "slate",
                    "second-map-bucket",
                    allowed_words,
                    answer_words,
                    second_guess_pool=answer_words,
                    second_guess_pool_name="answers",
                    csv_path=csv_path,
                    max_patterns=1,
                    max_second_guesses=1,
                )
                rows = run_build_second_map(
                    "slate",
                    "second-map-bucket",
                    allowed_words,
                    answer_words,
                    second_guess_pool=answer_words,
                    second_guess_pool_name="answers",
                    csv_path=csv_path,
                    max_patterns=1,
                    force=True,
                    max_second_guesses=1,
                )

        self.assertEqual(len(rows), 1)

    def test_read_completed_built_second_map_patterns_reads_existing_rows(self):
        rows = (
            {
                "first": "slate",
                "pattern": "GGGGG",
                "candidates": 1,
                "best_second": "slate",
                "average": "1.00",
                "solved_3_or_less": 1,
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
            path = Path(temp_dir) / "built.csv"
            write_built_second_map_csv(path, rows)

            completed = read_completed_built_second_map_patterns(path, "slate")

        self.assertEqual(completed, {"GGGGG"})

    def test_open_incremental_built_second_map_csv_writes_header_immediately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "built.csv"
            csv_file, _writer = open_incremental_built_second_map_csv(path, force=False)
            csv_file.close()

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(BUILT_SECOND_MAP_COLUMNS), csv_text)

    def test_load_built_second_map_reads_matching_first_rows(self):
        rows = (
            {
                "first": "slate",
                "pattern": "GGGGG",
                "candidates": 1,
                "best_second": "slate",
                "average": "1.00",
                "solved_3_or_less": 1,
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
            path = Path(temp_dir) / "map.csv"
            write_built_second_map_csv(path, rows)

            second_map = load_built_second_map(path, "slate", ("slate",))

        self.assertEqual(second_map, {"GGGGG": "slate"})

    def test_print_built_second_map_outputs_table(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_built_second_map(
                (
                    {
                        "first": "slate",
                        "pattern": "GGGGG",
                        "candidates": 1,
                        "best_second": "slate",
                        "average": "1.00",
                        "solved_3_or_less": 1,
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
            )

        report = output.getvalue()
        self.assertIn("First  Pattern", report)
        self.assertIn("Best2", report)

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

    def test_build_recommendation_reports_candidate_weights_and_bucket_summary(self):
        row = build_recommendation(
            ("slate", "....Y"),
            ("slate", "cider", "diner", "poker", "drown", "rocky"),
            ("cider", "diner", "poker", "drown", "rocky"),
            second_guess_pool_name="answers",
            prior_policy="downweight",
            prior_answer_weights={"cider": 0.05},
        )

        self.assertEqual(row["remaining_count"], 3)
        self.assertIn("cider", row["top_candidates"])
        self.assertIn("cider:0.05", row["prior_weights"])
        self.assertEqual(row["recommended_guess"], "drown")
        self.assertEqual(row["explanation"], "Used Human Mode override for slate ....Y.")
        self.assertIn("max_bucket", row)

    def test_print_recommendation_outputs_summary(self):
        output = io.StringIO()

        with redirect_stdout(output):
            print_recommendation(
                {
                    "path": "slate ....Y",
                    "remaining_count": 3,
                    "top_candidates": "cider, diner, poker",
                    "prior_weights": "cider:0.05, diner:1.00, poker:1.00",
                    "recommended_guess": "diner",
                    "recommendation_type": "answer",
                    "max_bucket": 1,
                    "bucket_count": 3,
                    "expected_remaining": "1.00",
                    "explanation": "Chose diner as a possible answer using bucket safety.",
                }
            )

        report = output.getvalue()
        self.assertIn("Recommendation:", report)
        self.assertIn("Recommended next guess: diner", report)
        self.assertIn("Bucket summary:", report)

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

    def test_write_opener_strategy_csv_creates_parent_folder(self):
        rows = (
            {
                "first": "slate",
                "strategy": "second-map-bucket",
                "pool": "answers",
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
            path = Path(temp_dir) / "results" / "opener_strategy.csv"

            write_opener_strategy_csv(path, rows)

            csv_text = path.read_text(encoding="utf-8")

        self.assertIn(",".join(OPENER_STRATEGY_COLUMNS), csv_text)
        self.assertIn("slate,second-map-bucket,answers", csv_text)

    def test_main_compare_openers_with_strategy_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "openers.csv"
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
                        "--compare-openers-with-strategy",
                        "slate",
                        "crane",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--no-overrides",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("First   Strategy", report)
        self.assertEqual(len(csv_text.strip().splitlines()), 3)
        self.assertIn("first,strategy,pool,tested", csv_text)

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

    def test_main_tune_pattern_weighted_csv_writes_weighted_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            csv_path = temp_path / "results" / "tune_pattern_weighted.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            prior_dated_path.write_text("date,word\n2025-08-01,slate\n", encoding="utf-8")

            with redirect_stdout(io.StringIO()):
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
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--prior-policy",
                        "downweight",
                        "--as-of-date",
                        "2025-09-01",
                        "--tune-pattern-objective",
                        "weighted-risk",
                        "--top",
                        "1",
                        "--csv",
                        str(csv_path),
                    ]
                )

            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn(",".join(TUNE_PATTERN_WEIGHTED_COLUMNS), csv_text)
        self.assertIn("weighted_avg", csv_text)

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

    def test_main_build_second_map_with_csv_writes_file_and_prints_table(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            csv_path = temp_path / "results" / "built_second_map.csv"
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
                        "--build-second-map",
                        "slate",
                        "--strategy",
                        "second-map-bucket",
                        "--second-guess-pool",
                        "answers",
                        "--tune-pattern-objective",
                        "branch-safe",
                        "--csv",
                        str(csv_path),
                    ]
                )

            report = output.getvalue()
            csv_text = csv_path.read_text(encoding="utf-8")

        self.assertIn("First  Pattern", report)
        self.assertIn(",".join(BUILT_SECOND_MAP_COLUMNS), csv_text)
        self.assertIn("best_second", csv_text)

    def test_main_strategy_can_use_built_second_map_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            map_path = temp_path / "results" / "built_second_map.csv"
            answers_path.write_text("raise\nslate\ncrane\n", encoding="utf-8")
            allowed_path.write_text("raise\nslate\ncrane\ntrace\n", encoding="utf-8")
            allowed_words = ("raise", "slate", "crane", "trace")
            answer_words = ("raise", "slate", "crane")
            rows = build_full_second_map_rows(
                "slate",
                "second-map-bucket",
                allowed_words,
                answer_words,
                second_guess_pool=answer_words,
            )
            write_built_second_map_csv(map_path, rows)
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
                        "--use-built-second-map",
                        str(map_path),
                    ]
                )

        self.assertIn("second-map-bucket", output.getvalue())

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

    def test_compare_openers_with_strategy_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--compare-openers-with-strategy", "slate", "crane"])

    def test_recommend_requires_state(self):
        with self.assertRaises(SystemExit):
            main(["--recommend"])

    def test_state_requires_recommend(self):
        with self.assertRaises(SystemExit):
            main(["--state", "slate", "....Y"])

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

    def test_weighted_worst_patterns_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--weighted-worst-patterns", "5"])

    def test_weighted_worst_patterns_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "baseline", "--first", "slate", "--weighted-worst-patterns", "0"])

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

    def test_show_prior_weighting_changes_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--show-prior-weighting-changes"])

    def test_show_small_candidate_events_requires_strategy(self):
        with self.assertRaises(SystemExit):
            main(["--show-small-candidate-events", "5"])

    def test_show_small_candidate_events_requires_positive_limit(self):
        with self.assertRaises(SystemExit):
            main(["--strategy", "baseline", "--show-small-candidate-events", "0"])

    def test_show_weighted_score_requires_strategy_or_tune_pattern(self):
        with self.assertRaises(SystemExit):
            main(["--show-weighted-score"])

    def test_weighted_risk_objective_requires_tune_pattern(self):
        with self.assertRaises(SystemExit):
            main(["--build-second-map", "slate", "--tune-pattern-objective", "weighted-risk"])

    def test_weighted_risk_objective_requires_downweight_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            answers_path = temp_path / "answers.txt"
            allowed_path = temp_path / "allowed.txt"
            prior_dated_path = temp_path / "prior_dated.csv"
            answers_path.write_text("slate\n", encoding="utf-8")
            allowed_path.write_text("slate\n", encoding="utf-8")
            prior_dated_path.write_text("date,word\n2025-08-01,slate\n", encoding="utf-8")

            with self.assertRaises(SystemExit):
                main(
                    [
                        "--answers",
                        str(answers_path),
                        "--allowed",
                        str(allowed_path),
                        "--prior-answers-dated",
                        str(prior_dated_path),
                        "--tune-pattern",
                        "slate",
                        "GGGGG",
                        "--tune-pattern-objective",
                        "weighted-risk",
                    ]
                )

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
