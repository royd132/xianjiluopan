from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .models import ResearchRequest, ReviewRequest
from .runtime import ForesightRuntime


app = FastAPI(
    title="Foresight Compass API",
    version="1.0.0",
    description="Evidence-grounded multi-agent market intelligence runtime",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
runtime = ForesightRuntime(Path(".foresight"))


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "runtime": "multi-agent", "mode": "offline-ready"}


@app.post("/api/v1/research", status_code=202)
async def create_research(request: ResearchRequest) -> dict:
    task_id = runtime.create_task(request)
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


@app.post("/api/v1/cards/{card_id}/review")
async def review_card(card_id: str, review: ReviewRequest) -> dict:
    try:
        feedback = runtime.review_card(card_id, review)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Card not found") from exc
    return feedback.model_dump(mode="json")
