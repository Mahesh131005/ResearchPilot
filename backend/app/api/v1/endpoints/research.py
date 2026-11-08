import uuid
import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_active_user
from app.db.session import AsyncSessionLocal
from app.core.security import decode_token
from app.models.research import User, ResearchJob
from app.services.job_manager import ResearchJobManager
from app.schemas.research import (
    ResearchJobCreate,
    ResearchJobResponse,
    ResearchEventResponse,
)
from app.schemas.report import ResearchReportSchema

router = APIRouter(prefix="/research", tags=["research"])

@router.post("/jobs", response_model=ResearchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_research_job(
    request: ResearchJobCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Submits a new multi-agent research inquiry bound to the current user.
    Enforces atomic rate limiting, quotas, and concurrency restrictions.
    Supports idempotency via X-Idempotency-Key header or client_token.
    """
    if x_idempotency_key and not request.client_token:
        request.client_token = x_idempotency_key
    manager = ResearchJobManager(db)
    job = await manager.create_job(request, user_id=current_user.id)
    return job

@router.get("/jobs", response_model=List[ResearchJobResponse])
async def list_research_jobs(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists research jobs owned by the authenticated user."""
    manager = ResearchJobManager(db)
    return await manager.list_jobs(user_id=current_user.id)

@router.get("/jobs/{job_id}", response_model=ResearchJobResponse)
async def get_research_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves status and structured research plan for a specific job. Returns 404 if not found or unowned."""
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )
    return job

@router.get("/jobs/{job_id}/events", response_model=List[ResearchEventResponse])
async def get_job_events(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns milestone events emitted by agents for a job owned by the user. Returns 404 if unowned."""
    manager = ResearchJobManager(db)
    events = await manager.get_job_events(job_id, user_id=current_user.id)
    if events is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )
    return events

@router.get("/jobs/{job_id}/report", response_model=ResearchReportSchema)
async def get_job_report(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves the completed structured research report with citations and fact-checked claims. Returns 404 if unowned."""
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )

    report_data = await manager.get_job_report(job_id, user_id=current_user.id)
    if not report_data:
        if job.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Research job failed: {job.error_message}"
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report generation is still processing or evidence was not compiled."
        )
    return report_data

@router.get("/jobs/{job_id}/pdf")
async def download_job_report_pdf(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Renders and streams the completed research report as an institutional-grade PDF document.
    Enforces ownership check.
    """
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )

    report_data = await manager.get_job_report(job_id, user_id=current_user.id)
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report has not been generated for this research job yet."
        )

    from app.services.pdf_generator import PDFReportGenerator
    generator = PDFReportGenerator()
    pdf_bytes = generator.build_report_pdf(
        report=report_data,
        job={"id": str(job.id), "query": job.query, "depth": job.depth}
    )

    filename = f"ResearchReport-{str(job_id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(
    job_id: uuid.UUID,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Emits live agent milestone updates until job completion or failure.
    Supports Bearer token via Authorization header or ?token= query parameter.
    """
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ", 1)[1]
    elif token:
        raw_token = token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for SSE stream"
        )

    payload = decode_token(raw_token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )

    user_id_str = payload.get("sub")
    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identity in token"
        )

    # Initial check that job exists and is owned by user
    async with AsyncSessionLocal() as init_session:
        manager = ResearchJobManager(init_session)
        job = await manager.get_job(job_id, user_id=user_uuid)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research job with ID {job_id} not found."
            )

    async def event_generator():
        last_event_count = 0
        heartbeat_counter = 0
        while True:
            async with AsyncSessionLocal() as session:
                manager = ResearchJobManager(session)
                job = await manager.get_job(job_id, user_id=user_uuid)
                if not job:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                events = await manager.get_job_events(job_id, user_id=user_uuid)
                events = events or []

                # Emit any new events
                if len(events) > last_event_count:
                    for ev in events[last_event_count:]:
                        ev_payload = {
                            "type": "agent_event",
                            "agent_name": ev.agent_name,
                            "event_type": ev.event_type,
                            "message": ev.message,
                            "timestamp": ev.created_at.isoformat(),
                            "job_status": job.status,
                        }
                        yield f"data: {json.dumps(ev_payload)}\n\n"
                    last_event_count = len(events)
                    heartbeat_counter = 0

                if job.status in ["completed", "failed"]:
                    yield f"data: {json.dumps({'type': 'job_status', 'status': job.status})}\n\n"
                    break

            await asyncio.sleep(1.0)
            heartbeat_counter += 1
            # Send periodic SSE comment keepalive every 15s to prevent cloud proxy timeouts (Render 100s idle limit)
            if heartbeat_counter >= 15:
                yield ": keepalive\n\n"
                heartbeat_counter = 0

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a research job owned by the user. Returns 404 if not found or unowned."""
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id, user_id=current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )
    await db.delete(job)
    await db.commit()
    return None
