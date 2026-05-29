"""Command-line entry point for Wordle Lab."""

import argparse
import csv
import re
import time
from collections import Counter, defaultdict
from datetime import date
from functools import cache
from pathlib import Path

from .scoring import is_solved, score_guess
from .simulator import (
    DEFAULT_ALLOWED_GUESSES_PATH,
    DEFAULT_ANSWERS_PATH,
    DEFAULT_FIRST_GUESS,
    DEFAULT_PRIOR_ANSWERS_DATED_PATH,
    DEFAULT_PRIOR_ANSWERS_PATH,
    GameResult,
    load_words,
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

TUNE_PATTERN_WEIGHTED_COLUMNS = TUNE_PATTERN_COLUMNS + (
    "weighted_avg",
    "weighted_5s",
    "weighted_6s",
    "weighted_risk",
)

TUNE_PATTERN_BRANCH_COLUMNS = TUNE_PATTERN_COLUMNS + (
    "worst_branch_pattern",
    "worst_branch_candidates",
    "worst_branch_fives",
    "worst_branch_risk",
)

TUNE_PATTERN_WEIGHTED_BRANCH_COLUMNS = TUNE_PATTERN_WEIGHTED_COLUMNS + (
    "worst_branch_pattern",
    "worst_branch_candidates",
    "worst_branch_fives",
    "worst_branch_risk",
)

BUILT_SECOND_MAP_COLUMNS = (
    "first",
    "pattern",
    "candidates",
    "best_second",
    "average",
    "solved_3_or_less",
    "solved_4_or_less",
    "fives",
    "sixes",
    "failed",
    "risk_score",
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

HUMAN_MODE_SECOND_GUESS_OVERRIDES = {
    ("slate", "....Y", "answers", "downweight"): "drown",
    ("slate", "..YY.", "answers", "downweight"): "hound",
    ("slate", "..Y.Y", "answers", "downweight"): "began",
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
        "--prior-stats",
        action="store_true",
        help="show prior-answer statistics",
    )
    mode.add_argument(
        "--prior-dated-stats",
        action="store_true",
        help="show dated prior-answer statistics",
    )
    mode.add_argument(
        "--clean-prior-source",
        nargs=2,
        metavar=("INPUT", "OUTPUT"),
        help="clean a pasted historical answer source into a prior-answer word list",
    )
    mode.add_argument(
        "--second-guess-map",
        metavar="FIRST",
        help="map first-guess feedback patterns to recommended second guesses",
    )
    mode.add_argument(
        "--build-second-map",
        metavar="FIRST",
        help="build a tuned second-guess map for every first-feedback pattern",
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
    mode.add_argument(
        "--recommend",
        action="store_true",
        help="recommend the next guess from a partial game state",
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
        "--weighted-worst-patterns",
        type=int,
        metavar="N",
        help="show first-feedback patterns ranked by weighted Human Mode risk for --strategy",
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
        choices=("risk", "branch-safe", "safe-balanced", "weighted-risk"),
        default="risk",
        help="ranking objective for --tune-pattern (default: risk)",
    )
    parser.add_argument(
        "--use-built-second-map",
        metavar="PATH",
        help="use a CSV built by --build-second-map instead of the default second map",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rebuild resumable outputs from scratch",
    )
    parser.add_argument(
        "--only-pattern",
        action="append",
        metavar="PATTERN",
        help="build only this first-feedback pattern; may be repeated",
    )
    parser.add_argument(
        "--max-patterns",
        type=int,
        metavar="N",
        help="build at most N selected first-feedback patterns",
    )
    parser.add_argument(
        "--only-worst-patterns",
        type=int,
        metavar="N",
        help="for --build-second-map, build only the N worst first-feedback patterns for the selected strategy",
    )
    parser.add_argument(
        "--min-candidates",
        type=int,
        default=1,
        metavar="N",
        help="for --build-second-map, skip patterns with fewer than N candidate answers (default: 1)",
    )
    parser.add_argument(
        "--max-second-guesses",
        type=int,
        metavar="N",
        help="for --build-second-map, evaluate at most N second guesses per pattern",
    )
    parser.add_argument(
        "--second-guess-candidates",
        choices=("top", "all"),
        default="all",
        help="second-guess candidate selection for --build-second-map (default: all)",
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
        "--state",
        nargs="+",
        metavar="STEP",
        help="alternating guess/feedback pairs for --recommend",
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
    parser.add_argument(
        "--prior-answers",
        default=str(DEFAULT_PRIOR_ANSWERS_PATH),
        help=f"prior answer word list (default: {DEFAULT_PRIOR_ANSWERS_PATH})",
    )
    parser.add_argument(
        "--prior-answers-dated",
        default=str(DEFAULT_PRIOR_ANSWERS_DATED_PATH),
        help=f"dated prior answer CSV (default: {DEFAULT_PRIOR_ANSWERS_DATED_PATH})",
    )
    parser.add_argument(
        "--prior-policy",
        choices=("ignore", "exclude", "downweight"),
        default="ignore",
        help="how to treat prior answers while solving (default: ignore)",
    )
    parser.add_argument(
        "--as-of-date",
        metavar="YYYY-MM-DD",
        help="date to use for dated prior-answer weighting",
    )
    parser.add_argument(
        "--show-prior-weighting-changes",
        action="store_true",
        help="show where dated prior weighting changes answer choices",
    )
    parser.add_argument(
        "--show-small-candidate-events",
        type=int,
        metavar="N",
        help="show the first N times a strategy reaches 2-5 remaining candidates",
    )
    parser.add_argument(
        "--prior-weight-stats",
        action="store_true",
        help="show answer counts by dated prior-answer weight bucket",
    )
    parser.add_argument(
        "--show-weighted-score",
        action="store_true",
        help="show weighted human-mode score for strategy runs",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.csv and not (
        args.compare or args.compare_openers_with_strategy or args.top_openers
        or args.second_guess_map or args.build_second_map or args.strategy
        or args.compare_strategies or args.tune_pattern or args.tune_branch
        or args.tune_path or args.recommend
    ):
        raise SystemExit(
            "--csv can only be used with --compare, --compare-openers-with-strategy, --top-openers, --second-guess-map, --build-second-map, --strategy, --compare-strategies, --tune-pattern, --tune-branch, or --tune-path"
        )
    if args.compare_openers_with_strategy and not args.strategy:
        raise SystemExit("--compare-openers-with-strategy requires --strategy")
    if args.recommend and not args.state:
        raise SystemExit("--recommend requires --state")
    if args.state and not args.recommend:
        raise SystemExit("--state can only be used with --recommend")
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
    if args.weighted_worst_patterns is not None and args.weighted_worst_patterns < 1:
        raise SystemExit("--weighted-worst-patterns must be at least 1")
    if args.weighted_worst_patterns is not None and not args.strategy:
        raise SystemExit("--weighted-worst-patterns can only be used with --strategy")
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
    if args.show_prior_weighting_changes and not args.strategy:
        raise SystemExit("--show-prior-weighting-changes can only be used with --strategy")
    if args.show_small_candidate_events is not None and not args.strategy:
        raise SystemExit("--show-small-candidate-events can only be used with --strategy")
    if args.show_small_candidate_events is not None and args.show_small_candidate_events < 1:
        raise SystemExit("--show-small-candidate-events must be at least 1")
    if args.show_weighted_score and not (args.strategy or args.tune_pattern):
        raise SystemExit("--show-weighted-score can only be used with --strategy or --tune-pattern")
    if args.tune_pattern_objective == "weighted-risk" and not args.tune_pattern:
        raise SystemExit("--tune-pattern-objective weighted-risk can only be used with --tune-pattern")
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
    if args.max_patterns is not None and args.max_patterns < 1:
        raise SystemExit("--max-patterns must be at least 1")
    if args.only_worst_patterns is not None and args.only_worst_patterns < 1:
        raise SystemExit("--only-worst-patterns must be at least 1")
    if args.min_candidates < 1:
        raise SystemExit("--min-candidates must be at least 1")
    if args.max_second_guesses is not None and args.max_second_guesses < 1:
        raise SystemExit("--max-second-guesses must be at least 1")

    if args.clean_prior_source:
        try:
            possible_answers = load_words(args.answers)
            stats = clean_prior_source(
                args.clean_prior_source[0],
                args.clean_prior_source[1],
                possible_answers,
            )
        except (FileNotFoundError, ValueError) as error:
            parser.error(str(error))
        print_clean_prior_source_report(stats)
        return

    if args.prior_dated_stats:
        try:
            dated_prior_answers = load_dated_prior_answers(args.prior_answers_dated)
        except (FileNotFoundError, ValueError) as error:
            parser.error(str(error))
        print_prior_dated_stats_report(dated_prior_answers)
        return

    try:
        allowed_guesses, possible_answers = load_word_lists(
            allowed_path=args.allowed,
            answers_path=args.answers,
        )
        prior_answers = load_words(args.prior_answers)
        dated_prior_answers = load_dated_prior_answers(args.prior_answers_dated)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    try:
        as_of_date = resolve_as_of_date(args.as_of_date, dated_prior_answers)
    except ValueError as error:
        parser.error(str(error))
    prior_answer_weights = build_prior_answer_weights(
        dated_prior_answers,
        as_of_date,
    )
    if args.tune_pattern_objective == "weighted-risk":
        if args.prior_policy != "downweight":
            parser.error("--tune-pattern-objective weighted-risk requires --prior-policy downweight")
        if not dated_prior_answers:
            parser.error("--tune-pattern-objective weighted-risk requires dated prior answers")

    if args.prior_weight_stats:
        print_prior_weight_stats_report(possible_answers, prior_answer_weights)
        return

    if args.recommend:
        try:
            row = build_recommendation(
                args.state,
                allowed_guesses,
                possible_answers,
                second_guess_pool_name=args.second_guess_pool,
                prior_answers=prior_answers,
                prior_policy=args.prior_policy,
                prior_answer_weights=prior_answer_weights,
                strategy=args.strategy or "second-map-bucket",
                use_overrides=False if args.no_overrides else None,
            )
        except ValueError as error:
            parser.error(str(error))
        print_recommendation(row)
        return

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
                prior_answers=prior_answers,
                prior_policy=args.prior_policy,
                prior_answer_weights=prior_answer_weights,
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
            prior_answers=prior_answers,
            prior_policy=args.prior_policy,
            prior_answer_weights=prior_answer_weights,
        )
        print_strategy_report(rows)
        if args.csv:
            write_strategy_csv(args.csv, rows)
        return
    if args.build_second_map:
        second_guess_pool = (
            allowed_guesses if args.second_guess_pool == "allowed" else possible_answers
        )
        try:
            rows = run_build_second_map(
                args.build_second_map.lower(),
                args.strategy or "second-map-bucket",
                allowed_guesses,
                possible_answers,
                second_guess_pool,
                second_guess_pool_name=args.second_guess_pool,
                trap_threshold=args.trap_threshold,
                answer_weighting=args.answer_weighting,
                small_candidate_order=args.small_candidate_order,
                objective=args.tune_pattern_objective,
                csv_path=args.csv,
                force=args.force,
                only_patterns=args.only_pattern,
                max_patterns=args.max_patterns,
                only_worst_patterns=args.only_worst_patterns,
                min_candidates=args.min_candidates,
                max_second_guesses=args.max_second_guesses,
                second_guess_candidates=args.second_guess_candidates,
            )
        except ValueError as error:
            parser.error(str(error))
        print_built_second_map(rows)
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
                prior_answer_weights=prior_answer_weights,
                include_weighted_columns=(
                    args.show_weighted_score
                    or args.tune_pattern_objective == "weighted-risk"
                ),
                max_second_guesses=args.max_second_guesses,
                second_guess_candidates=args.second_guess_candidates,
                show_progress=True,
                csv_path=args.csv,
            )
        except ValueError as error:
            parser.error(str(error))
        print_tune_pattern_report(
            rows,
            branch_summary=args.branch_summary,
            include_weighted_columns=(
                args.show_weighted_score
                or args.tune_pattern_objective == "weighted-risk"
            ),
        )
        pattern_worst_limit = args.show_pattern_worst or args.show_worst
        if pattern_worst_limit and args.second:
            print_worst_games(build_worst_game_rows(pattern_games, pattern_worst_limit))
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
        prior_weighting_changes = []
        small_candidate_events = []
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
                built_second_map_path=args.use_built_second_map,
                prior_answers=prior_answers,
                prior_policy=args.prior_policy,
                prior_answer_weights=prior_answer_weights,
                prior_weighting_changes=(
                    prior_weighting_changes
                    if args.show_prior_weighting_changes
                    else None
                ),
                small_candidate_events=(
                    small_candidate_events
                    if args.show_small_candidate_events
                    else None
                ),
            )
        except ValueError as error:
            parser.error(str(error))
        elapsed_seconds = time.perf_counter() - start_time
        print_strategy_report((row,))
        if args.strategy == "second-map-expected":
            print_expected_diagnostics(row, elapsed_seconds)
        if args.show_weighted_score:
            print_weighted_score_report(
                build_weighted_score_row(games, prior_answer_weights),
                enabled=args.prior_policy == "downweight",
            )
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
        if args.show_prior_weighting_changes:
            print_prior_weighting_changes(
                prior_weighting_changes,
                enabled=args.prior_policy == "downweight",
            )
        if args.show_small_candidate_events:
            print_small_candidate_events(
                small_candidate_events,
                limit=args.show_small_candidate_events,
            )
        worst_rows = ()
        if args.worst_patterns is not None:
            pattern_limit = None if args.worst_patterns == -1 else args.worst_patterns
            print_worst_patterns(build_worst_pattern_rows(games, pattern_limit))
        if args.weighted_worst_patterns:
            print_weighted_worst_patterns(
                build_weighted_worst_pattern_rows(
                    games,
                    prior_answer_weights,
                    args.weighted_worst_patterns,
                ),
                enabled=args.prior_policy == "downweight",
            )
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
    if args.prior_stats:
        print_prior_stats_report(possible_answers, prior_answers)
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

    if args.prior_policy == "ignore":
        result = run_simulation(
            allowed_guesses=allowed_guesses,
            possible_answers=possible_answers,
            first_guess=args.first.lower(),
        )
    else:
        tested_answers = apply_prior_policy_to_test_answers(
            possible_answers,
            prior_answers,
            args.prior_policy,
        )
        games = tuple(
            play_baseline_game(
                answer,
                allowed_guesses,
                tested_answers,
                args.first.lower(),
                prior_answers=prior_answers,
                prior_policy=args.prior_policy,
                prior_answer_weights=prior_answer_weights,
            )
            for answer in tested_answers
        )
        result = type("Result", (), {
            "games": games,
            "solved_count": sum(1 for game in games if game.solved),
            "failed_count": sum(1 for game in games if not game.solved),
            "average_guesses": sum(game.guess_count for game in games) / len(games) if games else 0,
            "guess_distribution": Counter(
                game.guess_count for game in games if game.solved and game.guess_count in range(1, 7)
            ),
        })()

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


def print_prior_stats_report(possible_answers, prior_answers):
    answer_words = set(possible_answers)
    prior_words = set(prior_answers)
    found_prior_answers = answer_words & prior_words
    remaining_non_prior_answers = answer_words - prior_words

    print(f"Answers: {len(possible_answers)}")
    print(f"Prior answers: {len(prior_answers)}")
    print(f"Prior answers found in answer list: {len(found_prior_answers)}")
    print(f"Remaining non-prior answers: {len(remaining_non_prior_answers)}")


def load_dated_prior_answers(path):
    csv_path = Path(path)
    try:
        csv_file = csv_path.open(newline="", encoding="utf-8")
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Dated prior answer file not found: {csv_path}") from error

    rows = []
    with csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError("Dated prior answer CSV must include date and word columns.")
        required_columns = {"date", "word"}
        if not required_columns.issubset(reader.fieldnames):
            raise ValueError("Dated prior answer CSV must include date and word columns.")
        for row_number, row in enumerate(reader, start=2):
            date_text = (row.get("date") or "").strip()
            word = (row.get("word") or "").strip()
            try:
                parsed_date = date.fromisoformat(date_text)
            except ValueError as error:
                raise ValueError(f"Invalid date on row {row_number}: {date_text!r}") from error
            if len(word) != 5 or not word.isalpha() or word != word.lower():
                raise ValueError(f"Invalid word on row {row_number}: {word!r}")
            rows.append((parsed_date, word))
    return tuple(rows)


def build_prior_dated_stats(dated_prior_answers):
    word_counts = Counter(word for _answer_date, word in dated_prior_answers)
    repeated_words = tuple(
        (word, count)
        for word, count in sorted(word_counts.items())
        if count > 1
    )
    dates = [answer_date for answer_date, _word in dated_prior_answers]
    return {
        "dated_prior_rows": len(dated_prior_answers),
        "valid_dated_prior_words": len(dated_prior_answers),
        "unique_prior_words": len(word_counts),
        "duplicates_repeats": len(dated_prior_answers) - len(word_counts),
        "oldest_date": min(dates).isoformat() if dates else "-",
        "newest_date": max(dates).isoformat() if dates else "-",
        "words_repeated_more_than_once": repeated_words,
    }


def resolve_as_of_date(as_of_date_text, dated_prior_answers):
    if as_of_date_text:
        try:
            return date.fromisoformat(as_of_date_text)
        except ValueError as error:
            raise ValueError(f"Invalid --as-of-date: {as_of_date_text!r}") from error
    if dated_prior_answers:
        return max(answer_date for answer_date, _word in dated_prior_answers)
    return date.today()


def prior_answer_weight_for_age(days_since_use):
    if days_since_use <= 90:
        return 0.05
    if days_since_use <= 365:
        return 0.15
    if days_since_use <= 730:
        return 0.35
    return 0.60


def build_prior_answer_weights(dated_prior_answers, as_of_date, fallback_prior_answers=()):
    latest_dates_by_word = {}
    for answer_date, word in dated_prior_answers:
        if word not in latest_dates_by_word or answer_date > latest_dates_by_word[word]:
            latest_dates_by_word[word] = answer_date

    weights = {word: 0.60 for word in fallback_prior_answers}
    for word, answer_date in latest_dates_by_word.items():
        days_since_use = max(0, (as_of_date - answer_date).days)
        weights[word] = prior_answer_weight_for_age(days_since_use)
    return weights


def prior_weight_for_word(word, prior_answer_weights):
    return prior_answer_weights.get(word, 1.0)


def prior_weight_bucket_label(weight):
    if weight == 1.0:
        return "never used"
    if weight == 0.05:
        return "used within last 90 days"
    if weight == 0.15:
        return "used 91-365 days ago"
    if weight == 0.35:
        return "used 366-730 days ago"
    if weight == 0.60:
        return "used more than 730 days ago"
    return "other"


def build_prior_weight_stats(possible_answers, prior_answer_weights):
    buckets = Counter()
    for answer in possible_answers:
        weight = prior_weight_for_word(answer, prior_answer_weights)
        buckets[(weight, prior_weight_bucket_label(weight))] += 1
    return tuple(
        {
            "weight": f"{weight:.2f}",
            "bucket": label,
            "count": buckets[(weight, label)],
        }
        for weight, label in (
            (1.0, "never used"),
            (0.05, "used within last 90 days"),
            (0.15, "used 91-365 days ago"),
            (0.35, "used 366-730 days ago"),
            (0.60, "used more than 730 days ago"),
        )
    )


def print_prior_weight_stats_report(possible_answers, prior_answer_weights):
    print("Prior weight stats:")
    print("weight  bucket                    count")
    for row in build_prior_weight_stats(possible_answers, prior_answer_weights):
        print(f"{row['weight']:<7} {row['bucket']:<25} {row['count']}")


def print_prior_dated_stats_report(dated_prior_answers):
    stats = build_prior_dated_stats(dated_prior_answers)
    repeated_words = stats["words_repeated_more_than_once"]
    repeated_text = (
        ", ".join(f"{word} ({count})" for word, count in repeated_words)
        if repeated_words
        else "none"
    )
    print(f"dated prior rows: {stats['dated_prior_rows']}")
    print(f"valid dated prior words: {stats['valid_dated_prior_words']}")
    print(f"unique prior words: {stats['unique_prior_words']}")
    print(f"duplicates/repeats: {stats['duplicates_repeats']}")
    print(f"oldest date: {stats['oldest_date']}")
    print(f"newest date: {stats['newest_date']}")
    print(f"words repeated more than once: {repeated_text}")


def clean_prior_source(input_path, output_path, possible_answers):
    input_path = Path(input_path)
    output_path = Path(output_path)
    try:
        source_text = input_path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Prior source file not found: {input_path}") from error

    answer_words = set(possible_answers)
    source_words = re.findall(r"\b[a-z]{5}\b", source_text)
    seen_words = set()
    cleaned_words = []
    duplicates_skipped = 0
    non_answer_words_skipped = 0

    for word in source_words:
        if word in seen_words:
            duplicates_skipped += 1
            continue
        seen_words.add(word)
        if word not in answer_words:
            non_answer_words_skipped += 1
            continue
        cleaned_words.append(word)

    if output_path.parent != Path("."):
        output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(f"{word}\n" for word in cleaned_words),
        encoding="utf-8",
    )
    return {
        "source_words_found": len(source_words),
        "valid_wordle_answers_written": len(cleaned_words),
        "duplicates_skipped": duplicates_skipped,
        "non_answer_words_skipped": non_answer_words_skipped,
    }


def print_clean_prior_source_report(stats):
    print(f"source words found: {stats['source_words_found']}")
    print(f"valid Wordle answers written: {stats['valid_wordle_answers_written']}")
    print(f"duplicates skipped: {stats['duplicates_skipped']}")
    print(f"non-answer words skipped: {stats['non_answer_words_skipped']}")


def build_recommendation(
    state_steps,
    allowed_guesses,
    possible_answers,
    second_guess_pool_name="allowed",
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
    strategy="second-map-bucket",
    use_overrides=None,
):
    path_guesses, path_patterns = parse_tune_path(state_steps, allowed_guesses)
    candidates = filter_candidates_for_path(possible_answers, path_guesses, path_patterns)
    candidates = apply_prior_policy_to_candidates(candidates, prior_answers, prior_policy)
    if not candidates:
        raise ValueError("No answers match the supplied recommendation state.")

    probe_pool = allowed_guesses if second_guess_pool_name == "allowed" else possible_answers
    override_mode = None
    recommendation = find_recommendation_first_pattern_override(
        path_guesses,
        path_patterns,
        second_guess_pool_name,
        probe_pool,
        strategy,
        use_overrides,
        prior_policy,
        prior_answer_weights,
    )
    if recommendation is not None:
        override_mode = (
            "Human Mode"
            if prior_policy == "downweight" and prior_answer_weights
            else "Pure Mode"
        )
    if recommendation is None:
        recommendation = choose_bucket_probe_with_prior_diagnostics(
            candidates,
            path_guesses,
            probe_pool,
            prior_policy=prior_policy,
            prior_answer_weights=prior_answer_weights,
        )
    if recommendation is None:
        recommendation = choose_answer_candidate(
            candidates,
            path_guesses,
            allowed_guesses,
            "off",
            prior_policy=prior_policy,
            prior_answer_weights=prior_answer_weights,
        )

    bucket_sizes = sorted(feedback_bucket_sizes(recommendation, candidates), reverse=True)
    max_bucket = bucket_sizes[0] if bucket_sizes else 0
    expected_remaining = (
        sum(size * size for size in bucket_sizes) / len(candidates)
        if candidates
        else 0
    )
    is_possible_answer = recommendation in set(candidates)
    return {
        "path": format_tune_path_label(path_guesses, path_patterns),
        "remaining_count": len(candidates),
        "top_candidates": format_recommendation_candidates(candidates),
        "prior_weights": (
            format_prior_weights(candidates, prior_answer_weights)
            if prior_policy == "downweight" and prior_answer_weights
            else ""
        ),
        "recommended_guess": recommendation,
        "recommendation_type": "answer" if is_possible_answer else "probe",
        "max_bucket": max_bucket,
        "bucket_count": len(bucket_sizes),
        "expected_remaining": f"{expected_remaining:.2f}",
        "explanation": build_recommendation_explanation(
            recommendation,
            is_possible_answer,
            prior_policy,
            prior_answer_weights,
            override_mode=override_mode,
            override_first=path_guesses[0],
            override_pattern=path_patterns[0],
        ),
    }


def find_recommendation_first_pattern_override(
    path_guesses,
    path_patterns,
    second_guess_pool_name,
    second_guess_pool,
    strategy,
    use_overrides,
    prior_policy,
    prior_answer_weights,
):
    if len(path_guesses) != 1 or len(path_patterns) != 1:
        return None
    first_guess = path_guesses[0]
    if not (first_guess == "slate" and tuned_overrides_enabled(strategy, use_overrides)):
        return None
    pattern = path_patterns[0]
    second_guess_by_pattern = {pattern: ""}
    apply_second_guess_overrides(
        first_guess,
        second_guess_pool_name,
        second_guess_pool,
        second_guess_by_pattern,
        prior_policy=prior_policy,
        prior_answer_weights=prior_answer_weights,
    )
    return second_guess_by_pattern.get(pattern) or None


def format_recommendation_candidates(candidates, limit=12):
    shown = ", ".join(candidates[:limit])
    if len(candidates) > limit:
        return f"{shown}..."
    return shown


def format_prior_weights(candidates, prior_answer_weights=None, limit=12):
    prior_answer_weights = prior_answer_weights or {}
    shown = ", ".join(
        f"{candidate}:{prior_weight_for_word(candidate, prior_answer_weights):.2f}"
        for candidate in candidates[:limit]
    )
    if len(candidates) > limit:
        return f"{shown}..."
    return shown


def build_recommendation_explanation(
    recommendation,
    is_possible_answer,
    prior_policy,
    prior_answer_weights=None,
    override_mode=None,
    override_first=None,
    override_pattern=None,
):
    if override_mode:
        return f"Used {override_mode} override for {override_first} {override_pattern}."
    guess_type = "possible answer" if is_possible_answer else "probe"
    if prior_policy == "downweight" and prior_answer_weights:
        return (
            f"Chose {recommendation} as a {guess_type} using bucket safety with "
            "dated prior-answer weights as a tie-breaker."
        )
    return f"Chose {recommendation} as a {guess_type} using bucket safety."


def print_recommendation(row):
    print("Recommendation:")
    print(f"State: {row['path']}")
    print(f"Remaining candidates: {row['remaining_count']}")
    print(f"Top candidates: {row['top_candidates']}")
    if row["prior_weights"]:
        print(f"Prior weights: {row['prior_weights']}")
    print(f"Recommended next guess: {row['recommended_guess']}")
    print(f"Recommendation type: {row['recommendation_type']}")
    print(
        "Bucket summary: "
        f"max_bucket={row['max_bucket']}, "
        f"bucket_count={row['bucket_count']}, "
        f"expected_remaining={row['expected_remaining']}"
    )
    print(f"Explanation: {row['explanation']}")


def print_timing_report(elapsed_seconds, opener_count):
    average_seconds = elapsed_seconds / opener_count if opener_count else 0
    print(f"Elapsed seconds: {elapsed_seconds:.2f}")
    print(f"Average seconds per opener: {average_seconds:.4f}")


def print_expected_diagnostics(row, elapsed_seconds):
    print(f"Expected-value states: {row.get('expected_states', 0)}")
    print(f"Expected-value fallbacks: {row.get('expected_fallbacks', 0)}")
    print(f"Elapsed seconds: {elapsed_seconds:.2f}")


def print_weighted_score_report(row, enabled=True):
    if not enabled:
        print("Weighted human-mode score: disabled")
        return
    print("Weighted human-mode score:")
    print(f"Total weight: {row['total_weight']:.2f}")
    print(f"Weighted average guesses: {row['weighted_average']:.2f}")
    print(f"Weighted <=3: {row['weighted_solved_3_or_less']:.2f}")
    print(f"Weighted <=4: {row['weighted_solved_4_or_less']:.2f}")
    print(f"Weighted 5s: {row['weighted_fives']:.2f}")
    print(f"Weighted 6s: {row['weighted_sixes']:.2f}")
    print(f"Weighted failed: {row['weighted_failed']:.2f}")


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
    prior_answer_weights=None,
    include_weighted_columns=False,
    max_second_guesses=None,
    second_guess_candidates="all",
    show_progress=False,
    csv_path=None,
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
        prior_answer_weights=prior_answer_weights,
        include_weighted_columns=include_weighted_columns,
        max_second_guesses=max_second_guesses,
        second_guess_candidates=second_guess_candidates,
        show_progress=show_progress,
        csv_path=csv_path,
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
    prior_answer_weights=None,
    include_weighted_columns=False,
    max_second_guesses=None,
    second_guess_candidates="all",
    show_progress=False,
    csv_path=None,
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
    if second_guess is None:
        selected_second_guesses = select_second_guess_candidates(
            second_guess_pool,
            candidates,
            max_second_guesses=max_second_guesses,
            mode=second_guess_candidates,
        )
    if not selected_second_guesses:
        raise ValueError(f"No second guesses selected for pattern {pattern!r}.")
    selected_games = ()
    writer_context = None
    if csv_path:
        writer_context = open_incremental_tune_pattern_csv(
            csv_path,
            branch_summary=branch_summary or objective == "branch-safe",
            include_weighted_columns=(
                include_weighted_columns or objective == "weighted-risk"
            ),
        )
    best_row = None
    best_rank = None
    pattern_start = time.perf_counter()
    total_second_guesses = len(selected_second_guesses)
    try:
        csv_file = None
        writer = None
        if writer_context is not None:
            csv_file, writer = writer_context
        for index, current_second_guess in enumerate(selected_second_guesses, start=1):
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
            row = build_tune_pattern_row(
                pattern,
                current_second_guess,
                len(candidates),
                games,
                candidates,
                branch_summary=branch_summary or objective == "branch-safe",
                prior_answer_weights=prior_answer_weights,
                include_weighted_columns=(
                    include_weighted_columns or objective == "weighted-risk"
                ),
            )
            rows.append(row)
            rank = tune_pattern_objective_rank(row, objective)
            if best_rank is None or rank < best_rank:
                best_row = row
                best_rank = rank
            if writer is not None:
                writer.writerow(row)
                csv_file.flush()
            if show_progress and (index % 100 == 0 or index == total_second_guesses):
                elapsed = time.perf_counter() - pattern_start
                risk_label = "weighted risk" if objective == "weighted-risk" else "risk"
                risk_value = (
                    best_row["weighted_risk"]
                    if objective == "weighted-risk"
                    else best_row["risk_score"]
                )
                print(
                    f"Pattern {pattern}: evaluated {index}/{total_second_guesses} "
                    f"second guesses; current best {best_row['second_guess']} "
                    f"{risk_label} {risk_value}; elapsed {elapsed:.2f}s"
                )
    finally:
        if writer_context is not None:
            writer_context[0].close()

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
    if objective == "safe-balanced":
        return (
            row["sixes"],
            row["fives"],
            row["risk_score"],
            average,
            row["second_guess"],
        )
    if objective == "weighted-risk":
        return (
            float(row["weighted_6s"]),
            float(row["weighted_risk"]),
            float(row["weighted_5s"]),
            float(row["weighted_avg"]),
            row["sixes"],
            row["risk_score"],
            row["second_guess"],
        )
    raise ValueError(f"Unsupported tune-pattern objective: {objective}")


def strip_tune_pattern_branch_summary(row):
    return {
        key: value
        for key, value in row.items()
        if key not in TUNE_PATTERN_BRANCH_COLUMNS[len(TUNE_PATTERN_COLUMNS):]
    }


def build_full_second_map_rows(
    first_guess,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    objective="risk",
):
    validate_tune_pattern(first_guess, "." * len(first_guess), strategy, allowed_guesses)
    return tuple(
        build_second_map_row_for_pattern(
            first_guess,
            pattern,
            strategy,
            allowed_guesses,
            possible_answers,
            second_guess_pool,
            trap_threshold,
            answer_weighting,
            small_candidate_order,
            objective,
        )
        for pattern, _candidates in first_pattern_candidate_groups(
            first_guess,
            possible_answers,
        )
    )


def run_build_second_map(
    first_guess,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool,
    second_guess_pool_name="allowed",
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    objective="risk",
    csv_path=None,
    force=False,
    only_patterns=None,
    max_patterns=None,
    only_worst_patterns=None,
    min_candidates=1,
    max_second_guesses=None,
    second_guess_candidates="all",
):
    validate_tune_pattern(first_guess, "." * len(first_guess), strategy, allowed_guesses)
    selected_patterns = select_second_map_patterns(
        first_guess,
        strategy,
        allowed_guesses,
        possible_answers,
        second_guess_pool_name,
        trap_threshold,
        answer_weighting,
        small_candidate_order,
        only_patterns=only_patterns,
        max_patterns=max_patterns,
        only_worst_patterns=only_worst_patterns,
        min_candidates=min_candidates,
    )
    completed_patterns = set()
    writer_context = None
    if csv_path:
        if not force:
            completed_patterns = read_completed_built_second_map_patterns(
                csv_path,
                first_guess,
            )
        writer_context = open_incremental_built_second_map_csv(csv_path, force=force)

    rows = []
    total_patterns = len(selected_patterns)
    total_start = time.perf_counter()
    try:
        csv_file = None
        writer = None
        if writer_context is not None:
            csv_file, writer = writer_context
        for index, (pattern, candidates) in enumerate(selected_patterns, start=1):
            if pattern in completed_patterns:
                print(
                    f"Skipped {index}/{total_patterns} pattern {pattern} "
                    f"({len(candidates)} candidates): already complete"
                )
                continue
            pattern_start = time.perf_counter()
            row = build_second_map_row_for_pattern(
                first_guess,
                pattern,
                strategy,
                allowed_guesses,
                possible_answers,
                second_guess_pool,
                trap_threshold,
                answer_weighting,
                small_candidate_order,
                objective,
                max_second_guesses=max_second_guesses,
                second_guess_candidates=second_guess_candidates,
                show_progress=True,
            )
            rows.append(row)
            if writer is not None:
                writer.writerow(row)
                csv_file.flush()
            pattern_elapsed = time.perf_counter() - pattern_start
            total_elapsed = time.perf_counter() - total_start
            print(
                f"Built {index}/{total_patterns} pattern {pattern} "
                f"({len(candidates)} candidates): best {row['best_second']} "
                f"in {pattern_elapsed:.2f}s; total {total_elapsed:.2f}s"
            )
    finally:
        if writer_context is not None:
            writer_context[0].close()
    return tuple(rows)


def first_pattern_candidate_groups(first_guess, possible_answers):
    grouped_answers = defaultdict(list)
    for answer in possible_answers:
        grouped_answers[score_guess(first_guess, answer)].append(answer)
    return tuple(
        (pattern, tuple(answers))
        for pattern, answers in sorted(grouped_answers.items())
    )


def select_second_map_patterns(
    first_guess,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool_name,
    trap_threshold,
    answer_weighting,
    small_candidate_order,
    only_patterns=None,
    max_patterns=None,
    only_worst_patterns=None,
    min_candidates=1,
):
    groups = list(first_pattern_candidate_groups(first_guess, possible_answers))
    if only_patterns:
        requested_patterns = set(only_patterns)
        groups = [(pattern, candidates) for pattern, candidates in groups if pattern in requested_patterns]
    if only_worst_patterns:
        _row, games = build_strategy_result(
            strategy,
            first_guess,
            allowed_guesses,
            possible_answers,
            second_guess_pool_name=second_guess_pool_name,
            trap_threshold=trap_threshold,
            answer_weighting=answer_weighting,
            small_candidate_order=small_candidate_order,
            use_overrides=None,
        )
        worst_patterns = {
            row["pattern"]
            for row in build_worst_pattern_rows(games, only_worst_patterns)
        }
        groups = [(pattern, candidates) for pattern, candidates in groups if pattern in worst_patterns]
    groups = [
        (pattern, candidates)
        for pattern, candidates in groups
        if len(candidates) >= min_candidates
    ]
    if max_patterns is not None:
        groups = groups[:max_patterns]
    return tuple(groups)


def build_second_map_row_for_pattern(
    first_guess,
    pattern,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool,
    trap_threshold=2,
    answer_weighting="off",
    small_candidate_order="normal",
    objective="risk",
    max_second_guesses=None,
    second_guess_candidates="all",
    show_progress=False,
):
    candidates = tuple(
        answer for answer in possible_answers if score_guess(first_guess, answer) == pattern
    )
    if not candidates:
        raise ValueError(f"No answers match first guess {first_guess!r} and pattern {pattern!r}.")
    selected_second_guesses = select_second_guess_candidates(
        second_guess_pool,
        candidates,
        max_second_guesses=max_second_guesses,
        mode=second_guess_candidates,
    )
    if not selected_second_guesses:
        raise ValueError(f"No second-map row could be built for pattern {pattern!r}.")
    best_row = None
    best_rank = None
    pattern_start = time.perf_counter()
    total_second_guesses = len(selected_second_guesses)
    for index, current_second_guess in enumerate(selected_second_guesses, start=1):
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
        row = build_tune_pattern_row(
            pattern,
            current_second_guess,
            len(candidates),
            games,
            candidates,
            branch_summary=True,
        )
        rank = tune_pattern_objective_rank(row, objective)
        if best_rank is None or rank < best_rank:
            best_row = row
            best_rank = rank
        if show_progress and (index % 100 == 0 or index == total_second_guesses):
            elapsed = time.perf_counter() - pattern_start
            print(
                f"Pattern {pattern} ({len(candidates)} candidates): "
                f"evaluated {index}/{total_second_guesses} second guesses; "
                f"current best {best_row['second_guess']} risk {best_row['risk_score']}; "
                f"elapsed {elapsed:.2f}s"
            )
    return format_built_second_map_row(first_guess, best_row)


def select_second_guess_candidates(
    second_guess_pool,
    candidates,
    max_second_guesses=None,
    mode="all",
):
    if mode == "all":
        selected = tuple(second_guess_pool)
    elif mode == "top":
        selected = tuple(
            sorted(
                second_guess_pool,
                key=lambda guess: second_guess_candidate_rank(guess, candidates),
            )
        )
    else:
        raise ValueError(f"Unsupported second-guess candidate mode: {mode}")
    if max_second_guesses is not None:
        selected = selected[:max_second_guesses]
    return selected


def second_guess_candidate_rank(guess, candidates):
    target_letters = set("".join(candidates))
    coverage = len(set(guess) & target_letters)
    unique_letters = len(set(guess))
    common_score = sum(1 for letter in set(guess) if letter in "etaoinshrldcu")
    is_not_candidate = guess not in set(candidates)
    return (-coverage, -unique_letters, is_not_candidate, -common_score, guess)


def format_built_second_map_row(first_guess, tune_row):
    return {
        "first": first_guess,
        "pattern": tune_row["pattern"],
        "candidates": tune_row["candidates"],
        "best_second": tune_row["second_guess"],
        "average": tune_row["average"],
        "solved_3_or_less": tune_row["solved_3_or_less"],
        "solved_4_or_less": tune_row["solved_4_or_less"],
        "fives": tune_row["fives"],
        "sixes": tune_row["sixes"],
        "failed": tune_row["failed"],
        "risk_score": tune_row["risk_score"],
        "worst_branch_pattern": tune_row["worst_branch_pattern"],
        "worst_branch_candidates": tune_row["worst_branch_candidates"],
        "worst_branch_fives": tune_row["worst_branch_fives"],
        "worst_branch_risk": tune_row["worst_branch_risk"],
    }


def load_built_second_map(path, first_guess, second_guess_pool):
    csv_path = Path(path)
    if not csv_path.exists():
        raise ValueError(f"Built second map file not found: {csv_path}")

    pool = set(second_guess_pool)
    required_columns = {"first", "pattern", "best_second"}
    second_guess_by_pattern = {}
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            raise ValueError(
                "Built second map CSV must include first, pattern, and best_second columns."
            )
        for row in reader:
            if row["first"] != first_guess:
                continue
            pattern = row["pattern"]
            best_second = row["best_second"]
            if len(pattern) != len(first_guess) or any(mark not in "GY." for mark in pattern):
                raise ValueError(f"Invalid pattern {pattern!r} in built second map.")
            if best_second not in pool:
                raise ValueError(
                    f"Built map second guess {best_second!r} is not in the selected second-guess pool."
                )
            second_guess_by_pattern[pattern] = best_second
    if not second_guess_by_pattern:
        raise ValueError(f"No rows for first guess {first_guess!r} in built second map.")
    return second_guess_by_pattern


def validate_second_guess_map_patterns(first_guess, possible_answers, second_guess_by_pattern):
    missing_patterns = sorted(
        {
            score_guess(first_guess, answer)
            for answer in possible_answers
            if score_guess(first_guess, answer) not in second_guess_by_pattern
        }
    )
    if missing_patterns:
        shown = ", ".join(missing_patterns[:5])
        raise ValueError(f"Built second map is missing first-feedback pattern(s): {shown}")


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
    prior_policy="ignore",
    prior_answer_weights=None,
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
    if prior_policy == "downweight" and prior_answer_weights:
        for (
            override_first,
            pattern,
            override_pool,
            override_prior_policy,
        ), override_guess in HUMAN_MODE_SECOND_GUESS_OVERRIDES.items():
            if (
                override_first != first_guess
                or override_pool != second_guess_pool_name
                or override_prior_policy != prior_policy
            ):
                continue
            if pattern not in second_guess_by_pattern:
                continue
            if override_guess not in pool:
                raise ValueError(
                    f"Human Mode override {override_guess!r} for {first_guess!r} {pattern!r} "
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
    prior_answer_weights=None,
    include_weighted_columns=False,
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
    if include_weighted_columns:
        row.update(build_tune_pattern_weighted_metrics(games, prior_answer_weights))
    if branch_summary:
        row.update(build_second_feedback_branch_summary(second_guess, candidates, games))
    return row


def build_tune_pattern_weighted_metrics(games, prior_answer_weights=None):
    weighted = build_weighted_score_row(games, prior_answer_weights or {})
    weighted_risk = (
        weighted["weighted_fives"] * 2
        + weighted["weighted_sixes"] * 5
        + weighted["weighted_failed"] * 20
    )
    return {
        "weighted_avg": f"{weighted['weighted_average']:.2f}",
        "weighted_5s": f"{weighted['weighted_fives']:.2f}",
        "weighted_6s": f"{weighted['weighted_sixes']:.2f}",
        "weighted_risk": f"{weighted_risk:.2f}",
    }


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


def print_tune_pattern_report(rows, branch_summary=False, include_weighted_columns=False):
    if branch_summary:
        header = (
            "Pattern  Second  Candidates  Avg   <=3   <=4   5s  6s  Fail  Risk"
        )
    else:
        header = "Pattern  Second  Candidates  Avg   <=3   <=4   5s  6s  Fail  Risk"
    if include_weighted_columns:
        header += "  WAvg   W5s    W6s    WRisk"
    if branch_summary:
        header += "  Worst2  WorstN  Worst5s  WorstRisk"
    print(header)
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
        if include_weighted_columns:
            line += (
                f"     {row['weighted_avg']:<6} "
                f"{row['weighted_5s']:<6} "
                f"{row['weighted_6s']:<6} "
                f"{row['weighted_risk']}"
            )
        if branch_summary:
            line += (
                f"     {row['worst_branch_pattern']:<7} "
                f"{row['worst_branch_candidates']:<7} "
                f"{row['worst_branch_fives']:<8} "
                f"{row['worst_branch_risk']}"
            )
        print(line)


def print_built_second_map(rows):
    print(
        "First  Pattern  Candidates  Best2  Avg   <=3   <=4   5s  6s  Fail  Risk  "
        "Worst2  WorstN  Worst5s  WorstRisk"
    )
    for row in rows:
        print(
            f"{row['first']:<6} "
            f"{row['pattern']:<8} "
            f"{row['candidates']:<11} "
            f"{row['best_second']:<6} "
            f"{row['average']:<5} "
            f"{row['solved_3_or_less']:<5} "
            f"{row['solved_4_or_less']:<5} "
            f"{row['fives']:<3} "
            f"{row['sixes']:<3} "
            f"{row['failed']:<5} "
            f"{row['risk_score']:<5} "
            f"{row['worst_branch_pattern']:<7} "
            f"{row['worst_branch_candidates']:<7} "
            f"{row['worst_branch_fives']:<8} "
            f"{row['worst_branch_risk']}"
        )


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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
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
            prior_answers=prior_answers,
            prior_policy=prior_policy,
            prior_answer_weights=prior_answer_weights,
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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
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
            prior_answers=prior_answers,
            prior_policy=prior_policy,
            prior_answer_weights=prior_answer_weights,
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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
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
        prior_answers=prior_answers,
        prior_policy=prior_policy,
        prior_answer_weights=prior_answer_weights,
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
    built_second_map_path=None,
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
    prior_weighting_changes=None,
    small_candidate_events=None,
):
    if first_guess not in allowed_guesses:
        raise ValueError(f"First guess {first_guess!r} is not in the allowed guess list.")
    tested_answers = apply_prior_policy_to_test_answers(
        possible_answers,
        prior_answers,
        prior_policy,
    )

    if strategy == "baseline":
        if (
            answer_weighting == "off"
            and small_candidate_order == "normal"
            and final_cluster_overrides == "off"
            and prior_policy == "ignore"
            and small_candidate_events is None
        ):
            result = run_simulation(
                allowed_guesses=allowed_guesses,
                possible_answers=tested_answers,
                first_guess=first_guess,
            )
            summary = build_comparison_row(first_guess, result)
            games = result.games
        else:
            games = tuple(
                play_baseline_game(
                    answer,
                    allowed_guesses,
                    tested_answers,
                    first_guess,
                    answer_weighting,
                    weighting_changes,
                    small_candidate_order,
                    small_order_changes,
                    final_cluster_overrides,
                    final_cluster_override_changes,
                    prior_answers,
                    prior_policy,
                    prior_answer_weights,
                    prior_weighting_changes,
                    small_candidate_events,
                )
                for answer in tested_answers
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
        if built_second_map_path:
            second_guess_by_pattern = load_built_second_map(
                built_second_map_path,
                first_guess,
                second_guess_pool,
            )
            validate_second_guess_map_patterns(
                first_guess,
                tested_answers,
                second_guess_by_pattern,
            )
        else:
            second_guess_rows = build_second_guess_map_rows(
                first_guess,
                allowed_guesses,
                tested_answers,
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
                    prior_policy=prior_policy,
                    prior_answer_weights=prior_answer_weights,
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
                tested_answers,
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
                prior_answers=prior_answers,
                prior_policy=prior_policy,
                prior_answer_weights=prior_answer_weights,
                prior_weighting_changes=prior_weighting_changes,
                small_candidate_events=small_candidate_events,
            )
            for answer in tested_answers
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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
    prior_weighting_changes=None,
    small_candidate_events=None,
):
    guesses = []
    candidates = apply_prior_policy_to_candidates(
        possible_answers,
        prior_answers,
        prior_policy,
    )
    if probe_pool is None:
        probe_pool = allowed_guesses

    first_feedback = score_guess(first_guess, answer)
    guesses.append(first_guess)
    if is_solved(first_feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    candidates = filter_candidates_by_feedback(candidates, first_guess, first_feedback)
    candidates = apply_prior_policy_to_candidates(candidates, prior_answers, prior_policy)
    second_guess = second_guess_by_pattern[first_feedback]
    record_small_candidate_event(
        small_candidate_events,
        answer,
        len(guesses) + 1,
        second_guess,
        candidates,
        prior_answer_weights,
    )
    second_feedback = score_guess(second_guess, answer)
    guesses.append(second_guess)
    if is_solved(second_feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    candidates = filter_candidates_by_feedback(candidates, second_guess, second_feedback)
    candidates = apply_prior_policy_to_candidates(candidates, prior_answers, prior_policy)
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
        pre_guess_candidates = candidates
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
                prior_answers,
                prior_policy,
                prior_answer_weights,
                prior_weighting_changes,
                None,
            )
        record_small_candidate_event(
            small_candidate_events,
            answer,
            len(guesses) + 1,
            next_guess,
            pre_guess_candidates,
            prior_answer_weights,
        )
        feedback = score_guess(next_guess, answer)
        guesses.append(next_guess)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        candidates = filter_candidates_by_feedback(candidates, next_guess, feedback)
        candidates = apply_prior_policy_to_candidates(candidates, prior_answers, prior_policy)

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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
    prior_weighting_changes=None,
    small_candidate_events=None,
):
    guesses = []
    candidates = apply_prior_policy_to_candidates(
        possible_answers,
        prior_answers,
        prior_policy,
    )

    while candidates:
        if guesses:
            pre_guess_candidates = candidates
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
                prior_answers,
                prior_policy,
                prior_answer_weights,
                prior_weighting_changes,
                None,
            )
        else:
            pre_guess_candidates = candidates
            next_guess = first_guess

        record_small_candidate_event(
            small_candidate_events,
            answer,
            len(guesses) + 1,
            next_guess,
            pre_guess_candidates,
            prior_answer_weights,
        )

        feedback = score_guess(next_guess, answer)
        guesses.append(next_guess)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)
        candidates = filter_candidates_by_feedback(candidates, next_guess, feedback)
        candidates = apply_prior_policy_to_candidates(candidates, prior_answers, prior_policy)

    return GameResult(answer=answer, guesses=tuple(guesses), solved=False)


