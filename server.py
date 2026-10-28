"""Flask REST server for Hangman.

The server owns every game. Clients only send difficulty choices and
letter guesses, and get back the client-safe game state as JSON.

Run locally:   python server.py          (http://localhost:5000)
On Render:     gunicorn server:app
"""

import os
import secrets
import threading
from collections import OrderedDict

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException, MethodNotAllowed

from game import DuplicateGuessError, GameOverError, HangmanGame, InvalidGuessError
from words import InvalidDifficultyError, WordManager

# The server is public, so cap how many games are kept in memory.
# When the cap is reached, the oldest game is removed.
MAX_GAMES = 10_000


class GameStore:
    """In-memory storage for games, keyed by a random game ID."""

    def __init__(self, max_games=MAX_GAMES):
        self.max_games = max_games
        self._games = OrderedDict()  # keeps creation order, oldest first
        # One lock for the whole store, so two requests at the same time
        # can't change the same game (or the store) at once.
        self.lock = threading.RLock()

    def add(self, game):
        """Store a game and return its new, unique ID."""
        with self.lock:
            game_id = secrets.token_hex(8)  # 16 hex characters, hard to guess
            while game_id in self._games:
                game_id = secrets.token_hex(8)
            self._games[game_id] = game
            while len(self._games) > self.max_games:
                self._games.popitem(last=False)  # remove the oldest game
            return game_id

    def get(self, game_id):
        """Return the game with this ID, or None."""
        with self.lock:
            return self._games.get(game_id)

    def __len__(self):
        with self.lock:
            return len(self._games)


class ApiError(Exception):
    """An error to send to the client as {"error": message} with a status code."""

    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def game_state(game_id, game):
    """The JSON body for a game: its ID, its difficulty, and the client-safe state."""
    return {"game_id": game_id, "difficulty": game.difficulty, **game.to_dict()}


def read_json_object():
    """Return the request body as a dict, or raise ApiError(400)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(
            "Request body must be a JSON object, sent with Content-Type: application/json.",
            400,
        )
    return data


def create_app(word_manager=None, max_games=MAX_GAMES):
    """Build the Flask app with its own empty game store.

    Tests call this to get a fresh server each time. Passing a word_manager
    lets tests choose the words.
    """
    app = Flask(__name__)
    app.json.sort_keys = False  # keep JSON fields in the order we write them

    # Load word lists now, so a bad list stops the server at startup
    # instead of failing on the first new game.
    words = word_manager if word_manager is not None else WordManager()
    store = GameStore(max_games)
    app.config["GAME_STORE"] = store

    def find_game(game_id):
        game = store.get(game_id)
        if game is None:
            raise ApiError("Game not found.", 404)
        return game

    # ----- Endpoints -----

    @app.get("/api/health")
    def health():
        """Lets Render (and you) check that the server is running."""
        return jsonify(status="ok")

    @app.post("/api/games")
    def create_game():
        data = read_json_object()
        if "difficulty" not in data:
            raise ApiError("Missing 'difficulty'. Use 'easy', 'medium', or 'hard'.", 400)
        try:
            game = HangmanGame.from_difficulty(data["difficulty"], word_manager=words)
        except InvalidDifficultyError as error:
            raise ApiError(str(error), 400) from None
        game_id = store.add(game)
        return jsonify(game_state(game_id, game)), 201

    @app.get("/api/games/<game_id>")
    def get_game(game_id):
        with store.lock:
            game = find_game(game_id)
            return jsonify(game_state(game_id, game))

    @app.post("/api/games/<game_id>/guess")
    def guess_letter(game_id):
        with store.lock:
            game = find_game(game_id)
            data = read_json_object()
            if "letter" not in data:
                raise ApiError("Missing 'letter'.", 400)
            try:
                correct = game.guess(data["letter"])
            except InvalidGuessError as error:
                raise ApiError(str(error), 400) from None
            except (DuplicateGuessError, GameOverError) as error:
                raise ApiError(str(error), 409) from None
            return jsonify({**game_state(game_id, game), "correct": correct})

    # ----- Errors: always JSON, never HTML pages or stack traces -----

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(error=error.message), error.status

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        messages = {404: "Not found.", 405: "Method not allowed."}
        response = jsonify(error=messages.get(error.code, error.name))
        response.status_code = error.code
        if isinstance(error, MethodNotAllowed) and error.valid_methods:
            response.headers["Allow"] = ", ".join(error.valid_methods)
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unexpected error")
        return jsonify(error="Internal server error."), 500

    return app


# Render (gunicorn server:app) and `python server.py` both use this app.
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=False)
