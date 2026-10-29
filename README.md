# CSE 4095 Hangman App

A Hangman game with a Flask REST server and a browser client.

> This README is a placeholder. Full documentation comes in Phase 14 (see `TODO.md`).

**Live app:** https://cse4095-hangman.onrender.com

The free Render plan sleeps when idle, so the first request can take 30–60 seconds. Check it's awake with `curl -s https://cse4095-hangman.onrender.com/api/health`.

## Run locally

Requires Python 3.14 (see `.python-version`).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open **http://localhost:5000** in your browser to play. Click letters or type them on your keyboard; press Enter for a new game when one ends.

You can also use the API directly:

```bash
curl -s -X POST localhost:5000/api/games -H "Content-Type: application/json" -d '{"difficulty":"easy"}'
curl -s -X POST localhost:5000/api/games/GAME_ID/guess -H "Content-Type: application/json" -d '{"letter":"e"}'
curl -s localhost:5000/api/games/GAME_ID
```

## Terminal client

Play Hangman in the terminal. It talks to the server over HTTP, like `curl`.

```bash
# Against a local server (start `python server.py` in another terminal first)
python terminal_client.py

# Against the live site (no local server needed)
python terminal_client.py --url https://cse4095-hangman.onrender.com
```

Type `quit` (or press Ctrl+C) to leave.

## Run the tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```

This runs everything (about 12 seconds):

| File | What it tests |
|---|---|
| `tests/test_words.py` | Loading and checking the word lists |
| `tests/test_game.py` | The game rules (`HangmanGame`) |
| `tests/test_server.py` | The REST API, the web page, security headers, many requests at once |
| `tests/test_terminal_client.py` | The terminal client against a real HTTP server |
| `tests/test_browser_client.py` | The browser code (`static/app.js`), run in Node with a small fake page against a real server. Skipped if Node.js isn't installed. |
| `tests/test_end_to_end.py` | Starts the app with gunicorn exactly like Render (and with `python server.py`), then plays through the API, the terminal client, and the browser code |

**Test the deployed site** (skipped unless you set the URL):

```bash
HANGMAN_LIVE_URL=https://cse4095-hangman.onrender.com python -m unittest tests.test_end_to_end
```

**Coverage report** (optional; `coverage` is a test-only tool, not in `requirements.txt`):

```bash
pip install coverage
python -m coverage run --branch --source=. --omit="tests/*,.venv/*" -m unittest discover -s tests
python -m coverage report -m
```

## Deployment

Deployed on Render using `render.yaml` (build and start commands) and `.python-version`.