def filter_candidates_by_feedback(candidates, guess, feedback):
    return tuple(
        candidate for candidate in candidates if score_guess(guess, candidate) == feedback
    )


def apply_prior_policy_to_candidates(candidates, prior_answers=(), prior_policy="ignore"):
    candidates = tuple(candidates)
    if prior_policy in {"ignore", "downweight"}:
        return candidates
    if prior_policy != "exclude":
        raise ValueError(f"Unsupported prior policy: {prior_policy}")
    prior_answer_set = set(prior_answers)
    if not prior_answer_set:
        return candidates
    filtered_candidates = tuple(candidate for candidate in candidates if candidate not in prior_answer_set)
    return filtered_candidates or candidates


def apply_prior_policy_to_test_answers(possible_answers, prior_answers=(), prior_policy="ignore"):
    if prior_policy != "exclude":
        if prior_policy not in {"ignore", "downweight"}:
            raise ValueError(f"Unsupported prior policy: {prior_policy}")
        return tuple(possible_answers)
    return apply_prior_policy_to_candidates(possible_answers, prior_answers, prior_policy)


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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
    prior_weighting_changes=None,
    small_candidate_events=None,
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
    if prior_policy not in {"ignore", "exclude", "downweight"}:
        raise ValueError(f"Unsupported prior policy: {prior_policy}")

    prior_answer_weights = dict(prior_answer_weights or {})
    normal_choice_candidates = available_candidates
    unweighted_choice = normal_choice_candidates[0]
    base_choice = unweighted_choice
    if answer_weighting == "simple":
        base_choice = max(
            normal_choice_candidates,
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
    if prior_policy == "downweight" and prior_answer_weights and len(candidates) in (2, 3, 4, 5):
        weighted_base_choice = choose_prior_weighted_endgame_candidate(
            base_choice,
            available_candidates,
            candidates,
            prior_answer_weights,
        )
        if prior_weighting_changes is not None and weighted_base_choice != base_choice:
            record_prior_weighting_change(
                prior_weighting_changes,
                answer,
                guess_number,
                base_choice,
                weighted_base_choice,
                candidates,
                prior_answer_weights,
            )
        base_choice = weighted_base_choice
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
        record_small_candidate_event(
            small_candidate_events,
            answer,
            guess_number,
            ordered_choice,
            candidates,
            prior_answer_weights,
        )
        return ordered_choice
    record_small_candidate_event(
        small_candidate_events,
        answer,
        guess_number,
        base_choice,
        candidates,
        prior_answer_weights,
    )
    return base_choice


def record_small_candidate_event(
    events,
    answer,
    guess_number,
    chosen_guess,
    candidates,
    prior_answer_weights=None,
):
    if events is None or len(candidates) not in (2, 3, 4, 5):
        return
    prior_answer_weights = prior_answer_weights or {}
    events.append(
        {
            "answer": answer or "",
            "guess_number": guess_number or 0,
            "normal_guess": chosen_guess,
            "remaining_candidates": tuple(candidates),
            "prior_weights": tuple(
                (candidate, prior_weight_for_word(candidate, prior_answer_weights))
                for candidate in candidates
            ),
            "chosen_is_candidate": chosen_guess in set(candidates),
        }
    )


def record_prior_weighting_change(
    changes,
    answer,
    guess_number,
    normal_guess,
    weighted_guess,
    candidates,
    prior_answer_weights,
):
    if changes is None or normal_guess == weighted_guess:
        return
    prior_answer_weights = prior_answer_weights or {}
    changes.append(
        {
            "answer": answer or "",
            "guess_number": guess_number or 0,
            "normal_guess": normal_guess,
            "weighted_guess": weighted_guess,
            "remaining_candidates": tuple(candidates),
            "prior_weights": tuple(
                (candidate, prior_weight_for_word(candidate, prior_answer_weights))
                for candidate in candidates
            ),
            "normal_weight": prior_weight_for_word(normal_guess, prior_answer_weights),
            "weighted_weight": prior_weight_for_word(weighted_guess, prior_answer_weights),
            "normal_max_bucket": max(feedback_bucket_sizes(normal_guess, candidates)),
            "weighted_max_bucket": max(feedback_bucket_sizes(weighted_guess, candidates)),
        }
    )


def choose_prior_weighted_endgame_candidate(
    normal_choice,
    available_candidates,
    candidates,
    prior_answer_weights,
):
    if normal_choice not in candidates:
        return normal_choice
    normal_rank = prior_safe_answer_rank(normal_choice, candidates)
    eligible_candidates = [
        candidate
        for candidate in available_candidates
        if candidate in candidates and prior_safe_answer_rank(candidate, candidates) == normal_rank
    ]
    if not eligible_candidates:
        return normal_choice
    return max(
        eligible_candidates,
        key=lambda candidate: (
            prior_weight_for_word(candidate, prior_answer_weights),
            -available_candidates.index(candidate),
        ),
    )


def prior_safe_answer_rank(guess, candidates):
    bucket_sizes = feedback_bucket_sizes(guess, candidates)
    max_bucket_size = max(bucket_sizes)
    expected_remaining = sum(size * size for size in bucket_sizes) / len(candidates)
    return (max_bucket_size, expected_remaining)


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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
    prior_weighting_changes=None,
    small_candidate_events=None,
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
                "off",
                None,
                prior_answers,
                prior_policy,
                prior_answer_weights,
                prior_weighting_changes,
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
            "off",
            None,
            prior_answers,
            prior_policy,
            prior_answer_weights,
            prior_weighting_changes,
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
            prior_answers,
            prior_policy,
            prior_answer_weights,
            prior_weighting_changes,
        )
    if use_bucket_strategy:
        probe = choose_bucket_probe_with_prior_diagnostics(
            candidates,
            previous_guesses,
            probe_pool,
            prior_policy,
            prior_answer_weights,
            prior_weighting_changes,
            answer,
            guess_number,
        )
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
            "off",
            None,
            prior_answers,
            prior_policy,
            prior_answer_weights,
            prior_weighting_changes,
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
        "off",
        None,
            prior_answers,
            prior_policy,
            prior_answer_weights,
            prior_weighting_changes,
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
    prior_answers=(),
    prior_policy="ignore",
    prior_answer_weights=None,
    prior_weighting_changes=None,
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
        "off",
        None,
        prior_answers,
        prior_policy,
        prior_answer_weights,
        prior_weighting_changes,
    )
    normal_max_bucket = max(feedback_bucket_sizes(normal_guess, candidates))
    if normal_max_bucket > trap_threshold:
        return choose_bucket_probe_with_prior_diagnostics(
            candidates,
            previous_guesses,
            probe_pool,
            prior_policy,
            prior_answer_weights,
            prior_weighting_changes,
            answer,
            guess_number,
        )
    return normal_guess


