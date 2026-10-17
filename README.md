# Project editor

A small editor for infrastructure project records, in front of an upstream records API that this repo does not own.

- `upstream/`: the provided records API. **Untouched.**
- `backend/`: FastAPI. Lists projects, returns one, saves edits with safe concurrent editing.
- `frontend/`: React + MUI. A project list and an edit form for the core fields and key dates.
- `DECISIONS.md`: what I chose, what I cut, what breaks first.

The browser only calls the backend (`/api`). It never calls the upstream.

## Run it

You need [uv](https://docs.astral.sh/uv/) and Node. Three terminals:

```sh
# 1. the upstream (port 8081; resets its data on every restart)
cd upstream && uv run upstream

# 2. the backend (port 8000)
cd backend && uv sync && uv run backend

# 3. the frontend dev server (port 5173, proxies /api to the backend)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. For a single process instead of the dev server, run `npm run build` in `frontend/` and open http://localhost:8000: the backend serves the built files.

Try the concurrency rules: open the same project in two tabs, change different fields and save both (both survive), then change the same field in both (the second save asks you to decide).

The upstream's faults can be switched off with `UPSTREAM_SLOW_RATE=0 UPSTREAM_TIMEOUT_RATE=0`; leave them on to see the backend cope.

Backend settings: `UPSTREAM_URL` (default `http://127.0.0.1:8081`), `UPSTREAM_API_KEY` (default `local-dev-key`), `PORT` (default `8000`).

## Tests

```sh
cd backend && uv run pytest
```

They run the backend against the real upstream app in process, with its `504`s scripted so each case is deterministic.

## What runs, and what does not

Runs: list, open, edit and save of name, country, sector, stage and key dates; per-field merge of concurrent edits; explicit conflict resolution; recovery from the upstream's `504`s and slow reads.

Does not: editing linked companies (kept untouched), authentication, who-changed-what history, a lock shared between backend instances. The UI type-checks and builds but has no automated tests and has not been click-tested in a browser. See `DECISIONS.md` for the reasoning and for what would break first with 50 editors.

## AI trail

See `ai-trail/NOTES.md` and `CLAUDE.md`.

---

All projects, companies and places in this repository are fictional.
