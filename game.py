"""Core Hangman game engine.

This module knows the rules of Hangman and nothing about Flask, the
browser, or the terminal. The server turns its results into HTTP responses.
"""

import string

from words import WordManager, normalize_difficulty

MAX_INCORRECT_GUESSES = 6

PLAYING = "playing"
WON = "won"
LOST = "lost"

_ALLOWED_LETTERS = set(string.ascii_lowercase)

# Created on first use, so importing game.py doesn't read files.
_default_word_manager = None


class GuessError(ValueError):
    """Base class for guesses that are rejected. Rejected guesses never change the game."""


class InvalidGuessError(GuessError):
    """The guess is not exactly one letter a-z."""


class DuplicateGuessError(GuessError):
    """The letter was already guessed."""


class GameOverError(GuessError):
    """The game is already won or lost, so no more guesses are allowed."""


def _get_default_word_manager():
    global _default_word_manager
    if _default_word_manager is None:
        _default_word_manager = WordManager()
    return _default_word_manager


class HangmanGame:
    """One game of Hangman.

    The hidden word is kept in self._word and is only included in
    to_dict() after the game is over.
    """

    def __init__(self, word, max_incorrect=MAX_INCORRECT_GUESSES, difficulty=None):
        cleaned = word.strip().lower() if isinstance(word, str) else ""
        if not cleaned or not set(cleaned) <= _ALLOWED_LETTERS:
            raise ValueError("The word must be made only of letters a-z.")
        if max_incorrect < 1:
            raise ValueError("max_incorrect must be at least 1.")

        self._word = cleaned
        self.max_incorrect = max_incorrect
        self.difficulty = difficulty
        self._guessed = []  # every accepted guess, in the order made

    @classmethod
    def from_difficulty(cls, difficulty, word_manager=None, max_incorrect=MAX_INCORRECT_GUESSES):
        """Start a game with a random word from the given difficulty."""
        level = normalize_difficulty(difficulty)
        manager = word_manager if word_manager is not None else _get_default_word_manager()
        return cls(manager.random_word(level), max_incorrect=max_incorrect, difficulty=level)

    # ----- Read-only game state -----

    @property
    def guessed_letters(self):
        return list(self._guessed)

    @property
    def correct_letters(self):
        return [letter for letter in self._guessed if letter in self._word]

    @property
    def incorrect_letters(self):
        return [letter for letter in self._guessed if letter not in self._word]

    @property
    def remaining_guesses(self):
        return self.max_incorrect - len(self.incorrect_letters)

    @property
    def pattern(self):
        """The word with unguessed letters shown as '_', e.g. '_ e _ _ e'."""
        return " ".join(c if c in self._guessed else "_" for c in self._word)

    @property
    def status(self):
        if all(c in self._guessed for c in self._word):
            return WON
        if self.remaining_guesses <= 0:
            return LOST
        return PLAYING

    @property
    def is_over(self):
        return self.status != PLAYING

    # ----- Actions -----

    def guess(self, letter):
        """Guess one letter. Returns True if it is in the word, False if not.

        Raises GameOverError, InvalidGuessError, or DuplicateGuessError
        without changing the game.
        """
        if self.is_over:
            raise GameOverError(f"The game is already {self.status}.")
        if not isinstance(letter, str):
            raise InvalidGuessError("A guess must be a single letter a-z.")
        cleaned = letter.strip().lower()
        if len(cleaned) != 1 or cleaned not in _ALLOWED_LETTERS:
            raise InvalidGuessError("A guess must be a single letter a-z.")
        if cleaned in self._guessed:
            raise DuplicateGuessError(f"The letter {cleaned!r} was already guessed.")

        self._guessed.append(cleaned)
        return cleaned in self._word

    def to_dict(self):
        """Game state that is safe to send to a client.

        The hidden word is included only after the game has ended.
        """
        state = {
            "pattern": self.pattern,
            "guessed_letters": self.guessed_letters,
            "incorrect_letters": self.incorrect_letters,
            "remaining_guesses": self.remaining_guesses,
            "status": self.status,
        }
        if self.is_over:
            state["word"] = self._word
        return state