def choose_bucket_probe_with_prior_diagnostics(
    candidates,
    previous_guesses,
    probe_pool,
    prior_policy="ignore",
    prior_answer_weights=None,
    prior_weighting_changes=None,
    answer=None,
    guess_number=None,
):
    if prior_policy == "downweight" and prior_answer_weights:
        normal_probe = choose_bucket_probe(
            candidates,
            previous_guesses,
            probe_pool,
            prior_answer_weights=None,
        )
        weighted_probe = choose_bucket_probe(
            candidates,
            previous_guesses,
            probe_pool,
            prior_answer_weights=prior_answer_weights,
        )
        record_prior_weighting_change(
            prior_weighting_changes,
            answer,
            guess_number,
            normal_probe,
            weighted_probe,
            candidates,
            prior_answer_weights,
        )
        return weighted_probe
    return choose_bucket_probe(candidates, previous_guesses, probe_pool)


def choose_bucket_probe(candidates, previous_guesses, probe_pool, prior_answer_weights=None):
    previous = set(previous_guesses)
    candidates = tuple(candidates)
    best_guess = None
    best_rank = None

    for guess in probe_pool:
        if guess in previous:
            continue
        rank = bucket_probe_rank(guess, candidates, prior_answer_weights=prior_answer_weights)
        if best_rank is None or rank < best_rank:
            best_guess = guess
            best_rank = rank

    return best_guess


