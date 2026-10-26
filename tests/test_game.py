import json
import tempfile
import unittest
from pathlib import Path

from game import (
    LOST,
    MAX_INCORRECT_GUESSES,
    PLAYING,
    WON,
    DuplicateGuessError,
    GameOverError,
    HangmanGame,
    InvalidGuessError,
)
from words import InvalidDifficultyError, WordManager


def play(game, letters):
    for letter in letters:
        game.guess(letter)
    return game


class NewGameTests(unittest.TestCase):
    def test_starting_state(self):
        game = HangmanGame("apple")
        self.assertEqual(game.pattern, "_ _ _ _ _")
        self.assertEqual(game.remaining_guesses, MAX_INCORRECT_GUESSES)
        self.assertEqual(game.max_incorrect, 6)
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.guessed_letters, [])
        self.assertEqual(game.correct_letters, [])
        self.assertEqual(game.incorrect_letters, [])
        self.assertFalse(game.is_over)

    def test_word_is_lowercased(self):
        game = play(HangmanGame("Apple"), "a")
        self.assertEqual(game.pattern, "a _ _ _ _")

    def test_rejects_bad_words(self):
        for bad in ["", "  ", "abc1", "don't", None]:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    HangmanGame(bad)


class GuessTests(unittest.TestCase):
    def test_correct_guess(self):
        game = HangmanGame("apple")
        self.assertTrue(game.guess("p"))
        self.assertEqual(game.pattern, "_ p p _ _")
        self.assertEqual(game.correct_letters, ["p"])
        self.assertEqual(game.incorrect_letters, [])
        self.assertEqual(game.remaining_guesses, 6)

    def test_incorrect_guess(self):
        game = HangmanGame("apple")
        self.assertFalse(game.guess("z"))
        self.assertEqual(game.pattern, "_ _ _ _ _")
        self.assertEqual(game.incorrect_letters, ["z"])
        self.assertEqual(game.remaining_guesses, 5)

    def test_uppercase_and_spaces_are_normalized(self):
        game = HangmanGame("apple")
        self.assertTrue(game.guess(" E "))
        self.assertEqual(game.guessed_letters, ["e"])
        self.assertEqual(game.pattern, "_ _ _ _ e")

    def test_guessed_letters_keep_their_order(self):
        game = play(HangmanGame("apple"), ["z", "a", "q", "p"])
        self.assertEqual(game.guessed_letters, ["z", "a", "q", "p"])
        self.assertEqual(game.correct_letters, ["a", "p"])
        self.assertEqual(game.incorrect_letters, ["z", "q"])

    def test_invalid_guesses_are_rejected_without_changes(self):
        game = play(HangmanGame("apple"), "z")
        before = game.to_dict()
        for bad in ["", " ", "ab", "1", "!", "é", None, 5]:
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidGuessError):
                    game.guess(bad)
                self.assertEqual(game.to_dict(), before)

    def test_duplicate_guesses_are_rejected_without_changes(self):
        game = play(HangmanGame("apple"), ["a", "z"])
        before = game.to_dict()
        for repeat in ["a", "A", "z", "Z"]:
            with self.subTest(repeat=repeat):
                with self.assertRaises(DuplicateGuessError):
                    game.guess(repeat)
                self.assertEqual(game.to_dict(), before)


