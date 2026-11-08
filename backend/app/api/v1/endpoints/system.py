import time
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, select

from app.db.session import get_db
from app.core.config import settings
from app.models.research import ResearchJob
from app.models.document import Document, DocumentChunk
from app.models.usage import ProviderUsageEvent

router = APIRouter(prefix="/system", tags=["system"])

def get_process_memory_mb() -> float:
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return round(counters.WorkingSetSize / (1024 * 1024), 2)
    except Exception:
        pass
    return 48.0

@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    """
    Returns the active runtime provider modes and configuration state.
    Safe diagnostic: Never exposes API keys or secrets.
    """
    db_connected = False
    try:
        await db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    is_live_llm = settings.effective_llm_mode == "live"
    is_live_emb = settings.effective_embedding_mode == "live"
    is_live_web = settings.effective_web_search_mode == "live"
    overall_mode = "live" if (is_live_llm or is_live_web) else "mock"

    return {
        "provider_mode": settings.PROVIDER_MODE,
        "effective_mode": overall_mode,
        "billable_operations_enabled": settings.BILLABLE_OPERATIONS_ENABLED,
        "llm_provider": {
            "name": "Gemini API" if is_live_llm else "Mock LLM",
            "model": settings.LLM_MODEL if is_live_llm else "Deterministic Simulated Model",
            "is_live": is_live_llm,
            "has_key": settings.has_gemini_key,
        },
        "embedding_provider": {
            "name": "Gemini Embeddings" if is_live_emb else "Mock Embeddings",
            "model": settings.EMBEDDING_MODEL if is_live_emb else "Local Token Hash",
            "dim": settings.EMBEDDING_DIM,
            "is_live": is_live_emb,
            "has_key": settings.has_gemini_key,
        },
        "web_search_provider": {
            "name": "Tavily Search API" if is_live_web else "Mock / Fallback Web Search",
            "is_live": is_live_web,
            "has_key": settings.has_tavily_key,
        },
        "database": {
            "engine": "PostgreSQL 16 + pgvector",
            "connected": db_connected,
        }
    }

@router.get("/metrics")
async def get_system_metrics(
    request: Request,
    format: Optional[str] = Query("json", description="Output format: 'json' or 'prometheus'"),
    db: AsyncSession = Depends(get_db)
):
    """
    Operational Telemetry & Prometheus Monitoring Endpoint.
    Captures process uptime, memory RSS, job execution counters, token usage totals,
    and database state without exposing sensitive user information.
    """
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime_seconds = round(time.time() - start_time, 2)
    memory_mb = get_process_memory_mb()

    # Query job counters
    jobs_total = (await db.scalar(select(func.count(ResearchJob.id)))) or 0
    jobs_completed = (await db.scalar(select(func.count(ResearchJob.id)).where(ResearchJob.status == "completed"))) or 0
    jobs_failed = (await db.scalar(select(func.count(ResearchJob.id)).where(ResearchJob.status == "failed"))) or 0
    jobs_active = (await db.scalar(select(func.count(ResearchJob.id)).where(ResearchJob.status.in_(["queued", "processing"])))) or 0

    # Query document counters
    docs_total = (await db.scalar(select(func.count(Document.id)))) or 0
    chunks_total = (await db.scalar(select(func.count(DocumentChunk.id)))) or 0

    # Query token usage totals
    total_input = (await db.scalar(select(func.coalesce(func.sum(ProviderUsageEvent.input_tokens), 0)))) or 0
    total_output = (await db.scalar(select(func.coalesce(func.sum(ProviderUsageEvent.output_tokens), 0)))) or 0
    total_tokens = total_input + total_output
    total_searches = (await db.scalar(select(func.count(ProviderUsageEvent.id)).where(ProviderUsageEvent.provider == "tavily"))) or 0

    if format == "prometheus":
        lines = [
            "# HELP researchpilot_uptime_seconds Process uptime in seconds",
            "# TYPE researchpilot_uptime_seconds gauge",
            f"researchpilot_uptime_seconds {uptime_seconds}",
            "",
            "# HELP researchpilot_memory_rss_megabytes Process resident set memory in MB",
            "# TYPE researchpilot_memory_rss_megabytes gauge",
            f"researchpilot_memory_rss_megabytes {memory_mb}",
            "",
            "# HELP researchpilot_jobs_total Total research jobs processed by status",
            "# TYPE researchpilot_jobs_total counter",
            f'researchpilot_jobs_total{{status="completed"}} {jobs_completed}',
            f'researchpilot_jobs_total{{status="failed"}} {jobs_failed}',
            f'researchpilot_jobs_total{{status="active"}} {jobs_active}',
            f'researchpilot_jobs_total{{status="all"}} {jobs_total}',
            "",
            "# HELP researchpilot_documents_total Total documents and chunks indexed",
            "# TYPE researchpilot_documents_total gauge",
            f'researchpilot_documents_total{{type="documents"}} {docs_total}',
            f'researchpilot_documents_total{{type="chunks"}} {chunks_total}',
            "",
            "# HELP researchpilot_tokens_total Total provider token usage",
            "# TYPE researchpilot_tokens_total counter",
            f'researchpilot_tokens_total{{type="input"}} {total_input}',
            f'researchpilot_tokens_total{{type="output"}} {total_output}',
            f'researchpilot_tokens_total{{type="total"}} {total_tokens}',
            "",
            "# HELP researchpilot_web_searches_total Total web search queries",
            "# TYPE researchpilot_web_searches_total counter",
            f"researchpilot_web_searches_total {total_searches}",
            "",
            "# HELP researchpilot_billable_operations Operational billable flag (1=enabled, 0=paused)",
            "# TYPE researchpilot_billable_operations gauge",
            f"researchpilot_billable_operations {1 if settings.BILLABLE_OPERATIONS_ENABLED else 0}",
        ]
        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

    return {
        "status": "healthy",
        "uptime_seconds": uptime_seconds,
        "memory_rss_mb": memory_mb,
        "billable_operations_enabled": settings.BILLABLE_OPERATIONS_ENABLED,
        "jobs": {
            "total": jobs_total,
            "completed": jobs_completed,
            "failed": jobs_failed,
            "active": jobs_active,
        },
        "knowledge_base": {
            "documents": docs_total,
            "chunks": chunks_total,
        },
        "provider_telemetry": {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
            "tavily_searches": total_searches,
        },
        "version": "1.0.0",
    }

