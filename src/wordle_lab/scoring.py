"""Wordle scoring helpers."""

from collections import Counter
from functools import cache

GREEN = "G"
YELLOW = "Y"
GRAY = "."


@cache
def score_guess(guess, answer):
    """Return Wordle feedback for a guess as a string of G, Y, and dots."""
    _validate_word_pair(guess, answer)

    result = [GRAY] * len(answer)
    remaining_letters = Counter()

    for index, (guess_letter, answer_letter) in enumerate(zip(guess, answer)):
        if guess_letter == answer_letter:
            result[index] = GREEN
        else:
            remaining_letters[answer_letter] += 1

    for index, guess_letter in enumerate(guess):
        if result[index] == GREEN:
            continue
        if remaining_letters[guess_letter] > 0:
            result[index] = YELLOW
            remaining_letters[guess_letter] -= 1

    return "".join(result)


def is_solved(feedback):
    """Return True when every letter is green."""
    return bool(feedback) and all(mark == GREEN for mark in feedback)


def _validate_word_pair(guess, answer):
    if len(guess) != len(answer):
        raise ValueError("Guess and answer must be the same length.")
    if not guess.isalpha() or not answer.isalpha():
        raise ValueError("Guess and answer must contain only letters.")