class WinLossTests(unittest.TestCase):
    def test_win(self):
        game = play(HangmanGame("apple"), "aple")
        self.assertEqual(game.status, WON)
        self.assertTrue(game.is_over)
        self.assertEqual(game.pattern, "a p p l e")

    def test_win_with_some_wrong_guesses(self):
        game = play(HangmanGame("apple"), "azpqle")
        self.assertEqual(game.status, WON)
        self.assertEqual(game.remaining_guesses, 4)

    def test_still_playing_after_five_wrong_guesses(self):
        game = play(HangmanGame("apple"), "bcdfg")
        self.assertEqual(game.status, PLAYING)
        self.assertEqual(game.remaining_guesses, 1)

    def test_loss_after_six_wrong_guesses(self):
        game = play(HangmanGame("apple"), "bcdfgh")
        self.assertEqual(game.status, LOST)
        self.assertTrue(game.is_over)
        self.assertEqual(game.remaining_guesses, 0)

    def test_custom_max_incorrect(self):
        game = play(HangmanGame("apple", max_incorrect=2), "bc")
        self.assertEqual(game.status, LOST)

    def test_no_guesses_after_a_win(self):
        game = play(HangmanGame("cat"), "cat")
        before = game.to_dict()
        for letter in ["z", "c", "ab"]:
            with self.subTest(letter=letter):
                with self.assertRaises(GameOverError):
                    game.guess(letter)
        self.assertEqual(game.to_dict(), before)

    def test_no_guesses_after_a_loss(self):
        game = play(HangmanGame("cat"), "bdefgh")
        before = game.to_dict()
        with self.assertRaises(GameOverError):
            game.guess("c")
        self.assertEqual(game.to_dict(), before)


class ClientSafeStateTests(unittest.TestCase):
    EXPECTED_KEYS = {"pattern", "guessed_letters", "incorrect_letters", "remaining_guesses", "status"}

    def test_state_while_playing_has_no_word(self):
        game = play(HangmanGame("apple"), "pz")
        state = game.to_dict()
        self.assertEqual(set(state), self.EXPECTED_KEYS)
        self.assertNotIn("apple", json.dumps(state))
        self.assertEqual(state, {
            "pattern": "_ p p _ _",
            "guessed_letters": ["p", "z"],
            "incorrect_letters": ["z"],
            "remaining_guesses": 5,
            "status": "playing",
        })

    def test_word_hidden_until_one_letter_left(self):
        game = play(HangmanGame("apple"), "apl")
        self.assertNotIn("word", game.to_dict())

    def test_word_revealed_after_win(self):
        state = play(HangmanGame("apple"), "aple").to_dict()
        self.assertEqual(state["word"], "apple")
        self.assertEqual(state["status"], "won")

    def test_word_revealed_after_loss(self):
        state = play(HangmanGame("apple"), "bcdfgh").to_dict()
        self.assertEqual(state["word"], "apple")
        self.assertEqual(state["status"], "lost")

    def test_state_is_json_serializable(self):
        json.dumps(HangmanGame("apple").to_dict())

    def test_changing_returned_lists_does_not_change_the_game(self):
        game = play(HangmanGame("apple"), "z")
        game.guessed_letters.append("q")
        game.to_dict()["incorrect_letters"].append("q")
        self.assertEqual(game.guessed_letters, ["z"])
        self.assertEqual(game.incorrect_letters, ["z"])


class FromDifficultyTests(unittest.TestCase):
    def test_uses_a_word_from_the_chosen_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "easy.txt").write_text("cat\n", encoding="utf-8")
            (folder / "medium.txt").write_text("apple\n", encoding="utf-8")
            (folder / "hard.txt").write_text("zephyr\n", encoding="utf-8")
            manager = WordManager(folder)

            game = HangmanGame.from_difficulty("Medium", word_manager=manager)
            self.assertEqual(game.difficulty, "medium")
            self.assertEqual(game.pattern, "_ _ _ _ _")
            play(game, "aple")
            self.assertEqual(game.to_dict()["word"], "apple")

    def test_default_word_manager_uses_real_lists(self):
        for level in ["easy", "medium", "hard"]:
            with self.subTest(level=level):
                game = HangmanGame.from_difficulty(level)
                self.assertEqual(game.status, PLAYING)
                self.assertEqual(game.difficulty, level)

    def test_invalid_difficulty(self):
        with self.assertRaises(InvalidDifficultyError):
            HangmanGame.from_difficulty("extreme")


if __name__ == "__main__":
    unittest.main()
