# Wordle Lab

A small local Python project for experimenting with Wordle strategies.

This first version is intentionally simple:

- loads word lists from local text files
- scores guesses with normal Wordle green/yellow/gray logic
- runs a basic filtering strategy over every possible answer
- reports the average number of guesses

No web app, network access, packages, API keys, or secrets are needed.

## Project Structure

```text
wordle-lab/
  README.md
  data/
    allowed_guesses.txt
    answers.txt
  src/
    wordle_lab/
      __init__.py
      __main__.py
      scoring.py
      simulator.py
  tests/
    test_scoring.py
    test_simulator.py
```

## Run The Simulator

From the project folder:

```bash
python -m src.wordle_lab
```

The default strategy starts with `raise`, then keeps the first remaining possible answer that matches all feedback so far.

## Compare Openers

Compare a few first guesses:

```bash
python -m src.wordle_lab --compare raise slate crane trace stare arise
```

Rank openers:

```bash
python -m src.wordle_lab --top-openers 25
python -m src.wordle_lab --top-openers 25 --opener-pool answers
python -m src.wordle_lab --top-openers 25 --opener-pool answers --limit-openers 100
```

`--opener-pool allowed` tests every allowed guess as an opener. This is exhaustive and can be very slow with full-size word lists.

`--opener-pool answers` tests only possible answer words as openers. This is usually better for human-realistic opener experiments and much faster.

Top-opener runs print occasional progress updates, such as:

```text
Tested 100/12972 openers...
```

They also print timing information:

```text
Elapsed seconds: 12.34
Average seconds per opener: 0.0048
```

Use `--limit-openers N` for quick trial runs before starting a full sweep.

## Map Second Guesses

Use a baseline opener, such as `slate`, and see what second guess looks best for each feedback pattern:

```bash
python -m src.wordle_lab --second-guess-map slate
python -m src.wordle_lab --second-guess-map slate --second-guess-pool answers
python -m src.wordle_lab --second-guess-map slate --csv results/second_guess_map_slate.csv
```

`--second-guess-pool allowed` lets second guesses use any allowed guess and is the default.

`--second-guess-pool answers` limits second guesses to possible answer words.

Feedback symbols are:

- `G` = green
- `Y` = yellow
- `.` = gray

## Compare Fixed Strategies

Treat `slate` as a fixed baseline opener:

```bash
python -m src.wordle_lab --strategy baseline --first slate
python -m src.wordle_lab --strategy second-map --first slate --second-guess-pool answers
python -m src.wordle_lab --strategy second-map-trap --first slate --second-guess-pool answers --show-worst 25
python -m src.wordle_lab --strategy second-map-bucket --first slate --second-guess-pool answers --show-worst 25
python -m src.wordle_lab --strategy second-map-hybrid --first slate --second-guess-pool answers --trap-threshold 3
python -m src.wordle_lab --strategy second-map --first slate --second-guess-pool answers --show-worst 25
python -m src.wordle_lab --strategy second-map-bucket --first slate --second-guess-pool answers --worst-patterns 20
python -m src.wordle_lab --tune-pattern slate ....Y --strategy second-map-bucket --second-guess-pool answers --top 25
python -m src.wordle_lab --tune-pattern slate ....Y --strategy second-map-bucket --second-guess-pool answers --second rocky --show-worst 25
python -m src.wordle_lab --strategy second-map --first slate --second-guess-pool answers --csv results/strategy_slate.csv
python -m src.wordle_lab --compare-strategies --csv results/strategy_leaderboard.csv
```

`baseline` uses the normal solver after the first guess.

`second-map` uses the precomputed balanced second guess for the first feedback pattern, then continues with the normal solver.

`second-map-trap` starts the same way, then uses a probe guess when the remaining candidates look like a trap family, such as answers that share four fixed positions.

`second-map-bucket` starts the same way, then chooses later guesses by minimizing the largest feedback bucket among the remaining candidates. This catches broader trap families that do not share exactly four fixed positions.

`second-map-hybrid` uses the normal candidate guess unless it would leave a feedback bucket larger than `--trap-threshold`; then it switches to the bucket probe. The default threshold is 2.

Use `--show-worst N` to print the hardest solved games after the strategy summary. When `--csv` is also used, Wordle Lab writes a companion worst-games CSV next to the strategy CSV with `_worst` added to the file name.

Use `--worst-patterns` to group solved games by the first feedback pattern and rank the hardest patterns by risk. Pass a number, such as `--worst-patterns 20`, to limit the table.

Use `--tune-pattern FIRST PATTERN` to focus on one first-feedback bucket and rank possible second guesses. The ranking prefers lower risk, then lower average guesses, then more solves in four or fewer guesses. Add `--csv` to save the tuning table.

Add `--second WORD` to evaluate one second guess for that pattern. Pair it with `--show-worst N` or `--show-pattern-worst N` to inspect the hardest answers inside that first-feedback bucket.

Built-in second-guess overrides can pin a tuned answer for a specific first word, feedback pattern, and pool. Use `--no-overrides` to compare against the unmodified second-map recommendation.

Use `--compare-strategies` to run the built-in `slate` leaderboard across baseline, second-map, trap, and bucket strategies with both answer-only and allowed second-guess pools.

## Word Lists

The starter word lists in `data/` are tiny so the project stays easy to inspect.

- `data/answers.txt` contains possible answer words.
- `data/allowed_guesses.txt` contains allowed guesses.

Add more five-letter lowercase words, one word per line, to run larger experiments.

## Run Tests

From the project folder:

```bash
python -m unittest discover
```
