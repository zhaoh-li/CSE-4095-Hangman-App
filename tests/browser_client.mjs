// Browser-client integration test.
//
// Runs the real static/app.js in Node with a small fake page (built from the
// ids in static/index.html) and plays against a real Hangman server.
// It checks what the page's code does, not how the page looks.
//
// Usage:
//   node tests/browser_client.mjs --base http://127.0.0.1:5000 [--word apple]
//
// With --word, the server must always pick that word (the Python test uses a
// fixed-word server), so exact win/loss results can be checked. Without it,
// checks that work with any word are run (used by the end-to-end test).
//
// Prints one JSON line per check: {"name": ..., "ok": true/false, "detail": ...}
// and exits with 1 if any check fails.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const APP_JS = readFileSync(join(ROOT, "static", "app.js"), "utf8");
const INDEX_HTML = readFileSync(join(ROOT, "static", "index.html"), "utf8");

const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, value, i, all) => {
    if (value.startsWith("--")) pairs.push([value.slice(2), all[i + 1]]);
    return pairs;
  }, [])
);
const BASE = (args.base || "http://127.0.0.1:5000").replace(/\/$/, "");
const WORD = args.word ? args.word.toLowerCase() : null;
const LETTERS = "abcdefghijklmnopqrstuvwxyz";
const RARE_FIRST = "qzxjkvwyfbgpmhdculotisnrae"; // usually loses with real words

let failures = 0;
function check(name, ok, detail = "") {
  if (!ok) failures++;
  console.log(JSON.stringify({ name, ok: Boolean(ok), detail: String(detail) }));
}

// ---------------------------------------------------------------------------
// A tiny fake DOM, just enough for app.js
// ---------------------------------------------------------------------------

class ClassList {
  constructor() { this.names = new Set(); }
  add(name) { this.names.add(name); }
  remove(name) { this.names.delete(name); }
  contains(name) { return this.names.has(name); }
  toggle(name, force) {
    const on = force === undefined ? !this.names.has(name) : Boolean(force);
    if (on) this.names.add(name); else this.names.delete(name);
    return on;
  }
}

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.classList = new ClassList();
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.textContent = "";
    this.disabled = false;
    this.radios = [];
  }
  set className(value) {
    this.classList = new ClassList();
    value.split(/\s+/).filter(Boolean).forEach((name) => this.classList.add(name));
  }
  get className() { return [...this.classList.names].join(" "); }
  append(...elements) { this.children.push(...elements); }
  replaceChildren() { this.children = []; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(type, listener) { (this.listeners[type] ||= []).push(listener); }
  fire(type, event = {}) { (this.listeners[type] || []).forEach((listener) => listener(event)); }
  closest(selector) { return selector === ".key" && this.classList.contains("key") ? this : null; }
  querySelectorAll(selector) {
    return selector === ".key" ? this.children.filter((c) => c.classList.contains("key")) : [];
  }
  querySelector(selector) {
    return selector === "input:checked" ? this.radios.find((radio) => radio.checked) || null : null;
  }
}

class FakeButton extends FakeElement {}

