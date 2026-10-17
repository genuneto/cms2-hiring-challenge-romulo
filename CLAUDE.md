# Context for AI tooling

A project editor in front of an upstream records API owned by another team. Hiring challenge; the code will be extended live in an interview, so keep it easy to change.

## Hard rules
- **Never modify anything in `upstream/`.** It is another team's service.
- **The browser never calls the upstream.** Only `backend/app/upstream.py` talks to it.
- Backend instances are stateless. Three run behind a load balancer, and a nightly job writes to the upstream directly. Never keep correctness-relevant state in process memory.

## Layout
- `backend/app/merge.py`: pure three-way merge. This is the definition of "same field". Change rules here first.
- `backend/app/service.py`: the save loop (read, merge, write, settle a timed-out write).
- `backend/app/upstream.py`: upstream client and its error types.
- `backend/app/main.py`, `models.py`: HTTP surface and DTOs.
- `frontend/src/`: `api.ts` (all calls), `model.ts` (helpers incl. `applyChoices`), `ProjectEditor.tsx`, `ConflictDialog.tsx`, `ProjectList.tsx`.

## Upstream behaviour to remember
- Last write wins; no version or timestamp.
- `PUT` replaces `key_dates` and `linked_companies` wholesale and requires every editable field.
- About 1 in 10 `GET /projects/{id}` takes ~2 s. About 1 in 10 `PUT`s answers `504`, and the write may or may not have happened.
- Responses carry ~15 read-only fields we do not expose.

## Invariants of the design
- Saves send `base` (what the form loaded) and `edited`. The backend merges against the live record.
- A conflict writes nothing. A conflict resolution must start from what is stored now, so a value that moved again is a new conflict, never an overwrite.
- A `504` is never retried blindly: re-read, re-merge. "My change is already there" is not a conflict.
- Key date identity is its label. Duplicate labels fall back to treating the whole list as one field.

## Commands
- Upstream: `cd upstream && uv run upstream` (port 8081)
- Backend: `cd backend && uv run backend` (port 8000); tests: `uv run pytest`
- Frontend: `cd frontend && npm run dev` (5173) or `npm run build`; `npm run typecheck`
- Deterministic upstream faults in tests: `backend/tests/conftest.py` (`ScriptedRng`)

## Conventions
- Add a test next to the behaviour. Break the code on purpose once to confirm the test can fail.
- MUI 9: system props such as `alignItems` on `Stack` are gone; use `sx`.
- Keep `DECISIONS.md` truthful: update it when a decision changes.
