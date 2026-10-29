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


class HealthTests(ServerTestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_health_does_not_create_games(self):
        self.client.get("/api/health")
        self.assertEqual(len(self.app.config["GAME_STORE"]), 0)


class EdgeCaseTests(ServerTestCase):
    def test_uppercase_repeat_is_a_duplicate(self):
        game_id = self.new_game()["game_id"]
        self.guess(game_id, "e")
        response = self.guess(game_id, "E")
        self.assertEqual(response.status_code, 409)

    def test_finished_game_removed_by_limit_returns_404(self):
        app = create_app(word_manager=FixedWords("cat"), max_games=1)
        client = app.test_client()
        old = client.post("/api/games", json={"difficulty": "easy"}).get_json()["game_id"]
        for letter in "cat":
            client.post(f"/api/games/{old}/guess", json={"letter": letter})
        client.post("/api/games", json={"difficulty": "easy"})  # pushes the old game out
        self.assertEqual(client.get(f"/api/games/{old}").status_code, 404)
        self.assertEqual(client.post(f"/api/games/{old}/guess", json={"letter": "z"}).status_code, 404)

    def test_repeated_random_id_is_replaced(self):
        from unittest import mock
        import server

        store = server.GameStore()
        with mock.patch.object(server.secrets, "token_hex",
                               side_effect=["aaaa", "aaaa", "bbbb"]):
            first = store.add(object())
            second = store.add(object())
        self.assertEqual((first, second), ("aaaa", "bbbb"))
        self.assertEqual(len(store), 2)


class ConcurrencyTests(unittest.TestCase):
    """Many requests at the same time must not lose or double-count guesses."""

    def test_simultaneous_guesses_on_one_game(self):
        import threading
        from werkzeug.serving import make_server
        import urllib.request

        word = "abcdefghijklmnopqrstuvwxyz"  # every guess is correct, so the game never ends early
        app = create_app(word_manager=FixedWords(word))
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.port}"

        def post(path, body):
            request = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    return response.status
            except urllib.error.HTTPError as error:
                error.close()
                return error.code

        try:
            game_id = json.loads(urllib.request.urlopen(urllib.request.Request(
                base + "/api/games", data=b'{"difficulty":"easy"}',
                headers={"Content-Type": "application/json"}, method="POST"), timeout=10).read())["game_id"]

            # 26 letters, each sent twice at the same moment: one of each pair must win, one must be a duplicate.
            letters = list(word) * 2
            results = [None] * len(letters)
            start = threading.Barrier(len(letters))

            def worker(i, letter):
                start.wait()
                results[i] = post(f"/api/games/{game_id}/guess", {"letter": letter})

            workers = [threading.Thread(target=worker, args=(i, l)) for i, l in enumerate(letters)]
            for w in workers:
                w.start()
            for w in workers:
                w.join(timeout=20)

            self.assertEqual(results.count(200), 26)
            self.assertEqual(results.count(409), 26)
            state = app.config["GAME_STORE"].get(game_id).to_dict()
            self.assertEqual(sorted(state["guessed_letters"]), list(word))
            self.assertEqual(state["status"], "won")
        finally:
            server.shutdown()
            thread.join(timeout=5)

    def test_simultaneous_new_games_get_unique_ids(self):
        import threading

        app = create_app(word_manager=FixedWords("apple"))
        ids = []
        lock = threading.Lock()

        def make_games():
            client = app.test_client()
            for _ in range(20):
                game_id = client.post("/api/games", json={"difficulty": "easy"}).get_json()["game_id"]
                with lock:
                    ids.append(game_id)

        threads = [threading.Thread(target=make_games) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        self.assertEqual(len(ids), 200)
        self.assertEqual(len(set(ids)), 200)
        self.assertEqual(len(app.config["GAME_STORE"]), 200)


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


# ---------------------------------------------------------------------------
# Phase 5: the web page and security headers
# ---------------------------------------------------------------------------

import re
import shutil
import subprocess
from pathlib import Path

from server import SECURITY_HEADERS
from words import WordManager

STATIC = Path(__file__).resolve().parent.parent / "static"


class WebPageTests(ServerTestCase):
    def test_home_page_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/html")
        html = response.get_data(as_text=True)
        response.close()
        for needed in ['id="keyboard"', 'id="pattern"', 'id="hangman"', 'id="new-game"',
                       'id="message"', 'id="remaining"', 'id="guessed"', 'id="wrong"',
                       'value="easy"', 'value="medium"', 'value="hard"',
                       "/static/app.js", "/static/style.css"]:
            with self.subTest(needed=needed):
                self.assertIn(needed, html)

    def test_drawing_has_six_parts(self):
        response = self.client.get("/")
        html = response.get_data(as_text=True)
        response.close()
        parts = re.findall(r'class="part" data-part="(\d)"', html)
        self.assertEqual(parts, ["1", "2", "3", "4", "5", "6"])

    def test_static_files_are_served_with_right_types(self):
        for path, mimetype in [("/static/app.js", "text/javascript"),
                               ("/static/style.css", "text/css")]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, mimetype)
                self.assertGreater(len(response.get_data()), 100)
                response.close()

    def test_page_uses_fetch_and_only_the_api(self):
        js = (STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn("fetch(", js)
        self.assertIn("/api/games", js)
        self.assertNotIn("innerHTML", js)  # text is always set with textContent

    def test_every_element_app_js_uses_exists_in_the_page(self):
        js = (STATIC / "app.js").read_text(encoding="utf-8")
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        ids = re.findall(r'getElementById\("([^"]+)"\)', js)
        self.assertGreater(len(ids), 5)
        for element_id in ids:
            with self.subTest(id=element_id):
                self.assertIn(f'id="{element_id}"', html)

    def test_no_inline_scripts_or_styles(self):
        """Needed for the Content-Security-Policy to allow the page."""
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, r"<script(?![^>]*\bsrc=)")
        self.assertNotIn("<style", html)
        self.assertNotIn("style=", html)
        self.assertNotRegex(html, r"\son[a-z]+=")  # no onclick= etc.


