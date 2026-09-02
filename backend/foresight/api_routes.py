from __future__ import annotations

import asyncio
import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .api_dependencies import get_runtime, require_admin_access
from .data import MockDataProvider
from .models import ProviderReloadRequest, ResearchRequest, ReviewRequest, ValidationResultRequest
from .runtime import ForesightRuntime, UnsupportedResearchModeError


router = APIRouter(prefix="/api/v1")
RuntimeDep = Annotated[ForesightRuntime, Depends(get_runtime)]
AdminDep = Annotated[None, Depends(require_admin_access)]


@router.get("/health")
async def health(runtime: RuntimeDep) -> dict:
    skill_counts = runtime.skills.status_counts()
    return {
        "status": "ok",
        "runtime": "multi-agent",
        "harness": runtime.harness.runtime_version,
        "policy_version": runtime.evolution.active_policy()["version"],
        "extension_count": len(runtime.harness.plugins.list()),
        "skill_count": skill_counts["total"],
        "active_skills": skill_counts["active"],
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


@router.get("/monitoring")
async def monitoring_snapshot(
    runtime: RuntimeDep,
    category: str = "pet feeder",
    market: str = "BR",
) -> dict:
    try:
        return runtime.monitoring_snapshot(category, market)
    except (UnsupportedResearchModeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/runtime/extensions")
async def runtime_extensions(runtime: RuntimeDep) -> dict:
    return runtime.extension_status()


@router.post("/runtime/providers/mock/reload")
async def reload_mock_provider(
    request: ProviderReloadRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
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


@router.post("/research", status_code=202)
async def create_research(request: ResearchRequest, runtime: RuntimeDep) -> dict:
    try:
        task_id = runtime.create_task(request)
    except UnsupportedResearchModeError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return {
        "task_id": task_id,
        "status": "running",
        "events_url": f"/api/v1/research/{task_id}/events",
    }


@router.get("/research/{task_id}")
async def research_status(task_id: str, runtime: RuntimeDep) -> dict:
    try:
        status = runtime.status(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    result = runtime.get_result(task_id)
    return {**status, "result": result.model_dump(mode="json") if result else None}


@router.get("/research/{task_id}/events")
async def research_events(task_id: str, runtime: RuntimeDep) -> StreamingResponse:
    if not runtime.has_event_stream(task_id):
        raise HTTPException(status_code=404, detail="Task not found")

    async def stream():
        try:
            async for event in runtime.events(task_id):
                data = json.dumps(event.as_dict(), ensure_ascii=False)
                yield f"event: {event.event_type.value}\ndata: {data}\n\n"
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/research/{task_id}/checkpoint")
async def research_checkpoint(task_id: str, runtime: RuntimeDep) -> dict:
    checkpoint = runtime.load_checkpoint(task_id)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint


@router.get("/research/{task_id}/run-events")
async def research_run_events(task_id: str, runtime: RuntimeDep) -> dict:
    try:
        events = runtime.run_events(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    return {"task_id": task_id, "events": events}


@router.get("/research/{task_id}/component-snapshot")
async def research_component_snapshot(task_id: str, runtime: RuntimeDep) -> dict:
    try:
        return runtime.component_snapshot(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.post("/research/{task_id}/cancel")
async def cancel_research(task_id: str, runtime: RuntimeDep, _admin: AdminDep) -> dict:
    try:
        runtime.cancel_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    return {"task_id": task_id, "status": "cancel_requested"}


@router.post("/research/{task_id}/resume", status_code=202)
async def resume_research(task_id: str, runtime: RuntimeDep, _admin: AdminDep) -> dict:
    try:
        runtime.resume_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task_id, "status": "running", "resumed": True}


@router.post("/cards/{card_id}/review")
async def review_card(
    card_id: str,
    review: ReviewRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        feedback = runtime.review_card(card_id, review)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Card not found") from exc
    return feedback.model_dump(mode="json")


@router.post("/contracts/{task_id}/validate-result", status_code=200)
async def submit_validation_result(
    task_id: str,
    result: ValidationResultRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        contract = runtime.submit_validation_result(task_id, result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return contract.model_dump(mode="json")


@router.get("/evolution")
async def evolution_status(runtime: RuntimeDep) -> dict:
    status = runtime.evolution.status()
    status["skills"] = runtime.skills.status()
    return status


@router.post("/evolution/candidates", status_code=201)
async def create_evolution_candidate(runtime: RuntimeDep, _admin: AdminDep) -> dict:
    try:
        return runtime.evolution.generate_candidate()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/evolution/policies/{version}/activate")
async def activate_evolution_policy(
    version: str,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        return runtime.evolution.activate(version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Policy version not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/evolution/rollback")
async def rollback_evolution_policy(runtime: RuntimeDep, _admin: AdminDep) -> dict:
    try:
        return runtime.evolution.rollback()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Skill Bank routes
# ---------------------------------------------------------------------------


@router.get("/skills")
async def skill_list(runtime: RuntimeDep) -> dict:
    return runtime.skills.status()


@router.get("/skills/retrieve")
async def skill_retrieve(
    runtime: RuntimeDep,
    category: str = "pet feeder",
    market: str = "BR",
) -> list[dict]:
    return runtime.skills.retrieve_for_research(category, market)


@router.post("/skills/{skill_id}/evaluate", status_code=201)
async def evaluate_skill(
    skill_id: str,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        return runtime.skills.evaluate_candidate(skill_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/skills/{skill_id}/promote")
async def promote_skill(
    skill_id: str,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        skill = runtime.skills.promote(skill_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Skill not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return skill.model_dump(mode="json")


@router.post("/skills/{name}/rollback")
async def rollback_skill(
    name: str,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        skill = runtime.skills.rollback_skill(name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return skill.model_dump(mode="json")
