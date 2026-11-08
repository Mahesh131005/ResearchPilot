import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def get_safe_db_target(url: Optional[str]) -> Dict[str, Any]:
    """
    Safely inspects a database URL and returns target details (host, port, database, dialect)
    without ever exposing passwords, usernames, or credentials.
    """
    if not url or not str(url).strip():
        return {
            "configured": False,
            "dialect": "none",
            "host": "none",
            "port": 0,
            "database": "none",
            "safe_summary": "missing",
        }
    try:
        from urllib.parse import urlparse
        clean_url = str(url).strip()
        scheme = "unknown"
        rest = clean_url
        if "://" in clean_url:
            scheme, rest = clean_url.split("://", 1)
        
        parsed = urlparse(f"http://{rest}")
        host = parsed.hostname or "unknown"
        port = parsed.port or (5432 if "postgres" in scheme else 0)
        db = parsed.path.lstrip("/") or "unknown"
        return {
            "configured": True,
            "dialect": scheme,
            "host": host,
            "port": port,
            "database": db,
            "safe_summary": f"{scheme}://***:***@{host}:{port}/{db}",
        }
    except Exception as e:
        return {
            "configured": True,
            "dialect": "unknown",
            "host": "unparseable",
            "port": 0,
            "database": "unknown",
            "safe_summary": f"unparseable-url ({str(e)})",
        }

