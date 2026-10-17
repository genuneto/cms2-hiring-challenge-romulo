"""HTTP surface for the browser. The browser only ever talks to this; it never sees the upstream or its API key."""

import dataclasses
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.merge import has_duplicate_labels
from app.models import (
    SECTORS,
    STAGES,
    ConflictOut,
    ConflictResponse,
    Editable,
    Options,
    Project,
    ProjectSummary,
    SaveRequest,
    SaveResponse,
)
from app.service import Conflicted, KeyedLocks, NotSaved, editable_of, save_project
from app.upstream import ProjectNotFound, UpstreamClient, UpstreamRejected, UpstreamUnavailable

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "http://127.0.0.1:8081")
UPSTREAM_API_KEY = os.environ.get("UPSTREAM_API_KEY", "local-dev-key")
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def to_project(record: dict) -> Project:
    return Project(id=record["id"], **editable_of(record))


def create_app(upstream_http: httpx.AsyncClient | None = None) -> FastAPI:
    owns_client = upstream_http is None
    http = upstream_http or httpx.AsyncClient(
        base_url=UPSTREAM_URL,
        headers={"X-Api-Key": UPSTREAM_API_KEY},
        timeout=httpx.Timeout(5.0, connect=2.0),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if owns_client:
            await http.aclose()

    app = FastAPI(title="Project editor backend", lifespan=lifespan)
    upstream = UpstreamClient(http)
    locks = KeyedLocks()

    @app.exception_handler(ProjectNotFound)
    async def _not_found(_: Request, exc: ProjectNotFound):
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "Project not found"})

    @app.exception_handler(UpstreamUnavailable)
    async def _unavailable(_: Request, exc: UpstreamUnavailable):
        return JSONResponse(status_code=503, content={"code": "upstream_unavailable", "message": f"Records service unavailable: {exc}"})

    @app.exception_handler(UpstreamRejected)
    async def _rejected(_: Request, exc: UpstreamRejected):
        return JSONResponse(status_code=502, content={"code": "upstream_rejected", "message": str(exc)})

    @app.exception_handler(NotSaved)
    async def _not_saved(_: Request, exc: NotSaved):
        code = "outcome_unknown" if exc.saved == "unknown" else "not_saved"
        return JSONResponse(status_code=503, content={"code": code, "saved": exc.saved, "message": exc.message})

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    @app.get("/api/options")
    async def options() -> Options:
        return Options(sectors=list(SECTORS), stages=list(STAGES))

    @app.get("/api/projects")
    async def list_projects() -> list[ProjectSummary]:
        records = await upstream.list_projects()
        return [
            ProjectSummary(
                id=r["id"], name=r["name"], sector=r["sector"], country=r["country"], stage=r["stage"], key_dates_count=len(r["key_dates"])
            )
            for r in records
        ]

    @app.get("/api/projects/{project_id}")
    async def get_project(project_id: str) -> Project:
        return to_project(await upstream.get_project(project_id))

    @app.patch(
        "/api/projects/{project_id}",
        responses={409: {"model": ConflictResponse}},
    )
    async def save(project_id: str, body: SaveRequest) -> SaveResponse:
        base = body.base.model_dump(mode="json")
        edited = body.edited.model_dump(mode="json")
        if has_duplicate_labels(edited["key_dates"]) and not has_duplicate_labels(base["key_dates"]):
            raise HTTPException(status_code=422, detail="Key date labels must be unique")

        outcome = await save_project(upstream, locks, project_id, base, edited)

        if isinstance(outcome, Conflicted):
            payload = ConflictResponse(
                current=to_project(outcome.current),
                conflicts=[ConflictOut(**dataclasses.asdict(c)) for c in outcome.conflicts],
                proposed=Editable(**outcome.proposed),
            )
            return JSONResponse(status_code=409, content=payload.model_dump(mode="json"))  # type: ignore[return-value]
        return SaveResponse(project=to_project(outcome.project), also_changed_by_others=outcome.incoming)

    if FRONTEND_DIST.is_dir():  # after `npm run build`, one process serves everything
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    return app


app = create_app()


def run() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
