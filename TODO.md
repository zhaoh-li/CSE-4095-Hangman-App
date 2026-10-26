# TODO — Hangman Client/Server Project

This file is the implementation roadmap for the Hangman project.

The authoritative system requirements are defined in `Specification.md`.

## Implementation Rules

- Implement one phase at a time.
- Complete and test all items in the current phase before moving to the next phase.
- Do not change the architecture or REST API defined in `Specification.md` unless necessary.
- If a deviation is necessary, document it in the README and update the specification.
- Keep the game engine independent from Flask, the browser UI, and the terminal UI.
- The server must remain authoritative.
- Never expose the hidden word before a game ends.
- Add tests as each phase is implemented rather than postponing testing until the end.
- Checkbox key: `[ ]` = to do, `[x]` = done, `[O]` = optional (not required for this assignment).

---

## Phase 1 — Project Skeleton and Core Game Engine

### Tasks

- [ ] Create the project directory structure.
- [ ] Add `words/easy.txt`.
- [ ] Add `words/medium.txt`.
- [ ] Add `words/hard.txt`.
- [ ] Create `game.py`.
- [ ] Implement a `HangmanGame` class.
- [ ] Store the hidden word internally.
- [ ] Track guessed letters.
- [ ] Track incorrect letters.
- [ ] Track the maximum number of incorrect guesses.
- [ ] Implement single-letter guess validation.
- [ ] Detect duplicate guesses.
- [ ] Implement masked-word generation.
- [ ] Implement win detection.
- [ ] Implement loss detection.
- [ ] Implement game status values such as `playing`, `won`, and `lost`.
- [ ] Implement a method that returns a client-safe game-state dictionary.
- [ ] Reveal the answer only after the game ends.
- [ ] Add unit tests for the game engine.

### Completion Criteria

The game engine can be tested entirely without running a web server.

All core rules are covered by unit tests.

---

## Phase 2 — Word Management

### Tasks

- [ ] Create a word-loading module or helper functions.
- [ ] Load Easy, Medium, and Hard word lists.
- [ ] Validate that loaded words contain only alphabetic characters.
- [ ] Remove accidental duplicates when loading.
- [ ] Support random word selection by difficulty.
- [ ] Return an error for an invalid difficulty.
- [ ] Add tests for word loading and word selection.

### Completion Criteria

The program can request a random word from each difficulty level reliably.

Invalid difficulty values are rejected cleanly.

---

## Phase 3 — Basic REST Server

### Tasks

- [ ] Create `server.py`.
- [ ] Configure Flask or FastAPI.
- [ ] Add in-memory storage for active games.
- [ ] Generate unique game IDs.
- [ ] Implement `POST /api/games`.
- [ ] Implement `GET /api/games/{game_id}`.
- [ ] Implement `POST /api/games/{game_id}/guess`.
- [ ] Validate difficulty input.
- [ ] Validate guess input.
- [ ] Return JSON responses consistently.
- [ ] Return appropriate HTTP status codes.
- [ ] Handle unknown game IDs.
- [ ] Handle malformed requests.
- [ ] Ensure the hidden word is never leaked during an active game.
- [ ] Add API tests.

### Completion Criteria

A complete Hangman game can be played using only `curl` or another HTTP client.

The browser and terminal clients are not required for this phase.

---

## Phase 4 — Human Terminal Client

### Tasks

- [ ] Create `terminal_client.py`.
- [ ] Connect to the Hangman server over HTTP.
- [ ] Let the user choose Easy, Medium, or Hard.
- [ ] Start a new game through the REST API.
- [ ] Display the masked word.
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

### Tasks

- [ ] Create `static/index.html`.
- [ ] Create `static/style.css`.
- [ ] Create `static/app.js`.
- [ ] Add a difficulty selector.
- [ ] Add a New Game button.
- [ ] Display the masked word.
- [ ] Display guessed letters.
- [ ] Display incorrect letters.
- [ ] Display remaining guesses.
- [ ] Add an on-screen alphabet keyboard.
- [ ] Disable already-guessed letters.
- [ ] Use `fetch()` to communicate with the REST API.
- [ ] Draw the Hangman state visually.
- [ ] Update the drawing after incorrect guesses.
- [ ] Display win and loss messages.
- [ ] Provide a restart/new-game flow.
- [ ] Make the interface usable on common desktop and mobile browser sizes.

### Completion Criteria

A human player can play the same server-hosted game from a browser.

No hidden word is stored in browser-side JavaScript.

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

### Tasks

- [ ] Define a game-log format.
- [ ] Record game ID.
- [ ] Record difficulty.
- [ ] Record each guess in order.
- [ ] Record whether each guess was correct.
- [ ] Record pattern after each guess.
- [ ] Record remaining guesses after each move.
- [ ] Record final outcome.
- [ ] Add optional timestamps.
- [ ] Add a replay utility or endpoint.
- [ ] Ensure logs do not expose hidden evaluation words before evaluation completion.

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
- [ ] Test automated bots.
- [ ] Test evaluation sessions.
- [ ] Test scoring.
- [ ] Test leaderboard ordering.
- [ ] Add an end-to-end automated test.

### Completion Criteria

The major user flows and failure cases are covered by automated tests.

---

## Phase 14 — Documentation and Packaging

### Tasks

- [ ] Create or update `README.md`.
- [ ] Document installation.
- [ ] Document how to start the server.
- [ ] Document how to use the browser client.
- [ ] Document how to use the terminal client.
- [ ] Document the REST API.
- [ ] Document how to write a student bot.
- [ ] Provide example requests and responses.
- [ ] Document scoring.
- [ ] Document evaluation rules.
- [ ] Document leaderboard behavior.
- [ ] Add dependency information such as `requirements.txt` or `pyproject.toml`.
- [ ] Verify that a fresh installation works from the documented instructions.

### Completion Criteria

A new user can clone the project, install dependencies, start the server, play from the terminal or browser, and run a sample bot using only the documentation.

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

1. Core Game Engine
2. Word Management
3. REST Server
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

The project should remain runnable after every completed phase.
