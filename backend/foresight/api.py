from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api_routes import router
from .runtime import ForesightRuntime


LOCAL_ORIGINS = [
    "http://localhost:4173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://127.0.0.1:5173",
]


def create_app(
    runtime: ForesightRuntime | None = None,
    *,
    workdir: Path | str = ".foresight",
    datasets_dir: Path | str = "datasets",
) -> FastAPI:
    """Build an isolated API application around an injected runtime."""

    load_dotenv(Path(".env"), override=False)
    application = FastAPI(
        title="Foresight Compass API",
        version="1.0.0",
        description="Evidence-grounded multi-agent market intelligence runtime",
    )
    application.state.runtime = runtime or ForesightRuntime(workdir, datasets_dir=datasets_dir)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    return application


app = create_app()


__all__ = ["app", "create_app"]
