"""AgentCo API server: health check + workspace APIs (projects, board, docs, chat)."""

import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from agentco import __version__
from agentco.workspace.api import router as workspace_router
from agentco.workspace.db import init_db, make_engine
from agentco.workspace.service import InvalidError, NotFoundError


async def check_llm() -> dict:
    """Ask the OpenAI-compatible endpoint which models it serves."""
    base_url = os.getenv("LLM_BASE_URL", "http://host.docker.internal:11434/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "")
    headers = {}
    if api_key := os.getenv("LLM_API_KEY"):
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{base_url}/models", headers=headers)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        return {"reachable": False, "base_url": base_url, "model": model, "error": str(exc)}

    available = {m["id"] for m in resp.json().get("data", [])}
    # Ollama lists "name:latest" for a model you refer to as just "name".
    names = {model, f"{model}:latest"} if ":" not in model else {model}
    return {
        "reachable": True,
        "base_url": base_url,
        "model": model,
        "model_available": bool(names & available),
    }


def create_app(engine: Engine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine or make_engine()
        init_db(app.state.engine)
        yield

    app = FastAPI(title="AgentCo", version=__version__, lifespan=lifespan)
    app.include_router(workspace_router)

    @app.exception_handler(NotFoundError)
    async def not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidError)
    async def invalid(_request: Request, exc: InvalidError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        # The service is healthy if it is up; LLM status is reported but does not
        # fail the check, so the stack still starts while a model is downloading.
        return {"status": "ok", "version": __version__, "llm": await check_llm()}

    return app


app = create_app()