def bucket_probe_rank(guess, candidates, prior_answer_weights=None):
    bucket_sizes = feedback_bucket_sizes(guess, candidates)
    max_bucket_size = max(bucket_sizes)
    expected_remaining = sum(size * size for size in bucket_sizes) / len(candidates)
    is_not_candidate = guess not in set(candidates)
    if prior_answer_weights is None:
        return (max_bucket_size, expected_remaining, is_not_candidate, guess)
    candidate_weight = prior_weight_for_word(guess, prior_answer_weights) if guess in set(candidates) else 0
    return (max_bucket_size, expected_remaining, is_not_candidate, -candidate_weight, guess)


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


def build_weighted_score_row(games, prior_answer_weights):
    total_weight = 0.0
    weighted_guess_sum = 0.0
    weighted_solved_3_or_less = 0.0
    weighted_solved_4_or_less = 0.0
    weighted_fives = 0.0
    weighted_sixes = 0.0
    weighted_failed = 0.0

    for game in games:
        weight = prior_weight_for_word(game.answer, prior_answer_weights)
        total_weight += weight
        weighted_guess_sum += weight * game.guess_count
        if game.solved and game.guess_count <= 3:
            weighted_solved_3_or_less += weight
        if game.solved and game.guess_count <= 4:
            weighted_solved_4_or_less += weight
        if game.solved and game.guess_count == 5:
            weighted_fives += weight
        if game.solved and game.guess_count == 6:
            weighted_sixes += weight
        if not game.solved:
            weighted_failed += weight

    weighted_average = weighted_guess_sum / total_weight if total_weight else 0
    return {
        "total_weight": total_weight,
        "weighted_average": weighted_average,
        "weighted_solved_3_or_less": weighted_solved_3_or_less,
        "weighted_solved_4_or_less": weighted_solved_4_or_less,
        "weighted_fives": weighted_fives,
        "weighted_sixes": weighted_sixes,
        "weighted_failed": weighted_failed,
    }


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


