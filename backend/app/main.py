import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.core.config import settings
from app.api.v1.router import api_router

# Set up logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("researchpilot")

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = time.time()
    logger.info("Initializing ResearchPilot backend (Production Readiness Active)...")
    logger.info("Database target (credentials omitted): async=%s, sync=%s", settings.safe_db_summary, settings.safe_sync_db_summary)

    # Clean up any orphaned jobs left in queued/processing from a previous crash/restart
    try:
        from app.db.session import AsyncSessionLocal
        from app.models.research import ResearchJob
        from sqlalchemy import update
        async with AsyncSessionLocal() as session:
            stmt = (
                update(ResearchJob)
                .where(ResearchJob.status.in_(["queued", "processing"]))
                .values(
                    status="failed",
                    error_message="Job was interrupted due to a backend container restart or cold start."
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount > 0:
                logger.info("Cleaned up %d orphaned in-flight research jobs on startup.", result.rowcount)
    except Exception as e:
        logger.warning("Could not clean up orphaned jobs on startup: %s", e)

    yield
    logger.info("Graceful shutdown initiated. Releasing resources...")

app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-Agent AI Research Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Headers & Request Body Size Middleware
@app.middleware("http")
async def security_and_size_middleware(request: Request, call_next):
    # Enforce request payload size limit (30MB default)
    max_bytes = settings.MAX_REQUEST_BODY_SIZE_MB * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            length = int(content_length)
            if length > max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request payload ({length} bytes) exceeds maximum allowed size of {settings.MAX_REQUEST_BODY_SIZE_MB}MB."
                    },
                )
        except ValueError:
            pass
    elif request.method in ("POST", "PUT", "PATCH"):
        # Handle chunked transfer or payloads without declared Content-Length
        total_bytes = 0
        chunks = []
        async for chunk in request.stream():
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request payload exceeds maximum allowed size of {settings.MAX_REQUEST_BODY_SIZE_MB}MB."
                    },
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)

    response = await call_next(request)

    # Attach standard OWASP security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), microphone=(), geolocation=()"

    return response

# HTTP Exception Handler (Preserves specific status codes and details)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception at {request.url.path}: {str(exc)}", exc_info=True)
    detail = "An unexpected server error occurred. Please try again later."
    if settings.DEBUG:
        detail = f"Local Server Error ({type(exc).__name__}): {str(exc)}"
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
    )

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {
        "message": "Welcome to ResearchPilot API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }

