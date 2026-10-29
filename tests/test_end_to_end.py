"""End-to-end tests: run the app the way Render does and use it like a player.

These start the real server as a separate program (gunicorn with the start
command from render.yaml, and `python server.py`), from a different folder,
with the real word lists, and talk to it over real HTTP.

Optional live test against the deployed site (skipped unless set):
    HANGMAN_LIVE_URL=https://cse4095-hangman.onrender.com python -m unittest tests.test_end_to_end
"""

import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import SECURITY_HEADERS  # noqa: E402
from words import WordManager  # noqa: E402

LIVE_URL = os.environ.get("HANGMAN_LIVE_URL", "").rstrip("/")
RARE_FIRST = "qzxjkvwyfbgpmhdculotisnrae"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def http(method, url, body=None, timeout=30):
    """Send a request. Returns (status, headers, parsed JSON or text)."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status, headers, raw = response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        with error:
            status, headers, raw = error.code, error.headers, error.read()
    text = raw.decode("utf-8")
    try:
        return status, headers, json.loads(text)
    except ValueError:
        return status, headers, text


def render_start_command(port):
    """The startCommand from render.yaml, with $PORT filled in and bound to localhost."""
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    command = re.search(r"^\s*startCommand:\s*(.+)$", text, re.MULTILINE).group(1).strip()
    command = command.replace("$PORT", str(port)).replace("0.0.0.0", "127.0.0.1")
    return shlex.split(command)


class RunningServer:
    """Start a server program, wait until /api/health answers, and stop it afterwards."""

    def __init__(self, command, env=None):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.folder = tempfile.TemporaryDirectory()  # run from somewhere other than the project
        full_env = {**os.environ, "PORT": str(self.port), **(env or {})}
        self.process = subprocess.Popen(
            command(self.port), cwd=self.folder.name, env=full_env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        self._wait_until_ready()

    def _wait_until_ready(self, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            if self.process.poll() is not None:
                raise RuntimeError(f"server exited early:\n{self.process.stdout.read()}")
            try:
                if http("GET", self.base + "/api/health", timeout=2)[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        self.stop()
        raise RuntimeError("server did not become ready")

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stdout.close()
        self.folder.cleanup()


def solver_guess(state, candidates):
    """A simple player for tests: guess the most common letter among the words that still fit."""
    pattern = state["pattern"].split(" ")
    wrong = set(state["incorrect_letters"])
    guessed = set(state["guessed_letters"])
    fits = [w for w in candidates
            if len(w) == len(pattern)
            and all(p == "_" and c not in guessed or p == c for p, c in zip(pattern, w))
            and not wrong & set(w)]
    counts = Counter(c for w in fits for c in set(w) if c not in guessed)
    if counts:
        return counts.most_common(1)[0][0]
    return next(c for c in "etaoinshrdlucmfwypvbgkjqxz" if c not in guessed)


class ApiPlayMixin:
    """Full games through the API with the real word lists. Needs self.base."""

    timeout = 30

    def play(self, difficulty, choose_letter):
        """Play one game. Checks the word stays hidden until the end. Returns the final state."""
        status, _, state = http("POST", self.base + "/api/games", {"difficulty": difficulty}, self.timeout)
        self.assertEqual(status, 201, state)
        game_id = state["game_id"]
        seen = [state]
        while state["status"] == "playing":
            letter = choose_letter(state)
            status, _, state = http("POST", f"{self.base}/api/games/{game_id}/guess", {"letter": letter}, self.timeout)
            self.assertEqual(status, 200, state)
            seen.append(state)

        word = state["word"]
        self.assertRegex(word, r"^[a-z]+$")
        for earlier in seen[:-1]:
            self.assertNotIn("word", earlier)
            # Look for the word only in values that could leak it. Field names
            # (like "guessed_letters" containing "letter"), "difficulty" (can be
            # "easy"), and the hex game_id (can spell "face") are skipped.
            could_leak = [v for k, v in earlier.items() if k not in ("difficulty", "game_id")]
            self.assertNotIn(word, json.dumps(could_leak).replace(" ", ""))
        self.assertEqual(http("GET", f"{self.base}/api/games/{game_id}", timeout=self.timeout)[2]["word"], word)
        status, _, body = http("POST", f"{self.base}/api/games/{game_id}/guess", {"letter": "a"}, self.timeout)
        self.assertEqual(status, 409, body)
        return state

    def assert_win_happens(self, difficulty="easy", tries=30):
        words = WordManager().words(difficulty)
        for _ in range(tries):
            state = self.play(difficulty, lambda s: solver_guess(s, words))
            if state["status"] == "won":
                self.assertEqual(state["pattern"].replace(" ", ""), state["word"])
                self.assertGreater(state["remaining_guesses"], 0)
                return
        self.fail(f"no win in {tries} {difficulty} games")

    def assert_loss_happens(self, difficulty="hard", tries=30):
        def rare(state):
            return next(c for c in RARE_FIRST if c not in state["guessed_letters"])

        for _ in range(tries):
            state = self.play(difficulty, rare)
            if state["status"] == "lost":
                self.assertEqual(state["remaining_guesses"], 0)
                self.assertEqual(len(state["incorrect_letters"]), 6)
                return
        self.fail(f"no loss in {tries} {difficulty} games")

    def run_terminal_client(self, timeout=60):
        # Leave out "y" and "n": letters left over after the game reach the
        # "Play again? (y/n)" prompt. 24 letters always give 6 wrong guesses,
        # so the game is sure to end.
        letters = "\n".join("etaoishrdlucmfwpvbgkjqxz")
        result = subprocess.run(
            [sys.executable, str(ROOT / "terminal_client.py"), "--url", self.base],
            input=f"1\n{letters}\nn\n", capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir(),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Connected.", result.stdout)
        self.assertRegex(result.stdout, r'You (won!|lost\.) The word was "[a-z]+"\.')
        self.assertIn("Thanks for playing!", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Local end-to-end: gunicorn, exactly like Render
# ---------------------------------------------------------------------------

@unittest.skipUnless(shutil.which("gunicorn") or (Path(sys.executable).parent / "gunicorn").exists(),
                     "gunicorn not installed")
class GunicornEndToEndTests(ApiPlayMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def command(port):
            args = render_start_command(port)
            assert args[0] == "gunicorn", args
            # Run gunicorn from this Python, with the project folder as its working folder.
            return [sys.executable, "-m", "gunicorn", *args[1:], "--chdir", str(ROOT)]

        cls.server = RunningServer(command)
        cls.base = cls.server.base

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_render_start_command_is_safe_for_in_memory_games(self):
        args = render_start_command(8000)
        self.assertEqual(args[0], "gunicorn")
        self.assertIn("server:app", args)
        self.assertEqual(args[args.index("--workers") + 1], "1")  # games live in one process

    def test_page_static_files_and_headers(self):
        for path, kind in [("/", "text/html"), ("/static/app.js", "text/javascript"),
                           ("/static/style.css", "text/css"), ("/api/health", "application/json")]:
            with self.subTest(path=path):
                status, headers, _ = http("GET", self.base + path)
                self.assertEqual(status, 200)
                self.assertTrue(headers["Content-Type"].startswith(kind), headers["Content-Type"])
                for name, value in SECURITY_HEADERS.items():
                    self.assertEqual(headers[name], value)

    def test_errors_are_json(self):
        cases = [("GET", "/api/games/nope", None, 404), ("POST", "/api/games", {"difficulty": "x"}, 400),
                 ("GET", "/no-such-page", None, 404), ("DELETE", "/api/games", None, 405)]
        for method, path, body, expected in cases:
            with self.subTest(method=method, path=path):
                status, headers, data = http(method, self.base + path, body)
                self.assertEqual(status, expected)
                self.assertIn("error", data)

    def test_win_path_with_real_words(self):
        self.assert_win_happens("easy")

    def test_loss_path_with_real_words(self):
        self.assert_loss_happens("hard")

    def test_every_difficulty_uses_its_own_list(self):
        for level in ("easy", "medium", "hard"):
            with self.subTest(level=level):
                state = self.play(level, lambda s: next(c for c in RARE_FIRST if c not in s["guessed_letters"]))
                self.assertIn(state["word"], WordManager().words(level))

    def test_terminal_client_program(self):
        self.run_terminal_client()

    @unittest.skipUnless(shutil.which("node"), "Node.js not installed")
    def test_browser_client_script(self):
        from tests.test_browser_client import run_browser_script

        code, checks, stderr = run_browser_script(self.base)  # real, unknown words
        self.assertGreaterEqual(len(checks), 40, stderr)
        for item in checks:
            with self.subTest(check=item["name"]):
                self.assertTrue(item["ok"], item["detail"])
        self.assertEqual(code, 0, stderr)


# ---------------------------------------------------------------------------
# Local end-to-end: `python server.py`, as the README says
# ---------------------------------------------------------------------------

class PythonServerEndToEndTests(ApiPlayMixin, unittest.TestCase):
    def test_python_server_py_starts_and_plays(self):
        server = RunningServer(lambda port: [sys.executable, str(ROOT / "server.py")])
        try:
            self.base = server.base
            status, headers, _ = http("GET", self.base + "/")
            self.assertEqual(status, 200)
            self.assertTrue(headers["Content-Type"].startswith("text/html"))
            self.play("medium", lambda s: next(c for c in RARE_FIRST if c not in s["guessed_letters"]))
        finally:
            server.stop()


# ---------------------------------------------------------------------------
# Optional: the deployed site
# ---------------------------------------------------------------------------

@unittest.skipUnless(LIVE_URL, "set HANGMAN_LIVE_URL to test the deployed site")
class LiveSiteTests(ApiPlayMixin, unittest.TestCase):
    base = LIVE_URL
    timeout = 90  # the free plan may need to wake up

    @classmethod
    def setUpClass(cls):
        # Wake the server up first.
        http("GET", LIVE_URL + "/api/health", timeout=120)

    def test_health(self):
        self.assertEqual(http("GET", self.base + "/api/health", timeout=self.timeout)[:3:2], (200, {"status": "ok"}))

    def test_page_and_security_headers(self):
        status, headers, body = http("GET", self.base + "/", timeout=self.timeout)
        self.assertEqual(status, 200)
        self.assertIn('id="keyboard"', body)
        for name, value in SECURITY_HEADERS.items():
            self.assertEqual(headers[name], value)

    def test_full_game(self):
        self.play("easy", lambda s: next(c for c in RARE_FIRST if c not in s["guessed_letters"]))

    def test_terminal_client_program(self):
        self.run_terminal_client(timeout=180)


if __name__ == "__main__":
    unittest.main()
