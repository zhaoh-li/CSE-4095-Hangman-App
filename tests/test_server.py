import json
import unittest

from server import MAX_GAMES, create_app
from words import DIFFICULTIES


class FixedWords:
    """A stand-in WordManager that always picks the same word."""

    def __init__(self, word):
        self.word = word

    def random_word(self, difficulty):
        return self.word


class ServerTestCase(unittest.TestCase):
    WORD = "apple"

    def setUp(self):
        self.app = create_app(word_manager=FixedWords(self.WORD))
        self.client = self.app.test_client()

    def new_game(self, difficulty="medium"):
        response = self.client.post("/api/games", json={"difficulty": difficulty})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def guess(self, game_id, letter):
        return self.client.post(f"/api/games/{game_id}/guess", json={"letter": letter})

    def play(self, game_id, letters):
        for letter in letters:
            response = self.guess(game_id, letter)
            self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def assert_no_word(self, response):
        """The hidden word must not appear anywhere in the response."""
        self.assertNotIn(self.WORD, response.get_data(as_text=True))


class CreateGameTests(ServerTestCase):
    def test_create_returns_201_and_starting_state(self):
        response = self.client.post("/api/games", json={"difficulty": "medium"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.is_json)
        body = response.get_json()
        self.assertEqual(set(body), {
            "game_id", "difficulty", "pattern", "guessed_letters",
            "incorrect_letters", "remaining_guesses", "status",
        })
        self.assertEqual(body["pattern"], "_ _ _ _ _")
        self.assertEqual(body["remaining_guesses"], 6)
        self.assertEqual(body["status"], "playing")
        self.assertEqual(body["guessed_letters"], [])
        self.assertEqual(body["incorrect_letters"], [])
        self.assertRegex(body["game_id"], r"^[0-9a-f]{16}$")
        self.assert_no_word(response)

    def test_every_difficulty_works(self):
        for level in DIFFICULTIES:
            with self.subTest(level=level):
                self.assertEqual(self.new_game(level)["difficulty"], level)

    def test_difficulty_ignores_case(self):
        self.assertEqual(self.new_game("HARD")["difficulty"], "hard")

    def test_bad_difficulty_returns_400(self):
        for body in [{}, {"difficulty": "extreme"}, {"difficulty": ""},
                     {"difficulty": None}, {"difficulty": 3}, {"level": "easy"}]:
            with self.subTest(body=body):
                response = self.client.post("/api/games", json=body)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    def test_body_must_be_a_json_object(self):
        cases = [
            dict(data="difficulty=easy", content_type="application/x-www-form-urlencoded"),
            dict(data='{"difficulty": "easy"', content_type="application/json"),  # broken JSON
            dict(data='["easy"]', content_type="application/json"),               # not an object
            dict(data='"easy"', content_type="application/json"),
            dict(data="", content_type="application/json"),
            dict(),                                                               # no body at all
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                response = self.client.post("/api/games", **kwargs)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())

    def test_extra_fields_are_ignored(self):
        response = self.client.post("/api/games", json={"difficulty": "easy", "word": "cat"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["pattern"], "_ _ _ _ _")  # still "apple"

    def test_game_ids_are_unique(self):
        ids = {self.new_game()["game_id"] for _ in range(200)}
        self.assertEqual(len(ids), 200)


class GetGameTests(ServerTestCase):
    def test_get_returns_current_state(self):
        game = self.new_game()
        self.play(game["game_id"], "pz")
        response = self.client.get(f"/api/games/{game['game_id']}")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["game_id"], game["game_id"])
        self.assertEqual(body["pattern"], "_ p p _ _")
        self.assertEqual(body["guessed_letters"], ["p", "z"])
        self.assertEqual(body["incorrect_letters"], ["z"])
        self.assertEqual(body["remaining_guesses"], 5)
        self.assert_no_word(response)

    def test_unknown_game_returns_404(self):
        response = self.client.get("/api/games/doesnotexist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Game not found."})