class NoWordListInBrowserTests(unittest.TestCase):
    """The browser must not contain the game's words or a way to load them."""

    def test_static_files_never_load_word_lists(self):
        for path in STATIC.iterdir():
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotIn("words/", text)
                self.assertNotIn(".txt", text)

    def test_static_files_do_not_embed_a_word_list(self):
        # Ordinary words like "letter" or "message" are fine. A copied word
        # list would put hundreds of list words into the file.
        manager = WordManager()
        all_words = {w for level in ("easy", "medium", "hard") for w in manager.words(level)}
        for path in STATIC.iterdir():
            text = path.read_text(encoding="utf-8").lower()
            found = set(re.findall(r"[a-z]+", text)) & all_words
            with self.subTest(file=path.name):
                self.assertLess(len(found), 40, sorted(found))

    def test_page_does_not_contain_the_hidden_word(self):
        app = create_app(word_manager=FixedWords("zymurgy"))
        client = app.test_client()
        client.post("/api/games", json={"difficulty": "hard"})
        for path in ["/", "/static/app.js", "/static/style.css"]:
            response = client.get(path)
            with self.subTest(path=path):
                self.assertNotIn("zymurgy", response.get_data(as_text=True))
            response.close()


class SecurityHeaderTests(ServerTestCase):
    def assert_security_headers(self, response):
        for name, value in SECURITY_HEADERS.items():
            self.assertEqual(response.headers.get(name), value, name)

    def test_headers_on_page_api_static_and_errors(self):
        game_id = self.new_game()["game_id"]
        requests = [
            ("get", "/"),
            ("get", "/static/app.js"),
            ("get", "/api/health"),
            ("get", f"/api/games/{game_id}"),
            ("get", "/api/games/nope"),       # 404
            ("get", "/nothing-here"),         # 404 from Flask
            ("delete", "/api/games"),         # 405
        ]
        for method, url in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assert_security_headers(response)
                response.close()

    def test_headers_on_server_error(self):
        class BrokenWords:
            def random_word(self, difficulty):
                raise RuntimeError("boom")

        app = create_app(word_manager=BrokenWords())
        app.logger.disabled = True
        response = app.test_client().post("/api/games", json={"difficulty": "easy"})
        self.assertEqual(response.status_code, 500)
        self.assert_security_headers(response)

    def test_csp_only_allows_this_site(self):
        csp = SECURITY_HEADERS["Content-Security-Policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)


@unittest.skipUnless(shutil.which("node"), "Node.js not installed")
class JavaScriptSyntaxTests(unittest.TestCase):
    def test_app_js_has_valid_syntax(self):
        result = subprocess.run(["node", "--check", str(STATIC / "app.js")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
