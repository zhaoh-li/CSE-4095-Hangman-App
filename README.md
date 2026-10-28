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

The server runs at `http://localhost:5000`. The web page arrives in Phase 5. Until then, use the API:

```bash
curl -s -X POST localhost:5000/api/games -H "Content-Type: application/json" -d '{"difficulty":"easy"}'
curl -s -X POST localhost:5000/api/games/GAME_ID/guess -H "Content-Type: application/json" -d '{"letter":"e"}'
curl -s localhost:5000/api/games/GAME_ID
```

## Run the tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```

## Deployment

Deployed on Render using `render.yaml` (build and start commands) and `.python-version`.