class GuessTests(ServerTestCase):
    def setUp(self):
        super().setUp()
        self.game_id = self.new_game()["game_id"]

    def test_correct_guess(self):
        response = self.guess(self.game_id, "p")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["correct"])
        self.assertEqual(body["pattern"], "_ p p _ _")
        self.assertEqual(body["remaining_guesses"], 6)
        self.assert_no_word(response)

    def test_wrong_guess(self):
        body = self.guess(self.game_id, "z").get_json()
        self.assertFalse(body["correct"])
        self.assertEqual(body["incorrect_letters"], ["z"])
        self.assertEqual(body["remaining_guesses"], 5)

    def test_uppercase_guess(self):
        body = self.guess(self.game_id, "E").get_json()
        self.assertTrue(body["correct"])
        self.assertEqual(body["guessed_letters"], ["e"])

    def test_invalid_letter_returns_400_and_changes_nothing(self):
        for letter in ["", "ab", "1", "!", "é", None, 5, ["a"]]:
            with self.subTest(letter=letter):
                response = self.guess(self.game_id, letter)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.get_json())
        state = self.client.get(f"/api/games/{self.game_id}").get_json()
        self.assertEqual(state["guessed_letters"], [])
        self.assertEqual(state["remaining_guesses"], 6)

    def test_missing_letter_returns_400(self):
        response = self.client.post(f"/api/games/{self.game_id}/guess", json={"leter": "a"})
        self.assertEqual(response.status_code, 400)

    def test_guess_body_must_be_json_object(self):
        response = self.client.post(f"/api/games/{self.game_id}/guess", data="letter=a")
        self.assertEqual(response.status_code, 400)

    def test_duplicate_guess_returns_409_and_changes_nothing(self):
        self.guess(self.game_id, "z")
        response = self.guess(self.game_id, "Z")
        self.assertEqual(response.status_code, 409)
        self.assertIn("error", response.get_json())
        state = self.client.get(f"/api/games/{self.game_id}").get_json()
        self.assertEqual(state["remaining_guesses"], 5)

    def test_guess_on_unknown_game_returns_404(self):
        response = self.guess("doesnotexist", "a")
        self.assertEqual(response.status_code, 404)


class FullGameTests(ServerTestCase):
    def test_win(self):
        game_id = self.new_game()["game_id"]
        before_last = self.play(game_id, "apl")
        self.assertNotIn("word", before_last)
        body = self.play(game_id, "e")
        self.assertEqual(body["status"], "won")
        self.assertEqual(body["pattern"], "a p p l e")
        self.assertEqual(body["word"], "apple")

    def test_loss(self):
        game_id = self.new_game()["game_id"]
        before_last = self.play(game_id, "bcdfg")
        self.assertEqual(before_last["status"], "playing")
        self.assertNotIn("word", before_last)
        body = self.play(game_id, "h")
        self.assertEqual(body["status"], "lost")
        self.assertEqual(body["remaining_guesses"], 0)
        self.assertEqual(body["word"], "apple")

    def test_word_shown_by_get_after_game_ends(self):
        game_id = self.new_game()["game_id"]
        self.play(game_id, "aple")
        body = self.client.get(f"/api/games/{game_id}").get_json()
        self.assertEqual(body["word"], "apple")

    def test_no_guesses_after_game_ends(self):
        for letters in ["aple", "bcdfgh"]:
            with self.subTest(letters=letters):
                game_id = self.new_game()["game_id"]
                self.play(game_id, letters)
                response = self.guess(game_id, "z")
                self.assertEqual(response.status_code, 409)

    def test_word_never_leaks_while_playing(self):
        """Every response before the game ends, including errors, hides the word."""
        responses = [self.client.post("/api/games", json={"difficulty": "easy"})]
        game_id = responses[0].get_json()["game_id"]
        for letter in ["a", "a", "zz", "p", "q", "l"]:  # includes a duplicate and an invalid
            responses.append(self.guess(game_id, letter))
        responses.append(self.client.get(f"/api/games/{game_id}"))
        self.assertEqual(responses[-1].get_json()["status"], "playing")
        for response in responses:
            self.assert_no_word(response)
            self.assertNotIn("word", response.get_json())


