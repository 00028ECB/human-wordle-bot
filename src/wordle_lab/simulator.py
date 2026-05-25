"""Simple command-line Wordle strategy simulator."""

from dataclasses import dataclass
from pathlib import Path

from .scoring import is_solved, score_guess

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALLOWED_GUESSES_PATH = PROJECT_ROOT / "data" / "allowed_guesses.txt"
DEFAULT_ANSWERS_PATH = PROJECT_ROOT / "data" / "answers.txt"
DEFAULT_FIRST_GUESS = "raise"


@dataclass(frozen=True)
class GameResult:
    answer: str
    guesses: tuple[str, ...]
    solved: bool

    @property
    def guess_count(self):
        return len(self.guesses)


@dataclass(frozen=True)
class SimulationResult:
    games: tuple[GameResult, ...]

    @property
    def average_guesses(self):
        if not self.games:
            return 0
        return sum(game.guess_count for game in self.games) / len(self.games)

    @property
    def solved_count(self):
        return sum(1 for game in self.games if game.solved)

    @property
    def failed_count(self):
        return sum(1 for game in self.games if not game.solved)

    @property
    def guess_distribution(self):
        distribution = {guess_count: 0 for guess_count in range(1, 7)}
        for game in self.games:
            if game.solved and game.guess_count in distribution:
                distribution[game.guess_count] += 1
        return distribution


def load_words(path, word_length=5):
    """Load lowercase words from a text file, skipping blanks and comments."""
    words = []
    seen = set()
    path = Path(path)

    try:
        word_file = path.open(encoding="utf-8")
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Word list file not found: {path}") from error

    with word_file:
        for line_number, line in enumerate(word_file, start=1):
            word = line.strip()
            if not word or word.startswith("#"):
                continue
            if len(word) != word_length or not word.isalpha() or word != word.lower():
                raise ValueError(f"Invalid word on line {line_number}: {word!r}")
            if word not in seen:
                seen.add(word)
                words.append(word)

    return tuple(words)


def filter_candidates(candidates, guess, feedback):
    """Keep answers that would produce the same feedback for this guess."""
    return tuple(
        candidate
        for candidate in candidates
        if score_guess(guess, candidate) == feedback
    )


def play_game(answer, allowed_guesses, possible_answers, first_guess=DEFAULT_FIRST_GUESS):
    """Play one game using a simple first-remaining-answer strategy."""
    if answer not in possible_answers:
        raise ValueError(f"Answer {answer!r} is not in the possible answer list.")
    if first_guess not in allowed_guesses:
        raise ValueError(f"First guess {first_guess!r} is not in the allowed guess list.")

    candidates = tuple(possible_answers)
    guesses = []
    next_guess = first_guess

    while True:
        if next_guess in guesses:
            raise RuntimeError(f"Strategy repeated guess {next_guess!r}.")

        guesses.append(next_guess)
        feedback = score_guess(next_guess, answer)
        if is_solved(feedback):
            return GameResult(answer=answer, guesses=tuple(guesses), solved=True)

        candidates = filter_candidates(candidates, next_guess, feedback)
        next_guess = _choose_next_guess(candidates, allowed_guesses)


def run_simulation(allowed_guesses, possible_answers, first_guess=DEFAULT_FIRST_GUESS):
    """Run the strategy once for every possible answer."""
    games = tuple(
        play_game(answer, allowed_guesses, possible_answers, first_guess)
        for answer in possible_answers
    )
    return SimulationResult(games=games)


def load_default_word_lists():
    """Load the default local word lists."""
    return load_word_lists(
        allowed_path=DEFAULT_ALLOWED_GUESSES_PATH,
        answers_path=DEFAULT_ANSWERS_PATH,
    )


def load_word_lists(allowed_path, answers_path):
    """Load allowed guesses and possible answers from local files."""
    allowed_guesses = load_words(allowed_path)
    possible_answers = load_words(answers_path)
    missing_answers = set(possible_answers) - set(allowed_guesses)
    if missing_answers:
        missing = ", ".join(sorted(missing_answers))
        raise ValueError(f"Answers missing from allowed guesses: {missing}")
    return allowed_guesses, possible_answers


def _choose_next_guess(candidates, allowed_guesses):
    if not candidates:
        raise RuntimeError("No possible answers remain for this feedback.")

    allowed = set(allowed_guesses)
    for candidate in candidates:
        if candidate in allowed:
            return candidate

    raise RuntimeError("No remaining candidate is allowed as a guess.")
