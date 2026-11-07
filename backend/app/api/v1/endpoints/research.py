import uuid
import json
import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, AsyncSessionLocal
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
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a new multi-agent research inquiry.
    Triggers the LangGraph orchestration engine with Planner, Web, Document, Fact Checker, and Report Writer agents.
    """
    manager = ResearchJobManager(db)
    job = await manager.create_job(request)
    return job

@router.get("/jobs", response_model=List[ResearchJobResponse])
async def list_research_jobs(
    db: AsyncSession = Depends(get_db),
):
    """Lists research jobs with status and timestamp."""
    manager = ResearchJobManager(db)
    return await manager.list_jobs()

@router.get("/jobs/{job_id}", response_model=ResearchJobResponse)
async def get_research_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves status and structured research plan for a specific job."""
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )
    return job

@router.get("/jobs/{job_id}/events", response_model=List[ResearchEventResponse])
async def get_job_events(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Returns milestone events emitted by agents during execution."""
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )
    return await manager.get_job_events(job_id)

@router.get("/jobs/{job_id}/report", response_model=ResearchReportSchema)
async def get_job_report(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves the completed structured research report with citations and fact-checked claims."""
    manager = ResearchJobManager(db)
    report_data = await manager.get_job_report(job_id)
    if not report_data:
        job = await manager.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Research job with ID {job_id} not found."
            )
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
    db: AsyncSession = Depends(get_db),
):
    """
    Renders and streams the completed research report as an institutional-grade PDF document.
    """
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )
    report_data = await manager.get_job_report(job_id)
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
):
    """
    Server-Sent Events (SSE) streaming endpoint.
    Emits live agent milestone updates until job completion or failure.
    """
    async def event_generator():
        last_event_count = 0
        while True:
            async with AsyncSessionLocal() as session:
                manager = ResearchJobManager(session)
                job = await manager.get_job(job_id)
                if not job:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                events = await manager.get_job_events(job_id)

                # Emit any new events
                if len(events) > last_event_count:
                    for ev in events[last_event_count:]:
                        payload = {
                            "type": "agent_event",
                            "agent_name": ev.agent_name,
                            "event_type": ev.event_type,
                            "message": ev.message,
                            "timestamp": ev.created_at.isoformat(),
                            "job_status": job.status,
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                    last_event_count = len(events)

                if job.status in ["completed", "failed"]:
                    yield f"data: {json.dumps({'type': 'job_status', 'status': job.status})}\n\n"
                    break

            await asyncio.sleep(1.0)

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
    db: AsyncSession = Depends(get_db),
):
    """Deletes a research job and associated reports, claims, and events."""
    manager = ResearchJobManager(db)
    job = await manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job with ID {job_id} not found."
        )
    await db.delete(job)
    await db.commit()
    return None
