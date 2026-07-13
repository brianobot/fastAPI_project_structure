from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.redis_manager import redis_manager

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]):
    """Liveness/readiness probe: 200 only when the DB and Redis are reachable."""
    checks = {"database": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        checks["database"] = "error"

    try:
        await redis_manager.redis_client.ping()
    except Exception:
        checks["redis"] = "error"

    if any(status != "ok" for status in checks.values()):
        raise HTTPException(status_code=503, detail=checks)

    return {"status": "ok", "checks": checks}
