import io
import logging
import socket
import threading
import unittest

from werkzeug.serving import make_server

# Hide the test server's per-request log lines.
logging.getLogger("werkzeug").setLevel(logging.ERROR)

from server import create_app
from terminal_client import (
    HANGMAN_STAGES,
    ApiError,
    HangmanClient,
    ServerUnavailableError,
    TerminalUI,
    hangman_drawing,
    main,
    normalize_url,
)


class FixedWords:
    def __init__(self, word):
        self.word = word

    def random_word(self, difficulty):
        return self.word


class BrokenWords:
    def random_word(self, difficulty):
        raise RuntimeError("boom")


def free_port():
    """A port number nothing is listening on."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class LiveServerTestCase(unittest.TestCase):
    """Starts a real HTTP server in the background for each test."""

    WORD = "apple"

    def setUp(self):
        self.app = create_app(word_manager=FixedWords(self.WORD))
        self.app.logger.disabled = True
        self.server = make_server("127.0.0.1", 0, self.app, threaded=True)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.port}"
        self.client = CountingClient(self.url, timeout=5)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)

    def run_ui(self, inputs, client=None):
        """Run the terminal UI with typed inputs. Returns (exit code, printed text)."""
        answers = iter(inputs)

        def fake_input(prompt):
            output.write(prompt)
            try:
                answer = next(answers)
            except StopIteration:
                raise EOFError from None  # like pressing Ctrl+D
            output.write(answer + "\n")
            return answer

        output = io.StringIO()
        code = TerminalUI(client or self.client, input_fn=fake_input, out=output).run()
        return code, output.getvalue()


class CountingClient(HangmanClient):
    """A real client that also counts how many guesses it sent."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guesses_sent = []

    def guess(self, game_id, letter):
        self.guesses_sent.append(letter)
        return super().guess(game_id, letter)


# ---------------------------------------------------------------------------
# Layer 1: HTTP client against a real server
# ---------------------------------------------------------------------------

class HttpClientTests(LiveServerTestCase):
    def test_health(self):
        self.assertEqual(self.client.health(), {"status": "ok"})

    def test_create_guess_and_get(self):
        state = self.client.create_game("easy")
        self.assertEqual(state["pattern"], "_ _ _ _ _")
        self.assertEqual(state["status"], "playing")

        state = self.client.guess(state["game_id"], "p")
        self.assertTrue(state["correct"])
        self.assertEqual(state["pattern"], "_ p p _ _")

        again = self.client.get_game(state["game_id"])
        self.assertEqual(again["guessed_letters"], ["p"])

    def test_server_errors_become_api_errors(self):
        game_id = self.client.create_game("easy")["game_id"]
        self.client.guess(game_id, "z")

        cases = [
            (lambda: self.client.create_game("extreme"), 400, "Invalid difficulty"),
            (lambda: self.client.guess(game_id, "ab"), 400, "single letter"),
            (lambda: self.client.guess(game_id, "z"), 409, "already guessed"),
            (lambda: self.client.get_game("nope"), 404, "Game not found."),
        ]
        for call, status, text in cases:
            with self.subTest(status=status, text=text):
                with self.assertRaises(ApiError) as caught:
                    call()
                self.assertEqual(caught.exception.status, status)
                self.assertIn(text, caught.exception.message)

    def test_closed_port_raises_server_unavailable(self):
        client = HangmanClient(f"http://127.0.0.1:{free_port()}", timeout=2)
        with self.assertRaises(ServerUnavailableError) as caught:
            client.health()
        self.assertIn("Can't reach the server", str(caught.exception))

    def test_slow_server_times_out(self):
        # A socket that accepts connections but never answers.
        with socket.socket() as silent:
            silent.bind(("127.0.0.1", 0))
            silent.listen()
            client = HangmanClient(f"http://127.0.0.1:{silent.getsockname()[1]}", timeout=0.5)
            with self.assertRaises(ServerUnavailableError) as caught:
                client.health()
        self.assertIn("didn't respond in time", str(caught.exception))


class NormalizeUrlTests(unittest.TestCase):
    def test_adds_scheme_and_removes_trailing_slash(self):
        self.assertEqual(normalize_url("localhost:5000"), "http://localhost:5000")
        self.assertEqual(normalize_url("127.0.0.1:5000/"), "http://127.0.0.1:5000")
        self.assertEqual(normalize_url("cse4095-hangman.onrender.com/"),
                         "https://cse4095-hangman.onrender.com")
        self.assertEqual(normalize_url(" https://example.com/ "), "https://example.com")


# ---------------------------------------------------------------------------
# Layer 2: the terminal screen, with typed input
# ---------------------------------------------------------------------------

