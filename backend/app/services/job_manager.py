import uuid
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.research import (
    User,
    ResearchJob,
    ResearchEvent,
    ResearchSource,
    ResearchReport,
    ReportClaim,
)
from app.models.document import Document
from app.schemas.research import ResearchJobCreate
from app.agents.graph import create_research_graph
from app.agents.state import ResearchState
from app.services.quota_service import QuotaService
from app.services.usage_service import UsageService
from app.services.billing_service import BillingService
from app.core.usage_context import set_usage_context, clear_usage_context
from app.core.config import settings

class ResearchJobManager:
    """Orchestrates job lifecycle, background multi-agent execution, and report persistence."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, req: ResearchJobCreate, user_id: Optional[uuid.UUID] = None) -> ResearchJob:
        if not settings.BILLABLE_OPERATIONS_ENABLED and settings.effective_llm_mode == "live":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Live billable operations are temporarily suspended by administrator "
                    "(BILLABLE_OPERATIONS_ENABLED=False). Historical reports, documents, and mock mode remain fully accessible."
                ),
            )

        reserved_budget = None
        if user_id:
            user = await self.db.get(User, user_id)
            if user:
                is_retry, existing_job = await QuotaService.check_and_reserve_job(
                    self.db, user, client_token=req.client_token
                )
                if is_retry and existing_job:
                    return existing_job

                # Atomically reserve monetary budget for the research job
                reserved_budget = await BillingService.reserve_job_budget(
                    self.db, user, client_token=req.client_token
                )

        if req.document_ids and user_id:
            # Verify ownership of requested documents; return 404 to avoid enumeration
            doc_stmt = select(Document.id).where(
                Document.id.in_(req.document_ids),
                Document.user_id == user_id
            )
            doc_res = await self.db.execute(doc_stmt)
            found_ids = set(doc_res.scalars().all())
            for did in req.document_ids:
                if did not in found_ids:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document with ID {did} not found."
                    )

        job = ResearchJob(
            id=uuid.uuid4(),
            user_id=user_id,
            client_token=req.client_token,
            query=req.query,
            depth=req.depth,
            status="queued",
            budget_reserved_usd=reserved_budget,
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
            job = await session.get(ResearchJob, job_id)
            if not job:
                return

            tok = set_usage_context(user_id=job.user_id, job_id=job.id, client_token=job.client_token)
            try:
                job.status = "processing"
                await session.commit()

                # Determine per-job Tavily limits from user's tier
                max_tavily = 5
                if job.user_id:
                    user = await session.get(User, job.user_id)
                    if user:
                        limits = await UsageService.get_user_limits(session, user)
                        max_tavily = limits.tavily_searches_per_job_limit

                graph = create_research_graph(session)

                initial_state: ResearchState = {
                    "job_id": str(job_id),
                    "user_id": str(job.user_id) if job.user_id else None,
                    "query": query,
                    "depth": depth,
                    "enable_web": enable_web,
                    "enable_documents": enable_documents,
                    "document_ids": document_ids,
                    "max_tavily_searches": max_tavily,
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
            finally:
                if job and job.user_id:
                    try:
                        await BillingService.reconcile_job_cost(
                            session, job_id=job.id, user_id=job.user_id
                        )
                    except Exception as b_err:
                        # Log error without masking workflow outcome
                        print(f"Warning: billing reconciliation failed for job {job_id}: {b_err}")
                clear_usage_context(tok)

    async def list_jobs(self, user_id: Optional[uuid.UUID] = None) -> List[ResearchJob]:
        stmt = select(ResearchJob)
        if user_id:
            stmt = stmt.where(ResearchJob.user_id == user_id)
        stmt = stmt.order_by(ResearchJob.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_job(self, job_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[ResearchJob]:
        job = await self.db.get(ResearchJob, job_id)
        if not job:
            return None
        if user_id and job.user_id != user_id:
            return None
        return job

    async def get_job_events(self, job_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[List[ResearchEvent]]:
        job = await self.get_job(job_id, user_id=user_id)
        if not job:
            return None

        stmt = (
            select(ResearchEvent)
            .where(ResearchEvent.job_id == job_id)
            .order_by(ResearchEvent.created_at.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_job_report(self, job_id: uuid.UUID, user_id: Optional[uuid.UUID] = None) -> Optional[Dict[str, Any]]:
        job = await self.get_job(job_id, user_id=user_id)
        if not job:
            return None

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
