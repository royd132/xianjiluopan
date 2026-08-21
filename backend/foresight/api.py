from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import secrets
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

from .data import MockDataProvider
from .models import ProviderReloadRequest, ResearchRequest, ReviewRequest
from .runtime import ForesightRuntime, UnsupportedResearchModeError


load_dotenv(Path(".env"), override=False)


app = FastAPI(
    title="Foresight Compass API",
    version="1.0.0",
    description="Evidence-grounded multi-agent market intelligence runtime",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
runtime = ForesightRuntime(Path(".foresight"))


def require_admin_access(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> None:
    if os.getenv("FORESIGHT_DEMO_READ_ONLY", "").lower() in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=403, detail="This deployment is configured as read-only")
    configured_token = os.getenv("FORESIGHT_ADMIN_TOKEN")
    if configured_token and (
        x_admin_token is None or not secrets.compare_digest(x_admin_token, configured_token)
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid X-Admin-Token header is required",
        )


@app.get("/api/v1/health")
async def health() -> dict:
    return {
        "status": "ok",
        "runtime": "multi-agent",
        "harness": runtime.harness.runtime_version,
        "policy_version": runtime.evolution.active_policy()["version"],
        "extension_count": len(runtime.harness.plugins.list()),
        "supported_modes": sorted(runtime.supported_modes),
        "scenario_capabilities": runtime.scenario_capabilities(),
        "mutation_protection": (
            "read-only"
            if os.getenv("FORESIGHT_DEMO_READ_ONLY", "").lower() in {"1", "true", "yes", "on"}
            else "token"
            if os.getenv("FORESIGHT_ADMIN_TOKEN")
            else "local-demo-open"
        ),
        "mode": "offline-ready",
    }


@app.get("/api/v1/monitoring")
async def monitoring_snapshot(category: str = "pet feeder", market: str = "BR") -> dict:
    try:
        return runtime.monitoring_snapshot(category, market)
    except (UnsupportedResearchModeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/runtime/extensions")
async def runtime_extensions() -> dict:
    return runtime.extension_status()


@app.post("/api/v1/runtime/providers/mock/reload")
async def reload_mock_provider(
    request: ProviderReloadRequest,
    _admin: None = Depends(require_admin_access),
) -> dict:
    try:
        plugin = runtime.install_provider(MockDataProvider(), request.version)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "plugin": plugin,
        "activation": "new-tasks-only",
        "running_tasks_remain_pinned": True,
    }


@app.post("/api/v1/runtime/providers/mock/rollback")
async def rollback_mock_provider(_admin: None = Depends(require_admin_access)) -> dict:
    try:
        plugin = runtime.rollback_provider("global")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "plugin": plugin,
        "activation": "new-tasks-only",
        "running_tasks_remain_pinned": True,
    }


@app.post("/api/v1/research", status_code=202)
async def create_research(request: ResearchRequest) -> dict:
    try:
        task_id = runtime.create_task(request)
    except UnsupportedResearchModeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return {"task_id": task_id, "status": "running", "events_url": f"/api/v1/research/{task_id}/events"}


@app.get("/api/v1/research/{task_id}")
async def research_status(task_id: str) -> dict:
    try:
        status = runtime.status(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    result = runtime.get_result(task_id)
    return {**status, "result": result.model_dump(mode="json") if result else None}


@app.get("/api/v1/research/{task_id}/events")
async def research_events(task_id: str) -> StreamingResponse:
    if task_id not in runtime.boards:
        raise HTTPException(status_code=404, detail="Task not found")

    async def stream():
        try:
            async for event in runtime.events(task_id):
                yield f"event: {event.event_type.value}\ndata: {json.dumps(event.as_dict(), ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/v1/research/{task_id}/checkpoint")
async def research_checkpoint(task_id: str) -> dict:
    checkpoint = runtime.load_checkpoint(task_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint


@app.get("/api/v1/research/{task_id}/run-events")
async def research_run_events(task_id: str) -> dict:
    try:
        events = runtime.run_events(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    return {"task_id": task_id, "events": events}


@app.get("/api/v1/research/{task_id}/component-snapshot")
async def research_component_snapshot(task_id: str) -> dict:
    try:
        return runtime.component_snapshot(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@app.post("/api/v1/research/{task_id}/cancel")
async def cancel_research(
    task_id: str,
    _admin: None = Depends(require_admin_access),
) -> dict:
    try:
        runtime.cancel_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    return {"task_id": task_id, "status": "cancel_requested"}


@app.post("/api/v1/research/{task_id}/resume", status_code=202)
async def resume_research(
    task_id: str,
    _admin: None = Depends(require_admin_access),
) -> dict:
    try:
        runtime.resume_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task_id, "status": "running", "resumed": True}


@app.post("/api/v1/cards/{card_id}/review")
async def review_card(
    card_id: str,
    review: ReviewRequest,
    _admin: None = Depends(require_admin_access),
) -> dict:
    try:
        feedback = runtime.review_card(card_id, review)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Card not found") from exc
    return feedback.model_dump(mode="json")


@app.get("/api/v1/evolution")
async def evolution_status() -> dict:
    return runtime.evolution.status()


@app.post("/api/v1/evolution/candidates", status_code=201)
async def create_evolution_candidate(_admin: None = Depends(require_admin_access)) -> dict:
    try:
        return runtime.evolution.generate_candidate()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/evolution/policies/{version}/activate")
async def activate_evolution_policy(
    version: str,
    _admin: None = Depends(require_admin_access),
) -> dict:
    try:
        return runtime.evolution.activate(version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Policy version not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/v1/evolution/rollback")
async def rollback_evolution_policy(_admin: None = Depends(require_admin_access)) -> dict:
    try:
        return runtime.evolution.rollback()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
