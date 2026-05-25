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
    if args.csv and not (args.compare or args.top_openers):
        raise SystemExit("--csv can only be used with --compare or --top-openers")
    if args.top_openers is not None and args.top_openers < 1:
        raise SystemExit("--top-openers must be at least 1")
    if args.limit_openers is not None and args.limit_openers < 1:
        raise SystemExit("--limit-openers must be at least 1")

    try:
        allowed_guesses, possible_answers = load_word_lists(
            allowed_path=args.allowed,
            answers_path=args.answers,
        )
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    if args.stats:
        print_stats_report(allowed_guesses, possible_answers)
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


if __name__ == "__main__":
    main()
