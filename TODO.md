# TODO — Hangman Client/Server Project

This file is the implementation roadmap for the Hangman project.

The authoritative system requirements are defined in `Specification.md`.

> **`Specification.md` is read-only. Never edit, rename, move, or delete it.**
> Where the assignment or this TODO differs from the spec, record the difference in this TODO and in the README, not in the spec.

> **Priority order:** assignment requirements > this TODO > `Specification.md`.
> When an assignment rule conflicts with this TODO, the assignment wins, and the TODO is updated to match (with an "Assignment note" in that phase).

## Implementation Rules

- Implement one phase at a time.
- Complete and test all items in the current phase before moving to the next phase.
- Do not change the architecture or REST API defined in `Specification.md` unless necessary.
- If a deviation is necessary, document it in the README (and in this TODO). Do not modify `Specification.md`.
- Terminology: use **pattern** for the masked word (e.g. `_ e _ _ e`), matching the REST API.
- The "game engine" is `game.py` + `words.py` together. They stay separate files: `words.py` loads and picks words, and `game.py` plays a game.
- Keep the game engine independent from Flask, the browser UI, and the terminal UI.
- The server must remain authoritative.
- Never expose the hidden word before a game ends.
- Add tests as each phase is implemented rather than postponing testing until the end.
- Checkbox key: `[ ]` = to do, `[x]` = done, `[O]` = optional (not required for this assignment).
- Check off TODO items as each one is finished. The final, updated TODO is part of the submission.

---

## Phase 1 — Project Skeleton, Core Game Engine, and Word Management

> **Assignment note:** The assignment's Phase 1 ("game engine") covers both the original Phase 1 and Phase 2. Phase 2's word-management tasks were moved here. The assignment also requires preventing guesses after a game ends, which the original TODO did not list.

### Tasks

**Project skeleton**

- [x] Create the project directory structure.
- [x] Add `words/easy.txt`.
- [x] Add `words/medium.txt`.
- [x] Add `words/hard.txt`.

**Word management (`words.py`), moved from Phase 2**

- [x] Create a word-loading module or helper functions.
- [x] Load Easy, Medium, and Hard word lists.
- [x] Validate that loaded words contain only alphabetic characters.
- [x] Remove accidental duplicates when loading.
- [x] Support random word selection by difficulty.
- [x] Return an error for an invalid difficulty.

**Game engine (`game.py`)**

- [x] Create `game.py`.
- [x] Implement a `HangmanGame` class.
- [x] Support starting a game from a difficulty level (random word chosen via `words.py`).
- [x] Store the hidden word internally.
- [x] Track guessed letters.
- [x] Track correct and incorrect letters.
- [x] Track the maximum number of incorrect guesses.
- [x] Track remaining incorrect guesses.
- [x] Implement single-letter guess validation.
- [x] Detect duplicate guesses.
- [x] Implement pattern generation (the masked word).
- [x] Implement win detection.
- [x] Implement loss detection.
- [x] Prevent further guesses after a game ends.
- [x] Implement game status values such as `playing`, `won`, and `lost`.
- [x] Implement a method that returns a client-safe game-state dictionary.
- [x] Reveal the answer only after the game ends.

**Tests**

- [x] Add unit tests for the game engine (`tests/test_game.py`).
- [x] Add tests for word loading and word selection (`tests/test_words.py`).

### Completion Criteria

The game engine can be tested entirely without running a web server.

All core rules are covered by unit tests.

The program can request a random word from each difficulty level reliably.

Invalid difficulty values are rejected cleanly.

---

## Phase 2 — Word Management

Merged into Phase 1 (see the assignment note there). Phase numbers after this are unchanged.

---

## Phase 3 — Basic REST Server

> **Assignment note:** The assignment requires **Flask** (FastAPI is not allowed). It also requires the server to *accept* JSON (not only return it) and to keep each game's state separate. These were added or reworded below. The three endpoints are the required minimum, so extra endpoints (such as serving the web page in Phase 5) are allowed.
>
> **Deployment note:** Render runs `gunicorn server:app`, so the file must be `server.py` and the Flask object must be named `app`.

### Tasks

