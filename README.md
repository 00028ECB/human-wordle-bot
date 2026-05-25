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
