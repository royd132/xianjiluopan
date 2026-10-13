from __future__ import annotations

import asyncio
import json
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .api_dependencies import get_runtime, require_admin_access
from .data import MockDataProvider
from .models import ActualOutcomeRequest, ContractAcknowledgementRequest, DecisionContract, ExecutionTaskCreateRequest, ExecutionTaskUpdateRequest, MonitoringSubscription, MonitoringSubscriptionRequest, OverrideRequest, ProviderReloadRequest, ResearchRequest, ReviewRequest, UnitEconomicsRequest, UnitEconomicsResponse, ValidationResultRequest
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
        "real_data": runtime.real_provider.data_status(),
        "calibration": runtime.calibration_summary(),
        "actual_outcomes": runtime.harness.memory.list_actual_outcomes(5),
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


@router.get("/monitoring/subscriptions")
async def list_monitoring_subscriptions(runtime: RuntimeDep, workspace_id: str = "default") -> dict:
    return {"items": runtime.list_monitoring_subscriptions(workspace_id)}


@router.post("/monitoring/subscriptions", response_model=MonitoringSubscription, status_code=201)
async def create_monitoring_subscription(
    request: MonitoringSubscriptionRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> MonitoringSubscription:
    try:
        return MonitoringSubscription.model_validate(runtime.create_monitoring_subscription(request))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/monitoring/subscriptions/{subscription_id}/check")
async def check_monitoring_subscription(subscription_id: str, runtime: RuntimeDep) -> dict:
    try:
        return runtime.check_monitoring_subscription(subscription_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Monitoring subscription not found") from exc
    except UnsupportedResearchModeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/monitoring/subscriptions/{subscription_id}", status_code=204)
async def delete_monitoring_subscription(subscription_id: str, runtime: RuntimeDep, _admin: AdminDep) -> None:
    if not runtime.delete_monitoring_subscription(subscription_id):
        raise HTTPException(status_code=404, detail="Monitoring subscription not found")


@router.get("/data/status")
async def data_status(runtime: RuntimeDep) -> dict:
    """Expose source readiness so the UI can explain live vs cached evidence."""

    return runtime.real_provider.data_status()


def _compute_unit_economics(request: UnitEconomicsRequest) -> UnitEconomicsResponse:
    base = request.product_cost + request.packaging_cost + request.domestic_shipping + request.international_shipping
    duties = base * request.duty_rate_pct / 100
    vat = (base + duties) * request.vat_rate_pct / 100
    fee_rate = (request.platform_fee_rate_pct + request.payment_fee_rate_pct) / 100
    return_rate = request.return_rate_pct / 100
    fees = request.selling_price * fee_rate
    return_reserve = request.selling_price * return_rate
    fixed_cost = base + duties + vat + request.ad_cost_per_order
    profit = request.selling_price - fixed_cost - fees - return_reserve
    margin = profit / request.selling_price * 100
    denominator = max(0.01, 1 - fee_rate - return_rate)
    break_even = (base + duties + vat + request.ad_cost_per_order) / denominator
    max_cpc = max(0.0, request.selling_price * (1 - request.target_margin_pct / 100 - fee_rate - return_rate) - (base + duties + vat))
    return UnitEconomicsResponse(
        landed_cost=round(base + duties + vat, 2),
        duties=round(duties, 2),
        vat=round(vat, 2),
        platform_and_payment_fees=round(fees, 2),
        return_reserve=round(return_reserve, 2),
        contribution_profit=round(profit, 2),
        contribution_margin_pct=round(margin, 2),
        break_even_price=round(break_even, 2),
        max_cpc_at_target_margin=round(max_cpc, 2),
    )


@router.post("/economics/calculate", response_model=UnitEconomicsResponse)
async def calculate_unit_economics(request: UnitEconomicsRequest) -> UnitEconomicsResponse:
    return _compute_unit_economics(request)


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


@router.get("/research")
async def research_history(
    runtime: RuntimeDep,
    workspace_id: str | None = None,
    limit: int = 50,
) -> dict:
    """List durable research runs for the decision history drawer."""

    runs = runtime.harness.runs.list_runs(workspace_id=workspace_id, limit=limit)
    return {
        "items": [
            {
                "task_id": item["task_id"],
                "status": item["status"],
                "trace_id": item["trace_id"],
                "started_at": item["started_at"],
                "updated_at": item["updated_at"],
                "error": item.get("error"),
                "request": item["request"],
                "result": item.get("result"),
            }
            for item in runs
        ],
    }


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


@router.post("/contracts/{task_id}/override", status_code=200)
async def override_contract(
    task_id: str,
    override: OverrideRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        contract = runtime.override_contract(task_id, override)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return contract.model_dump(mode="json")


@router.post("/contracts/{task_id}/acknowledge", status_code=200)
async def acknowledge_contract(
    task_id: str,
    request: ContractAcknowledgementRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        contract = runtime.acknowledge_contract(task_id, request.operator)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc
    return contract.model_dump(mode="json")


@router.patch("/contracts/{task_id}/tasks/{execution_task_id}", status_code=200)
async def update_execution_task(
    task_id: str,
    execution_task_id: str,
    request: ExecutionTaskUpdateRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        contract = runtime.update_execution_task(task_id, execution_task_id, request.status, request.owner)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Contract or execution task not found") from exc
    return contract.model_dump(mode="json")


@router.post("/contracts/{task_id}/tasks", response_model=DecisionContract, status_code=201)
async def create_execution_task(
    task_id: str,
    request: ExecutionTaskCreateRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        contract = runtime.create_execution_task(
            task_id, request.title, request.status, request.owner, request.due_at
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Contract or execution task not found") from exc
    return contract.model_dump(mode="json")


@router.post("/contracts/{task_id}/outcome", status_code=201)
async def record_actual_outcome(
    task_id: str,
    request: ActualOutcomeRequest,
    runtime: RuntimeDep,
    _admin: AdminDep,
) -> dict:
    try:
        return runtime.record_actual_outcome(task_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Contract not found") from exc


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


@router.post("/evolution/relax", status_code=201)
async def relax_evolution_policy(runtime: RuntimeDep, _admin: AdminDep) -> dict:
    candidate = runtime.evolution.generate_relaxation_candidate()
    if candidate is None:
        raise HTTPException(status_code=409, detail="Current policy is already at baseline or open failures exist")
    return candidate


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
