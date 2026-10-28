"""Play Hangman in the terminal against a Hangman server.

This client has no game logic. It sends letters to the server and shows
what the server answers. The server decides whether a guess is correct
and whether the game is won or lost.

Run:
    python terminal_client.py                       # local server (http://localhost:5000)
    python terminal_client.py --url https://cse4095-hangman.onrender.com
"""

import argparse
import json
import os
import string
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:5000"
# Render's free plan can take about a minute to wake up, so wait a while.
DEFAULT_TIMEOUT = 90

DIFFICULTY_CHOICES = {
    "1": "easy", "e": "easy", "easy": "easy",
    "2": "medium", "m": "medium", "medium": "medium",
    "3": "hard", "h": "hard", "hard": "hard",
}
QUIT_WORDS = {"quit", "exit", "q"}

# Drawing stages, indexed by the number of wrong guesses (0 to 6).
HANGMAN_STAGES = [
    """
  +---+
  |   |
      |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
      |
      |
=========""",
    """
  +---+
  |   |
  O   |
  |   |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|   |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
      |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
 /    |
=========""",
    """
  +---+
  |   |
  O   |
 /|\\  |
 / \\  |
=========""",
]


# ---------------------------------------------------------------------------
# Layer 1: talking to the server over HTTP
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """The server answered with an error status (400, 404, 409, 500, ...)."""

    def __init__(self, status, message):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


class ServerUnavailableError(Exception):
    """The server could not be reached, or did not answer like a Hangman server."""


def normalize_url(url):
    """Add a scheme if missing and remove a trailing slash.

    'localhost:5000' -> 'http://localhost:5000'
    'cse4095-hangman.onrender.com/' -> 'https://cse4095-hangman.onrender.com'
    """
    url = url.strip().rstrip("/")
    if "://" not in url:
        is_local = url.startswith(("localhost", "127.0.0.1"))
        url = ("http://" if is_local else "https://") + url
    return url


class HangmanClient:
    """Sends requests to the Hangman REST API and returns the JSON answers."""

    def __init__(self, base_url=DEFAULT_URL, timeout=DEFAULT_TIMEOUT):
        self.base_url = normalize_url(base_url)
        self.timeout = timeout

    def health(self):
        return self._request("GET", "/api/health")

    def create_game(self, difficulty):
        return self._request("POST", "/api/games", {"difficulty": difficulty})

    def get_game(self, game_id):
        return self._request("GET", f"/api/games/{game_id}")

    def guess(self, game_id, letter):
        return self._request("POST", f"/api/games/{game_id}/guess", {"letter": letter})

    def _request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            # The server answered, but with an error status. Use its message.
            with error:
                raise ApiError(error.code, _error_message(error)) from None
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            if isinstance(error, TimeoutError) or isinstance(reason, TimeoutError):
                raise ServerUnavailableError(
                    f"The server at {self.base_url} didn't respond in time."
                ) from None
            raise ServerUnavailableError(
                f"Can't reach the server at {self.base_url}. Is it running?"
            ) from None

        try:
            return json.loads(text)
        except ValueError:
            raise ServerUnavailableError(
                f"{self.base_url} answered, but not like a Hangman server."
            ) from None


def _error_message(http_error):
    """Get the server's {"error": ...} message, or a fallback."""
    try:
        body = json.loads(http_error.read().decode("utf-8"))
        if isinstance(body, dict) and body.get("error"):
            return body["error"]
    except (ValueError, OSError):
        pass
    return str(http_error.reason)


# ---------------------------------------------------------------------------
# Layer 2: the terminal screen
# ---------------------------------------------------------------------------

class QuitGame(Exception):
    """The player typed 'quit'."""


def hangman_drawing(incorrect_count):
    """Pick the drawing for this many wrong guesses (display only)."""
    stage = max(0, min(incorrect_count, len(HANGMAN_STAGES) - 1))
    return HANGMAN_STAGES[stage]