class PlayTests(LiveServerTestCase):
    def test_win(self):
        code, text = self.run_ui(["1", "a", "p", "l", "e", "n"])
        self.assertEqual(code, 0)
        self.assertIn("Yes! 'a' is in the word.", text)
        self.assertIn("Word:       a p p l e", text)
        self.assertIn('You won! The word was "apple".', text)
        self.assertIn("Thanks for playing!", text)

    def test_loss(self):
        code, text = self.run_ui(["hard", "b", "c", "d", "f", "g", "h", "no"])
        self.assertEqual(code, 0)
        self.assertIn("Nope, no 'b'.", text)
        self.assertIn("Lives left: 0", text)
        self.assertIn('You lost. The word was "apple".', text)

    def test_word_not_shown_before_game_ends(self):
        code, text = self.run_ui(["1", "a", "p", "quit"])
        self.assertNotIn("apple", text)

    def test_shows_guessed_and_wrong_letters(self):
        code, text = self.run_ui(["1", "z", "p", "quit"])
        self.assertIn("Guessed:    z, p", text)
        self.assertIn("Wrong:      z", text)
        self.assertIn("Lives left: 5", text)

    def test_invalid_input_is_caught_without_a_request(self):
        code, text = self.run_ui(["1", "", "ab", "1", "!", "quit"])
        self.assertEqual(text.count("Please type a single letter a-z."), 4)
        self.assertEqual(self.client.guesses_sent, [])

    def test_repeated_letter_is_caught_without_a_request(self):
        code, text = self.run_ui(["1", "z", "Z", "quit"])
        self.assertIn("You already guessed 'z'.", text)
        self.assertEqual(self.client.guesses_sent, ["z"])

    def test_uppercase_input_works(self):
        code, text = self.run_ui(["1", "A", "quit"])
        self.assertIn("Yes! 'a' is in the word.", text)

    def test_difficulty_choices(self):
        for choice in ["1", "2", "3", "e", "medium", "HARD"]:
            with self.subTest(choice=choice):
                code, text = self.run_ui([choice, "quit"])
                self.assertIn("Word:       _ _ _ _ _", text)

    def test_invalid_difficulty_asks_again(self):
        code, text = self.run_ui(["4", "extreme", "", "2", "quit"])
        self.assertEqual(text.count("Please type 1, 2, or 3"), 3)
        self.assertIn("Word:       _ _ _ _ _", text)

    def test_play_again(self):
        code, text = self.run_ui(["1", "a", "p", "l", "e", "y", "2", "a", "p", "l", "e", "n"])
        self.assertEqual(text.count("You won!"), 2)

    def test_play_again_asks_until_y_or_n(self):
        code, text = self.run_ui(["1", "a", "p", "l", "e", "maybe", "n"])
        self.assertIn("Please type y or n.", text)
        self.assertIn("Thanks for playing!", text)

    def test_quit_mid_game(self):
        code, text = self.run_ui(["1", "a", "quit"])
        self.assertEqual(code, 0)
        self.assertIn("Goodbye!", text)

    def test_ctrl_d_exits_cleanly(self):
        code, text = self.run_ui(["1", "a"])  # input runs out -> EOFError
        self.assertEqual(code, 0)
        self.assertIn("Goodbye!", text)
        self.assertNotIn("Traceback", text)

    def test_drawing_changes_with_wrong_guesses(self):
        code, text = self.run_ui(["1", "b", "c", "quit"])
        for stage in HANGMAN_STAGES[:3]:
            self.assertIn(stage, text)
        self.assertNotIn(HANGMAN_STAGES[3], text)


class ServerProblemTests(LiveServerTestCase):
    def test_server_down_gives_clean_message(self):
        client = HangmanClient(f"http://127.0.0.1:{free_port()}", timeout=2)
        code, text = self.run_ui(["1"], client=client)
        self.assertEqual(code, 1)
        self.assertIn("Can't reach the server", text)
        self.assertNotIn("Traceback", text)

    def test_not_a_hangman_server(self):
        # Point the client at a URL that answers 404 for /api/health.
        client = HangmanClient(self.url + "/nothing", timeout=5)
        code, text = self.run_ui(["1"], client=client)
        self.assertEqual(code, 1)
        self.assertIn("not like a Hangman server", text)

    def test_game_removed_from_server(self):
        store = self.app.config["GAME_STORE"]

        def clear_then_guess(game_id, letter):
            store._games.clear()  # as if the server restarted
            return HangmanClient.guess(self.client, game_id, letter)

        self.client.guess = clear_then_guess
        code, text = self.run_ui(["1", "a", "n"])
        self.assertIn("This game no longer exists on the server", text)

    def test_server_error_on_create(self):
        app = create_app(word_manager=BrokenWords())
        app.logger.disabled = True
        server = make_server("127.0.0.1", 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        try:
            client = HangmanClient(f"http://127.0.0.1:{server.port}", timeout=5)
            code, text = self.run_ui(["1", "n"], client=client)
            self.assertIn("Couldn't start a game: Internal server error.", text)
            self.assertNotIn("boom", text)
        finally:
            server.shutdown()
            thread.join(timeout=5)


class DrawingTests(unittest.TestCase):
    def test_stages(self):
        self.assertEqual(len(HANGMAN_STAGES), 7)
        self.assertEqual(hangman_drawing(0), HANGMAN_STAGES[0])
        self.assertEqual(hangman_drawing(6), HANGMAN_STAGES[6])
        self.assertEqual(hangman_drawing(99), HANGMAN_STAGES[6])
        self.assertEqual(hangman_drawing(-1), HANGMAN_STAGES[0])
        self.assertEqual(len(set(HANGMAN_STAGES)), 7)


class MainTests(unittest.TestCase):
    def test_main_reports_unreachable_server(self):
        import contextlib

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--url", f"http://127.0.0.1:{free_port()}", "--timeout", "2"])
        self.assertEqual(code, 1)
        self.assertIn("Can't reach the server", output.getvalue())


if __name__ == "__main__":
    unittest.main()
