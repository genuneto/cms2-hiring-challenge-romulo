"""The save path: read fresh, merge, write, and settle any doubt about a write that timed out.

Nothing here is remembered between requests. Every decision is made by comparing the person's `base` with the
upstream's state as read a moment ago. That is what lets three instances behind a load balancer agree, and what
lets us notice writes made by the nightly job, which never passes through this code.
"""

import asyncio
import logging
import weakref
from dataclasses import dataclass

from app.merge import Conflict, merge
from app.upstream import UpstreamClient, UpstreamUnavailable, WriteOutcomeUnknown

log = logging.getLogger("service")

MAX_WRITE_ATTEMPTS = 3
BACKOFF_SECONDS = 0.15


def editable_of(record: dict) -> dict:
    """Narrow a wide upstream record to the fields we edit, with dates as plain strings."""
    return {
        "name": record["name"],
        "sector": record["sector"],
        "country": record["country"],
        "stage": record["stage"],
        "key_dates": [{"label": d["label"], "date": d["date"]} for d in record["key_dates"]],
    }


@dataclass
class Saved:
    project: dict  # full upstream record as stored
    incoming: list[str]
    wrote: bool
    attempts: int


@dataclass
class Conflicted:
    current: dict
    conflicts: list[Conflict]
    proposed: dict


class NotSaved(Exception):
    """`saved` is "no" when we know nothing was written, "unknown" when we could not find out."""

    def __init__(self, saved: str, message: str) -> None:
        super().__init__(message)
        self.saved = saved
        self.message = message


class KeyedLocks:
    """One asyncio lock per project id, per process.

    This only narrows the window between two saves that happen to land on the same instance. It is NOT what makes
    concurrent editing correct: with three instances, and a nightly job writing straight to the upstream, the
    guarantee comes from re-reading and merging, and the remaining window is described in DECISIONS.md.
    """

    def __init__(self) -> None:
        self._locks: "weakref.WeakValueDictionary[str, asyncio.Lock]" = weakref.WeakValueDictionary()

    def get(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock


async def save_project(upstream: UpstreamClient, locks: KeyedLocks, project_id: str, base: dict, edited: dict) -> Saved | Conflicted:
    maybe_written = False
    lock = locks.get(project_id)
    async with lock:
        # Attempt N+1 is a read-only verification pass: after the last failed write it tells us what really happened.
        for attempt in range(1, MAX_WRITE_ATTEMPTS + 2):
            try:
                current = await upstream.get_project(project_id)
            except UpstreamUnavailable as exc:
                raise NotSaved("unknown" if maybe_written else "no", f"Could not read the project: {exc}") from exc

            theirs = editable_of(current)
            result = merge(base, edited, theirs)

            if result.conflicts:
                log.info("conflict project=%s keys=%s", project_id, [c.key for c in result.conflicts])
                return Conflicted(current=current, conflicts=result.conflicts, proposed=result.merged)

            if result.merged == theirs:
                # Nothing left to write: either there was nothing to change, or an earlier timed-out write DID land.
                log.info("saved project=%s wrote=false attempts=%d", project_id, attempt - 1)
                return Saved(project=current, incoming=result.incoming, wrote=False, attempts=attempt - 1)

            if attempt > MAX_WRITE_ATTEMPTS:
                break

            # PUT replaces both lists wholesale and requires every field. linked_companies is not edited here, so it
            # is sent back exactly as just read, which keeps whatever the nightly job last put there.
            body = {**result.merged, "linked_companies": current["linked_companies"]}
            try:
                stored = await upstream.put_project(project_id, body)
            except WriteOutcomeUnknown as exc:
                maybe_written = True
                log.warning("write outcome unknown project=%s attempt=%d reason=%s", project_id, attempt, exc)
                await asyncio.sleep(BACKOFF_SECONDS * attempt)
                continue

            log.info("saved project=%s wrote=true attempts=%d", project_id, attempt)
            return Saved(project=stored, incoming=result.incoming, wrote=True, attempts=attempt)

    raise NotSaved("no", "The records service kept timing out. The last check showed your change was not saved.")
