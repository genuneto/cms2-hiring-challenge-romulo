"""The only module that talks to the upstream records API, and the only one that knows its habits.

Habits handled here:
    slow GET        (~1 in 10 takes ~2s)  -> 5s timeout, one retry. Reads are safe to repeat.
    504 on PUT      (write may or may not  -> raised as WriteOutcomeUnknown and NEVER retried blindly here.
                     have landed)             The caller re-reads and re-merges, which settles what happened.
    wide responses                         -> callers narrow them; see service.editable_of.
"""

import httpx

READ_ATTEMPTS = 2


class ProjectNotFound(Exception):
    pass


class UpstreamUnavailable(Exception):
    """A read failed (timeout, connection, 5xx, bad credentials). Nothing was written by this call."""


class UpstreamRejected(Exception):
    """Upstream answered 422/4xx to a write we built. That is a bug on our side, not a transient fault."""


class WriteOutcomeUnknown(Exception):
    """A PUT timed out or errored after we may have sent it. The write may have landed."""


class UpstreamClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def list_projects(self) -> list[dict]:
        return await self._get("/projects")

    async def get_project(self, project_id: str) -> dict:
        return await self._get(f"/projects/{project_id}")

    async def put_project(self, project_id: str, body: dict) -> dict:
        try:
            response = await self._client.put(f"/projects/{project_id}", json=body)
        except httpx.TransportError as exc:
            raise WriteOutcomeUnknown(str(exc) or type(exc).__name__) from exc
        if response.status_code == 404:
            raise ProjectNotFound(project_id)
        if response.status_code >= 500:
            raise WriteOutcomeUnknown(f"upstream answered {response.status_code}")
        if response.status_code >= 400:
            raise UpstreamRejected(f"upstream answered {response.status_code}: {response.text[:200]}")
        return response.json()

    async def _get(self, path: str):
        last = "no attempt made"
        for _ in range(READ_ATTEMPTS):
            try:
                response = await self._client.get(path)
            except httpx.TransportError as exc:
                last = str(exc) or type(exc).__name__
                continue
            if response.status_code == 404:
                raise ProjectNotFound(path)
            if response.status_code >= 500:
                last = f"upstream answered {response.status_code}"
                continue
            if response.status_code >= 400:
                raise UpstreamUnavailable(f"upstream answered {response.status_code}")
            return response.json()
        raise UpstreamUnavailable(last)
