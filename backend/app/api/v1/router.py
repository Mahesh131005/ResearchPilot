from fastapi import APIRouter
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.qa import router as qa_router
from app.api.v1.endpoints.research import router as research_router
from app.api.v1.endpoints.system import router as system_router
from app.api.v1.endpoints.usage import router as usage_router
from app.api.v1.endpoints.billing import router as billing_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(documents_router)
api_router.include_router(qa_router)
api_router.include_router(research_router)
api_router.include_router(usage_router)
api_router.include_router(billing_router)


