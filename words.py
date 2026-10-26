"""Word management for Hangman: load word lists and pick random words.

This module has no web or UI code, so it can be used and tested on its own.
"""

import random
import string
from pathlib import Path

DIFFICULTIES = ("easy", "medium", "hard")

# Find words/ next to this file, so it works no matter which folder the
# program is started from (for example, when Render runs gunicorn).
WORDS_DIR = Path(__file__).resolve().parent / "words"

_ALLOWED_LETTERS = set(string.ascii_lowercase)


class InvalidDifficultyError(ValueError):
    """Raised when a difficulty is not one of DIFFICULTIES."""


class WordListError(ValueError):
    """Raised when a word list file is missing, empty, or has a bad word."""


def normalize_difficulty(difficulty):
    """Return the difficulty in lowercase, or raise InvalidDifficultyError."""
    if isinstance(difficulty, str):
        cleaned = difficulty.strip().lower()
        if cleaned in DIFFICULTIES:
            return cleaned
    raise InvalidDifficultyError(
        f"Invalid difficulty {difficulty!r}. Choose one of: {', '.join(DIFFICULTIES)}."
    )


def load_word_list(path):
    """Load one word list file.

    Each word is stripped and lowercased. Blank lines are skipped and
    duplicates are removed (first occurrence kept). Any word that is not
    made only of the letters a-z is rejected with a WordListError.
    """
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise WordListError(f"Word list not found: {path}") from None

    words = {}  # a dict keeps insertion order, so it removes duplicates in order
    for line_number, line in enumerate(lines, start=1):
        word = line.strip().lower()
        if not word:
            continue
        if not set(word) <= _ALLOWED_LETTERS:
            raise WordListError(
                f"{path.name} line {line_number}: {line.strip()!r} is not made only of letters a-z."
            )
        words[word] = None

    if not words:
        raise WordListError(f"Word list is empty: {path}")
    return list(words)


class WordManager:
    """Holds the Easy, Medium, and Hard word lists and picks random words.

    The lists are loaded once, when the WordManager is created.
    """

    def __init__(self, words_dir=WORDS_DIR, rng=None):
        words_dir = Path(words_dir)
        self._rng = rng if rng is not None else random.Random()
        self._lists = {
            level: tuple(load_word_list(words_dir / f"{level}.txt"))
            for level in DIFFICULTIES
        }

    def words(self, difficulty):
        """Return all words for a difficulty, as a tuple."""
        return self._lists[normalize_difficulty(difficulty)]

    def random_word(self, difficulty):
        """Return a random word for a difficulty."""
        return self._rng.choice(self.words(difficulty))
