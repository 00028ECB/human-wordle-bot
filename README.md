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
