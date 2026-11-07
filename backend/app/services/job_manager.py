import uuid
import asyncio
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.research import (
    ResearchJob,
    ResearchEvent,
    ResearchSource,
    ResearchReport,
    ReportClaim,
)
from app.schemas.research import ResearchJobCreate
from app.agents.graph import create_research_graph
from app.agents.state import ResearchState

class ResearchJobManager:
    """Orchestrates job lifecycle, background multi-agent execution, and report persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, req: ResearchJobCreate) -> ResearchJob:
        job = ResearchJob(
            id=uuid.uuid4(),
            query=req.query,
            depth=req.depth,
            status="queued"
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        doc_ids = [str(did) for did in req.document_ids]
        asyncio.create_task(
            self._execute_workflow(
                job_id=job.id,
                query=req.query,
                depth=req.depth,
                enable_web=req.enable_web,
                enable_documents=req.enable_documents,
                document_ids=doc_ids,
            )
        )

        return job

    async def _execute_workflow(
        self,
        job_id: uuid.UUID,
        query: str,
        depth: str,
        enable_web: bool,
        enable_documents: bool,
        document_ids: List[str],
    ):
        """Asynchronously executes the 5-agent LangGraph workflow."""
        async with AsyncSessionLocal() as session:
            try:
                job = await session.get(ResearchJob, job_id)
                if not job:
                    return
                job.status = "processing"
                await session.commit()

                graph = create_research_graph(session)

                initial_state: ResearchState = {
                    "job_id": str(job_id),
                    "query": query,
                    "depth": depth,
                    "enable_web": enable_web,
                    "enable_documents": enable_documents,
                    "document_ids": document_ids,
                    "plan": None,
                    "web_evidence": [],
                    "document_evidence": [],
                    "normalized_evidence": [],
                    "fact_checked_claims": [],
                    "report": None,
                    "events": [],
                    "error": None,
                }

                final_state = await graph.ainvoke(initial_state)

                job = await session.get(ResearchJob, job_id)
                job.plan = final_state.get("plan")
                job.status = "completed"

                # 1. Persist milestone events
                for ev in final_state.get("events", []):
                    event_row = ResearchEvent(
                        id=uuid.uuid4(),
                        job_id=job_id,
                        agent_name=ev.get("agent_name", "System"),
                        event_type=ev.get("event_type", "milestone"),
                        message=ev.get("message", ""),
                        payload=ev.get("payload"),
                    )
                    session.add(event_row)

                # 2. Persist sources
                for ev_item in final_state.get("normalized_evidence", []):
                    doc_uuid = None
                    if ev_item.get("document_id"):
                        try:
                            doc_uuid = uuid.UUID(ev_item["document_id"])
                        except ValueError:
                            pass

                    source_row = ResearchSource(
                        id=uuid.uuid4(),
                        job_id=job_id,
                        source_type=ev_item.get("source_type", "web"),
                        title=ev_item.get("title", ""),
                        url=ev_item.get("url"),
                        document_id=doc_uuid,
                        page_number=ev_item.get("page_number"),
                        snippet=ev_item.get("content", "")[:1000],
                    )
                    session.add(source_row)

                # 3. Persist Final Research Report and Claims
                report_data = final_state.get("report")
                if report_data:
                    report_id = uuid.uuid4()
                    report_row = ResearchReport(
                        id=report_id,
                        job_id=job_id,
                        title=report_data.get("title", "Research Report"),
                        executive_summary=report_data.get("executive_summary", ""),
                        content=report_data,
                    )
                    session.add(report_row)

                    for claim_item in report_data.get("claims", []):
                        claim_row = ReportClaim(
                            id=uuid.uuid4(),
                            report_id=report_id,
                            claim_text=claim_item.get("claim_text", ""),
                            verification_status=claim_item.get("verification_status", "supported"),
                            confidence_score=claim_item.get("confidence_score"),
                            evidence_quote=claim_item.get("evidence_quote"),
                            citation_source=claim_item.get("citation_source"),
                        )
                        session.add(claim_row)

                await session.commit()

            except Exception as e:
                job = await session.get(ResearchJob, job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    err_event = ResearchEvent(
                        id=uuid.uuid4(),
                        job_id=job_id,
                        agent_name="System / Provider",
                        event_type="error",
                        message=f"Workflow execution halted: {str(e)}",
                        payload={"error": str(e)},
                    )
                    session.add(err_event)
                    await session.commit()

    async def list_jobs(self) -> List[ResearchJob]:
        stmt = select(ResearchJob).order_by(ResearchJob.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_job(self, job_id: uuid.UUID) -> Optional[ResearchJob]:
        return await self.db.get(ResearchJob, job_id)

    async def get_job_events(self, job_id: uuid.UUID) -> List[ResearchEvent]:
        stmt = (
            select(ResearchEvent)
            .where(ResearchEvent.job_id == job_id)
            .order_by(ResearchEvent.created_at.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_job_report(self, job_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        stmt = (
            select(ResearchReport)
            .where(ResearchReport.job_id == job_id)
            .options(selectinload(ResearchReport.claims))
        )
        res = await self.db.execute(stmt)
        report_row = res.scalar_one_or_none()
        if not report_row:
            return None
        return report_row.content