class TerminalUI:
    """Reads the keyboard and prints the game. All game decisions come from the server."""

    def __init__(self, client, input_fn=input, out=None):
        self.client = client
        self.input_fn = input_fn
        self.out = out if out is not None else sys.stdout

    # ----- small helpers -----

    def say(self, text=""):
        print(text, file=self.out)

    def ask(self, prompt):
        answer = self.input_fn(prompt).strip().lower()
        if answer in QUIT_WORDS:
            raise QuitGame
        return answer

    # ----- main loop -----

    def run(self):
        """Run the client. Returns 0 on a normal exit, 1 if the server can't be used."""
        try:
            self.say(f"Connecting to {self.client.base_url} ...")
            self.say("(The free server may take up to a minute to wake up.)")
            try:
                self.client.health()
            except ApiError:
                raise ServerUnavailableError(
                    f"{self.client.base_url} answered, but not like a Hangman server."
                ) from None
            self.say("Connected. Type 'quit' at any time to leave.")

            while True:
                self.play_game(self.choose_difficulty())
                if not self.ask_yes_no("Play again? (y/n) "):
                    break
            self.say("Thanks for playing!")
            return 0
        except (QuitGame, EOFError, KeyboardInterrupt):
            self.say("\nGoodbye!")
            return 0
        except ServerUnavailableError as error:
            self.say(f"\nError: {error}")
            return 1

    def choose_difficulty(self):
        while True:
            self.say()
            self.say("Choose a difficulty: [1] easy  [2] medium  [3] hard")
            choice = DIFFICULTY_CHOICES.get(self.ask("> "))
            if choice:
                return choice
            self.say("Please type 1, 2, or 3 (or easy, medium, hard).")

    def ask_yes_no(self, prompt):
        while True:
            try:
                answer = self.ask(prompt)
            except QuitGame:
                return False
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            self.say("Please type y or n.")

    def ask_letter(self, state):
        """Ask until the player types a new single letter.

        These checks only catch obvious typing mistakes before sending.
        The server still validates every guess.
        """
        while True:
            letter = self.ask("Guess a letter (or 'quit'): ")
            if len(letter) != 1 or letter not in string.ascii_lowercase:
                self.say("Please type a single letter a-z.")
            elif letter in state.get("guessed_letters", []):
                self.say(f"You already guessed '{letter}'.")
            else:
                return letter

    # ----- one game -----

    def play_game(self, difficulty):
        try:
            state = self.client.create_game(difficulty)
        except ApiError as error:
            self.say(f"Couldn't start a game: {error.message}")
            return
        game_id = state["game_id"]

        while state["status"] == "playing":
            self.show(state)
            letter = self.ask_letter(state)
            try:
                state = self.client.guess(game_id, letter)
            except ApiError as error:
                if error.status == 404:
                    self.say("This game no longer exists on the server (it may have restarted).")
                    return
                if error.status >= 500:
                    self.say("Server error. Let's start a new game.")
                    return
                # 400 or 409: show the server's reason, then refresh the state.
                self.say(error.message)
                state = self.client.get_game(game_id)
                continue
            if state.get("correct"):
                self.say(f"Yes! '{letter}' is in the word.")
            else:
                self.say(f"Nope, no '{letter}'.")

        self.show(state)
        word = state.get("word", "?")
        if state["status"] == "won":
            self.say(f'You won! The word was "{word}".')
        else:
            self.say(f'You lost. The word was "{word}".')

    def show(self, state):
        guessed = state.get("guessed_letters", [])
        wrong = state.get("incorrect_letters", [])
        self.say(hangman_drawing(len(wrong)))
        self.say()
        self.say(f"Word:       {state['pattern']}")
        self.say(f"Guessed:    {', '.join(guessed) if guessed else '-'}")
        self.say(f"Wrong:      {', '.join(wrong) if wrong else '-'}")
        self.say(f"Lives left: {state['remaining_guesses']}")
        self.say()


# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Play Hangman in the terminal.")
    parser.add_argument(
        "--url",
        default=os.environ.get("HANGMAN_URL", DEFAULT_URL),
        help=f"Hangman server address (default: $HANGMAN_URL or {DEFAULT_URL})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"seconds to wait for the server (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args(argv)
    return TerminalUI(HangmanClient(args.url, timeout=args.timeout)).run()


if __name__ == "__main__":
    sys.exit(main())
