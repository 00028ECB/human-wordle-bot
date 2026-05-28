"""Command-line entry point for Wordle Lab."""

import argparse
import csv
import time
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

from .scoring import is_solved, score_guess
from .simulator import (
    DEFAULT_ALLOWED_GUESSES_PATH,
    DEFAULT_ANSWERS_PATH,
    DEFAULT_FIRST_GUESS,
    GameResult,
    load_word_lists,
    run_simulation,
)

CSV_COLUMNS = (
    "first_guess",
    "tested",
    "solved",
    "average",
    "solved_3_or_less",
    "solved_4_or_less",
    "fives",
    "sixes",
    "failed",
    "risk_score",
)

SECOND_GUESS_COLUMNS = (
    "pattern",
    "candidates",
    "best_average",
    "best_balanced",
    "sample_answers",
)

STRATEGY_COLUMNS = (
    "strategy",
    "first_guess",
    "second_guess_pool",
    "tested",
    "solved",
    "average",
    "solved_3_or_less",
    "solved_4_or_less",
    "fives",
    "sixes",
    "failed",
    "risk_score",
)

OPENER_STRATEGY_COLUMNS = (
    "first",
    "strategy",
    "pool",
    "tested",
    "solved",
    "average",
    "solved_3_or_less",
    "solved_4_or_less",
    "fives",
    "sixes",
    "failed",
    "risk_score",
)

WORST_GAME_COLUMNS = (
    "answer",
    "guess_count",
    "path",
    "feedback",
)

TUNE_PATTERN_COLUMNS = (
    "pattern",
    "second_guess",
    "candidates",
    "average",
    "solved_3_or_less",
    "solved_4_or_less",
    "fives",
    "sixes",
    "failed",
    "risk_score",
)

TUNE_PATTERN_BRANCH_COLUMNS = TUNE_PATTERN_COLUMNS + (
    "worst_branch_pattern",
    "worst_branch_candidates",
    "worst_branch_fives",
    "worst_branch_risk",
)

TUNE_BRANCH_COLUMNS = (
    "first_pattern",
    "second_guess",
    "second_pattern",
    "third_guess",
    "candidates",
    "average",
    "solved_3_or_less",
    "solved_4_or_less",
    "fives",
    "sixes",
    "failed",
    "risk_score",
)

TUNE_PATH_COLUMNS = (
    "path",
    "next_guess",
    "candidates",
    "average",
    "solved_4_or_less",
    "fives",
    "sixes",
    "failed",
    "risk_score",
)

TUNE_PATH_BRANCH_COLUMNS = TUNE_PATH_COLUMNS + (
    "worst_branch_pattern",
    "worst_branch_candidates",
    "worst_branch_fives",
    "worst_branch_risk",
)

SECOND_GUESS_OVERRIDES = {
    ("slate", ".....", "answers"): "frond",
    ("slate", "...Y.", "answers"): "tough",
    ("slate", "...YY", "answers"): "deter",
    ("slate", "....Y", "answers"): "rocky",
    ("slate", "..G.G", "answers"): "brick",
    ("slate", "..Y..", "answers"): "randy",
    ("slate", "..Y.Y", "answers"): "march",
    ("slate", "..YY.", "answers"): "pouch",
    ("slate", ".YY..", "answers"): "rally",
    ("slate", ".Y...", "answers"): "dilly",
    ("slate", "G..Y.", "answers"): "count",
    ("slate", "..G..", "answers"): "grind",
    ("slate", "Y....", "answers"): "missy",
}

PATH_GUESS_OVERRIDES = {
    ("slate", ".....", "frond", ".....", "answers"): "chump",
    ("slate", ".....", "frond", "..Y..", "answers"): "pouch",
}

SMALL_CANDIDATE_ORDER_PREFERENCES = {
    # Explicit mini-family preferences. Keys are sorted so lookup is stable.
    ("femur", "fewer"): ("fewer", "femur"),
    ("piper", "viper"): ("viper", "piper"),
    ("ember", "upper"): ("ember", "upper"),
    ("biddy", "giddy"): ("giddy", "biddy"),
    ("frank", "prank"): ("prank", "frank"),
    ("pried", "weird"): ("weird", "pried"),
    ("breed", "greed"): ("greed", "breed"),
    ("brief", "grief"): ("grief", "brief"),
}