def build_weighted_worst_pattern_rows(games, prior_answer_weights, limit):
    grouped_games = defaultdict(list)
    for game in games:
        if not game.guesses:
            continue
        pattern = score_guess(game.guesses[0], game.answer)
        grouped_games[pattern].append(game)

    rows = tuple(
        format_weighted_worst_pattern_row(pattern, group, prior_answer_weights)
        for pattern, group in grouped_games.items()
    )
    ranked_rows = sorted(
        rows,
        key=lambda row: (
            -row["weighted_risk_value"],
            -row["weighted_avg_value"],
            row["pattern"],
        ),
    )
    return tuple(strip_weighted_worst_pattern_sort_values(row) for row in ranked_rows[:limit])


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


def format_weighted_worst_pattern_row(pattern, games, prior_answer_weights):
    total_weight = 0.0
    weighted_guess_sum = 0.0
    weighted_fives = 0.0
    weighted_sixes = 0.0
    weighted_failed = 0.0
    max_guesses = 0

    for game in games:
        weight = prior_weight_for_word(game.answer, prior_answer_weights)
        total_weight += weight
        weighted_guess_sum += weight * game.guess_count
        max_guesses = max(max_guesses, game.guess_count)
        if game.solved and game.guess_count == 5:
            weighted_fives += weight
        if game.solved and game.guess_count == 6:
            weighted_sixes += weight
        if not game.solved:
            weighted_failed += weight

    weighted_average = weighted_guess_sum / total_weight if total_weight else 0
    weighted_risk = weighted_fives * 2 + weighted_sixes * 5 + weighted_failed * 20
    return {
        "pattern": pattern,
        "games": len(games),
        "total_weight": f"{total_weight:.2f}",
        "weighted_avg": f"{weighted_average:.2f}",
        "weighted_5s": f"{weighted_fives:.2f}",
        "weighted_6s": f"{weighted_sixes:.2f}",
        "weighted_risk": f"{weighted_risk:.2f}",
        "max_guesses": max_guesses,
        "weighted_risk_value": weighted_risk,
        "weighted_avg_value": weighted_average,
    }