- [x] Create `server.py`.
- [x] Configure Flask (required by the assignment). Name the Flask object `app`.
- [x] Add in-memory storage for active games.
- [x] Keep each game's state separate (a guess in one game never affects another).
- [x] Generate unique game IDs.
- [x] Implement `POST /api/games`.
- [x] Implement `GET /api/games/{game_id}`.
- [x] Implement `POST /api/games/{game_id}/guess`.
- [x] Validate difficulty input.
- [x] Validate guess input.
- [x] Accept JSON request bodies and return JSON responses consistently.
- [x] Return appropriate HTTP status codes.
- [x] Handle unknown game IDs.
- [x] Handle malformed requests.
- [x] Match the spec's request and response JSON fields exactly:
  - Create request: `{"difficulty": "easy" | "medium" | "hard"}` (lowercase).
  - Guess request: `{"letter": "e"}`.
  - Responses include `pattern` (spaced, e.g. `_ e _ _ e`), `guessed_letters`, `incorrect_letters`, `remaining_guesses`, and `status`; create also returns `game_id`.
  - All three endpoints return the full game state (a superset of the spec's fields). The answer appears as `word` only after the game ends.
- [x] `python server.py` starts the server locally (debug off by default).
- [x] Ensure the hidden word is never leaked during an active game.
- [x] Limit stored games to 10,000 (oldest removed first), so a public server can't run out of memory. *(Added; not in the spec or assignment.)*
- [x] Add API tests (`tests/test_server.py`), including a test that two games don't affect each other.
- [ ] **Early deployment (from Phase 15):** once the API tests pass, complete Phase 15 and deploy to Render. See the note in Phase 15.

### Completion Criteria

A complete Hangman game can be played using only `curl` or another HTTP client, both locally and at the live Render URL.

The browser and terminal clients are not required for this phase.

---

## Phase 4 — Human Terminal Client

### Tasks

- [ ] Create `terminal_client.py`.
- [ ] Connect to the Hangman server over HTTP.
- [ ] Let the user choose Easy, Medium, or Hard.
- [ ] Start a new game through the REST API.
- [ ] Display the pattern (masked word).
- [ ] Display guessed letters.
- [ ] Display incorrect letters.
- [ ] Display remaining incorrect guesses.
- [ ] Prompt for one letter at a time.
- [ ] Submit guesses through the REST API.
- [ ] Handle invalid input locally when appropriate.
- [ ] Handle server errors gracefully.
- [ ] Display win and loss messages.
- [ ] Allow the user to start another game.

### Completion Criteria

A human player can play a full game from a terminal without using the browser.

The terminal client contains no Hangman game logic beyond presentation and input handling.

---

## Phase 5 — Browser Client

> **Assignment note:** The assignment requires guessing by clicking buttons **or using the physical keyboard** (both are supported here), starting another game **without reloading the page**, and a browser with **no game engine of its own**: Flask decides every guess result and the win/loss outcome. The Hangman figure may be drawn with SVG or HTML elements.

### Tasks

- [ ] Create `static/index.html`.
- [ ] Create `static/style.css`.
- [ ] Create `static/app.js`.
- [ ] Serve `static/index.html` from Flask at `/`.
- [ ] Add a difficulty selector.
- [ ] Add a New Game button.
- [ ] Display the pattern (masked word).
- [ ] Display guessed letters.
- [ ] Display incorrect letters.
- [ ] Display remaining incorrect guesses.
- [ ] Add an on-screen alphabet keyboard.
- [ ] Accept guesses from the physical keyboard (letter keys only; ignore other keys, already-guessed letters, and all keys once the game is over).
- [ ] Disable already-guessed letters.
- [ ] Use `fetch()` to communicate with the REST API.
- [ ] The browser contains no game logic. It only sends guesses and displays the server's response. Flask decides whether a guess is correct and whether the game is won or lost.
- [ ] Draw the Hangman state visually (SVG or HTML elements).
- [ ] Update the drawing after incorrect guesses.
- [ ] Display win and loss messages.
- [ ] Show the word when the game ends.
- [ ] Show a clear message when the server can't be reached or returns an error.
- [ ] Start another game without reloading the page.
- [ ] Make the interface usable on common desktop and mobile browser sizes.

### Completion Criteria

A human player can play the same server-hosted game from a browser.

No hidden word is stored in browser-side JavaScript.

The browser contains no Hangman game engine.

---

## Phase 6 — Reference Automated Clients

### Tasks

- [O] Create `bot_examples/`.
- [O] Implement `random_bot.py`.
- [O] Implement `frequency_bot.py`.
- [O] Define a common bot interaction pattern.
- [O] Create a reusable HTTP client helper if useful.
- [O] Make each bot capable of playing a complete game automatically.
- [O] Print game results and summary statistics.
- [O] Ensure bots use only information exposed through the REST API.
- [O] Document how students can write their own bot.

### Completion Criteria

At least two automated clients can independently play games against the server.

One bot should clearly outperform random guessing over many games.

---

## Phase 7 — Dictionary-Based Bot Example

### Tasks

- [O] Implement `dictionary_bot.py`.
- [O] Load an allowed training dictionary.
- [O] Filter candidate words by current pattern.
- [O] Remove candidates containing known incorrect letters.
- [O] Respect known letter positions.
- [O] Track letters already guessed.
- [O] Compute candidate-letter frequencies.
- [O] Choose the next letter using the remaining candidates.
- [O] Fall back to global letter frequency if no candidates remain.
- [O] Compare its performance against the random and frequency bots.

### Completion Criteria

The dictionary bot completes games without server-side knowledge and demonstrates a measurable improvement over simpler reference bots.

---

## Phase 8 — Evaluation Mode

### Tasks

- [O] Separate normal game play from official evaluation mode.
- [O] Add an evaluation-session model.
- [O] Generate a unique evaluation ID.
- [O] Define the number of evaluation games.
- [O] Support evaluation across Easy, Medium, and Hard words.
- [O] Ensure the server controls all evaluation words.
- [O] Prevent skipping or restarting unfavorable evaluation games.
- [O] Require games to be played in the intended sequence.
- [O] Record wins and losses.
- [O] Record total guesses.
- [O] Record incorrect guesses.
- [O] Record remaining guesses after wins.
- [O] Record per-game results.
- [O] Add evaluation API endpoints.
- [O] Add tests for evaluation integrity.

### Completion Criteria

A bot can start an evaluation session, play every assigned game, and receive an official result summary.

A client cannot choose or inspect the hidden evaluation words.

---

## Phase 9 — Scoring System

### Tasks

- [O] Define the official scoring formula.
- [O] Make wins the primary performance signal.
- [O] Use guess efficiency as a secondary signal or tiebreaker.
- [O] Define how losses are scored.
- [O] Define how invalid guesses affect scoring.
- [O] Define how duplicate guesses affect scoring.
- [O] Define how abandoned games affect scoring.
- [O] Record total score for each evaluation.
- [O] Add tests for scoring calculations.
- [O] Document the scoring rules clearly for students.

### Completion Criteria

Given the same game history, the scoring system always produces the same result.

The scoring formula is simple enough to explain and verify independently.

---

## Phase 10 — Leaderboard

### Tasks

- [O] Define a leaderboard record format.
- [O] Store participant or bot name.
- [O] Store total games.
- [O] Store games won.
- [O] Store win rate.
- [O] Store average guesses.
- [O] Store average remaining guesses on wins.
- [O] Store total score.
- [O] Rank results consistently.
- [O] Add a leaderboard API endpoint.
- [O] Add a browser leaderboard view.
- [O] Display rankings in the terminal if useful.
- [O] Decide whether leaderboard data should persist across server restarts.

### Completion Criteria

Completed evaluation runs can be ranked automatically and displayed consistently.

---

## Phase 11 — Evaluation Integrity and Anti-Cheating Safeguards

### Tasks

- [O] Ensure game state responses never contain the answer while status is `playing`.
- [O] Ensure evaluation words are server-controlled.
- [O] Prevent clients from requesting arbitrary evaluation game IDs.
- [O] Reject malformed or unauthorized evaluation requests.
- [O] Add optional rate limiting if needed.
- [O] Add optional per-request timeout rules.
- [O] Log evaluation actions.
- [O] Detect repeated invalid guesses.
- [O] Define behavior for disconnected clients.
- [O] Define behavior for incomplete evaluations.
- [O] Keep training word lists separate from hidden evaluation lists if desired.

### Completion Criteria

A student can solve the assignment using the documented API, but cannot gain the hidden word through normal API responses.

---

## Phase 12 — Logging and Replay

> **Assignment note:** Logging and replay come from the spec only and are not required by the assignment.

### Tasks

- [O] Define a game-log format.
- [O] Record game ID.
- [O] Record difficulty.
- [O] Record each guess in order.
- [O] Record whether each guess was correct.
- [O] Record pattern after each guess.
- [O] Record remaining guesses after each move.
- [O] Record final outcome.
- [O] Add optional timestamps.
- [O] Add a replay utility or endpoint.
- [O] Ensure logs do not expose hidden evaluation words before evaluation completion.

### Completion Criteria

An instructor can inspect or replay a completed game step by step for debugging or grading.

---

## Phase 13 — Testing

### Tasks

- [ ] Complete unit tests for `HangmanGame`.
- [ ] Complete tests for word loading.
- [ ] Complete REST API tests.
- [ ] Test duplicate guesses.
- [ ] Test invalid letters.
- [ ] Test invalid difficulty.
- [ ] Test missing game IDs.
- [ ] Test win paths.
- [ ] Test loss paths.
- [ ] Test answer disclosure rules.
- [ ] Test terminal-client integration.
- [ ] Test browser-client integration.
- [O] Test automated bots.
- [O] Test evaluation sessions.
- [O] Test scoring.
- [O] Test leaderboard ordering.
- [ ] Add an end-to-end automated test.

### Completion Criteria

The major user flows and failure cases are covered by automated tests.

---

## Phase 14 — Documentation and Packaging

> **Assignment note:** The README must include instructions for running the application locally. The repository must contain the items listed in the final checklist task below. Bot, scoring, evaluation, and leaderboard documentation is optional.

### Tasks

- [ ] Create or update `README.md`.
- [ ] README: step-by-step local setup (virtual environment, `pip install -r requirements.txt`, `python server.py`, open `http://localhost:5000`, run the tests).
- [ ] Document how to start the server.
- [ ] Document how to use the browser client.
- [ ] Document how to use the terminal client.
- [ ] Document the REST API.
- [O] Document how to write a student bot.
- [ ] Provide example requests and responses.
- [O] Document scoring.
- [O] Document evaluation rules.
- [O] Document leaderboard behavior.
- [ ] Add dependency information such as `requirements.txt` or `pyproject.toml`.
- [ ] Verify that a fresh installation works from the documented instructions.
- [ ] Document deviations from the spec's suggested structure: `words.py`, `tests/`, `.gitignore`, `render.yaml`, `.python-version`.
- [ ] Confirm the repo contains everything the assignment lists: game engine and Flask server, HTML/CSS/JS frontend, word lists, original `Specification.md`, updated `TODO.md`, dependency and deployment configuration, tests, and README with local run instructions.
- [ ] TODO.md checkmarks are up to date.

### Completion Criteria

A new user can clone the project, install dependencies, start the server, play from the terminal or browser using only the documentation. (Running a sample bot is optional.)

---

## Phase 15 — Deployment

> **Done early:** This phase is completed at the end of Phase 3, not after Phase 14, so deployment problems show up while there is little code. Until Phase 5, the live URL serves only the API (`/` returns "Not Found"). Later phases deploy automatically on each `git push` to `main`.

> **Assignment note:** The assignment requires deploying your own implementation, and the repository must contain the dependency and deployment configuration. Settings typed into Render's dashboard are not visible in the repo, so they live in `render.yaml`.

### Tasks

- [x] Add `flask` and `gunicorn` to `requirements.txt`.
- [x] Add `.python-version` to pin the Python version used locally and on Render.
- [x] Add `render.yaml` (build: `pip install -r requirements.txt`; start: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 server:app`; free plan).
- [x] Add `GET /api/health` (returns `{"status": "ok"}`) for Render's health check. *(Added; not in the spec or assignment.)*
- [x] Run the app locally with gunicorn using the same start command as Render.
- [ ] Deploy to Render from the GitHub repo.
- [ ] Check the live URL with `curl`: `/api/health`, then a full game through `/api/games`.
- [ ] Check the live URL in the browser: play a full game. *(Waits for Phase 5, the web page.)*
- [ ] Add the live URL to the README.

### Completion Criteria

Anyone can open the live URL and play a full game, and the deployment can be recreated from the files in the repository.

---

# Optional Future Phases

These should not be implemented until the core project is stable.

## Persistent Storage

- [ ] Store games in a database.
- [ ] Store evaluations in a database.
- [ ] Persist leaderboard results.

## Accounts and Authentication

- [ ] Student accounts.
- [ ] API keys or tokens.
- [ ] Authenticated evaluation submissions.

## Tournament Mode

- [ ] Batch evaluation of multiple bots.
- [ ] Scheduled tournaments.
- [ ] Tournament history.
- [ ] Public results page.

## Advanced Bot Analysis

- [ ] Entropy-based guessing.
- [ ] Information-gain strategies.
- [ ] Performance charts.
- [ ] Per-difficulty statistics.
- [ ] Head-to-head bot comparisons.

## Multiplayer

- [ ] Human-vs-human modes.
- [ ] Custom words.
- [ ] Spectator mode.

---

# Recommended Development Order

Use this order unless there is a compelling reason to change it:

1. Core Game Engine and Word Management
2. (Merged into Phase 1)
3. REST Server, then Phase 15 (Deployment) early
4. Human Terminal Client
5. Browser Client
6. Reference Automated Clients
7. Dictionary-Based Bot
8. Evaluation Mode
9. Scoring
10. Leaderboard
11. Evaluation Integrity
12. Logging and Replay
13. Full Testing
14. Documentation and Packaging
15. Deployment (done early, at the end of Phase 3)

The project should remain runnable after every completed phase.
