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

SECOND_GUESS_OVERRIDES = {
    ("slate", ".....", "answers"): "frond",
    ("slate", "...Y.", "answers"): "tough",
    ("slate", "....Y", "answers"): "rocky",
    ("slate", "..Y..", "answers"): "randy",
    ("slate", "..Y.Y", "answers"): "march",
    ("slate", "..YY.", "answers"): "pouch",
    ("slate", ".Y...", "answers"): "dilly",
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
        "--trap-threshold",
        type=int,
        default=2,
        metavar="N",
        help="max bucket threshold for --strategy second-map-hybrid (default: 2)",
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
        args.compare or args.top_openers or args.second_guess_map or args.strategy
        or args.compare_strategies or args.tune_pattern
    ):
        raise SystemExit(
            "--csv can only be used with --compare, --top-openers, --second-guess-map, --strategy, --compare-strategies, or --tune-pattern"
        )
    if args.top_openers is not None and args.top_openers < 1:
        raise SystemExit("--top-openers must be at least 1")
    if args.limit_openers is not None and args.limit_openers < 1:
        raise SystemExit("--limit-openers must be at least 1")
    if args.show_worst is not None and args.show_worst < 1:
        raise SystemExit("--show-worst must be at least 1")
    if args.show_pattern_worst is not None and args.show_pattern_worst < 1:
        raise SystemExit("--show-pattern-worst must be at least 1")
    if args.worst_patterns is not None and args.worst_patterns == 0:
        raise SystemExit("--worst-patterns must be at least 1 when a limit is provided")
    if args.worst_patterns is not None and not args.strategy:
        raise SystemExit("--worst-patterns can only be used with --strategy")
    if args.trap_threshold < 1:
        raise SystemExit("--trap-threshold must be at least 1")
    if args.top < 1:
        raise SystemExit("--top must be at least 1")

    try:
        allowed_guesses, possible_answers = load_word_lists(
            allowed_path=args.allowed,
            answers_path=args.answers,
        )
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    if args.compare_strategies:
        rows = build_strategy_comparison_rows(
            allowed_guesses,
            possible_answers,
            use_overrides=not args.no_overrides,
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
            )
        except ValueError as error:
            parser.error(str(error))
        print_tune_pattern_report(rows)
        pattern_worst_limit = args.show_pattern_worst or args.show_worst
        if pattern_worst_limit and args.second:
            print_worst_games(build_worst_game_rows(pattern_games, pattern_worst_limit))
        if args.csv:
            write_tune_pattern_csv(args.csv, rows)
        return
    if args.strategy:
        try:
            row, games = build_strategy_result(
                args.strategy,
                args.first.lower(),
                allowed_guesses,
                possible_answers,
                second_guess_pool_name=args.second_guess_pool,
                trap_threshold=args.trap_threshold,
                use_overrides=not args.no_overrides,
            )
        except ValueError as error:
            parser.error(str(error))
        print_strategy_report((row,))
        worst_rows = ()
        if args.worst_patterns is not None:
            pattern_limit = None if args.worst_patterns == -1 else args.worst_patterns
            print_worst_patterns(build_worst_pattern_rows(games, pattern_limit))
        if args.show_worst:
            worst_rows = build_worst_game_rows(games, args.show_worst)
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


def build_tune_pattern_rows(
    first_guess,
    pattern,
    strategy,
    allowed_guesses,
    possible_answers,
    second_guess_pool,
    top=25,
    trap_threshold=2,
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
            )
            for answer in candidates
        )
        if second_guess:
            selected_games = games
        rows.append(build_tune_pattern_row(pattern, current_second_guess, len(candidates), games))

    ranked_rows = sorted(
        rows,
        key=lambda row: (
            row["risk_score"],
            float(row["average"]),
            -row["solved_4_or_less"],
            row["second_guess"],
        ),
    )
    return tuple(ranked_rows[:top]), selected_games


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
):
    return choose_next_guess_with_optional_probe(
        candidates,
        previous_guesses,
        allowed_guesses,
        probe_pool,
        use_trap_avoidance=(strategy == "second-map-trap"),
        use_bucket_strategy=(strategy == "second-map-bucket"),
        use_hybrid_strategy=(strategy == "second-map-hybrid"),
        trap_threshold=trap_threshold,
    )