// fetchControl lets a scenario change what the "network" does.
function makePage(fetchControl = {}) {
  const ids = [...INDEX_HTML.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
  const byId = {};
  for (const id of ids) byId[id] = id === "new-game" ? new FakeButton("button") : new FakeElement("div");

  const difficulties = [...INDEX_HTML.matchAll(/name="difficulty" value="([a-z]+)"( checked)?/g)];
  byId.difficulty.radios = difficulties.map((m) => ({ value: m[1], checked: Boolean(m[2]) }));

  const partNumbers = [...INDEX_HTML.matchAll(/class="part" data-part="(\d+)"/g)].map((m) => m[1]);
  const parts = partNumbers.map((n) => {
    const part = new FakeElement("line");
    part.dataset.part = n;
    return part;
  });

  const app = new FakeElement("main");
  const documentListeners = {};
  const document = {
    querySelector: (selector) => (selector === ".app" ? app : null),
    getElementById: (id) => {
      if (!byId[id]) throw new Error(`app.js asked for #${id}, which is not in index.html`);
      return byId[id];
    },
    querySelectorAll: (selector) => (selector === "#hangman .part" ? parts : []),
    createElement: (tag) => (tag === "button" ? new FakeButton(tag) : new FakeElement(tag)),
    addEventListener: (type, listener) => { (documentListeners[type] ||= []).push(listener); },
  };

  const log = [];  // every request and the JSON answer
  async function fakeFetch(path, options = {}) {
    const method = options.method || "GET";
    if (fetchControl.before) {
      const replaced = await fetchControl.before(path, options);
      if (replaced) {
        log.push({ method, path, status: replaced.status, body: null });
        return replaced;
      }
    }
    const realPath = fetchControl.rewrite ? fetchControl.rewrite(path, options) : path;
    const response = await fetch(BASE + realPath, options);
    const text = await response.clone().text();
    let body = null;
    try { body = JSON.parse(text); } catch { /* not JSON */ }
    log.push({ method, path: realPath, status: response.status, body });
    return response;
  }

  const context = vm.createContext({
    document,
    HTMLButtonElement: FakeButton,
    AbortController,
    setTimeout,
    clearTimeout,
    console,
    fetch: fakeFetch,
  });
  vm.runInContext(APP_JS, context, { filename: "static/app.js" });

  const keys = () => byId.keyboard.children.filter((c) => c.classList.contains("key"));
  const key = (letter) => keys().find((k) => k.dataset.letter === letter);

  return {
    byId, parts, log,
    keys, key,
    message: () => byId.message.textContent,
    messageKind: () => byId.message.className,
    patternText: () => byId.pattern.children.map((c) => c.textContent || "_").join(" "),
    patternBoxes: () => byId.pattern.children,
    shownParts: () => parts.filter((p) => p.classList.contains("shown")).length,
    status: () => (byId.board.classList.contains("won") ? "won"
      : byId.board.classList.contains("lost") ? "lost" : "playing"),
    click: (letter) => byId.keyboard.fire("click", { target: key(letter) }),
    press: (k, extra = {}) =>
      (documentListeners.keydown || []).forEach((listener) =>
        listener({ key: k, target: {}, preventDefault() {}, ...extra })),
    setDifficulty: (value) => {
      byId.difficulty.radios.forEach((radio) => (radio.checked = radio.value === value));
      byId.difficulty.fire("change");
    },
    clickNewGame: () => byId["new-game"].fire("click"),
    requests: () => log.length,
  };
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function until(condition, ms = 5000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    if (condition()) return true;
    await sleep(10);
  }
  return false;
}
const started = (page) => until(() => /^New (easy|medium|hard) game/.test(page.message()));
const settled = async (page) => { await sleep(30); await until(() => !page.byId.message.textContent.endsWith("…")); };

async function guessLetter(page, letter) {
  const before = page.requests();
  page.click(letter);
  await until(() => page.requests() > before && page.key(letter).disabled);
}

async function playUntilOver(page, order) {
  for (const letter of order) {
    if (page.status() !== "playing") break;
    if (!page.key(letter).disabled) await guessLetter(page, letter);
  }
}

function wordRevealedAt(page) {
  // Index of the first answer that contains "word", or -1.
  return page.log.findIndex((entry) => entry.body && typeof entry.body === "object" && "word" in entry.body);
}

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------

async function startOfGame() {
  const page = makePage();
  check("page starts a game by itself", await started(page), page.message());
  check("default difficulty is medium", page.message().startsWith("New medium game"), page.message());
  check("26 letter buttons", page.keys().length === 26, page.keys().length);
  check("all letters enabled at start", page.keys().every((k) => !k.disabled));
  check("lives shows 6 of 6", page.byId.remaining.textContent === "6 of 6", page.byId.remaining.textContent);
  check("no drawing parts at start", page.shownParts() === 0, page.shownParts());
  check("guessed and wrong show a dash", page.byId.guessed.textContent === "–" && page.byId.wrong.textContent === "–");
  check("pattern is all blanks", page.patternBoxes().length > 0 && page.patternBoxes().every((b) => b.textContent === ""),
    page.patternText());
  if (WORD) check("one box per letter", page.patternBoxes().length === WORD.length, page.patternBoxes().length);
  check("only the API is called", page.log.every((e) => e.path.startsWith("/api/")), page.log.map((e) => e.path));
}

async function clickingAndTyping() {
  const page = makePage();
  await started(page);

  await guessLetter(page, "e");
  const eWrong = page.key("e").classList.contains("wrong");
  const eRight = page.key("e").classList.contains("correct");
  check("clicked letter is colored correct or wrong", eWrong !== eRight, page.key("e").className);
  check("message matches the server's answer",
    (eRight && page.message() === 'Yes! "E" is in the word.') || (eWrong && page.message() === 'Nope, no "E".'),
    page.message());
  check("guessed list shows the letter", page.byId.guessed.textContent === "e", page.byId.guessed.textContent);

  const before = page.requests();
  page.press("e"); page.press("E");
  page.press("1"); page.press("Shift"); page.press("ArrowLeft"); page.press(" ");
  page.press("r", { ctrlKey: true }); page.press("r", { metaKey: true }); page.press("r", { altKey: true });
  page.press("a", { repeat: true });
  page.click("e");
  await sleep(100);
  check("repeats, non-letters, shortcuts and held keys send nothing", page.requests() === before,
    page.requests() - before);

  page.press("A");
  await until(() => page.key("a").disabled);
  check("typing a letter guesses it", page.key("a").disabled && page.byId.guessed.textContent === "e, a",
    page.byId.guessed.textContent);

  // Double-click: only one request should go out.
  const beforeDouble = page.requests();
  page.click("t"); page.click("t"); page.press("t");
  await until(() => page.key("t").disabled);
  await sleep(50);
  check("double click sends one guess", page.requests() - beforeDouble === 1, page.requests() - beforeDouble);
}

async function lossPath() {
  const page = makePage();
  await started(page);
  const order = WORD ? [...LETTERS].filter((l) => !WORD.includes(l)) : [...RARE_FIRST];
  const revealBefore = [];
  for (const letter of order) {
    if (page.status() !== "playing") break;
    if (page.key(letter).disabled) continue;
    await guessLetter(page, letter);
    revealBefore.push(wordRevealedAt(page));
    const wrong = page.byId.wrong.textContent.split(", ").filter((x) => x !== "–").length;
    if (page.status() === "playing") {
      check(`drawing has ${wrong} part(s) after ${wrong} wrong`, page.shownParts() === wrong, page.shownParts());
    }
  }
  if (!WORD && page.status() !== "lost") {
    check("loss path (skipped: this word was won)", true, page.message());
    return;
  }
  check("game is lost", page.status() === "lost", page.message());
  check("lost message shows the word", /^You lost\. The word was "[A-Z]+"\.$/.test(page.message()), page.message());
  if (WORD) check("lost message has the right word", page.message().includes(`"${WORD.toUpperCase()}"`), page.message());
  check("lost message is styled as a loss", page.messageKind().includes("message--lose"), page.messageKind());
  check("all 6 parts shown", page.shownParts() === 6, page.shownParts());
  check("lives shows 0", page.byId.remaining.textContent.startsWith("0 of"), page.byId.remaining.textContent);
  check("missed letters are marked", page.patternBoxes().some((b) => b.classList.contains("missed")));
  check("full word is shown", !page.patternText().includes("_"), page.patternText());
  check("all keys disabled after the game", page.keys().every((k) => k.disabled));
  const last = page.log.length - 1;
  check("word arrives only in the final answer", wordRevealedAt(page) === last, `${wordRevealedAt(page)} of ${last}`);

  const before = page.requests();
  page.press("z"); page.click("z");
  await sleep(80);
  check("letters are ignored after the game ends", page.requests() === before);
}

async function winPath() {
  if (!WORD) return; // a guaranteed win needs a known word
  const page = makePage();
  await started(page);
  await guessLetter(page, "z"); // one wrong guess first
  for (const letter of new Set(WORD)) {
    if (page.status() === "playing") {
      check("word hidden while playing", !page.message().includes(WORD.toUpperCase())
        && !page.patternText().replace(/ /g, "").includes(WORD), page.patternText());
      await guessLetter(page, letter);
    }
  }
  check("game is won", page.status() === "won", page.message());
  check("win message shows the word", page.message() === `You won! The word was "${WORD.toUpperCase()}".`, page.message());
  check("win message is styled as a win", page.messageKind().includes("message--win"), page.messageKind());
  check("drawing shows only the wrong guesses", page.shownParts() === 1, page.shownParts());
  check("lives shows 5 of 6", page.byId.remaining.textContent === "5 of 6", page.byId.remaining.textContent);
  check("no letters marked missed on a win", !page.patternBoxes().some((b) => b.classList.contains("missed")));
  check("all keys disabled after the win", page.keys().every((k) => k.disabled));
}

async function newGames() {
  const page = makePage();
  await started(page);

  // Changing difficulty before guessing starts that game right away.
  page.setDifficulty("hard");
  check("difficulty change before guessing starts a hard game",
    await until(() => page.message() === "New hard game. Guess a letter!"), page.message());

  // Changing difficulty mid-game only takes effect on New Game.
  await guessLetter(page, "e");
  const gamesBefore = page.log.filter((e) => e.method === "POST" && e.path === "/api/games").length;
  page.setDifficulty("easy");
  await sleep(80);
  check("difficulty change mid-game waits for New Game", page.message() === "Press New Game to play easy.", page.message());
  check("no new game started mid-game",
    page.log.filter((e) => e.method === "POST" && e.path === "/api/games").length === gamesBefore);

  // New Game button mid-game.
  page.clickNewGame();
  check("New Game button starts an easy game without reloading",
    await until(() => page.message() === "New easy game. Guess a letter!"), page.message());
  check("board resets on New Game", page.keys().every((k) => !k.disabled) && page.shownParts() === 0
    && page.byId.guessed.textContent === "–");

  // Enter mid-game does nothing; Enter after the game ends starts a new one.
  const before = page.requests();
  page.press("Enter");
  await sleep(80);
  check("Enter mid-game does nothing", page.requests() === before);

  await playUntilOver(page, WORD ? [...LETTERS].filter((l) => !WORD.includes(l)) : [...RARE_FIRST]);

  // After the game: Enter on a focused button is left to the button (no double start).
  const beforeButtonEnter = page.requests();
  page.press("Enter", { target: new FakeButton("button") });
  await sleep(80);
  check("Enter on a focused button is left to the button", page.requests() === beforeButtonEnter,
    page.requests() - beforeButtonEnter);

  page.press("Enter");
  check("Enter after the game ends starts a new game",
    await until(() => page.message() === "New easy game. Guess a letter!" && page.status() === "playing"), page.message());
}

async function serverProblems() {
  // Server can't be reached during a guess.
  {
    let offline = false;
    const page = makePage({ before: () => { if (offline) throw new TypeError("Failed to fetch"); } });
    await started(page);
    offline = true;
    page.click("e");
    await until(() => page.message().startsWith("Can't reach"));
    check("unreachable server shows a clear message",
      page.message() === "Can't reach the server. Check your connection and try New Game.", page.message());
    check("unreachable message is styled as an error", page.messageKind().includes("message--error"));
  }

  // Server can't be reached at page load.
  {
    const page = makePage({ before: () => { throw new TypeError("Failed to fetch"); } });
    await until(() => page.message().startsWith("Can't reach"));
    check("unreachable at load shows a message and no keys work",
      page.message().startsWith("Can't reach") && page.keys().every((k) => k.disabled), page.message());
  }

  // Game no longer exists (404).
  {
    let breakGuess = false;
    const page = makePage({
      rewrite: (path) => (breakGuess && path.endsWith("/guess") ? "/api/games/doesnotexist/guess" : path),
    });
    await started(page);
    breakGuess = true;
    page.click("e");
    await until(() => page.message().startsWith("This game no longer exists"));
    check("missing game (404) explains and asks for a new game",
      page.message().startsWith("This game no longer exists on the server"), page.message());
    check("keys are disabled after a missing game", page.keys().every((k) => k.disabled));
  }

  // Server error (500) when starting a game.
  {
    const page = makePage({
      before: (path, options) => (options.method === "POST" && path === "/api/games"
        ? new Response(JSON.stringify({ error: "Internal server error." }),
          { status: 500, headers: { "Content-Type": "application/json" } })
        : null),
    });
    await until(() => page.message().startsWith("Server error"));
    check("server error (500) shows a friendly message", page.message() === "Server error. Try New Game.", page.message());
  }

  // Server rejects a guess the page thought was fine (409): show it, then reload the state.
  {
    let rejectOnce = false;
    const page = makePage({
      before: (path, options) => {
        if (rejectOnce && path.endsWith("/guess")) {
          rejectOnce = false;
          return new Response(JSON.stringify({ error: "The letter 'e' was already guessed." }),
            { status: 409, headers: { "Content-Type": "application/json" } });
        }
        return null;
      },
    });
    await started(page);
    rejectOnce = true;
    const before = page.log.length;
    page.click("e");
    await until(() => page.log.length >= before + 2);
    check("rejected guess (409) shows the server's message", page.message() === "The letter 'e' was already guessed.",
      page.message());
    check("rejected guess reloads the game state",
      page.log.slice(before).some((e) => e.method === "GET" && e.path.startsWith("/api/games/")));
  }

  // Slow server: a "waking up" note after 3 seconds.
  {
    const page = makePage({ before: async (path) => { if (path === "/api/games") await sleep(3400); return null; } });
    check("slow server shows the waking-up note",
      await until(() => page.message().startsWith("Waking up the server"), 3300), page.message());
    check("slow server still starts the game", await started(page), page.message());
  }
}

// ---------------------------------------------------------------------------

const scenarios = [startOfGame, clickingAndTyping, lossPath, winPath, newGames, serverProblems];
for (const scenario of scenarios) {
  try {
    await scenario();
  } catch (error) {
    check(`${scenario.name} ran without crashing`, false, error.stack || error);
  }
}
process.exit(failures ? 1 : 0);
