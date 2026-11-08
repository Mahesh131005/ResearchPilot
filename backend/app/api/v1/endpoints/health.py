import os
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Liveness probe: verifies process responsiveness and basic DB ping."""
    db_status = "unreachable"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        version="1.0.0"
    )

@router.get("/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe: validates end-to-end service readiness for traffic routing:
    - Database connection pool health
    - Local disk storage write capability for document uploads
    - Emergency billable operations switch state
    Returns HTTP 200 when ready, HTTP 503 when degraded or unready.
    """
    db_connected = False
    db_error = None
    try:
        await db.execute(text("SELECT 1"))
        db_connected = True
    except Exception as e:
        db_connected = False
        db_error = str(e)

    # Verify upload directory write access
    disk_writable = False
    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        test_file = os.path.join(settings.UPLOAD_DIR, ".readiness_probe.tmp")
        with open(test_file, "w") as f:
            f.write("probe")
        if os.path.exists(test_file):
            os.remove(test_file)
            disk_writable = True
    except Exception:
        disk_writable = False

    is_ready = db_connected and disk_writable

    checks = {
        "database": "connected" if db_connected else f"unreachable: {db_error}",
        "disk_storage": "writable" if disk_writable else "read_only_or_inaccessible",
        "billable_operations": "enabled" if settings.BILLABLE_OPERATIONS_ENABLED else "paused_by_policy",
        "provider_mode": settings.PROVIDER_MODE,
    }

    if is_ready:
        return {
            "status": "ready",
            "checks": checks,
            "version": "1.0.0",
        }

    return JSONResponse(
        status_code=503,
        content={
            "status": "unready",
            "checks": checks,
            "detail": "One or more critical service dependencies are degraded.",
            "version": "1.0.0",
        },
    )

