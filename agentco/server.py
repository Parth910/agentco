"""AgentCo API server. For now it only exposes a health check; the workspace
APIs (board, docs, chat) are added in M3."""

import os

import httpx
from fastapi import FastAPI

from agentco import __version__

app = FastAPI(title="AgentCo", version=__version__)


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

    available = [m["id"] for m in resp.json().get("data", [])]
    return {
        "reachable": True,
        "base_url": base_url,
        "model": model,
        "model_available": model in available,
    }


@app.get("/health")
async def health() -> dict:
    # The service is healthy if it is up; LLM status is reported but does not
    # fail the check, so the stack still starts while a model is downloading.
    return {"status": "ok", "version": __version__, "llm": await check_llm()}
