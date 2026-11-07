import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "ResearchPilot"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres@172.27.2.138:5433/researchpilot"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres@172.27.2.138:5433/researchpilot"

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

    model_config = SettingsConfigDict(
        env_file=(".env", str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