FINAL_CLUSTER_OVERRIDES = {
    ("buxom", "gumbo", "jumbo"): "jumbo",
    ("dried", "pried", "weird"): "weird",
    ("ember", "purer", "upper"): "ember",
    ("femur", "fever", "fewer"): "fewer",
    ("giver", "piper", "viper"): "viper",
    ("biddy", "giddy"): "giddy",
    ("breed", "greed"): "greed",
    ("brief", "grief"): "grief",
    ("frank", "prank"): "prank",
    ("never", "newer"): "newer",
}


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run the Wordle Lab baseline strategy over local word lists."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--first",
        default=DEFAULT_FIRST_GUESS,
        help=f"first guess to use for every game (default: {DEFAULT_FIRST_GUESS})",
    )
    mode.add_argument(
        "--compare",
        nargs="+",
        help="compare multiple first guesses",
    )
    mode.add_argument(
        "--compare-openers-with-strategy",
        nargs="+",
        metavar="FIRST",
        help="compare multiple first guesses using the selected --strategy",
    )
    mode.add_argument(
        "--top-openers",
        type=int,
        metavar="N",
        help="rank every allowed guess and show the top N openers",
    )
    mode.add_argument(
        "--stats",
        action="store_true",
        help="show word list statistics",
    )
    mode.add_argument(
        "--second-guess-map",
        metavar="FIRST",
        help="map first-guess feedback patterns to recommended second guesses",
    )
    mode.add_argument(
        "--compare-strategies",
        action="store_true",
        help="compare the built-in slate strategy set",
    )
    mode.add_argument(
        "--tune-pattern",
        nargs=2,
        metavar=("FIRST", "PATTERN"),
        help="rank second guesses for one first-guess feedback pattern",
    )
    mode.add_argument(
        "--tune-branch",
        nargs=4,
        metavar=("FIRST", "FIRST_PATTERN", "SECOND", "SECOND_PATTERN"),
        help="rank third guesses for one first-guess and second-guess branch",
    )
    mode.add_argument(
        "--tune-path",
        nargs="+",
        metavar="STEP",
        help="rank the next guess after an arbitrary guess/pattern path",
    )
    parser.add_argument(
        "--csv",
        help="write compare results to a CSV file",
    )
    parser.add_argument(
        "--rank-by",
        choices=("average", "risk", "balanced"),
        default="average",
        help="ranking method for --top-openers (default: average)",
    )
    parser.add_argument(
        "--opener-pool",
        choices=("allowed", "answers"),
        default="allowed",
        help="opener candidates for --top-openers (default: allowed)",
    )
    parser.add_argument(
        "--limit-openers",
        type=int,
        metavar="N",
        help="only test the first N openers from the selected opener pool",
    )
    parser.add_argument(
        "--second-guess-pool",
        choices=("allowed", "answers"),
        default="allowed",
        help="second-guess candidates for --second-guess-map or --strategy second-map (default: allowed)",
    )
    parser.add_argument(
        "--strategy",
        choices=(
            "baseline",
            "second-map",
            "second-map-trap",
            "second-map-bucket",
            "second-map-expected",
            "second-map-hybrid",
        ),
        help="test a fixed first-word strategy",
    )
    parser.add_argument(
        "--show-worst",
        type=int,
        metavar="N",
        help="show the N worst solved games for --strategy",
    )
    parser.add_argument(
        "--show-candidate-trace",
        action="store_true",
        help="include remaining candidate counts in --show-worst paths for --strategy",
    )
    parser.add_argument(
        "--show-pattern-worst",
        type=int,
        metavar="N",
        help="show the N worst games for --tune-pattern --second",
    )
    parser.add_argument(
        "--worst-patterns",
        nargs="?",
        const=-1,
        type=int,
        metavar="N",
        help="show first-feedback patterns ranked by risk for --strategy",
    )
    parser.add_argument(
        "--worst-prefixes",
        type=int,
        metavar="N",
        help="show path prefixes with the most 5+ guess solved games for --strategy",
    )
    parser.add_argument(
        "--show-final-clusters",
        type=int,
        metavar="N",
        help="show repeated candidate clusters before guess 4 for 5+ guess solved games",
    )
    parser.add_argument(
        "--trap-threshold",
        type=int,
        default=2,
        metavar="N",
        help="max bucket threshold for --strategy second-map-hybrid (default: 2)",
    )
    parser.add_argument(
        "--endgame-threshold",
        type=int,
        default=10,
        metavar="N",
        help="candidate count for --strategy second-map-expected EV search (default: 10)",
    )
    parser.add_argument(
        "--max-expected-guesses",
        type=int,
        default=10,
        metavar="M",
        help="maximum candidate guesses to evaluate in expected-value search (default: 10)",
    )
    parser.add_argument(
        "--max-expected-states",
        type=int,
        default=50000,
        metavar="N",
        help="maximum memoized expected-value states before bucket fallback (default: 50000)",
    )
    parser.add_argument(
        "--expected-depth",
        type=int,
        default=2,
        metavar="D",
        help="recursive lookahead depth for expected-value search (default: 2)",
    )
    parser.add_argument(
        "--no-overrides",
        action="store_true",
        help="disable built-in pattern-specific second-guess overrides",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        metavar="N",
        help="number of rows for --tune-pattern (default: 25)",
    )
    parser.add_argument(
        "--tune-path-objective",
        choices=("risk", "average", "fives", "safe-balanced"),
        default="risk",
        help="ranking objective for --tune-branch and --tune-path (default: risk)",
    )
    parser.add_argument(
        "--tune-pattern-objective",
        choices=("risk", "branch-safe"),
        default="risk",
        help="ranking objective for --tune-pattern (default: risk)",
    )
    parser.add_argument(
        "--answer-weighting",
        choices=("off", "simple"),
        default="off",
        help="answer candidate weighting mode for strategy solving (default: off)",
    )
    parser.add_argument(
        "--show-weighting-changes",
        action="store_true",
        help="show where --answer-weighting simple changes answer-candidate choices",
    )
    parser.add_argument(
        "--small-candidate-order",
        choices=("normal", "likelihood"),
        default="normal",
        help="ordering mode for 2-3 remaining answer candidates (default: normal)",
    )
    parser.add_argument(
        "--show-small-order-changes",
        action="store_true",
        help="show where --small-candidate-order likelihood changes small-candidate choices",
    )
    parser.add_argument(
        "--final-cluster-overrides",
        choices=("on", "off"),
        default="off",
        help="use exact final-cluster override map during strategy solving (default: off)",
    )
    parser.add_argument(
        "--show-final-cluster-override-changes",
        action="store_true",
        help="show where exact final-cluster overrides change strategy choices",
    )
    parser.add_argument(
        "--branch-summary",
        action="store_true",
        help="include worst branch summary columns for --tune-pattern",
    )
    parser.add_argument(
        "--second",
        help="evaluate one second guess for --tune-pattern",
    )
    parser.add_argument(
        "--answers",
        default=str(DEFAULT_ANSWERS_PATH),
        help=f"possible answer word list (default: {DEFAULT_ANSWERS_PATH})",
    )
    parser.add_argument(
        "--allowed",
        default=str(DEFAULT_ALLOWED_GUESSES_PATH),
        help=f"allowed guess word list (default: {DEFAULT_ALLOWED_GUESSES_PATH})",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.csv and not (
        args.compare or args.compare_openers_with_strategy or args.top_openers
        or args.second_guess_map or args.strategy or args.compare_strategies
        or args.tune_pattern or args.tune_branch or args.tune_path
    ):
        raise SystemExit(
            "--csv can only be used with --compare, --compare-openers-with-strategy, --top-openers, --second-guess-map, --strategy, --compare-strategies, --tune-pattern, --tune-branch, or --tune-path"
        )
    if args.compare_openers_with_strategy and not args.strategy:
        raise SystemExit("--compare-openers-with-strategy requires --strategy")
    if args.top_openers is not None and args.top_openers < 1:
        raise SystemExit("--top-openers must be at least 1")
    if args.limit_openers is not None and args.limit_openers < 1:
        raise SystemExit("--limit-openers must be at least 1")
    if args.show_worst is not None and args.show_worst < 1:
        raise SystemExit("--show-worst must be at least 1")
    if args.show_candidate_trace and not args.strategy:
        raise SystemExit("--show-candidate-trace can only be used with --strategy")
    if args.show_candidate_trace and not args.show_worst:
        raise SystemExit("--show-candidate-trace requires --show-worst")
    if args.show_pattern_worst is not None and args.show_pattern_worst < 1:
        raise SystemExit("--show-pattern-worst must be at least 1")
    if args.worst_patterns is not None and args.worst_patterns == 0:
        raise SystemExit("--worst-patterns must be at least 1 when a limit is provided")
    if args.worst_patterns is not None and not args.strategy:
        raise SystemExit("--worst-patterns can only be used with --strategy")
    if args.worst_prefixes is not None and args.worst_prefixes < 1:
        raise SystemExit("--worst-prefixes must be at least 1")
    if args.worst_prefixes is not None and not args.strategy:
        raise SystemExit("--worst-prefixes can only be used with --strategy")
    if args.show_final_clusters is not None and args.show_final_clusters < 1:
        raise SystemExit("--show-final-clusters must be at least 1")
    if args.show_final_clusters is not None and not args.strategy:
        raise SystemExit("--show-final-clusters can only be used with --strategy")
    if args.show_small_order_changes and not args.strategy:
        raise SystemExit("--show-small-order-changes can only be used with --strategy")
    if args.show_final_cluster_override_changes and not args.strategy:
        raise SystemExit("--show-final-cluster-override-changes can only be used with --strategy")
    if args.trap_threshold < 1:
        raise SystemExit("--trap-threshold must be at least 1")
    if args.endgame_threshold < 1:
        raise SystemExit("--endgame-threshold must be at least 1")
    if args.max_expected_guesses < 1:
        raise SystemExit("--max-expected-guesses must be at least 1")
    if args.max_expected_states < 1:
        raise SystemExit("--max-expected-states must be at least 1")
    if args.expected_depth < 1:
        raise SystemExit("--expected-depth must be at least 1")
    if args.top < 1:
        raise SystemExit("--top must be at least 1")

    try:
        allowed_guesses, possible_answers = load_word_lists(
            allowed_path=args.allowed,
            answers_path=args.answers,
        )
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    if args.compare_openers_with_strategy:
        try:
            rows = build_opener_strategy_comparison_rows(
                args.compare_openers_with_strategy,
                args.strategy,
                allowed_guesses,
                possible_answers,
                second_guess_pool_name=args.second_guess_pool,
                trap_threshold=args.trap_threshold,
                use_overrides=False if args.no_overrides else None,
                answer_weighting=args.answer_weighting,
                small_candidate_order=args.small_candidate_order,
                endgame_threshold=args.endgame_threshold,
                max_expected_guesses=args.max_expected_guesses,
                max_expected_states=args.max_expected_states,
                expected_depth=args.expected_depth,
                final_cluster_overrides=args.final_cluster_overrides,
            )
        except ValueError as error:
            parser.error(str(error))
        print_opener_strategy_report(rows)
        if args.csv:
            write_opener_strategy_csv(args.csv, rows)
        return

    if args.compare_strategies:
        rows = build_strategy_comparison_rows(
            allowed_guesses,
            possible_answers,
            use_overrides=False if args.no_overrides else None,
            answer_weighting=args.answer_weighting,
            small_candidate_order=args.small_candidate_order,
        )
        print_strategy_report(rows)
        if args.csv:
            write_strategy_csv(args.csv, rows)
        return
    if args.tune_pattern:
        first_guess, pattern = args.tune_pattern
        second_guess_pool = (
            allowed_guesses if args.second_guess_pool == "allowed" else possible_answers
        )
        try:
            rows, pattern_games = build_tune_pattern_result(
                first_guess.lower(),
                pattern,
                args.strategy or "second-map-bucket",
                allowed_guesses,
                possible_answers,
                second_guess_pool,
                top=args.top,
                second_guess=args.second.lower() if args.second else None,
                trap_threshold=args.trap_threshold,
                answer_weighting=args.answer_weighting,
                small_candidate_order=args.small_candidate_order,
                branch_summary=args.branch_summary,
                objective=args.tune_pattern_objective,
            )
        except ValueError as error:
            parser.error(str(error))
        print_tune_pattern_report(rows, branch_summary=args.branch_summary)
        pattern_worst_limit = args.show_pattern_worst or args.show_worst
        if pattern_worst_limit and args.second:
            print_worst_games(build_worst_game_rows(pattern_games, pattern_worst_limit))
        if args.csv:
            write_tune_pattern_csv(args.csv, rows)
        return
    if args.tune_branch:
        first_guess, first_pattern, second_guess, second_pattern = args.tune_branch
        third_guess_pool = (
            allowed_guesses if args.second_guess_pool == "allowed" else possible_answers
        )
        try:
            rows, branch_games = build_tune_branch_result(
                first_guess.lower(),
                first_pattern,
                second_guess.lower(),
                second_pattern,
                args.strategy or "second-map-bucket",
                allowed_guesses,
                possible_answers,
                third_guess_pool,
                top=args.top,
                third_guess=args.second.lower() if args.second else None,
                trap_threshold=args.trap_threshold,
                answer_weighting=args.answer_weighting,
                small_candidate_order=args.small_candidate_order,
                objective=args.tune_path_objective,
            )
        except ValueError as error:
            parser.error(str(error))
        print_tune_branch_report(rows)
        if args.show_worst and args.second:
            print_worst_games(build_worst_game_rows(branch_games, args.show_worst))
        if args.csv:
            write_tune_branch_csv(args.csv, rows)
        return
    if args.tune_path:
        next_guess_pool = (
            allowed_guesses if args.second_guess_pool == "allowed" else possible_answers
        )
        try:
            rows, path_games = build_tune_path_result(
                args.tune_path,
                args.strategy or "second-map-bucket",
                allowed_guesses,
                possible_answers,
                next_guess_pool,
                top=args.top,
                next_guess=args.second.lower() if args.second else None,
                trap_threshold=args.trap_threshold,
                answer_weighting=args.answer_weighting,
                small_candidate_order=args.small_candidate_order,
                branch_summary=args.branch_summary,
                objective=args.tune_path_objective,
            )
        except ValueError as error:
            parser.error(str(error))
        print_tune_path_report(rows, branch_summary=args.branch_summary)
        if args.show_worst:
            print_worst_games(build_worst_game_rows(path_games, args.show_worst))
        if args.csv:
            write_tune_path_csv(args.csv, rows)
        return
    if args.strategy:
        weighting_changes = []
        small_order_changes = []
        final_cluster_override_changes = []
        start_time = time.perf_counter()
        try:
            row, games = build_strategy_result(
                args.strategy,
                args.first.lower(),
                allowed_guesses,
                possible_answers,
                second_guess_pool_name=args.second_guess_pool,
                trap_threshold=args.trap_threshold,
                endgame_threshold=args.endgame_threshold,
                max_expected_guesses=args.max_expected_guesses,
                max_expected_states=args.max_expected_states,
                expected_depth=args.expected_depth,
                use_overrides=False if args.no_overrides else None,
                answer_weighting=args.answer_weighting,
                weighting_changes=weighting_changes if args.show_weighting_changes else None,
                small_candidate_order=args.small_candidate_order,
                small_order_changes=(
                    small_order_changes if args.show_small_order_changes else None
                ),
                final_cluster_overrides=args.final_cluster_overrides,
                final_cluster_override_changes=(
                    final_cluster_override_changes
                    if args.show_final_cluster_override_changes
                    else None
                ),
            )
        except ValueError as error:
            parser.error(str(error))
        elapsed_seconds = time.perf_counter() - start_time
        print_strategy_report((row,))
        if args.strategy == "second-map-expected":
            print_expected_diagnostics(row, elapsed_seconds)
        if args.show_weighting_changes:
            print_weighting_changes(weighting_changes, enabled=args.answer_weighting == "simple")
        if args.show_small_order_changes:
            print_small_order_changes(
                small_order_changes,
                enabled=args.small_candidate_order == "likelihood",
            )
        if args.show_final_cluster_override_changes:
            print_final_cluster_override_changes(
                final_cluster_override_changes,
                enabled=args.final_cluster_overrides == "on",
            )
        worst_rows = ()
        if args.worst_patterns is not None:
            pattern_limit = None if args.worst_patterns == -1 else args.worst_patterns
            print_worst_patterns(build_worst_pattern_rows(games, pattern_limit))
        if args.worst_prefixes:
            print_worst_prefixes(build_worst_prefix_rows(games, args.worst_prefixes))
        if args.show_final_clusters:
            print_final_clusters(
                build_final_cluster_rows(
                    games,
                    possible_answers,
                    args.show_final_clusters,
                )
            )
        if args.show_worst:
            worst_rows = build_worst_game_rows(
                games,
                args.show_worst,
                possible_answers if args.show_candidate_trace else None,
            )
            print_worst_games(worst_rows)
        if args.csv:
            write_strategy_csv(args.csv, (row,))
            if worst_rows:
                write_worst_games_csv(worst_csv_path(args.csv), worst_rows)
        return
    if args.stats:
        print_stats_report(allowed_guesses, possible_answers)
        return
    if args.second_guess_map:
        second_guess_pool = (
            allowed_guesses if args.second_guess_pool == "allowed" else possible_answers
        )
        try:
            rows = build_second_guess_map_rows(
                args.second_guess_map.lower(),
                allowed_guesses,
                possible_answers,
                second_guess_pool,
            )
        except ValueError as error:
            parser.error(str(error))
        print_second_guess_map(rows)
        if args.csv:
            write_second_guess_csv(args.csv, rows)
        return
    if args.compare:
        rows = build_comparison_rows(args.compare, allowed_guesses, possible_answers)
        print_comparison_report(rows)
        if args.csv:
            write_comparison_csv(args.csv, rows)
        return
    if args.top_openers:
        opener_guesses = (
            allowed_guesses if args.opener_pool == "allowed" else possible_answers
        )
        if args.limit_openers:
            opener_guesses = opener_guesses[: args.limit_openers]
        start_time = time.perf_counter()
        rows = build_top_opener_rows(
            args.top_openers,
            opener_guesses,
            allowed_guesses,
            possible_answers,
            rank_by=args.rank_by,
            show_progress=True,
        )
        elapsed_seconds = time.perf_counter() - start_time
        print_comparison_report(rows)
        print_timing_report(elapsed_seconds, len(opener_guesses))
        if args.csv:
            write_comparison_csv(args.csv, rows)
        return

    result = run_simulation(
        allowed_guesses=allowed_guesses,
        possible_answers=possible_answers,
        first_guess=args.first.lower(),
    )

    print("Wordle Lab baseline strategy")
    print(f"Answers tested: {len(result.games)}")
    print(f"Solved: {result.solved_count}/{len(result.games)}")
    print(f"Average guesses: {result.average_guesses:.2f}")
    print(f"First guess: {args.first.lower()}")
    print("Guess distribution:")
    for guess_count in range(1, 7):
        print(f"  {guess_count} guesses: {result.guess_distribution[guess_count]}")
    print(f"  Failed: {result.failed_count}")


def print_stats_report(allowed_guesses, possible_answers):
    answer_words = set(possible_answers)
    allowed_words = set(allowed_guesses)
    overlap = answer_words & allowed_words
    allowed_only = allowed_words - answer_words

    print(f"Answers: {len(possible_answers)}")
    print(f"Allowed guesses: {len(allowed_guesses)}")
    print(f"Overlap: {len(overlap)}")
    print(f"Allowed-only guesses: {len(allowed_only)}")


def print_timing_report(elapsed_seconds, opener_count):
    average_seconds = elapsed_seconds / opener_count if opener_count else 0
    print(f"Elapsed seconds: {elapsed_seconds:.2f}")
    print(f"Average seconds per opener: {average_seconds:.4f}")


def print_expected_diagnostics(row, elapsed_seconds):
    print(f"Expected-value states: {row.get('expected_states', 0)}")
    print(f"Expected-value fallbacks: {row.get('expected_fallbacks', 0)}")
    print(f"Elapsed seconds: {elapsed_seconds:.2f}")


def build_tune_pattern_rows(
    first_guess,
    pattern,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool,
    top=25,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    branch_summary=False,
    objective="risk",
):
    rows, _games = build_tune_pattern_result(
        first_guess,
        pattern,
        strategy,
        allowed_guesses,
        possible_answers,
        second_guess_pool,
        top=top,
        trap_threshold=trap_threshold,
        answer_weighting=answer_weighting,
        small_candidate_order=small_candidate_order,
        branch_summary=branch_summary,
        objective=objective,
    )
    return rows


def build_tune_pattern_result(
    first_guess,
    pattern,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool,
    top=25,
    second_guess=None,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    branch_summary=False,
    objective="risk",
):
    validate_tune_pattern(first_guess, pattern, strategy, allowed_guesses)
    if second_guess is not None and second_guess not in second_guess_pool:
        raise ValueError(f"Second guess {second_guess!r} is not in the selected second-guess pool.")
    candidates = tuple(
        answer for answer in possible_answers if score_guess(first_guess, answer) == pattern
    )
    if not candidates:
        raise ValueError(f"No answers match first guess {first_guess!r} and pattern {pattern!r}.")

    rows = []
    selected_second_guesses = (second_guess,) if second_guess else second_guess_pool
    selected_games = ()
    for current_second_guess in selected_second_guesses:
        games = tuple(
            play_tuned_pattern_game(
                answer,
                allowed_guesses,
                candidates,
                first_guess,
                pattern,
                current_second_guess,
                strategy,
                second_guess_pool,
                trap_threshold,
                answer_weighting,
                small_candidate_order,
            )
            for answer in candidates
        )
        if second_guess:
            selected_games = games
        rows.append(
            build_tune_pattern_row(
                pattern,
                current_second_guess,
                len(candidates),
                games,
                candidates,
                branch_summary=branch_summary or objective == "branch-safe",
            )
        )

    ranked_rows = sorted(
        rows,
        key=lambda row: tune_pattern_objective_rank(row, objective),
    )
    returned_rows = tuple(ranked_rows[:top])
    if objective == "branch-safe" and not branch_summary:
        returned_rows = tuple(strip_tune_pattern_branch_summary(row) for row in returned_rows)
    return returned_rows, selected_games


def tune_pattern_objective_rank(row, objective="risk"):
    average = float(row["average"])
    if objective == "risk":
        return (
            row["risk_score"],
            average,
            -row["solved_4_or_less"],
            row["second_guess"],
        )
    if objective == "branch-safe":
        return (
            row["sixes"],
            row["risk_score"],
            row["worst_branch_risk"],
            row["worst_branch_fives"],
            row["fives"],
            average,
            row["second_guess"],
        )
    raise ValueError(f"Unsupported tune-pattern objective: {objective}")


def strip_tune_pattern_branch_summary(row):
    return {
        key: value
        for key, value in row.items()
        if key not in TUNE_PATTERN_BRANCH_COLUMNS[len(TUNE_PATTERN_COLUMNS):]
    }


def validate_tune_pattern(first_guess, pattern, strategy, allowed_guesses):
    if first_guess not in allowed_guesses:
        raise ValueError(f"First guess {first_guess!r} is not in the allowed guess list.")
    if len(pattern) != len(first_guess) or any(mark not in "GY." for mark in pattern):
        raise ValueError("Pattern must use G, Y, and . with the same length as the first guess.")
    if strategy not in {
        "baseline",
        "second-map",
        "second-map-trap",
        "second-map-bucket",
        "second-map-expected",
        "second-map-hybrid",
    }:
        raise ValueError(f"Unsupported strategy: {strategy}")


def apply_second_guess_overrides(
    first_guess,
    second_guess_pool_name,
    second_guess_pool,
    second_guess_by_pattern,
):
    pool = set(second_guess_pool)
    for (override_first, pattern, override_pool), override_guess in SECOND_GUESS_OVERRIDES.items():
        if override_first != first_guess or override_pool != second_guess_pool_name:
            continue
        if pattern not in second_guess_by_pattern:
            continue
        if override_guess not in pool:
            raise ValueError(
                f"Override {override_guess!r} for {first_guess!r} {pattern!r} "
                f"is not in the {second_guess_pool_name} second-guess pool."
            )
        second_guess_by_pattern[pattern] = override_guess


def find_path_guess_override(
    first_guess,
    first_pattern,
    second_guess,
    second_pattern,
    second_guess_pool_name,
    guess_pool,
    previous_guesses,
):
    override_guess = PATH_GUESS_OVERRIDES.get(
        (first_guess, first_pattern, second_guess, second_pattern, second_guess_pool_name)
    )
    if override_guess is None:
        return None
    if override_guess not in guess_pool:
        raise ValueError(
            f"Override {override_guess!r} for path "
            f"{first_guess!r} {first_pattern!r} {second_guess!r} {second_pattern!r} "
            f"is not in the {second_guess_pool_name} guess pool."
        )
    if override_guess in previous_guesses:
        raise ValueError(
            f"Override {override_guess!r} for path "
            f"{first_guess!r} {first_pattern!r} {second_guess!r} {second_pattern!r} "
            "was already guessed."
        )
    return override_guess


def tuned_overrides_enabled(strategy, use_overrides):
    if use_overrides is False:
        return False
    if use_overrides is True:
        return True
    return strategy in {"second-map-bucket", "second-map-expected"}


def play_tuned_pattern_game(
    answer,
    allowed_guesses,
    candidates,
    first_guess,
    pattern,
    second_guess,
    strategy,
    probe_pool,
    trap_threshold,
    answer_weighting="off",
    small_candidate_order="normal",
):
    guesses = [first_guess]
    if is_solved(pattern):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    feedback = score_guess(second_guess, answer)
    guesses.append(second_guess)
    if is_solved(feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    remaining_candidates = filter_candidates_by_feedback(candidates, second_guess, feedback)
    while remaining_candidates:
        next_guess = choose_later_strategy_guess(
            strategy,
            remaining_candidates,
            guesses,
            allowed_guesses,
            probe_pool,
            trap_threshold,
            answer_weighting,
            small_candidate_order,
        )
        feedback = score_guess(next_guess, answer)
        guesses.append(next_guess)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        remaining_candidates = filter_candidates_by_feedback(
            remaining_candidates,
            next_guess,
            feedback,
        )

    return GameResult(answer=answer, guesses=tuple(guesses), solved=False)


def choose_later_strategy_guess(
    strategy,
    candidates,
    previous_guesses,
    allowed_guesses,
    probe_pool,
    trap_threshold,
    answer_weighting="off",
    small_candidate_order="normal",
    small_order_changes=None,
    answer=None,
    guess_number=None,
):
    return choose_next_guess_with_optional_probe(
        candidates,
        previous_guesses,
        allowed_guesses,
        probe_pool,
        use_trap_avoidance=(strategy == "second-map-trap"),
        use_bucket_strategy=(strategy in {"second-map-bucket", "second-map-expected"}),
        use_hybrid_strategy=(strategy == "second-map-hybrid"),
        trap_threshold=trap_threshold,
        answer_weighting=answer_weighting,
        small_candidate_order=small_candidate_order,
        small_order_changes=small_order_changes,
        answer=answer,
        guess_number=guess_number,
    )


def build_tune_pattern_row(
    pattern,
    second_guess,
    candidate_count,
    games,
    candidates=(),
    branch_summary=False,
):
    summary = build_summary_row_from_games(second_guess, games)
    row = {
        "pattern": pattern,
        "second_guess": second_guess,
        "candidates": candidate_count,
        "average": summary["average"],
        "solved_3_or_less": summary["solved_3_or_less"],
        "solved_4_or_less": summary["solved_4_or_less"],
        "fives": summary["fives"],
        "sixes": summary["sixes"],
        "failed": summary["failed"],
        "risk_score": summary["risk_score"],
    }
    if branch_summary:
        row.update(build_second_feedback_branch_summary(second_guess, candidates, games))
    return row


def build_second_feedback_branch_summary(second_guess, candidates, games):
    games_by_answer = {game.answer: game for game in games}
    grouped_answers = defaultdict(list)
    for answer in candidates:
        grouped_answers[score_guess(second_guess, answer)].append(answer)

    if not grouped_answers:
        return {
            "worst_branch_pattern": "",
            "worst_branch_candidates": 0,
            "worst_branch_fives": 0,
            "worst_branch_risk": 0,
        }

    branch_rows = []
    for branch_pattern, answers in grouped_answers.items():
        branch_games = [games_by_answer[answer] for answer in answers]
        fives = sum(1 for game in branch_games if game.solved and game.guess_count == 5)
        sixes = sum(1 for game in branch_games if game.solved and game.guess_count == 6)
        failed = sum(1 for game in branch_games if not game.solved)
        risk = fives * 2 + sixes * 5 + failed * 20
        average = (
            sum(game.guess_count for game in branch_games) / len(branch_games)
            if branch_games
            else 0
        )
        branch_rows.append(
            {
                "worst_branch_pattern": branch_pattern,
                "worst_branch_candidates": len(answers),
                "worst_branch_fives": fives,
                "worst_branch_risk": risk,
                "average": average,
            }
        )

    worst_branch = max(
        branch_rows,
        key=lambda row: (
            row["worst_branch_risk"],
            row["worst_branch_candidates"],
            row["average"],
            row["worst_branch_pattern"],
        ),
    )
    del worst_branch["average"]
    return worst_branch


def print_tune_pattern_report(rows, branch_summary=False):
    if branch_summary:
        print(
            "Pattern  Second  Candidates  Avg   <=3   <=4   5s  6s  Fail  Risk  "
            "Worst2  WorstN  Worst5s  WorstRisk"
        )
    else:
        print("Pattern  Second  Candidates  Avg   <=3   <=4   5s  6s  Fail  Risk")
    for row in rows:
        line = (
            f"{row['pattern']:<8} "
            f"{row['second_guess']:<7} "
            f"{row['candidates']:<11} "
            f"{row['average']:<5} "
            f"{row['solved_3_or_less']:<5} "
            f"{row['solved_4_or_less']:<5} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['failed']:<5} "
            f"{row['risk_score']}"
        )
        if branch_summary:
            line += (
                f"     {row['worst_branch_pattern']:<7} "
                f"{row['worst_branch_candidates']:<7} "
                f"{row['worst_branch_fives']:<8} "
                f"{row['worst_branch_risk']}"
            )
        print(line)


def build_tune_branch_result(
    first_guess,
    first_pattern,
    second_guess,
    second_pattern,
    strategy,
    allowed_guesses,
    possible_answers,
    third_guess_pool,
    top=25,
    third_guess=None,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    objective="risk",
):
    validate_tune_pattern(first_guess, first_pattern, strategy, allowed_guesses)
    if second_guess not in allowed_guesses:
        raise ValueError(f"Second guess {second_guess!r} is not in the allowed guess list.")
    if len(second_pattern) != len(second_guess) or any(mark not in "GY." for mark in second_pattern):
        raise ValueError("Second pattern must use G, Y, and . with the same length as the second guess.")
    if third_guess is not None and third_guess not in third_guess_pool:
        raise ValueError(f"Third guess {third_guess!r} is not in the selected third-guess pool.")

    candidates = tuple(
        answer
        for answer in possible_answers
        if score_guess(first_guess, answer) == first_pattern
        and score_guess(second_guess, answer) == second_pattern
    )
    if not candidates:
        raise ValueError(
            f"No answers match branch {first_guess!r} {first_pattern!r}, "
            f"{second_guess!r} {second_pattern!r}."
        )

    rows = []
    selected_games = ()
    selected_third_guesses = (third_guess,) if third_guess else third_guess_pool
    for current_third_guess in selected_third_guesses:
        games = tuple(
            play_tuned_branch_game(
                answer,
                allowed_guesses,
                candidates,
                first_guess,
                first_pattern,
                second_guess,
                second_pattern,
                current_third_guess,
                strategy,
                third_guess_pool,
                trap_threshold,
                answer_weighting,
                small_candidate_order,
            )
            for answer in candidates
        )
        if third_guess:
            selected_games = games
        rows.append(
            build_tune_branch_row(
                first_pattern,
                second_guess,
                second_pattern,
                current_third_guess,
                len(candidates),
                games,
            )
        )

    ranked_rows = rank_tune_rows(rows, "third_guess", objective)
    return tuple(ranked_rows[:top]), selected_games


def build_tune_branch_rows(
    first_guess,
    first_pattern,
    second_guess,
    second_pattern,
    strategy,
    allowed_guesses,
    possible_answers,
    third_guess_pool,
    top=25,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    objective="risk",
):
    rows, _games = build_tune_branch_result(
        first_guess,
        first_pattern,
        second_guess,
        second_pattern,
        strategy,
        allowed_guesses,
        possible_answers,
        third_guess_pool,
        top=top,
        trap_threshold=trap_threshold,
        answer_weighting=answer_weighting,
        small_candidate_order=small_candidate_order,
        objective=objective,
    )
    return rows


def play_tuned_branch_game(
    answer,
    allowed_guesses,
    candidates,
    first_guess,
    first_pattern,
    second_guess,
    second_pattern,
    third_guess,
    strategy,
    probe_pool,
    trap_threshold,
    answer_weighting="off",
    small_candidate_order="normal",
):
    guesses = [first_guess]
    if is_solved(first_pattern):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    guesses.append(second_guess)
    if is_solved(second_pattern):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    feedback = score_guess(third_guess, answer)
    guesses.append(third_guess)
    if is_solved(feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    remaining_candidates = filter_candidates_by_feedback(candidates, third_guess, feedback)
    while remaining_candidates:
        next_guess = choose_later_strategy_guess(
            strategy,
            remaining_candidates,
            guesses,
            allowed_guesses,
            probe_pool,
            trap_threshold,
            answer_weighting,
            small_candidate_order,
        )
        feedback = score_guess(next_guess, answer)
        guesses.append(next_guess)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        remaining_candidates = filter_candidates_by_feedback(
            remaining_candidates,
            next_guess,
            feedback,
        )

    return GameResult(answer=answer, guesses=tuple(guesses), solved=False)


def build_tune_branch_row(
    first_pattern,
    second_guess,
    second_pattern,
    third_guess,
    candidate_count,
    games,
):
    summary = build_summary_row_from_games(third_guess, games)
    return {
        "first_pattern": first_pattern,
        "second_guess": second_guess,
        "second_pattern": second_pattern,
        "third_guess": third_guess,
        "candidates": candidate_count,
        "average": summary["average"],
        "solved_3_or_less": summary["solved_3_or_less"],
        "solved_4_or_less": summary["solved_4_or_less"],
        "fives": summary["fives"],
        "sixes": summary["sixes"],
        "failed": summary["failed"],
        "risk_score": summary["risk_score"],
    }


def print_tune_branch_report(rows):
    print("FirstPat  Second  SecondPat  Third  Candidates  Avg   <=3   <=4   5s  6s  Fail  Risk")
    for row in rows:
        print(
            f"{row['first_pattern']:<8} "
            f"{row['second_guess']:<7} "
            f"{row['second_pattern']:<9} "
            f"{row['third_guess']:<6} "
            f"{row['candidates']:<11} "
            f"{row['average']:<5} "
            f"{row['solved_3_or_less']:<5} "
            f"{row['solved_4_or_less']:<5} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['failed']:<5} "
            f"{row['risk_score']}"
        )


def build_tune_path_result(
    path_steps,
    strategy,
    allowed_guesses,
    possible_answers,
    next_guess_pool,
    top=25,
    next_guess=None,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    branch_summary=False,
    objective="risk",
):
    path_guesses, path_patterns = parse_tune_path(path_steps, allowed_guesses)
    validate_tune_path_strategy(strategy)
    if next_guess is not None and next_guess not in next_guess_pool:
        raise ValueError(f"Next guess {next_guess!r} is not in the selected next-guess pool.")

    candidates = filter_candidates_for_path(possible_answers, path_guesses, path_patterns)
    if not candidates:
        raise ValueError("No answers match the supplied tune path.")

    rows = []
    selected_games = ()
    selected_next_guesses = (next_guess,) if next_guess else next_guess_pool
    path_label = format_tune_path_label(path_guesses, path_patterns)
    for current_next_guess in selected_next_guesses:
        games = tuple(
            play_tuned_path_game(
                answer,
                allowed_guesses,
                candidates,
                path_guesses,
                current_next_guess,
                strategy,
                next_guess_pool,
                trap_threshold,
                answer_weighting,
                small_candidate_order,
            )
            for answer in candidates
        )
        if next_guess:
            selected_games = games
        rows.append(
            build_tune_path_row(
                path_label,
                current_next_guess,
                len(candidates),
                games,
                candidates,
                branch_summary=branch_summary,
            )
        )

    ranked_rows = rank_tune_rows(rows, "next_guess", objective)
    if not selected_games and ranked_rows:
        best_next_guess = ranked_rows[0]["next_guess"]
        selected_games = tuple(
            play_tuned_path_game(
                answer,
                allowed_guesses,
                candidates,
                path_guesses,
                best_next_guess,
                strategy,
                next_guess_pool,
                trap_threshold,
                answer_weighting,
                small_candidate_order,
            )
            for answer in candidates
        )
    return tuple(ranked_rows[:top]), selected_games


def build_tune_path_rows(
    path_steps,
    strategy,
    allowed_guesses,
    possible_answers,
    next_guess_pool,
    top=25,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    branch_summary=False,
    objective="risk",
):
    rows, _games = build_tune_path_result(
        path_steps,
        strategy,
        allowed_guesses,
        possible_answers,
        next_guess_pool,
        top=top,
        trap_threshold=trap_threshold,
        answer_weighting=answer_weighting,
        small_candidate_order=small_candidate_order,
        branch_summary=branch_summary,
        objective=objective,
    )
    return rows


def rank_tune_rows(rows, guess_key, objective="risk"):
    return sorted(rows, key=lambda row: tune_objective_rank(row, guess_key, objective))


def tune_objective_rank(row, guess_key, objective="risk"):
    average = float(row["average"])
    if objective == "risk":
        return (
            row["risk_score"],
            average,
            -row["solved_4_or_less"],
            row[guess_key],
        )
    if objective == "average":
        return (
            average,
            row["risk_score"],
            -row["solved_4_or_less"],
            row[guess_key],
        )
    if objective == "fives":
        return (
            row["fives"],
            row["sixes"],
            row["risk_score"],
            average,
            row[guess_key],
        )
    if objective == "safe-balanced":
        return (
            row["sixes"],
            row["fives"],
            row["risk_score"],
            average,
            row[guess_key],
        )
    raise ValueError(f"Unsupported tune-path objective: {objective}")


def parse_tune_path(path_steps, allowed_guesses):
    if len(path_steps) < 2:
        raise ValueError("Tune path must include at least one guess and feedback pattern.")
    if len(path_steps) % 2 != 0:
        raise ValueError("Tune path must end with a feedback pattern for the last guess.")

    guesses = tuple(step.lower() for step in path_steps[0::2])
    patterns = tuple(path_steps[1::2])
    for guess in guesses:
        if guess not in allowed_guesses:
            raise ValueError(f"Guess {guess!r} is not in the allowed guess list.")
    for guess, pattern in zip(guesses, patterns):
        if len(pattern) != len(guess) or any(mark not in "GY." for mark in pattern):
            raise ValueError("Path patterns must use G, Y, and . with the same length as their guess.")
    return guesses, patterns


def validate_tune_path_strategy(strategy):
    if strategy not in {
        "baseline",
        "second-map",
        "second-map-trap",
        "second-map-bucket",
        "second-map-expected",
        "second-map-hybrid",
    }:
        raise ValueError(f"Unsupported strategy: {strategy}")


def filter_candidates_for_path(possible_answers, path_guesses, path_patterns):
    candidates = tuple(possible_answers)
    for guess, pattern in zip(path_guesses, path_patterns):
        candidates = tuple(
            answer for answer in candidates if score_guess(guess, answer) == pattern
        )
    return candidates


def format_tune_path_label(path_guesses, path_patterns):
    parts = []
    for index, guess in enumerate(path_guesses):
        parts.append(guess)
        parts.append(path_patterns[index])
    return " ".join(parts)


def play_tuned_path_game(
    answer,
    allowed_guesses,
    candidates,
    path_guesses,
    next_guess,
    strategy,
    probe_pool,
    trap_threshold,
    answer_weighting="off",
    small_candidate_order="normal",
):
    guesses = list(path_guesses)
    feedback = score_guess(next_guess, answer)
    guesses.append(next_guess)
    if is_solved(feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    remaining_candidates = filter_candidates_by_feedback(candidates, next_guess, feedback)
    while remaining_candidates:
        if answer in remaining_candidates and all(
            candidate in guesses for candidate in remaining_candidates
        ):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        later_guess = choose_later_strategy_guess(
            strategy,
            remaining_candidates,
            guesses,
            allowed_guesses,
            probe_pool,
            trap_threshold,
            answer_weighting,
            small_candidate_order,
        )
        feedback = score_guess(later_guess, answer)
        guesses.append(later_guess)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        remaining_candidates = filter_candidates_by_feedback(
            remaining_candidates,
            later_guess,
            feedback,
        )

    return GameResult(answer=answer, guesses=tuple(guesses), solved=False)


def build_tune_path_row(
    path_label,
    next_guess,
    candidate_count,
    games,
    candidates=(),
    branch_summary=False,
):
    summary = build_summary_row_from_games(next_guess, games)
    row = {
        "path": path_label,
        "next_guess": next_guess,
        "candidates": candidate_count,
        "average": summary["average"],
        "solved_4_or_less": summary["solved_4_or_less"],
        "fives": summary["fives"],
        "sixes": summary["sixes"],
        "failed": summary["failed"],
        "risk_score": summary["risk_score"],
    }
    if branch_summary:
        row.update(build_second_feedback_branch_summary(next_guess, candidates, games))
    return row


def print_tune_path_report(rows, branch_summary=False):
    if branch_summary:
        print(
            "Path  Next  Candidates  Avg   <=4   5s  6s  Fail  Risk  "
            "WorstNext  WorstN  Worst5s  WorstRisk"
        )
    else:
        print("Path  Next  Candidates  Avg   <=4   5s  6s  Fail  Risk")
    for row in rows:
        line = (
            f"{row['path']:<20} "
            f"{row['next_guess']:<6} "
            f"{row['candidates']:<11} "
            f"{row['average']:<5} "
            f"{row['solved_4_or_less']:<5} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['failed']:<5} "
            f"{row['risk_score']}"
        )
        if branch_summary:
            line += (
                f"     {row['worst_branch_pattern']:<9} "
                f"{row['worst_branch_candidates']:<7} "
                f"{row['worst_branch_fives']:<8} "
                f"{row['worst_branch_risk']}"
            )
        print(line)


def build_strategy_comparison_rows(
    allowed_guesses,
    possible_answers,
    first_guess="slate",
    use_overrides=None,
    answer_weighting="off",
    small_candidate_order="normal",
    endgame_threshold=25,
    max_expected_guesses=10,
    max_expected_states=50000,
    expected_depth=2,
    final_cluster_overrides="off",
):
    strategy_specs = (
        ("baseline", "", 2),
        ("second-map", "answers", 2),
        ("second-map", "allowed", 2),
        ("second-map-trap", "answers", 2),
        ("second-map-trap", "allowed", 2),
        ("second-map-bucket", "answers", 2),
        ("second-map-bucket", "allowed", 2),
        ("second-map-hybrid", "answers", 2),
        ("second-map-hybrid", "allowed", 2),
    )
    rows = []
    for strategy, second_guess_pool_name, trap_threshold in strategy_specs:
        row = build_strategy_row(
            strategy,
            first_guess,
            allowed_guesses,
            possible_answers,
            second_guess_pool_name=second_guess_pool_name or "allowed",
            trap_threshold=trap_threshold,
            use_overrides=use_overrides,
            answer_weighting=answer_weighting,
            small_candidate_order=small_candidate_order,
            endgame_threshold=endgame_threshold,
            max_expected_guesses=max_expected_guesses,
            max_expected_states=max_expected_states,
            expected_depth=expected_depth,
            final_cluster_overrides=final_cluster_overrides,
        )
        if strategy == "baseline":
            row = {**row, "second_guess_pool": "-"}
        rows.append(row)
    return tuple(rows)


def build_opener_strategy_comparison_rows(
    first_guesses,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool_name="allowed",
    trap_threshold=2,
    use_overrides=None,
    answer_weighting="off",
    small_candidate_order="normal",
    endgame_threshold=10,
    max_expected_guesses=10,
    max_expected_states=50000,
    expected_depth=2,
    final_cluster_overrides="off",
):
    rows = []
    for first_guess in first_guesses:
        first_guess = first_guess.lower()
        opener_use_overrides = use_overrides
        if first_guess != "slate":
            opener_use_overrides = False
        row = build_strategy_row(
            strategy,
            first_guess,
            allowed_guesses,
            possible_answers,
            second_guess_pool_name=second_guess_pool_name,
            trap_threshold=trap_threshold,
            use_overrides=opener_use_overrides,
            answer_weighting=answer_weighting,
            small_candidate_order=small_candidate_order,
            endgame_threshold=endgame_threshold,
            max_expected_guesses=max_expected_guesses,
            max_expected_states=max_expected_states,
            expected_depth=expected_depth,
            final_cluster_overrides=final_cluster_overrides,
        )
        rows.append(format_opener_strategy_row(row))
    return tuple(rows)


def format_opener_strategy_row(row):
    return {
        "first": row["first_guess"],
        "strategy": row["strategy"],
        "pool": row["second_guess_pool"] or "-",
        "tested": row["tested"],
        "solved": row["solved"],
        "average": row["average"],
        "solved_3_or_less": row["solved_3_or_less"],
        "solved_4_or_less": row["solved_4_or_less"],
        "fives": row["fives"],
        "sixes": row["sixes"],
        "failed": row["failed"],
        "risk_score": row["risk_score"],
    }


def build_strategy_row(
    strategy,
    first_guess,
    allowed_guesses,
    possible_answers,
    second_guess_pool_name="allowed",
    trap_threshold=2,
    use_overrides=None,
    answer_weighting="off",
    small_candidate_order="normal",
    endgame_threshold=25,
    max_expected_guesses=10,
    max_expected_states=50000,
    expected_depth=2,
    final_cluster_overrides="off",
):
    row, _games = build_strategy_result(
        strategy,
        first_guess,
        allowed_guesses,
        possible_answers,
        second_guess_pool_name=second_guess_pool_name,
        trap_threshold=trap_threshold,
        use_overrides=use_overrides,
        answer_weighting=answer_weighting,
        small_candidate_order=small_candidate_order,
        endgame_threshold=endgame_threshold,
        max_expected_guesses=max_expected_guesses,
        max_expected_states=max_expected_states,
        expected_depth=expected_depth,
        final_cluster_overrides=final_cluster_overrides,
    )
    return row


def build_strategy_result(
    strategy,
    first_guess,
    allowed_guesses,
    possible_answers,
    second_guess_pool_name="allowed",
    trap_threshold=2,
    use_overrides=None,
    answer_weighting="off",
    weighting_changes=None,
    small_candidate_order="normal",
    small_order_changes=None,
    endgame_threshold=25,
    max_expected_guesses=10,
    max_expected_states=50000,
    expected_depth=2,
    final_cluster_overrides="off",
    final_cluster_override_changes=None,
):
    if first_guess not in allowed_guesses:
        raise ValueError(f"First guess {first_guess!r} is not in the allowed guess list.")

    if strategy == "baseline":
        if (
            answer_weighting == "off"
            and small_candidate_order == "normal"
            and final_cluster_overrides == "off"
        ):
            result = run_simulation(
                allowed_guesses=allowed_guesses,
                possible_answers=possible_answers,
                first_guess=first_guess,
            )
            summary = build_comparison_row(first_guess, result)
            games = result.games
        else:
            games = tuple(
                play_baseline_game(
                    answer,
                    allowed_guesses,
                    possible_answers,
                    first_guess,
                    answer_weighting,
                    weighting_changes,
                    small_candidate_order,
                    small_order_changes,
                    final_cluster_overrides,
                    final_cluster_override_changes,
                )
                for answer in possible_answers
            )
            summary = build_summary_row_from_games(first_guess, games)
        return {
            "strategy": "baseline",
            "first_guess": first_guess,
            "second_guess_pool": "",
            **summary,
        }, games

    if strategy in {
        "second-map",
        "second-map-trap",
        "second-map-bucket",
        "second-map-expected",
        "second-map-hybrid",
    }:
        effective_use_overrides = (
            first_guess == "slate"
            and tuned_overrides_enabled(strategy, use_overrides)
        )
        second_guess_pool = (
            allowed_guesses if second_guess_pool_name == "allowed" else possible_answers
        )
        second_guess_rows = build_second_guess_map_rows(
            first_guess,
            allowed_guesses,
            possible_answers,
            second_guess_pool=second_guess_pool,
        )
        second_guess_by_pattern = {
            row["pattern"]: row["best_balanced"] for row in second_guess_rows
        }
        if effective_use_overrides:
            apply_second_guess_overrides(
                first_guess,
                second_guess_pool_name,
                second_guess_pool,
                second_guess_by_pattern,
            )
        expected_optimizer = None
        if strategy == "second-map-expected":
            expected_optimizer = ExpectedValueOptimizer(
                second_guess_pool,
                max_guesses=max_expected_guesses,
                max_states=max_expected_states,
                max_depth=expected_depth,
            )
        games = tuple(
            play_second_map_game(
                answer,
                allowed_guesses,
                possible_answers,
                first_guess,
                second_guess_by_pattern,
                use_trap_avoidance=(strategy == "second-map-trap"),
                use_bucket_strategy=(strategy in {"second-map-bucket", "second-map-expected"}),
                use_expected_strategy=(strategy == "second-map-expected"),
                use_hybrid_strategy=(strategy == "second-map-hybrid"),
                trap_threshold=trap_threshold,
                endgame_threshold=endgame_threshold,
                probe_pool=second_guess_pool,
                expected_optimizer=expected_optimizer,
                answer_weighting=answer_weighting,
                weighting_changes=weighting_changes,
                small_candidate_order=small_candidate_order,
                small_order_changes=small_order_changes,
                final_cluster_overrides=final_cluster_overrides,
                final_cluster_override_changes=final_cluster_override_changes,
                use_overrides=effective_use_overrides,
                second_guess_pool_name=second_guess_pool_name,
            )
            for answer in possible_answers
        )
        summary = build_summary_row_from_games(first_guess, games)
        row = {
            "strategy": strategy,
            "first_guess": first_guess,
            "second_guess_pool": second_guess_pool_name,
            **summary,
        }
        if expected_optimizer is not None:
            row.update(
                {
                    "expected_states": expected_optimizer.state_count,
                    "expected_fallbacks": expected_optimizer.fallback_count,
                }
            )
        return row, games

    raise ValueError(f"Unsupported strategy: {strategy}")


def play_second_map_game(
    answer,
    allowed_guesses,
    possible_answers,
    first_guess,
    second_guess_by_pattern,
    use_trap_avoidance=False,
    use_bucket_strategy=False,
    use_expected_strategy=False,
    use_hybrid_strategy=False,
    trap_threshold=2,
    endgame_threshold=25,
    probe_pool=None,
    expected_optimizer=None,
    answer_weighting="off",
    weighting_changes=None,
    small_candidate_order="normal",
    small_order_changes=None,
    final_cluster_overrides="off",
    final_cluster_override_changes=None,
    use_overrides=False,
    second_guess_pool_name="allowed",
):
    guesses = []
    candidates = tuple(possible_answers)
    if probe_pool is None:
        probe_pool = allowed_guesses

    first_feedback = score_guess(first_guess, answer)
    guesses.append(first_guess)
    if is_solved(first_feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    candidates = filter_candidates_by_feedback(candidates, first_guess, first_feedback)
    second_guess = second_guess_by_pattern[first_feedback]
    second_feedback = score_guess(second_guess, answer)
    guesses.append(second_guess)
    if is_solved(second_feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    candidates = filter_candidates_by_feedback(candidates, second_guess, second_feedback)
    path_override = None
    if use_overrides:
        path_override = find_path_guess_override(
            first_guess,
            first_feedback,
            second_guess,
            second_feedback,
            second_guess_pool_name,
            probe_pool,
            guesses,
        )
    while candidates:
        if path_override is not None:
            next_guess = path_override
            path_override = None
        else:
            next_guess = choose_next_guess_with_optional_probe(
                candidates,
                guesses,
                allowed_guesses,
                probe_pool,
                use_trap_avoidance,
                use_bucket_strategy,
                use_hybrid_strategy,
                trap_threshold,
                answer_weighting,
                weighting_changes,
                small_candidate_order,
                small_order_changes,
                answer,
                len(guesses) + 1,
                use_expected_strategy,
                endgame_threshold,
                expected_optimizer,
                final_cluster_overrides,
                final_cluster_override_changes,
            )
        feedback = score_guess(next_guess, answer)
        guesses.append(next_guess)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        candidates = filter_candidates_by_feedback(candidates, next_guess, feedback)

    return GameResult(answer=answer, guesses=tuple(guesses), solved=False)


def play_baseline_game(
    answer,
    allowed_guesses,
    possible_answers,
    first_guess,
    answer_weighting="off",
    weighting_changes=None,
    small_candidate_order="normal",
    small_order_changes=None,
    final_cluster_overrides="off",
    final_cluster_override_changes=None,
):
    guesses = []
    candidates = tuple(possible_answers)

    while candidates:
        if guesses:
            next_guess = choose_answer_candidate(
                candidates,
                guesses,
                allowed_guesses,
                answer_weighting,
                weighting_changes,
                answer,
                len(guesses) + 1,
                small_candidate_order,
                small_order_changes,
                final_cluster_overrides,
                final_cluster_override_changes,
            )
        else:
            next_guess = first_guess

        feedback = score_guess(next_guess, answer)
        guesses.append(next_guess)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        candidates = filter_candidates_by_feedback(candidates, next_guess, feedback)

    return GameResult(answer=answer, guesses=tuple(guesses), solved=False)


def filter_candidates_by_feedback(candidates, guess, feedback):
    return tuple(
        candidate for candidate in candidates if score_guess(guess, candidate) == feedback
    )


def choose_next_candidate(candidates, previous_guesses, allowed_guesses):
    return choose_answer_candidate(candidates, previous_guesses, allowed_guesses, "off")


def choose_answer_candidate(
    candidates,
    previous_guesses,
    allowed_guesses,
    answer_weighting,
    weighting_changes=None,
    answer=None,
    guess_number=None,
    small_candidate_order="normal",
    small_order_changes=None,
    final_cluster_overrides="off",
    final_cluster_override_changes=None,
):
    allowed = set(allowed_guesses)
    previous = set(previous_guesses)
    available_candidates = [
        candidate
        for candidate in candidates
        if candidate in allowed and candidate not in previous
    ]
    if not available_candidates:
        raise RuntimeError("No remaining candidate is available as a new guess.")
    if answer_weighting not in {"off", "simple"}:
        raise ValueError(f"Unsupported answer weighting mode: {answer_weighting}")
    if small_candidate_order not in {"normal", "likelihood"}:
        raise ValueError(f"Unsupported small-candidate order mode: {small_candidate_order}")
    if final_cluster_overrides not in {"off", "on"}:
        raise ValueError(f"Unsupported final-cluster override mode: {final_cluster_overrides}")

    unweighted_choice = available_candidates[0]
    base_choice = unweighted_choice
    if answer_weighting == "simple":
        base_choice = max(
            available_candidates,
            key=lambda candidate: (answer_likelihood_score(candidate), -candidates.index(candidate)),
        )
        if weighting_changes is not None and base_choice != unweighted_choice:
            weighting_changes.append(
                {
                    "answer": answer or "",
                    "guess_number": guess_number or 0,
                    "unweighted_choice": unweighted_choice,
                    "weighted_choice": base_choice,
                    "remaining_candidates": tuple(candidates),
                }
            )
    if final_cluster_overrides == "on":
        override_guess = find_final_cluster_override(candidates, previous_guesses)
        if override_guess is not None and override_guess in available_candidates:
            if final_cluster_override_changes is not None and override_guess != base_choice:
                final_cluster_override_changes.append(
                    {
                        "answer": answer or "",
                        "guess_number": guess_number or 0,
                        "normal_choice": base_choice,
                        "override_choice": override_guess,
                        "remaining_candidates": tuple(sorted(candidates)),
                    }
                )
            return override_guess
    if (
        small_candidate_order == "likelihood"
        and len(candidates) in (2, 3)
        and (guess_number or 0) >= 4
    ):
        ordered_choice = choose_small_candidate_by_likelihood(available_candidates)
        if small_order_changes is not None and ordered_choice != base_choice:
            small_order_changes.append(
                {
                    "answer": answer or "",
                    "guess_number": guess_number or 0,
                    "normal_choice": base_choice,
                    "ordered_choice": ordered_choice,
                    "remaining_candidates": tuple(candidates),
                }
            )
        return ordered_choice
    return base_choice


def answer_likelihood_score(word):
    score = 0
    common_letters = set("etaoinshrldcu")
    rare_letters = set("xzqj")
    very_rare_letters = set("qxzj")
    awkward_pairs = ("qx", "xq", "jq", "qj", "zx", "xz", "jj", "qq", "vv", "ww")
    common_endings = ("er", "ch", "sh", "th", "ck", "ly", "dy", "ny", "ry", "ty", "al", "el")

    for letter in word:
        if letter in common_letters:
            score += 2
        if letter in rare_letters:
            score -= 4

    positional_bonus = (
        set("scrptb"),
        set("aeoril"),
        set("aironeu"),
        set("nteral"),
        set("eytrhd"),
    )
    for index, letter in enumerate(word):
        if index < len(positional_bonus) and letter in positional_bonus[index]:
            score += 2

    repeated_letters = len(word) - len(set(word))
    if repeated_letters:
        score -= 4 * repeated_letters
        if any(word.count(letter) > 1 and letter in very_rare_letters for letter in set(word)):
            score -= 6

    if word.endswith(common_endings):
        score += 4
    if word[-1] in "eytldr":
        score += 2
    if word[1] in "aeiou" or word[2] in "aeiou":
        score += 2
    if sum(1 for letter in word if letter in "aeiou") in (1, 2):
        score += 2

    for pair in awkward_pairs:
        if pair in word:
            score -= 5

    if "q" in word and "qu" not in word:
        score -= 6

    return score


def choose_small_candidate_by_likelihood(available_candidates):
    preference_key = tuple(sorted(available_candidates))
    preferred_order = SMALL_CANDIDATE_ORDER_PREFERENCES.get(preference_key)
    if not preferred_order:
        return available_candidates[0]
    available = set(available_candidates)
    for candidate in preferred_order:
        if candidate in available:
            return candidate
    return available_candidates[0]


def find_final_cluster_override(candidates, previous_guesses):
    key = tuple(sorted(candidates))
    override_guess = FINAL_CLUSTER_OVERRIDES.get(key)
    if override_guess is None or override_guess in previous_guesses:
        return None
    if override_guess not in candidates:
        return None
    return override_guess


def choose_next_candidate_weighted(candidates, previous_guesses, allowed_guesses):
    return choose_answer_candidate(candidates, previous_guesses, allowed_guesses, "simple")


def choose_next_candidate_unweighted(candidates, previous_guesses, allowed_guesses):
    return choose_answer_candidate(candidates, previous_guesses, allowed_guesses, "off")


def choose_next_candidate_from_available(candidates, previous_guesses, allowed_guesses):
    for candidate in candidates:
        if candidate in allowed_guesses and candidate not in previous_guesses:
            return candidate
    raise RuntimeError("No remaining candidate is available as a new guess.")


class ExpectedValueOptimizer:
    def __init__(self, guess_pool, max_guesses=10, max_states=50000, max_depth=2):
        self.guess_pool = tuple(guess_pool)
        self.max_guesses = max_guesses
        self.max_states = max_states
        self.max_depth = max_depth
        self.state_count = 0
        self.fallback_count = 0

    def choose_guess(self, candidates, previous_guesses=()):
        candidates = tuple(candidates)
        previous_guesses = tuple(previous_guesses)
        if not candidates:
            raise RuntimeError("No remaining candidates for expected-value search.")
        if len(candidates) == 1:
            return candidates[0]
        if self.state_count >= self.max_states:
            self.fallback_count += 1
            return self.bucket_fallback_guess(candidates, previous_guesses)

        best_guess = None
        best_rank = None
        for guess in self._candidate_guesses(candidates, previous_guesses):
            expected_guesses = self._guess_expected_total(
                guess,
                candidates,
                previous_guesses,
                self.max_depth,
            )
            if expected_guesses == float("inf"):
                continue
            rank = (expected_guesses, guess not in candidates, guess)
            if best_rank is None or rank < best_rank:
                best_guess = guess
                best_rank = rank

        if best_guess is None:
            self.fallback_count += 1
            return self.bucket_fallback_guess(candidates, previous_guesses)
        return best_guess

    @cache
    def expected_total(self, candidates, previous_guesses, depth_remaining):
        self.state_count += 1
        candidates = tuple(candidates)
        previous_guesses = tuple(previous_guesses)
        if len(candidates) <= 1:
            return 1.0
        if depth_remaining <= 0 or self.state_count >= self.max_states:
            return self.estimate_remaining(candidates)

        best_value = float("inf")
        for guess in self._candidate_guesses(candidates, previous_guesses):
            value = self._guess_expected_total(
                guess,
                candidates,
                previous_guesses,
                depth_remaining,
            )
            if value < best_value:
                best_value = value
        return best_value

    def _guess_expected_total(self, guess, candidates, previous_guesses, depth_remaining):
        buckets = self._feedback_buckets(guess, candidates)
        total = 1.0
        candidate_count = len(candidates)
        next_previous = tuple((*previous_guesses, guess))

        for feedback, bucket in buckets.items():
            if is_solved(feedback):
                continue
            next_candidates = tuple(bucket)
            if next_candidates == candidates:
                return float("inf")
            total += (
                len(next_candidates)
                / candidate_count
                * self.expected_total(next_candidates, next_previous, depth_remaining - 1)
            )
        return total

    def estimate_remaining(self, candidates):
        bucket_count = max(1, len(set(score_guess(candidates[0], answer) for answer in candidates)))
        return max(1.0, len(candidates) / bucket_count)

    def bucket_fallback_guess(self, candidates, previous_guesses):
        probe = choose_bucket_probe(candidates, previous_guesses, self.guess_pool)
        if probe is not None:
            return probe
        return choose_answer_candidate(candidates, previous_guesses, candidates, "off")

    def _feedback_buckets(self, guess, candidates):
        buckets = defaultdict(list)
        for candidate in candidates:
            buckets[score_guess(guess, candidate)].append(candidate)
        return buckets

    def _candidate_guesses(self, candidates, previous_guesses):
        previous = set(previous_guesses)
        ranked_guesses = sorted(
            (guess for guess in candidates if guess in self.guess_pool and guess not in previous),
            key=lambda guess: bucket_probe_rank(guess, candidates),
        )
        return tuple(ranked_guesses[: self.max_guesses])


def choose_next_guess_with_optional_probe(
    candidates,
    previous_guesses,
    allowed_guesses,
    probe_pool,
    use_trap_avoidance,
    use_bucket_strategy=False,
    use_hybrid_strategy=False,
    trap_threshold=2,
    answer_weighting="off",
    weighting_changes=None,
    small_candidate_order="normal",
    small_order_changes=None,
    answer=None,
    guess_number=None,
    use_expected_strategy=False,
    endgame_threshold=25,
    expected_optimizer=None,
    final_cluster_overrides="off",
    final_cluster_override_changes=None,
):
    if final_cluster_overrides == "on":
        override_guess = find_final_cluster_override(candidates, previous_guesses)
        if override_guess is not None:
            normal_choice = choose_answer_candidate(
                candidates,
                previous_guesses,
                allowed_guesses,
                answer_weighting,
                None,
                answer,
                guess_number,
                "normal",
                None,
            )
            if (
                final_cluster_override_changes is not None
                and override_guess != normal_choice
            ):
                final_cluster_override_changes.append(
                    {
                        "answer": answer or "",
                        "guess_number": guess_number or 0,
                        "normal_choice": normal_choice,
                        "override_choice": override_guess,
                        "remaining_candidates": tuple(sorted(candidates)),
                    }
                )
            return override_guess
    elif final_cluster_overrides != "off":
        raise ValueError(f"Unsupported final-cluster override mode: {final_cluster_overrides}")

    if (
        use_expected_strategy
        and expected_optimizer is not None
        and len(candidates) <= endgame_threshold
    ):
        return expected_optimizer.choose_guess(candidates, previous_guesses)
    if small_candidate_order == "likelihood" and len(candidates) in (2, 3):
        return choose_answer_candidate(
            candidates,
            previous_guesses,
            allowed_guesses,
            answer_weighting,
            weighting_changes,
            answer,
            guess_number,
            small_candidate_order,
            small_order_changes,
        )
    if use_hybrid_strategy:
        return choose_hybrid_guess(
            candidates,
            previous_guesses,
            allowed_guesses,
            probe_pool,
            trap_threshold,
            answer_weighting,
            weighting_changes,
            small_candidate_order,
            small_order_changes,
            answer,
            guess_number,
        )
    if use_bucket_strategy:
        probe = choose_bucket_probe(candidates, previous_guesses, probe_pool)
        if probe is not None:
            return probe
        return choose_answer_candidate(
            candidates,
            previous_guesses,
            allowed_guesses,
            answer_weighting,
            weighting_changes,
            answer,
            guess_number,
            small_candidate_order,
            small_order_changes,
        )
    if use_trap_avoidance and is_trap_family(candidates):
        probe = choose_trap_probe(candidates, previous_guesses, probe_pool)
        if probe is not None:
            return probe
    return choose_answer_candidate(
        candidates,
        previous_guesses,
        allowed_guesses,
        answer_weighting,
        weighting_changes,
        answer,
        guess_number,
        small_candidate_order,
        small_order_changes,
    )


def choose_hybrid_guess(
    candidates,
    previous_guesses,
    allowed_guesses,
    probe_pool,
    trap_threshold,
    answer_weighting="off",
    weighting_changes=None,
    small_candidate_order="normal",
    small_order_changes=None,
    answer=None,
    guess_number=None,
):
    normal_guess = choose_answer_candidate(
        candidates,
        previous_guesses,
        allowed_guesses,
        answer_weighting,
        weighting_changes,
        answer,
        guess_number,
        small_candidate_order,
        small_order_changes,
    )
    normal_max_bucket = max(feedback_bucket_sizes(normal_guess, candidates))
    if normal_max_bucket > trap_threshold:
        return choose_bucket_probe(candidates, previous_guesses, probe_pool)
    return normal_guess


def choose_bucket_probe(candidates, previous_guesses, probe_pool):
    previous = set(previous_guesses)
    candidates = tuple(candidates)
    best_guess = None
    best_rank = None

    for guess in probe_pool:
        if guess in previous:
            continue
        rank = bucket_probe_rank(guess, candidates)
        if best_rank is None or rank < best_rank:
            best_guess = guess
            best_rank = rank

    return best_guess


def bucket_probe_rank(guess, candidates):
    bucket_sizes = feedback_bucket_sizes(guess, candidates)
    max_bucket_size = max(bucket_sizes)
    expected_remaining = sum(size * size for size in bucket_sizes) / len(candidates)
    is_not_candidate = guess not in set(candidates)
    return (max_bucket_size, expected_remaining, is_not_candidate, guess)


def feedback_bucket_sizes(guess, candidates):
    buckets = Counter(score_guess(guess, candidate) for candidate in candidates)
    return tuple(buckets.values())


def is_trap_family(candidates):
    if len(candidates) <= 2:
        return False
    fixed_positions = 0
    for letters in zip(*candidates):
        if len(set(letters)) == 1:
            fixed_positions += 1
    return fixed_positions >= 4


def choose_trap_probe(candidates, previous_guesses, probe_pool):
    target_letters = differing_letters(candidates)
    previous = set(previous_guesses)
    candidate_set = set(candidates)
    best_probe = None
    best_rank = (-1, False)

    for guess in probe_pool:
        if guess in previous:
            continue
        score = len(set(guess) & target_letters)
        rank = (score, guess not in candidate_set)
        if rank > best_rank:
            best_probe = guess
            best_rank = rank

    return best_probe


def differing_letters(candidates):
    letters = set()
    for position_letters in zip(*candidates):
        unique_letters = set(position_letters)
        if len(unique_letters) > 1:
            letters.update(unique_letters)
    return letters


def build_summary_row_from_games(first_guess, games):
    distribution = Counter({guess_count: 0 for guess_count in range(1, 7)})
    solved = 0
    total_guesses = 0
    for game in games:
        total_guesses += game.guess_count
        if game.solved:
            solved += 1
            if game.guess_count in distribution:
                distribution[game.guess_count] += 1
    tested = len(games)
    average_guesses = total_guesses / tested if tested else 0
    return build_summary_row(
        first_guess=first_guess,
        tested=tested,
        solved=solved,
        average_guesses=average_guesses,
        distribution=distribution,
        failed=tested - solved,
    )


def build_worst_game_rows(games, limit, possible_answers=None):
    solved_games = [game for game in games if game.solved]
    worst_games = sorted(
        solved_games,
        key=lambda game: (-game.guess_count, game.answer),
    )
    return tuple(
        format_worst_game_row(game, possible_answers) for game in worst_games[:limit]
    )


def build_worst_pattern_rows(games, limit=None):
    grouped_games = defaultdict(list)
    for game in games:
        if not game.solved or not game.guesses:
            continue
        pattern = score_guess(game.guesses[0], game.answer)
        grouped_games[pattern].append(game)

    rows = tuple(format_worst_pattern_row(pattern, group) for pattern, group in grouped_games.items())
    ranked_rows = sorted(
        rows,
        key=lambda row: (-row["risk"], -float(row["average"]), row["pattern"]),
    )
    if limit is None:
        return tuple(ranked_rows)
    return tuple(ranked_rows[:limit])


def build_worst_prefix_rows(games, limit, prefix_lengths=(2, 3, 4)):
    grouped_games = defaultdict(list)
    for game in games:
        if not game.solved or game.guess_count < 5:
            continue
        for prefix_length in prefix_lengths:
            if len(game.guesses) >= prefix_length:
                grouped_games[game.guesses[:prefix_length]].append(game)

    rows = tuple(
        format_worst_prefix_row(prefix, group)
        for prefix, group in grouped_games.items()
    )
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            -row["risk"],
            -row["fives"],
            -row["sixes"],
            row["prefix"],
        ),
    )
    return tuple(ranked_rows[:limit])


def build_final_cluster_rows(games, possible_answers, limit):
    grouped_games = defaultdict(list)
    for game in games:
        if not game.solved or game.guess_count < 5 or len(game.guesses) < 4:
            continue
        candidates = candidates_before_guess(game, possible_answers, guess_number=4)
        grouped_games[candidates].append(game)

    rows = tuple(
        format_final_cluster_row(candidates, group)
        for candidates, group in grouped_games.items()
    )
    ranked_rows = sorted(
        rows,
        key=lambda row: (-row["risk"], -row["games"], row["candidates"]),
    )
    return tuple(ranked_rows[:limit])


def candidates_before_guess(game, possible_answers, guess_number):
    candidates = tuple(possible_answers)
    for guess in game.guesses[: guess_number - 1]:
        feedback = score_guess(guess, game.answer)
        if is_solved(feedback):
            break
        candidates = filter_candidates_by_feedback(candidates, guess, feedback)
    return tuple(sorted(candidates))


def format_final_cluster_row(candidates, games):
    fives = sum(1 for game in games if game.guess_count == 5)
    sixes = sum(1 for game in games if game.guess_count == 6)
    risk = fives * 2 + sixes * 5
    fourth_guesses = Counter(game.guesses[3] for game in games if len(game.guesses) >= 4)
    fourth_guess_used = ", ".join(
        guess for guess, _count in sorted(fourth_guesses.items(), key=lambda item: (-item[1], item[0]))[:3]
    )
    sample_answers = ", ".join(sorted(game.answer for game in games)[:5])
    return {
        "candidates": "/".join(candidates),
        "games": len(games),
        "fives": fives,
        "sixes": sixes,
        "risk": risk,
        "fourth_guess_used": fourth_guess_used,
        "sample_answers": sample_answers,
    }


def format_worst_prefix_row(prefix, games):
    fives = sum(1 for game in games if game.guess_count == 5)
    sixes = sum(1 for game in games if game.guess_count == 6)
    risk = fives * 2 + sixes * 5
    sample_answers = ", ".join(sorted(game.answer for game in games)[:5])
    return {
        "prefix": " -> ".join(prefix),
        "games": len(games),
        "fives": fives,
        "sixes": sixes,
        "risk": risk,
        "sample_answers": sample_answers,
    }


def format_worst_pattern_row(pattern, games):
    total_games = len(games)
    guess_counts = [game.guess_count for game in games]
    fives = sum(1 for count in guess_counts if count == 5)
    sixes = sum(1 for count in guess_counts if count == 6)
    risk = fives * 2 + sixes * 5
    average_guesses = sum(guess_counts) / total_games if total_games else 0
    max_guesses = max(guess_counts) if guess_counts else 0
    return {
        "pattern": pattern,
        "total_games": total_games,
        "average": f"{average_guesses:.2f}",
        "fives": fives,
        "sixes": sixes,
        "max_guesses": max_guesses,
        "risk": risk,
    }


def format_worst_game_row(game, possible_answers=None):
    feedbacks = tuple(score_guess(guess, game.answer) for guess in game.guesses)
    path = " -> ".join(game.guesses)
    if possible_answers is not None:
        path = format_candidate_trace_path(game, possible_answers)
    return {
        "answer": game.answer,
        "guess_count": game.guess_count,
        "path": path,
        "feedback": " -> ".join(feedbacks),
    }


def format_candidate_trace_path(game, possible_answers):
    candidates = tuple(possible_answers)
    parts = []
    for guess in game.guesses:
        parts.append(f"{guess}({len(candidates)})")
        feedback = score_guess(guess, game.answer)
        if is_solved(feedback):
            break
        candidates = filter_candidates_by_feedback(candidates, guess, feedback)
    return " -> ".join(parts)


def print_worst_games(rows):
    print("Worst games:")
    print("answer  guesses  path")
    for row in rows:
        print(
            f"{row['answer']:<7} "
            f"{row['guess_count']:<8} "
            f"{row['path']} "
            f"({row['feedback']})"
        )


def print_worst_patterns(rows):
    print("Worst patterns:")
    print("pattern  games  avg   5s  6s  max  risk")
    for row in rows:
        print(
            f"{row['pattern']:<8} "
            f"{row['total_games']:<6} "
            f"{row['average']:<5} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['max_guesses']:<4} "
            f"{row['risk']}"
        )


def print_worst_prefixes(rows):
    print("Worst prefixes:")
    print("prefix  games  5s  6s  risk  sample_answers")
    for row in rows:
        print(
            f"{row['prefix']:<30} "
            f"{row['games']:<6} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['risk']:<5} "
            f"{row['sample_answers']}"
        )


def print_final_clusters(rows):
    print("Final clusters:")
    print("candidates  games  5s  6s  risk  fourth_guess_used  sample_answers")
    for row in rows:
        print(
            f"{row['candidates']:<30} "
            f"{row['games']:<6} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['risk']:<5} "
            f"{row['fourth_guess_used']:<18} "
            f"{row['sample_answers']}"
        )


def print_weighting_changes(changes, enabled=True, limit=25):
    if not enabled:
        print("Weighting changed decisions: 0")
        print("Games affected: 0")
        return

    affected_games = {change["answer"] for change in changes if change["answer"]}
    print(f"Weighting changed decisions: {len(changes)}")
    print(f"Games affected: {len(affected_games)}")
    if not changes:
        return

    print("Weighting change examples:")
    print("answer  guess#  unweighted  weighted  remaining_candidates")
    for change in changes[:limit]:
        print(
            f"{change['answer']:<7} "
            f"{change['guess_number']:<7} "
            f"{change['unweighted_choice']:<11} "
            f"{change['weighted_choice']:<8} "
            f"{format_remaining_candidates(change['remaining_candidates'])}"
        )


def print_small_order_changes(changes, enabled=True, limit=25):
    if not enabled:
        print("Small-order changed decisions: 0")
        print("Games affected: 0")
        return

    affected_games = {change["answer"] for change in changes if change["answer"]}
    print(f"Small-order changed decisions: {len(changes)}")
    print(f"Games affected: {len(affected_games)}")
    if not changes:
        return

    print("Small-order change examples:")
    print("answer  guess#  normal  ordered  remaining_candidates")
    for change in changes[:limit]:
        print(
            f"{change['answer']:<7} "
            f"{change['guess_number']:<7} "
            f"{change['normal_choice']:<7} "
            f"{change['ordered_choice']:<8} "
            f"{format_remaining_candidates(change['remaining_candidates'])}"
        )


def print_final_cluster_override_changes(changes, enabled=True, limit=25):
    if not enabled:
        print("Final-cluster override changed decisions: 0")
        print("Games affected: 0")
        return

    affected_games = {change["answer"] for change in changes if change["answer"]}
    print(f"Final-cluster override changed decisions: {len(changes)}")
    print(f"Games affected: {len(affected_games)}")
    if not changes:
        return

    print("Final-cluster override examples:")
    print("answer  guess#  normal  override  remaining_candidates")
    for change in changes[:limit]:
        print(
            f"{change['answer']:<7} "
            f"{change['guess_number']:<7} "
            f"{change['normal_choice']:<7} "
            f"{change['override_choice']:<8} "
            f"{format_remaining_candidates(change['remaining_candidates'])}"
        )


def format_remaining_candidates(candidates, limit=12):
    shown = ", ".join(candidates[:limit])
    if len(candidates) > limit:
        return f"{shown}..."
    return shown


def print_strategy_report(rows):
    print("Strategy    First  Pool     Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk")
    for row in rows:
        print(
            f"{row['strategy']:<11} "
            f"{row['first_guess']:<6} "
            f"{row['second_guess_pool'] or '-':<8} "
            f"{row['tested']:<7} "
            f"{row['solved']:<7} "
            f"{row['average']:<5} "
            f"{row['solved_3_or_less']:<5} "
            f"{row['solved_4_or_less']:<5} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['failed']:<5} "
            f"{row['risk_score']}"
        )


def print_opener_strategy_report(rows):
    print("First   Strategy    Pool     Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk")
    for row in rows:
        print(
            f"{row['first']:<7} "
            f"{row['strategy']:<11} "
            f"{row['pool']:<8} "
            f"{row['tested']:<7} "
            f"{row['solved']:<7} "
            f"{row['average']:<5} "
            f"{row['solved_3_or_less']:<5} "
            f"{row['solved_4_or_less']:<5} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['failed']:<5} "
            f"{row['risk_score']}"
        )


def build_second_guess_map_rows(
    first_guess,
    allowed_guesses,
    possible_answers,
    second_guess_pool=None,
):
    if first_guess not in allowed_guesses:
        raise ValueError(f"First guess {first_guess!r} is not in the allowed guess list.")
    if second_guess_pool is None:
        second_guess_pool = allowed_guesses

    grouped_answers = defaultdict(list)
    for answer in possible_answers:
        grouped_answers[score_guess(first_guess, answer)].append(answer)

    rows = []
    for pattern in sorted(grouped_answers):
        candidates = tuple(grouped_answers[pattern])
        scorer = TopOpenerScorer(allowed_guesses, candidates)
        scored_rows = tuple(scorer.score_opener(guess) for guess in second_guess_pool)
        best_average = min(scored_rows, key=_rank_key("average"))
        best_balanced = min(scored_rows, key=_rank_key("balanced"))
        rows.append(
            {
                "pattern": pattern,
                "candidates": len(candidates),
                "best_average": best_average["first_guess"],
                "best_balanced": best_balanced["first_guess"],
                "sample_answers": format_sample_answers(candidates),
            }
        )
    return tuple(rows)


def format_sample_answers(answers, sample_size=3):
    samples = ", ".join(answers[:sample_size])
    if len(answers) > sample_size:
        return f"{samples}..."
    return samples


def print_second_guess_map(rows):
    print("Pattern  Candidates  Best Avg  Best Balanced  Sample answers")
    for row in rows:
        print(
            f"{row['pattern']:<8} "
            f"{row['candidates']:<11} "
            f"{row['best_average']:<9} "
            f"{row['best_balanced']:<14} "
            f"{row['sample_answers']}"
        )


def build_comparison_rows(first_guesses, allowed_guesses, possible_answers):
    rows = []
    for first_guess in first_guesses:
        normalized_first_guess = first_guess.lower()
        result = run_simulation(
            allowed_guesses=allowed_guesses,
            possible_answers=possible_answers,
            first_guess=normalized_first_guess,
        )
        rows.append(build_comparison_row(normalized_first_guess, result))
    return tuple(rows)


def build_top_opener_rows(
    limit,
    opener_guesses,
    allowed_guesses,
    possible_answers,
    rank_by="average",
    show_progress=False,
    progress_every=100,
):
    scorer = TopOpenerScorer(allowed_guesses, possible_answers)
    rows = []
    total_openers = len(opener_guesses)
    for index, first_guess in enumerate(opener_guesses, start=1):
        rows.append(scorer.score_opener(first_guess))
        if show_progress and index % progress_every == 0:
            print(f"Tested {index}/{total_openers} openers...")

    ranked_rows = sorted(rows, key=_rank_key(rank_by))
    return tuple(ranked_rows[:limit])


def _rank_key(rank_by):
    if rank_by == "average":
        return lambda row: (float(row["average"]), row["first_guess"])
    if rank_by == "risk":
        return lambda row: (row["risk_score"], float(row["average"]), row["first_guess"])
    if rank_by == "balanced":
        return lambda row: (
            row["risk_score"],
            float(row["average"]),
            -row["solved_3_or_less"],
            row["first_guess"],
        )
    raise ValueError(f"Unsupported rank method: {rank_by}")


def build_comparison_row(first_guess, result):
    distribution = result.guess_distribution
    return build_summary_row(
        first_guess=first_guess,
        tested=len(result.games),
        solved=result.solved_count,
        average_guesses=result.average_guesses,
        distribution=distribution,
        failed=result.failed_count,
    )


def build_summary_row(first_guess, tested, solved, average_guesses, distribution, failed):
    solved_in_3_or_fewer = sum(distribution[guess_count] for guess_count in range(1, 4))
    solved_in_4_or_fewer = sum(distribution[guess_count] for guess_count in range(1, 5))
    risk_score = distribution[5] * 2 + distribution[6] * 5 + failed * 20
    return {
        "first_guess": first_guess,
        "tested": tested,
        "solved": solved,
        "average": f"{average_guesses:.2f}",
        "solved_3_or_less": solved_in_3_or_fewer,
        "solved_4_or_less": solved_in_4_or_fewer,
        "fives": distribution[5],
        "sixes": distribution[6],
        "failed": failed,
        "risk_score": risk_score,
    }


class TopOpenerScorer:
    """Fast scorer for top-opener sweeps over one fixed answer list."""

    def __init__(self, allowed_guesses, possible_answers):
        self.allowed_guesses = allowed_guesses
        self.possible_answers = possible_answers
        self.answer_indices = tuple(range(len(possible_answers)))
        self.solved_feedback = "G" * len(possible_answers[0]) if possible_answers else ""

    @cache
    def feedbacks_for_guess(self, guess):
        return tuple(score_guess(guess, answer) for answer in self.possible_answers)

    def score_opener(self, first_guess):
        distribution = Counter({guess_count: 0 for guess_count in range(1, 7)})
        feedbacks = self.feedbacks_for_guess(first_guess)
        buckets = self._partition_indices(self.answer_indices, feedbacks)

        for feedback, answer_indices in buckets.items():
            if is_solved(feedback):
                distribution[1] += len(answer_indices)
                continue

            candidates = tuple(answer_indices)
            for answer_index in candidates:
                guess_count = 1 + self._guesses_from_candidates(answer_index, candidates)
                distribution[guess_count] += 1

        tested = len(self.possible_answers)
        solved = sum(distribution.values())
        average_guesses = (
            sum(guess_count * count for guess_count, count in distribution.items()) / tested
            if tested
            else 0
        )
        return build_summary_row(
            first_guess=first_guess,
            tested=tested,
            solved=solved,
            average_guesses=average_guesses,
            distribution=distribution,
            failed=tested - solved,
        )

    @cache
    def _guesses_from_candidates(self, answer_index, candidates):
        guess_index = candidates[0]
        if guess_index == answer_index:
            return 1

        guess = self.possible_answers[guess_index]
        feedback = self.feedbacks_for_guess(guess)[answer_index]
        next_candidates = tuple(
            candidate_index
            for candidate_index in candidates
            if self.feedbacks_for_guess(guess)[candidate_index] == feedback
        )
        return 1 + self._guesses_from_candidates(answer_index, next_candidates)

    def _partition_indices(self, indices, feedbacks):
        buckets = defaultdict(list)
        for answer_index in indices:
            buckets[feedbacks[answer_index]].append(answer_index)
        return buckets


def print_comparison_report(rows):
    print("First   Tested  Solved  Avg   <=3   <=4   5s  6s  Fail  Risk")
    for row in rows:
        print(format_comparison_row(row))


def format_comparison_row(row):
    return (
        f"{row['first_guess']:<7} "
        f"{row['tested']:<7} "
        f"{row['solved']:<7} "
        f"{row['average']:<5} "
        f"{row['solved_3_or_less']:<5} "
        f"{row['solved_4_or_less']:<5} "
        f"{row['fives']:<3} "
        f"{row['sixes']:<3} "
        f"{row['failed']:<5} "
        f"{row['risk_score']}"
    )


def write_comparison_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_second_guess_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SECOND_GUESS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_strategy_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=STRATEGY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_opener_strategy_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OPENER_STRATEGY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_tune_pattern_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = (
            TUNE_PATTERN_BRANCH_COLUMNS
            if rows and "worst_branch_pattern" in rows[0]
            else TUNE_PATTERN_COLUMNS
        )
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_tune_branch_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=TUNE_BRANCH_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_tune_path_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = (
            TUNE_PATH_BRANCH_COLUMNS
            if rows and "worst_branch_pattern" in rows[0]
            else TUNE_PATH_COLUMNS
        )
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def worst_csv_path(path):
    csv_path = Path(path)
    return csv_path.with_name(f"{csv_path.stem}_worst{csv_path.suffix}")


def write_worst_games_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=WORST_GAME_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