class Settings(BaseSettings):
    def __init__(self, *args, **kwargs):
        # In production, never load local development .env files from disk unless explicitly requested
        if os.environ.get("APP_ENV", "").lower() == "production" and "_env_file" not in kwargs:
            kwargs["_env_file"] = None
        super().__init__(*args, **kwargs)

    APP_NAME: str = "ResearchPilot"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres@localhost:5433/researchpilot"
    SYNC_DATABASE_URL: Optional[str] = None

    # Security & Authentication
    SECRET_KEY: str = "researchpilot-sec-key-e4b78912cf30a91672e817d98341b52a"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    INITIAL_ADMIN_EMAIL: str = "admin@researchpilot.local"
    INITIAL_ADMIN_PASSWORD: str = "ResearchPilot!Admin2026"

    # Ingestion & RAG
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120
    MAX_FILE_SIZE_MB: int = 25
    UPLOAD_DIR: str = str(BASE_DIR / "uploads")
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]
    TOP_K_RETRIEVAL: int = 5
    SIMILARITY_THRESHOLD: float = 0.35 # Minimum cosine similarity for relevance

    # Provider Configuration
    EMBEDDING_PROVIDER: str = "gemini"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"

    # External Provider Keys
    GEMINI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # Provider Mode: "auto", "mock", or "live"
    # - "auto": Uses live Gemini/Tavily if keys are configured; otherwise falls back cleanly to mock.
    # - "mock": Strictly runs in mock mode using simulated models and deterministic datasets.
    # - "live": Strictly requires valid API keys; raises an error if keys are absent or invalid.
    PROVIDER_MODE: str = "auto"

    # Emergency Spending Kill-Switch
    # When False, blocks live operations that could incur external API charges.
    BILLABLE_OPERATIONS_ENABLED: bool = True

    # Global Monetary Spending Ceilings & Monetization (Stage 6)
    GLOBAL_DAILY_BUDGET_USD: float = 50.0
    GLOBAL_MONTHLY_BUDGET_USD: float = 500.0
    DEFAULT_JOB_RESERVATION_USD: float = 0.05
    FREE_TIER_COMPLIMENTARY_BALANCE_USD: float = 1.00
    PRO_TIER_MONTHLY_BUDGET_USD: float = 25.00

    # Stripe Billing Configuration
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_MODE: str = "auto"  # "auto", "mock", "live"

    # Redis (Distributed Rate Limiting & Background Queue Readiness)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Request Body Size Protection (Enforced via Middleware)
    MAX_REQUEST_BODY_SIZE_MB: int = 30

    # Graceful Shutdown
    GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS: int = 15

    # Rate Limiting & User Quotas (Configurable per-tier defaults)
    RATE_LIMIT_FREE_HOURLY: int = 5
    RATE_LIMIT_FREE_DAILY: int = 5
    RATE_LIMIT_FREE_MONTHLY: int = 100
    RATE_LIMIT_FREE_CONCURRENT: int = 1
    RATE_LIMIT_FREE_TAVILY_PER_JOB: int = 5

    RATE_LIMIT_PRO_HOURLY: int = 30
    RATE_LIMIT_PRO_DAILY: int = 50
    RATE_LIMIT_PRO_MONTHLY: int = 1000
    RATE_LIMIT_PRO_CONCURRENT: int = 3
    RATE_LIMIT_PRO_TAVILY_PER_JOB: int = 20

    RATE_LIMIT_ADMIN_HOURLY: int = 1000
    RATE_LIMIT_ADMIN_DAILY: int = 1000
    RATE_LIMIT_ADMIN_MONTHLY: int = 50000
    RATE_LIMIT_ADMIN_CONCURRENT: int = 10
    RATE_LIMIT_ADMIN_TAVILY_PER_JOB: int = 50

    def get_tier_limits(self, tier: str) -> dict:
        t = (tier or "free").lower()
        if t in ("admin", "enterprise"):
            return {
                "hourly_submissions": self.RATE_LIMIT_ADMIN_HOURLY,
                "daily_jobs": self.RATE_LIMIT_ADMIN_DAILY,
                "monthly_jobs": self.RATE_LIMIT_ADMIN_MONTHLY,
                "concurrent_jobs": self.RATE_LIMIT_ADMIN_CONCURRENT,
                "tavily_searches_per_job": self.RATE_LIMIT_ADMIN_TAVILY_PER_JOB,
            }
        elif t == "pro":
            return {
                "hourly_submissions": self.RATE_LIMIT_PRO_HOURLY,
                "daily_jobs": self.RATE_LIMIT_PRO_DAILY,
                "monthly_jobs": self.RATE_LIMIT_PRO_MONTHLY,
                "concurrent_jobs": self.RATE_LIMIT_PRO_CONCURRENT,
                "tavily_searches_per_job": self.RATE_LIMIT_PRO_TAVILY_PER_JOB,
            }
        return {
            "hourly_submissions": self.RATE_LIMIT_FREE_HOURLY,
            "daily_jobs": self.RATE_LIMIT_FREE_DAILY,
            "monthly_jobs": self.RATE_LIMIT_FREE_MONTHLY,
            "concurrent_jobs": self.RATE_LIMIT_FREE_CONCURRENT,
            "tavily_searches_per_job": self.RATE_LIMIT_FREE_TAVILY_PER_JOB,
        }

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip())

    @property
    def has_tavily_key(self) -> bool:
        return bool(self.TAVILY_API_KEY and self.TAVILY_API_KEY.strip())

    @property
    def effective_llm_mode(self) -> str:
        mode = self.PROVIDER_MODE.lower()
        if mode == "mock":
            return "mock"
        elif mode == "live":
            return "live"
        return "live" if self.has_gemini_key else "mock"

    @property
    def effective_embedding_mode(self) -> str:
        mode = self.PROVIDER_MODE.lower()
        if mode == "mock":
            return "mock"
        elif mode == "live":
            return "live"
        return "live" if self.has_gemini_key else "mock"

    @property
    def effective_web_search_mode(self) -> str:
        mode = self.PROVIDER_MODE.lower()
        if mode == "mock":
            return "mock"
        elif mode == "live":
            return "live"
        return "live" if self.has_tavily_key else "mock"

    @property
    def has_stripe_key(self) -> bool:
        return bool(self.STRIPE_SECRET_KEY and self.STRIPE_SECRET_KEY.strip())

    @property
    def effective_stripe_mode(self) -> str:
        mode = (self.STRIPE_MODE or "auto").lower()
        if mode == "mock":
            return "mock"
        elif mode == "live":
            return "live"
        return "live" if self.has_stripe_key else "mock"

    @property
    def safe_db_summary(self) -> str:
        """Safe database target description omitting all credentials."""
        info = get_safe_db_target(self.DATABASE_URL)
        return info.get("safe_summary", "unknown")

    @property
    def safe_sync_db_summary(self) -> str:
        """Safe synchronous database target description omitting all credentials."""
        info = get_safe_db_target(self.SYNC_DATABASE_URL)
        return info.get("safe_summary", "unknown")

    @model_validator(mode="after")
    def normalize_settings(self):
        is_production = self.APP_ENV.lower() == "production"

        # 1. Inspect and normalize async DATABASE_URL
        url = self.DATABASE_URL or ""

        # Production startup validation for DATABASE_URL
        if is_production:
            if not url or not url.strip():
                raise ValueError(
                    "FATAL CONFIGURATION ERROR: DATABASE_URL is missing or empty in production! "
                    "In Render, ensure researchpilot-api has DATABASE_URL linked from researchpilot-db."
                )
            
            # Inspect host and port to detect unintentional fallback to localhost or dev port
            db_target = get_safe_db_target(url)
            host = str(db_target.get("host", "")).lower()
            port = db_target.get("port")
            if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or port == 5433:
                raise ValueError(
                    f"FATAL CONFIGURATION ERROR: DATABASE_URL in production points to a local address "
                    f"({host}:{port}). Render web services cannot connect to localhost for managed databases. "
                    f"Please ensure Render's managed database connection string is properly configured."
                )

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # asyncpg requires ssl=require instead of sslmode=require
        if "sslmode=" in url:
            url = url.replace("sslmode=require", "ssl=require").replace("sslmode=prefer", "").replace("sslmode=disable", "")
        self.DATABASE_URL = url

        # 2. Normalize SYNC_DATABASE_URL for Alembic and synchronous tooling
        sync = self.SYNC_DATABASE_URL
        url_target = get_safe_db_target(url)
        sync_target = get_safe_db_target(sync) if sync else {}

        is_url_remote = (
            url_target.get("host") not in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "none", "unknown")
            and url_target.get("port") != 5433
        )
        is_sync_local = (
            sync_target.get("host") in ("localhost", "127.0.0.1", "::1", "0.0.0.0")
            or sync_target.get("port") == 5433
        )

        if not sync or not sync.strip() or (is_url_remote and is_sync_local):
            # Automatically derive from DATABASE_URL
            sync = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
            # psycopg2 requires sslmode=require instead of ssl=require
            if "ssl=require" in sync:
                sync = sync.replace("ssl=require", "sslmode=require")
        else:
            if sync.startswith("postgres://"):
                sync = sync.replace("postgres://", "postgresql+psycopg2://", 1)
            elif sync.startswith("postgresql://") and not sync.startswith("postgresql+"):
                sync = sync.replace("postgresql://", "postgresql+psycopg2://", 1)
            elif sync.startswith("postgresql+asyncpg://"):
                sync = sync.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
            if "ssl=require" in sync:
                sync = sync.replace("ssl=require", "sslmode=require")

        if is_production:
            sync_target = get_safe_db_target(sync)
            s_host = str(sync_target.get("host", "")).lower()
            s_port = sync_target.get("port")
            if s_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or s_port == 5433:
                raise ValueError(
                    f"FATAL CONFIGURATION ERROR: SYNC_DATABASE_URL in production points to a local address "
                    f"({s_host}:{s_port}). Please verify Render environment variables."
                )

        self.SYNC_DATABASE_URL = sync

        # 3. Normalize CORS_ORIGINS if provided as comma-separated string
        if isinstance(self.CORS_ORIGINS, str):
            self.CORS_ORIGINS = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

        return self


    model_config = SettingsConfigDict(
        env_file=(".env", str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
