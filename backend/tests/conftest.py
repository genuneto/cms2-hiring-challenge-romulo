"""Fixtures that run OUR backend against the REAL upstream app, in process, with scripted faults.

The upstream is imported from ../upstream (see pyproject pythonpath) and never modified. Its random faults are
made deterministic by handing it a scripted rng, so "the 504 that did write" and "the 504 that did not" are tests,
not luck.
"""

from dataclasses import dataclass

import httpx
import pytest

from app import service
from app.main import create_app
from records_api.main import API_KEY, create_app as create_upstream_app

UPSTREAM_HEADERS = {"X-Api-Key": API_KEY}


class ScriptedRng:
    """Upstream asks `rng.random()` whether to fail, then (on a failed PUT) whether the write landed."""

    def __init__(self) -> None:
        self.queue: list[float] = []

    def script(self, *values: float) -> None:
        self.queue.extend(values)

    def random(self) -> float:
        return self.queue.pop(0) if self.queue else 0.99


# With UPSTREAM_TIMEOUT_RATE=0.5: a first draw below 0.5 is a 504; a second draw below 0.5 means "the write landed".
FAIL_AND_LAND = (0.1, 0.1)
FAIL_NOT_LANDED = (0.1, 0.9)


@dataclass
class Env:
    api: httpx.AsyncClient  # the browser's view: our backend
    direct: httpx.AsyncClient  # a writer that bypasses us, like the nightly import job
    rng: ScriptedRng

    async def load(self, project_id: str = "P-1001") -> dict:
        response = await self.api.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        return response.json()

    async def upstream_record(self, project_id: str = "P-1001") -> dict:
        return (await self.direct.get(f"/projects/{project_id}")).json()

    async def nightly_write(self, project_id: str = "P-1001", **changes) -> None:
        record = await self.upstream_record(project_id)
        body = {k: record[k] for k in ("name", "sector", "country", "stage", "key_dates", "linked_companies")}
        body.update(changes)
        assert (await self.direct.put(f"/projects/{project_id}", json=body)).status_code == 200

    async def save(self, base: dict, edited: dict, project_id: str = "P-1001") -> httpx.Response:
        strip = lambda p: {k: p[k] for k in ("name", "sector", "country", "stage", "key_dates")}  # noqa: E731
        return await self.api.patch(f"/api/projects/{project_id}", json={"base": strip(base), "edited": strip(edited)})


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(service, "BACKOFF_SECONDS", 0)


@pytest.fixture
async def env(monkeypatch):
    monkeypatch.setenv("UPSTREAM_SLOW_RATE", "0")
    monkeypatch.setenv("UPSTREAM_TIMEOUT_RATE", "0.5")
    rng = ScriptedRng()
    upstream_app = create_upstream_app(rng=rng)
    upstream_transport = httpx.ASGITransport(app=upstream_app)
    upstream_http = httpx.AsyncClient(transport=upstream_transport, base_url="http://upstream", headers=UPSTREAM_HEADERS)
    direct = httpx.AsyncClient(transport=upstream_transport, base_url="http://upstream", headers=UPSTREAM_HEADERS)
    backend = create_app(upstream_http=upstream_http)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend), base_url="http://backend") as api:
        yield Env(api=api, direct=direct, rng=rng)
    await upstream_http.aclose()
    await direct.aclose()
