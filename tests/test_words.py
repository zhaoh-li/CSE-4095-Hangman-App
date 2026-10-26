import random
import tempfile
import unittest
from pathlib import Path

from words import (
    DIFFICULTIES,
    InvalidDifficultyError,
    WordListError,
    WordManager,
    load_word_list,
    normalize_difficulty,
)


def make_words_dir(tmp, easy="cat\n", medium="apple\n", hard="zephyr\n"):
    """Create a temporary words/ folder with the given file contents."""
    folder = Path(tmp)
    (folder / "easy.txt").write_text(easy, encoding="utf-8")
    (folder / "medium.txt").write_text(medium, encoding="utf-8")
    (folder / "hard.txt").write_text(hard, encoding="utf-8")
    return folder


class RealWordListTests(unittest.TestCase):
    """Checks on the real files in words/."""

    @classmethod
    def setUpClass(cls):
        cls.manager = WordManager()

    def test_every_list_loads_and_is_not_empty(self):
        for level in DIFFICULTIES:
            with self.subTest(level=level):
                self.assertGreater(len(self.manager.words(level)), 0)

    def test_words_are_lowercase_letters_only(self):
        for level in DIFFICULTIES:
            for word in self.manager.words(level):
                with self.subTest(level=level, word=word):
                    self.assertRegex(word, r"^[a-z]+$")

    def test_no_duplicates(self):
        for level in DIFFICULTIES:
            words = self.manager.words(level)
            with self.subTest(level=level):
                self.assertEqual(len(words), len(set(words)))

    def test_random_word_comes_from_the_right_list(self):
        for level in DIFFICULTIES:
            for _ in range(20):
                with self.subTest(level=level):
                    self.assertIn(self.manager.random_word(level), self.manager.words(level))


class DifficultyTests(unittest.TestCase):
    def test_valid_difficulties(self):
        for level in DIFFICULTIES:
            self.assertEqual(normalize_difficulty(level), level)

    def test_difficulty_ignores_case_and_spaces(self):
        self.assertEqual(normalize_difficulty("Medium"), "medium")
        self.assertEqual(normalize_difficulty("  HARD "), "hard")

    def test_invalid_difficulties_are_rejected(self):
        for bad in ["", "extreme", "easyy", None, 1, ["easy"]]:
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidDifficultyError):
                    normalize_difficulty(bad)

    def test_manager_rejects_invalid_difficulty(self):
        manager = WordManager()
        with self.assertRaises(InvalidDifficultyError):
            manager.random_word("extreme")
        with self.assertRaises(InvalidDifficultyError):
            manager.words("extreme")


class LoadWordListTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, text):
        path = self.tmp / "list.txt"
        path.write_text(text, encoding="utf-8")
        return path

    def test_cleans_case_spaces_blank_lines_and_duplicates(self):
        path = self.write("  Apple\nbanana\n\nAPPLE\n   \ncherry  \nbanana\n")
        self.assertEqual(load_word_list(path), ["apple", "banana", "cherry"])

    def test_rejects_words_that_are_not_letters_only(self):
        for bad in ["don't", "café", "abc1", "two words", "high-five"]:
            with self.subTest(bad=bad):
                path = self.write(f"apple\n{bad}\n")
                with self.assertRaises(WordListError) as caught:
                    load_word_list(path)
                self.assertIn("line 2", str(caught.exception))

    def test_rejects_empty_file(self):
        with self.assertRaises(WordListError):
            load_word_list(self.write("\n  \n"))

    def test_rejects_missing_file(self):
        with self.assertRaises(WordListError):
            load_word_list(self.tmp / "missing.txt")


class WordManagerTests(unittest.TestCase):
    def test_loads_from_a_custom_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = WordManager(make_words_dir(tmp, easy="cat\ndog\n"))
            self.assertEqual(manager.words("easy"), ("cat", "dog"))
            self.assertEqual(manager.words("medium"), ("apple",))

    def test_same_seed_picks_same_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = make_words_dir(tmp, easy="a\nb\nc\nd\ne\nf\ng\n")
            first = WordManager(folder, rng=random.Random(42))
            second = WordManager(folder, rng=random.Random(42))
            picks_1 = [first.random_word("easy") for _ in range(10)]
            picks_2 = [second.random_word("easy") for _ in range(10)]
            self.assertEqual(picks_1, picks_2)

    def test_missing_list_file_fails_on_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = make_words_dir(tmp)
            (folder / "hard.txt").unlink()
            with self.assertRaises(WordListError):
                WordManager(folder)


if __name__ == "__main__":
    unittest.main()
