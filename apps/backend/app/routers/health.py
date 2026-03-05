"""Health check and status endpoints."""

from typing import Any

from fastapi import APIRouter, Depends

from app.database import db
from app.dependencies import get_current_user
from app.llm import check_llm_health, get_llm_config
from app.schemas import HealthResponse, StatusResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check endpoint (unauthenticated — used by Docker healthcheck)."""
    llm_status = await check_llm_health()

    return HealthResponse(
        status="healthy" if llm_status["healthy"] else "degraded",
        llm=llm_status,
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(current_user: dict[str, Any] = Depends(get_current_user)) -> StatusResponse:
    """Get per-user application status.

    Returns:
        - LLM configuration status (uses this user's provider/key)
        - Master resume existence (scoped to this user)
        - Database statistics (scoped to this user)
    """
    user_id: str = current_user["user_id"]
    config = get_llm_config()
    # Check config only — no live LLM call here to keep the endpoint fast.
    # Full LLM health check (with actual API call) is available via GET /config/llm.
    llm_configured = bool(config.api_key) or config.provider == "ollama"
    db_stats = db.get_stats(user_id)

    return StatusResponse(
        status="ready" if llm_configured and db_stats["has_master_resume"] else "setup_required",
        llm_configured=llm_configured,
        llm_healthy=llm_configured,
        has_master_resume=db_stats["has_master_resume"],
        database_stats=db_stats,
    )