class SeparateGamesTests(unittest.TestCase):
    def test_guesses_in_one_game_do_not_affect_another(self):
        app = create_app(word_manager=FixedWords("apple"))
        client = app.test_client()
        game_a = client.post("/api/games", json={"difficulty": "easy"}).get_json()["game_id"]
        game_b = client.post("/api/games", json={"difficulty": "easy"}).get_json()["game_id"]

        client.post(f"/api/games/{game_a}/guess", json={"letter": "p"})
        client.post(f"/api/games/{game_a}/guess", json={"letter": "z"})

        a = client.get(f"/api/games/{game_a}").get_json()
        b = client.get(f"/api/games/{game_b}").get_json()
        self.assertEqual(a["guessed_letters"], ["p", "z"])
        self.assertEqual(b["guessed_letters"], [])
        self.assertEqual(b["pattern"], "_ _ _ _ _")
        self.assertEqual(b["remaining_guesses"], 6)

        # The same letter is not a duplicate in a different game.
        response = client.post(f"/api/games/{game_b}/guess", json={"letter": "z"})
        self.assertEqual(response.status_code, 200)

    def test_separate_apps_do_not_share_games(self):
        first = create_app(word_manager=FixedWords("apple")).test_client()
        second = create_app(word_manager=FixedWords("apple")).test_client()
        game_id = first.post("/api/games", json={"difficulty": "easy"}).get_json()["game_id"]
        self.assertEqual(second.get(f"/api/games/{game_id}").status_code, 404)


class GameLimitTests(unittest.TestCase):
    def test_default_limit_is_10000(self):
        self.assertEqual(MAX_GAMES, 10_000)

    def test_oldest_game_is_removed_when_limit_is_reached(self):
        app = create_app(word_manager=FixedWords("apple"), max_games=3)
        client = app.test_client()
        ids = [client.post("/api/games", json={"difficulty": "easy"}).get_json()["game_id"]
               for _ in range(4)]
        self.assertEqual(len(app.config["GAME_STORE"]), 3)
        self.assertEqual(client.get(f"/api/games/{ids[0]}").status_code, 404)
        for game_id in ids[1:]:
            self.assertEqual(client.get(f"/api/games/{game_id}").status_code, 200)


class JsonErrorTests(ServerTestCase):
    def test_unknown_url_returns_json_404(self):
        response = self.client.get("/api/nothing-here")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {"error": "Not found."})

    def test_wrong_method_returns_json_405(self):
        game_id = self.new_game()["game_id"]
        for method, url in [("get", f"/api/games/{game_id}/guess"),
                            ("delete", f"/api/games/{game_id}"),
                            ("get", "/api/games")]:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response.get_json(), {"error": "Method not allowed."})
                self.assertIn("Allow", response.headers)

    def test_unexpected_errors_return_json_500_without_details(self):
        class BrokenWords:
            def random_word(self, difficulty):
                raise RuntimeError("secret internal detail")

        app = create_app(word_manager=BrokenWords())
        app.logger.disabled = True  # keep the test output clean
        response = app.test_client().post("/api/games", json={"difficulty": "easy"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "Internal server error."})
        self.assertNotIn("secret", response.get_data(as_text=True))


class RealWordListTests(unittest.TestCase):
    def test_default_app_uses_real_word_lists(self):
        from server import app

        client = app.test_client()
        for level in DIFFICULTIES:
            with self.subTest(level=level):
                response = client.post("/api/games", json={"difficulty": level})
                self.assertEqual(response.status_code, 201)
                body = response.get_json()
                self.assertEqual(body["status"], "playing")
                self.assertNotIn("word", body)
                json.dumps(body)


if __name__ == "__main__":
    unittest.main()
