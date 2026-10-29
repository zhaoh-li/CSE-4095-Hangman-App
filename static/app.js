// Hangman browser client.
//
// This file has no game logic and no word lists. It sends the player's
// guesses to the Flask server with fetch() and redraws the page from the
// server's JSON answer. The server decides whether a guess is correct and
// whether the game is won or lost. The hidden word only arrives (as "word")
// after the game ends.

"use strict";

(() => {
  const REQUEST_TIMEOUT_MS = 90000; // Render's free plan can take ~1 minute to wake up
  const SLOW_NOTICE_MS = 3000;      // show "waking up" if a request takes this long
  const LETTERS = "abcdefghijklmnopqrstuvwxyz";
  const DRAWING_PARTS = 6;

  const els = {
    app: document.querySelector(".app"),
    board: document.getElementById("board"),
    pattern: document.getElementById("pattern"),
    remaining: document.getElementById("remaining"),
    guessed: document.getElementById("guessed"),
    wrong: document.getElementById("wrong"),
    message: document.getElementById("message"),
    keyboard: document.getElementById("keyboard"),
    newGame: document.getElementById("new-game"),
    difficulty: document.getElementById("difficulty"),
    parts: document.querySelectorAll("#hangman .part"),
  };

  let game = null;       // the server's latest answer for the current game
  let busy = false;      // true while a request is in flight
  let maxGuesses = DRAWING_PARTS;

  // ----- Talking to the server -----

  class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status; // 0 means the server could not be reached
    }
  }

  async function api(method, path, body) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    const slowNotice = setTimeout(
      () => showMessage("Waking up the server… this can take up to a minute.", "info"),
      SLOW_NOTICE_MS
    );

    let response;
    let data = null;
    try {
      const options = { method, signal: controller.signal, headers: { Accept: "application/json" } };
      if (body !== undefined) {
        options.headers["Content-Type"] = "application/json";
        options.body = JSON.stringify(body);
      }
      response = await fetch(path, options);
      data = await response.json().catch(() => null);
    } catch (error) {
      throw new ApiError(0, "Can't reach the server. Check your connection and try New Game.");
    } finally {
      clearTimeout(timeout);
      clearTimeout(slowNotice);
    }

    if (!response.ok) {
      const message = data && typeof data.error === "string"
        ? data.error
        : `Server error (${response.status}).`;
      throw new ApiError(response.status, message);
    }
    if (!data) {
      throw new ApiError(response.status, "Unexpected answer from the server.");
    }
    return data;
  }

  // ----- Actions -----

  function selectedDifficulty() {
    const checked = els.difficulty.querySelector("input:checked");
    return checked ? checked.value : "medium";
  }

  async function newGame() {
    if (busy) return;
    setBusy(true);
    showMessage("Starting a new game…", "info");
    try {
      const state = await api("POST", "/api/games", { difficulty: selectedDifficulty() });
      game = state;
      maxGuesses = state.remaining_guesses + state.incorrect_letters.length;
      render(state);
      showMessage(`New ${state.difficulty} game. Guess a letter!`, "info");
    } catch (error) {
      game = null;
      render(null);
      showError(error);
    } finally {
      setBusy(false);
    }
  }

  async function guess(letter) {
    // Ignore input that can't be a new guess. The server still checks everything.
    if (busy || !game || game.status !== "playing" || game.guessed_letters.includes(letter)) {
      return;
    }
    setBusy(true);
    const shown = letter.toUpperCase();
    try {
      const state = await api("POST", `/api/games/${encodeURIComponent(game.game_id)}/guess`, { letter });
      game = state;
      render(state);
      if (state.status === "won") {
        showMessage(`You won! The word was "${state.word.toUpperCase()}".`, "win");
      } else if (state.status === "lost") {
        showMessage(`You lost. The word was "${state.word.toUpperCase()}".`, "lose");
      } else if (state.correct) {
        showMessage(`Yes! "${shown}" is in the word.`, "good");
      } else {
        showMessage(`Nope, no "${shown}".`, "bad");
      }
    } catch (error) {
      if (error.status === 404) {
        game = null;
        render(null);
        showMessage("This game no longer exists on the server (it may have restarted). Start a new game.", "error");
      } else if (error.status === 400 || error.status === 409) {
        showMessage(error.message, "error");
        await refresh();
      } else {
        showError(error);
      }
    } finally {
      setBusy(false);
    }
  }

  // Reload the current game's state from the server after a rejected guess.
  async function refresh() {
    if (!game) return;
    try {
      game = await api("GET", `/api/games/${encodeURIComponent(game.game_id)}`);
      render(game);
    } catch (error) {
      // Keep the message already shown.
    }
  }

  // ----- Drawing the page from the server's answer -----

  function render(state) {
    const playing = Boolean(state) && state.status === "playing";
    const guessed = state ? state.guessed_letters : [];
    const wrong = state ? state.incorrect_letters : [];

    els.board.classList.toggle("won", Boolean(state) && state.status === "won");
    els.board.classList.toggle("lost", Boolean(state) && state.status === "lost");

    renderPattern(state);

    els.remaining.textContent = state ? `${state.remaining_guesses} of ${maxGuesses}` : "–";
    els.guessed.textContent = guessed.length ? guessed.join(", ") : "–";
    els.wrong.textContent = wrong.length ? wrong.join(", ") : "–";

    // One body part per wrong guess (counted from the server's list).
    els.parts.forEach((part) => {
      part.classList.toggle("shown", Number(part.dataset.part) <= wrong.length);
    });

    els.keyboard.querySelectorAll(".key").forEach((key) => {
      const letter = key.dataset.letter;
      const used = guessed.includes(letter);
      key.classList.toggle("wrong", wrong.includes(letter));
      key.classList.toggle("correct", used && !wrong.includes(letter));
      key.disabled = !playing || used;
    });
  }

  function renderPattern(state) {
    els.pattern.replaceChildren();
    if (!state) return;

    const slots = state.pattern.split(" ");
    // After the game ends the server sends the word; show the letters that were missed.
    const word = typeof state.word === "string" ? state.word : null;

    slots.forEach((slot, index) => {
      const box = document.createElement("span");
      box.className = "letter";
      if (slot === "_" && word) {
        box.textContent = word[index] || "";
        box.classList.add("missed");
      } else {
        box.textContent = slot === "_" ? "" : slot;
      }
      els.pattern.append(box);
    });
    els.pattern.setAttribute("aria-label", `Word: ${slots.map((s) => (s === "_" ? "blank" : s)).join(" ")}`);
  }

  function showMessage(text, kind) {
    els.message.textContent = text;
    els.message.className = `message message--${kind}`;
  }

  function showError(error) {
    if (error instanceof ApiError && error.status >= 500) {
      showMessage("Server error. Try New Game.", "error");
    } else if (error instanceof ApiError) {
      showMessage(error.message, "error");
    } else {
      showMessage("Something went wrong. Try New Game.", "error");
    }
  }

  function setBusy(value) {
    busy = value;
    els.app.classList.toggle("busy", value);
    els.app.setAttribute("aria-busy", String(value));
  }

  // ----- Setup -----

  function buildKeyboard() {
    for (const letter of LETTERS) {
      const key = document.createElement("button");
      key.type = "button";
      key.className = "key";
      key.dataset.letter = letter;
      key.textContent = letter;
      key.setAttribute("aria-label", `Guess ${letter.toUpperCase()}`);
      key.disabled = true;
      els.keyboard.append(key);
    }
  }

  els.keyboard.addEventListener("click", (event) => {
    const key = event.target.closest(".key");
    if (key && !key.disabled) guess(key.dataset.letter);
  });

  els.newGame.addEventListener("click", () => newGame());

  // Changing difficulty starts a new game right away, unless a game is in
  // progress with guesses made (then it applies to the next New Game).
  els.difficulty.addEventListener("change", () => {
    if (!game || game.status !== "playing" || game.guessed_letters.length === 0) {
      newGame();
    } else {
      showMessage(`Press New Game to play ${selectedDifficulty()}.`, "info");
    }
  });

  // Physical keyboard: letters guess, Enter starts a new game after a game ends.
  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey || event.metaKey || event.altKey || event.repeat) return;
    const key = event.key.toLowerCase();

    if (key === "enter") {
      const onButton = event.target instanceof HTMLButtonElement;
      if (!onButton && (!game || game.status !== "playing")) {
        event.preventDefault();
        newGame();
      }
      return;
    }

    if (key.length === 1 && LETTERS.includes(key)) {
      event.preventDefault();
      guess(key);
    }
  });

  buildKeyboard();
  render(null);
  newGame();
})();
