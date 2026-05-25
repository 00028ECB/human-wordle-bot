"""Command-line entry point for Wordle Lab."""

import argparse
import csv
from pathlib import Path

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

    try:
        allowed_guesses, possible_answers = load_word_lists(
            allowed_path=args.allowed,
            answers_path=args.answers,
        )
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    if args.compare:
        rows = build_comparison_rows(args.compare, allowed_guesses, possible_answers)
        print_comparison_report(rows)
        if args.csv:
            write_comparison_csv(args.csv, rows)
        return
    if args.top_openers:
        rows = build_top_opener_rows(
            args.top_openers,
            allowed_guesses,
            possible_answers,
            rank_by=args.rank_by,
        )
        print_comparison_report(rows)
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


def build_top_opener_rows(limit, allowed_guesses, possible_answers, rank_by="average"):
    rows = build_comparison_rows(allowed_guesses, allowed_guesses, possible_answers)
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
    solved_in_3_or_fewer = sum(distribution[guess_count] for guess_count in range(1, 4))
    solved_in_4_or_fewer = sum(distribution[guess_count] for guess_count in range(1, 5))
    risk_score = distribution[5] * 2 + distribution[6] * 5 + result.failed_count * 20
    return {
        "first_guess": first_guess,
        "tested": len(result.games),
        "solved": result.solved_count,
        "average": f"{result.average_guesses:.2f}",
        "solved_3_or_less": solved_in_3_or_fewer,
        "solved_4_or_less": solved_in_4_or_fewer,
        "fives": distribution[5],
        "sixes": distribution[6],
        "failed": result.failed_count,
        "risk_score": risk_score,
    }


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
