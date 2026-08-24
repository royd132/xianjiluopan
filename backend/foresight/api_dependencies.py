from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException, Request

from .runtime import ForesightRuntime


def get_runtime(request: Request) -> ForesightRuntime:
    """Resolve the runtime owned by this FastAPI application."""

    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, ForesightRuntime):
        raise RuntimeError("Foresight runtime is not configured")
    return runtime


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