def build_tune_pattern_row(pattern, second_guess, candidate_count, games):
    summary = build_summary_row_from_games(second_guess, games)
    return {
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


def print_tune_pattern_report(rows):
    print("Pattern  Second  Candidates  Avg   <=3   <=4   5s  6s  Fail  Risk")
    for row in rows:
        print(
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


def build_strategy_comparison_rows(
    allowed_guesses,
    possible_answers,
    first_guess="slate",
    use_overrides=True,
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
        )
        if strategy == "baseline":
            row = {**row, "second_guess_pool": "-"}
        rows.append(row)
    return tuple(rows)


def build_strategy_row(
    strategy,
    first_guess,
    allowed_guesses,
    possible_answers,
    second_guess_pool_name="allowed",
    trap_threshold=2,
    use_overrides=True,
):
    row, _games = build_strategy_result(
        strategy,
        first_guess,
        allowed_guesses,
        possible_answers,
        second_guess_pool_name=second_guess_pool_name,
        trap_threshold=trap_threshold,
        use_overrides=use_overrides,
    )
    return row


def build_strategy_result(
    strategy,
    first_guess,
    allowed_guesses,
    possible_answers,
    second_guess_pool_name="allowed",
    trap_threshold=2,
    use_overrides=True,
):
    if first_guess not in allowed_guesses:
        raise ValueError(f"First guess {first_guess!r} is not in the allowed guess list.")

    if strategy == "baseline":
        result = run_simulation(
            allowed_guesses=allowed_guesses,
            possible_answers=possible_answers,
            first_guess=first_guess,
        )
        summary = build_comparison_row(first_guess, result)
        return {
            "strategy": "baseline",
            "first_guess": first_guess,
            "second_guess_pool": "",
            **summary,
        }, result.games

    if strategy in {
        "second-map",
        "second-map-trap",
        "second-map-bucket",
        "second-map-hybrid",
    }:
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
        if use_overrides:
            apply_second_guess_overrides(
                first_guess,
                second_guess_pool_name,
                second_guess_pool,
                second_guess_by_pattern,
            )
        games = tuple(
            play_second_map_game(
                answer,
                allowed_guesses,
                possible_answers,
                first_guess,
                second_guess_by_pattern,
                use_trap_avoidance=(strategy == "second-map-trap"),
                use_bucket_strategy=(strategy == "second-map-bucket"),
                use_hybrid_strategy=(strategy == "second-map-hybrid"),
                trap_threshold=trap_threshold,
                probe_pool=second_guess_pool,
            )
            for answer in possible_answers
        )
        summary = build_summary_row_from_games(first_guess, games)
        return {
            "strategy": strategy,
            "first_guess": first_guess,
            "second_guess_pool": second_guess_pool_name,
            **summary,
        }, games

    raise ValueError(f"Unsupported strategy: {strategy}")


def play_second_map_game(
    answer,
    allowed_guesses,
    possible_answers,
    first_guess,
    second_guess_by_pattern,
    use_trap_avoidance=False,
    use_bucket_strategy=False,
    use_hybrid_strategy=False,
    trap_threshold=2,
    probe_pool=None,
):
    guesses = []
    candidates = tuple(possible_answers)
    if probe_pool is None:
        probe_pool = allowed_guesses

    feedback = score_guess(first_guess, answer)
    guesses.append(first_guess)
    if is_solved(feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    candidates = filter_candidates_by_feedback(candidates, first_guess, feedback)
    second_guess = second_guess_by_pattern[feedback]
    feedback = score_guess(second_guess, answer)
    guesses.append(second_guess)
    if is_solved(feedback):
        return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

    candidates = filter_candidates_by_feedback(candidates, second_guess, feedback)
    while candidates:
        next_guess = choose_next_guess_with_optional_probe(
            candidates,
            guesses,
            allowed_guesses,
            probe_pool,
            use_trap_avoidance,
            use_bucket_strategy,
            use_hybrid_strategy,
            trap_threshold,
        )
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
    allowed = set(allowed_guesses)
    previous = set(previous_guesses)
    for candidate in candidates:
        if candidate in allowed and candidate not in previous:
            return candidate
    raise RuntimeError("No remaining candidate is available as a new guess.")


def choose_next_guess_with_optional_probe(
    candidates,
    previous_guesses,
    allowed_guesses,
    probe_pool,
    use_trap_avoidance,
    use_bucket_strategy=False,
    use_hybrid_strategy=False,
    trap_threshold=2,
):
    if use_hybrid_strategy:
        return choose_hybrid_guess(
            candidates,
            previous_guesses,
            allowed_guesses,
            probe_pool,
            trap_threshold,
        )
    if use_bucket_strategy:
        return choose_bucket_probe(candidates, previous_guesses, probe_pool)
    if use_trap_avoidance and is_trap_family(candidates):
        probe = choose_trap_probe(candidates, previous_guesses, probe_pool)
        if probe is not None:
            return probe
    return choose_next_candidate(candidates, previous_guesses, allowed_guesses)


def choose_hybrid_guess(
    candidates,
    previous_guesses,
    allowed_guesses,
    probe_pool,
    trap_threshold,
):
    normal_guess = choose_next_candidate(candidates, previous_guesses, allowed_guesses)
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

    if best_guess is None:
        raise RuntimeError("No available bucket probe guess.")
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


def build_worst_game_rows(games, limit):
    solved_games = [game for game in games if game.solved]
    worst_games = sorted(
        solved_games,
        key=lambda game: (-game.guess_count, game.answer),
    )
    return tuple(format_worst_game_row(game) for game in worst_games[:limit])


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


def format_worst_game_row(game):
    feedbacks = tuple(score_guess(guess, game.answer) for guess in game.guesses)
    return {
        "answer": game.answer,
        "guess_count": game.guess_count,
        "path": " -> ".join(game.guesses),
        "feedback": " -> ".join(feedbacks),
    }


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


def write_tune_pattern_csv(path, rows):
    csv_path = Path(path)
    if csv_path.parent != Path("."):
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=TUNE_PATTERN_COLUMNS)
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
