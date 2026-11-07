from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["system"])

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

