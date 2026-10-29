# CSE 4095 Hangman App

A Hangman game with a **Flask REST server** and a **browser client**, plus a terminal client.
The server holds every game and decides every result; clients only send guesses and show the answers.

**Play it live:** https://cse4095-hangman.onrender.com

> The live site runs on Render's free plan, which sleeps after about 15 minutes without visitors.
> The first visit after that can take 30–60 seconds while it wakes up.

## Contents

- [Features](#features)
- [Quick start (run locally)](#quick-start-run-locally)
- [Playing in the browser](#playing-in-the-browser)
- [Terminal client](#terminal-client)
- [REST API](#rest-api)
- [Game rules](#game-rules)
- [Project structure](#project-structure)
- [Running the tests](#running-the-tests)
- [Deployment](#deployment)
- [Security](#security)
- [Differences from the specification](#differences-from-the-specification)

## Features

- Play in the **browser** (click letters or type them) or in the **terminal**.
- **Easy, Medium, and Hard** word lists.
- A Hangman drawing that grows with each wrong guess.
- New games without reloading the page.
- The **server is the referee**: the hidden word never reaches a client until the game ends.
- Deployed on Render from this repository.

## Quick start (run locally)

**You need:** [Python 3.14](https://www.python.org/downloads/) (see `.python-version`) and [Git](https://git-scm.com/).

**1. Get the code**

```bash
git clone https://github.com/zhaoh-li/CSE-4095-Hangman-App.git
cd CSE-4095-Hangman-App
```

**2. Create a virtual environment and install the dependencies**

A virtual environment is a private folder of Python packages for this project only.

Linux, macOS, or WSL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Your prompt now starts with `(.venv)`. Activate it again in every new terminal before running the commands below.

**3. Start the server**

```bash
python server.py
```

Leave it running. It's ready when it prints `Running on http://127.0.0.1:5000`.

**4. Play**

Open **http://localhost:5000** in your browser.

Press **Ctrl+C** in the server's terminal to stop it.

## Playing in the browser

| Action | How |
|---|---|
| Pick a difficulty | **Easy / Medium / Hard** at the top. Before your first guess, switching starts a new game right away; mid-game, it applies when you press New Game. |
| Start a new game | **New Game** button, or **Enter** after a game ends |
| Guess a letter | Click a letter button, or type the letter on your keyboard |

- **Green** letters are in the word; **red** letters are not. Used letters can't be guessed again.
- Each wrong guess adds a body part. Six wrong guesses lose the game.
- When the game ends, the word is shown. On a loss, the letters you missed are marked in red.
- If the server can't be reached, the page says so. Press New Game to try again.

## Terminal client

Play in the terminal. It talks to the server over HTTP, just like the browser does.

```bash
# Against your local server (start `python server.py` in another terminal first)
python terminal_client.py

# Against the live site (no local server needed)
python terminal_client.py --url https://cse4095-hangman.onrender.com
```

- Choose `1`, `2`, or `3` (or type `easy`, `medium`, `hard`), then type one letter at a time.
- Type `quit` or press **Ctrl+C** to leave. After each game it asks **Play again? (y/n)**.
- To avoid typing the URL each time: `export HANGMAN_URL=https://cse4095-hangman.onrender.com`
- `--timeout SECONDS` sets how long to wait for the server (default 90, for Render's wake-up).

## REST API

All requests and responses use JSON. Send request bodies with the header `Content-Type: application/json`.

| Method | Endpoint | Purpose | Success |
|---|---|---|---|
| `POST` | `/api/games` | Create a new game | `201` |
| `GET` | `/api/games/{game_id}` | Get a game's current state | `200` |
| `POST` | `/api/games/{game_id}/guess` | Guess one letter | `200` |
| `GET` | `/api/health` | Check the server is running: `{"status": "ok"}` | `200` |
| `GET` | `/` | The browser client (HTML page) | `200` |

The examples below use `localhost:5000`; replace it with `https://cse4095-hangman.onrender.com` to use the live site.

### Create a game

```bash
curl -s -X POST localhost:5000/api/games \
  -H "Content-Type: application/json" \
  -d '{"difficulty": "medium"}'
```

`difficulty` must be `"easy"`, `"medium"`, or `"hard"` (case doesn't matter). Response, `201 Created`:

```json
{
  "game_id": "3f9a1c2b7e4d8a06",
  "difficulty": "medium",
  "pattern": "_ _ _ _ _",
  "guessed_letters": [],
  "incorrect_letters": [],
  "remaining_guesses": 6,
  "status": "playing"
}
```

### Guess a letter

```bash
curl -s -X POST localhost:5000/api/games/3f9a1c2b7e4d8a06/guess \
  -H "Content-Type: application/json" \
  -d '{"letter": "p"}'
```

Response, `200 OK`:

```json
{
  "game_id": "3f9a1c2b7e4d8a06",
  "difficulty": "medium",
  "pattern": "_ p p _ _",
  "guessed_letters": ["p"],
  "incorrect_letters": [],
  "remaining_guesses": 6,
  "status": "playing",
  "correct": true
}
```

A wrong guess looks the same with `"correct": false`, the letter added to `incorrect_letters`, and one fewer `remaining_guesses`.

### Get the current state

```bash
curl -s localhost:5000/api/games/3f9a1c2b7e4d8a06
```

Returns the same fields as a guess, without `correct`.

### When the game ends

The answer appears as `word`, only once `status` is `won` or `lost`:

```json
{
  "game_id": "3f9a1c2b7e4d8a06",
  "difficulty": "medium",
  "pattern": "a p p l e",
  "guessed_letters": ["p", "z", "a", "l", "e"],
  "incorrect_letters": ["z"],
  "remaining_guesses": 5,
  "status": "won",
  "word": "apple",
  "correct": true
}
```

### Game state fields

| Field | Meaning |
|---|---|
| `game_id` | 16 random hex characters. Use it in the game's URLs. |
| `difficulty` | `easy`, `medium`, or `hard` |
| `pattern` | The word with unguessed letters as `_`, separated by spaces |
| `guessed_letters` | Every accepted guess, in the order made |
| `incorrect_letters` | Guesses that are not in the word |
| `remaining_guesses` | Wrong guesses left (starts at 6) |
| `status` | `playing`, `won`, or `lost` |
| `word` | The answer. **Only present after the game ends.** |
| `correct` | Guess responses only: whether that letter is in the word |

### Errors

Every error is JSON with a single `error` message, for example:

```json
{ "error": "The letter 'e' was already guessed." }
```

| Status | When | Example message |
|---|---|---|
| `400` | Body isn't a JSON object, or is missing the `Content-Type` header | `Request body must be a JSON object, sent with Content-Type: application/json.` |
| `400` | Missing or invalid difficulty | `Invalid difficulty 'extreme'. Choose one of: easy, medium, hard.` |
| `400` | Missing letter, or not a single letter a–z | `A guess must be a single letter a-z.` |
| `404` | Unknown game ID or URL | `Game not found.` |
| `405` | Wrong method for the URL (e.g. `GET` on `/guess`) | `Method not allowed.` |
| `409` | Letter already guessed (case-insensitive) | `The letter 'e' was already guessed.` |
| `409` | Guess after the game ended | `The game is already won.` |
| `500` | Unexpected server problem (no details are shown) | `Internal server error.` |

Rejected requests never change the game and never cost a guess.

## Game rules

- The server picks a random word from the chosen difficulty's list.
- Guess one letter (a–z) at a time. Uppercase counts as lowercase.
- You can make **6 wrong guesses**. The sixth wrong guess loses the game.
- Guess every letter in the word to win.
- Repeating a letter is rejected and does not cost a guess.
- No guesses are accepted after the game ends.
- The word is revealed only when the game ends.
- Games are kept in the server's memory. A server restart (or the free Render plan going to sleep) clears them.

## Project structure

```
├── game.py                  Game rules: the HangmanGame class (no web code)
├── words.py                 Loads, checks, and picks words (WordManager)
├── server.py                Flask app: REST API, web page, error handling, security headers
├── terminal_client.py       Terminal client (HTTP only, no game rules)
├── words/                   easy.txt, medium.txt, hard.txt
├── static/
│   ├── index.html           Browser page layout
│   ├── style.css            Look and layout (desktop and phone)
│   └── app.js               Browser behavior: fetch() calls and redrawing (no game rules)
├── tests/                   Automated tests (see below)
├── requirements.txt         Python dependencies (Flask, gunicorn)
├── render.yaml              Render deployment settings
├── .python-version          Python version for local use and Render
├── Specification.md         Original project specification (unchanged)
└── TODO.md                  Implementation roadmap with progress checkmarks
```

The layers only talk downward: `server.py` uses `game.py`, which uses `words.py`. The clients (browser and terminal) use only the REST API.

## Running the tests

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

The app is deployed on [Render](https://render.com) as a Python web service, configured by files in this repository:

| File | Purpose |
|---|---|
| `render.yaml` | Build command `pip install -r requirements.txt`; start command `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 server:app`; free plan; health check at `/api/health`; auto-deploy on push to `main` |
| `.python-version` | Python 3.14 |
| `requirements.txt` | Flask and gunicorn |

- **Every push to `main` redeploys automatically.**
- **One worker only:** games live in memory, and a second worker process would have its own separate games. Four threads let that worker serve several requests at once; a lock keeps them from interfering.
- **To deploy your own copy:** on Render, choose **New → Blueprint**, pick your fork of this repo, and apply. Render reads `render.yaml`.
- **Run the production server locally** (same as Render):
  `gunicorn --bind 127.0.0.1:8000 --workers 1 --threads 4 server:app`

## Security

- **The hidden word stays on the server.** Responses include `word` only after the game ends. The browser has no word lists or game rules.
- **Input is validated** on the server. Bad requests get a `4xx` JSON error and change nothing.
- **Errors never show internal details** such as stack traces; Flask's debug mode is off.
- **Game IDs are random** (64 bits), so other players' games can't be guessed.
- **At most 10,000 games** are kept in memory (the oldest is removed first), so a public server can't be made to run out of memory.
- **Security headers** on every response: `Content-Security-Policy` (scripts, styles, and requests only from this site), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: same-origin`.

## Differences from the specification

`Specification.md` describes a larger system and is kept unchanged. This assignment requires only the server and browser client, deployed. Where this project differs from the specification:

| Difference | Reason |
|---|---|
| Added `words.py` | The spec's "Word Manager" component, in its own file |
| Added `tests/` | Tests are required by the TODO; the spec's layout has no folder for them |
| Added `.gitignore`, `render.yaml`, `.python-version` | Keeping local files out of Git; deployment configuration (required by the assignment) |
| No `bot_examples/` | Bots are not required by the assignment |
| Extra endpoints: `GET /` and `GET /api/health` | Serve the browser page; Render's health check |
| All three game endpoints return the full game state, with `difficulty` added, and guess responses add `correct` | A superset of the spec's fields, so clients always get the same shape |
| Duplicate guesses are rejected with `409` | The spec allows duplicates to be "ignored or rejected" |
| Flask only (no FastAPI) | Required by the assignment |
| 10,000-game limit, security headers, JSON-only errors | Protection for a public server |
| Terminal client included | Not required by the assignment; kept as an extra client |
| Not built: student bots, evaluation mode, scoring, leaderboard, logging and replay | Optional for this assignment (marked `[O]` in `TODO.md`) |
| In `TODO.md`, Phase 2 (Word Management) is merged into Phase 1, and Phase 15 (Deployment) was done right after Phase 3 | To match the assignment's phases, and to find deployment problems early |