def strip_weighted_worst_pattern_sort_values(row):
    return {
        key: value
        for key, value in row.items()
        if key not in {"weighted_risk_value", "weighted_avg_value"}
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


def print_weighted_worst_patterns(rows, enabled=True):
    if not enabled:
        print("Weighted worst patterns: disabled")
        return
    print("Weighted worst patterns:")
    print("pattern  games  total_weight  weighted_avg  weighted_5s  weighted_6s  weighted_risk  max_guesses")
    for row in rows:
        print(
            f"{row['pattern']:<8} "
            f"{row['games']:<6} "
            f"{row['total_weight']:<13} "
            f"{row['weighted_avg']:<13} "
            f"{row['weighted_5s']:<12} "
            f"{row['weighted_6s']:<12} "
            f"{row['weighted_risk']:<14} "
            f"{row['max_guesses']}"
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


def print_prior_weighting_changes(changes, enabled=True, limit=25):
    if not enabled:
        print("Prior-weighting changed decisions: 0")
        print("Games affected: 0")
        return

    affected_games = {change["answer"] for change in changes if change["answer"]}
    print(f"Prior-weighting changed decisions: {len(changes)}")
    print(f"Games affected: {len(affected_games)}")
    if not changes:
        return

    print("Prior-weighting change examples:")
    print("answer  guess#  normal  weighted  normal_w  weighted_w  remaining_candidates  prior_weights")
    for change in changes[:limit]:
        prior_weights = ", ".join(
            f"{word}:{weight:.2f}"
            for word, weight in change.get("prior_weights", ())
        )
        print(
            f"{change['answer']:<7} "
            f"{change['guess_number']:<7} "
            f"{change['normal_guess']:<7} "
            f"{change['weighted_guess']:<8} "
            f"{change['normal_weight']:<9.2f} "
            f"{change['weighted_weight']:<10.2f} "
            f"{format_remaining_candidates(change['remaining_candidates']):<22} "
            f"{prior_weights}"
        )
    increased = sum(
        1
        for change in changes
        if change.get("weighted_max_bucket", 0) > change.get("normal_max_bucket", 0)
    )
    print(f"Prior-weighting max-bucket increases: {increased}")


def print_small_candidate_events(events, limit):
    print("Small candidate events:")
    print("answer  guess#  normal  is_candidate  remaining_candidates  prior_weights")
    for event in events[:limit]:
        weights = ", ".join(
            f"{word}:{weight:.2f}" for word, weight in event["prior_weights"]
        )
        print(
            f"{event['answer']:<7} "
            f"{event['guess_number']:<7} "
            f"{event['normal_guess']:<7} "
            f"{str(event['chosen_is_candidate']):<12} "
            f"{format_remaining_candidates(event['remaining_candidates']):<22} "
            f"{weights}"
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


def write_built_second_map_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=BUILT_SECOND_MAP_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_completed_built_second_map_patterns(path, first_guess):
    csv_path = Path(path)
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            return set()
        if not {"first", "pattern"}.issubset(reader.fieldnames):
            raise ValueError(
                "Existing built second map CSV must include first and pattern columns."
            )
        return {
            row["pattern"]
            for row in reader
            if row.get("first") == first_guess and row.get("pattern")
        }


def open_incremental_built_second_map_csv(path, force=False):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = force or not csv_path.exists() or csv_path.stat().st_size == 0
    mode = "w" if force else "a"
    csv_file = csv_path.open(mode, newline="", encoding="utf-8")
    writer = csv.DictWriter(csv_file, fieldnames=BUILT_SECOND_MAP_COLUMNS)
    if write_header:
        writer.writeheader()
        csv_file.flush()
    return csv_file, writer


def open_incremental_tune_pattern_csv(path, branch_summary=False, include_weighted_columns=False):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = csv_path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        csv_file,
        fieldnames=tune_pattern_csv_columns(
            branch_summary=branch_summary,
            include_weighted_columns=include_weighted_columns,
        ),
    )
    writer.writeheader()
    csv_file.flush()
    return csv_file, writer


def write_tune_pattern_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        fieldnames = tune_pattern_csv_columns(
            branch_summary=bool(rows and "worst_branch_pattern" in rows[0]),
            include_weighted_columns=bool(rows and "weighted_avg" in rows[0]),
        )
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def tune_pattern_csv_columns(branch_summary=False, include_weighted_columns=False):
    if branch_summary and include_weighted_columns:
        return TUNE_PATTERN_WEIGHTED_BRANCH_COLUMNS
    if branch_summary:
        return TUNE_PATTERN_BRANCH_COLUMNS
    if include_weighted_columns:
        return TUNE_PATTERN_WEIGHTED_COLUMNS
    return TUNE_PATTERN_COLUMNS


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
