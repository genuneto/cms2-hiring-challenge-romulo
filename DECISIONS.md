# Decisions

## What I built
A FastAPI backend in front of the upstream records API, and a React + MUI project list and edit form (core fields and key dates). The browser only ever calls `/api` on my backend; the upstream and its key are never exposed.

## Core choice: a stateless three-way merge, not version numbers
The upstream has no version, no ETag, and the last write wins, so it cannot reject a stale save. The form therefore sends the snapshot it loaded (`base`) along with its edits. On save, the backend re-reads the live record and compares per field:

- the person did not touch it → keep what is stored
- only the person changed it → apply it
- both changed it to different values → **conflict, nothing is written**. The `409` returns both values and the person chooses, explicitly and per field. The second saver decides.

The comparison is against the live upstream record, not against anything my backend remembers. That is why it behaves the same on three instances behind a load balancer, and why it notices the nightly job's direct writes. A version counter kept in my own storage would have been blind to that job.

## What "the same field" means for key dates
**One entry, identified by its label.** Two researchers moving different milestones is the normal case, and a whole-list rule would make them conflict constantly. The label is the only identity an entry has (no ids). Consequences I accept: renaming a label is a removal plus an addition, so a concurrent edit of the old label's date conflicts (safe, if occasionally noisy); both people adding the same label with different dates conflict; the same date does not. Upstream allows duplicate labels, where entries cannot be told apart, so then the whole list becomes one field. The UI and API refuse to create new duplicates.

## How the upstream's habits are handled
- **`PUT` replaces the lists:** every save sends the full merged `key_dates`, and `linked_companies` echoed from the read made just before the write, so changes made there by others survive.
- **`504` is ambiguous:** never blindly retried. The backend re-reads and re-merges. If my change is already stored it counts as "same value", so nothing is written and the answer is "saved". Retries are idempotent. After three writes it does one verification read and answers truthfully: saved, not saved, or unknown.
- **Slow `GET`:** 5 s timeout and one retry. **Wide responses:** the API returns five fields.

## What I cut
- Editing `linked_companies`: the brief asks for core fields and key dates, so it is passed through untouched.
- Who-changed-what attribution or an audit log: the upstream has no notion of identity.
- A shared lock, list caching or pagination, auth, live updates.
- Frontend tests. **The UI type-checks and builds, but I have not clicked through it in a browser.**

## What breaks first with 50 editors
1. **The cross-instance race.** Read-then-write is not atomic. Two saves on different instances inside the same few milliseconds both read the old record, and the second `PUT` erases the first, even on different fields. My per-project lock only covers saves landing on the same instance; removing it makes two tests fail, which shows the race is real. Fix: a per-project lock in shared storage (Redis or Postgres advisory lock) around read-merge-write. The nightly job would still bypass it, so the real fix is an `If-Match` or version field from the upstream team.
2. **Hot projects:** the lock is held across slow reads and retries, so editors of one project queue for seconds.
3. **The list** fetches every project in full on each load. At scale it needs pagination or a cache.
4. **Conflict prompts** become frequent on popular projects. Per-field granularity only helps when people touch different fields.

## What I checked
29 automated tests: merge rules, and the backend against the real upstream app with scripted `504`s (landed and not landed). Breaking the lock and the conflict rule on purpose turned the right tests red. An end-to-end run against the real services with the upstream's default faults: 80 saves, 15 `504`s handled, no outcome misreported; 40 of 40 concurrent different-field saves survived; a nightly write was preserved or flagged correctly.
