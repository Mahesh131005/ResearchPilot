import logging
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import ProviderAuthenticationError, ProviderQuotaError, ProviderAPIError
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.gemini_provider import GeminiEmbeddingProvider, GeminiProvider
from app.providers.cohere_provider import CohereProvider
from app.providers.mock_provider import MockEmbeddingProvider, MockLLMProvider

logger = logging.getLogger("researchpilot")
T = TypeVar("T", bound=BaseModel)


class FallbackLLMProvider(LLMProvider):
    """
    Resilient multi-provider wrapper:
    Attempts request with primary LLM (e.g. Gemini).
    Upon quota exhaustion or transient failure, automatically falls back to secondary LLM (e.g. Cohere).
    """

    def __init__(self, primary: LLMProvider, secondary: LLMProvider):
        self.primary = primary
        self.secondary = secondary

    @property
    def is_live(self) -> bool:
        return self.primary.is_live or self.secondary.is_live

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        try:
            return await self.primary.generate(prompt, system_instruction, temperature)
        except (ProviderQuotaError, ProviderAPIError) as e:
            if self.secondary and self.secondary.is_live:
                logger.warning(f"Primary LLM provider failed ({e}). Automatically failing over to secondary LLM...")
                return await self.secondary.generate(prompt, system_instruction, temperature)
            raise

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> T:
        try:
            return await self.primary.generate_structured(prompt, schema, system_instruction, temperature)
        except (ProviderQuotaError, ProviderAPIError) as e:
            if self.secondary and self.secondary.is_live:
                logger.warning(f"Primary LLM structured generation failed ({e}). Failing over to secondary LLM...")
                return await self.secondary.generate_structured(prompt, schema, system_instruction, temperature)
            raise


def get_embedding_provider(
    provider_name: Optional[str] = None,
    custom_api_key: Optional[str] = None,
) -> EmbeddingProvider:
    """
    Returns the appropriate dense embedding provider based on configuration and mode.
    """
    mode = settings.PROVIDER_MODE.lower()
    name = (provider_name or settings.EMBEDDING_PROVIDER).lower()

    if mode == "mock" or name in ["mock", "test", "local"]:
        return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM)

    active_key = custom_api_key or settings.GEMINI_API_KEY
    if mode == "live":
        if not active_key:
            raise ProviderAuthenticationError(
                "PROVIDER_MODE is set to 'live' but GEMINI_API_KEY is not configured."
            )
        return GeminiEmbeddingProvider(
            api_key=active_key,
            model=settings.EMBEDDING_MODEL
        )

    # mode == "auto"
    if active_key:
        return GeminiEmbeddingProvider(
            api_key=active_key,
            model=settings.EMBEDDING_MODEL
        )
    return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM)


def get_llm_provider(
    provider_name: Optional[str] = None,
    custom_api_key: Optional[str] = None,
    custom_cohere_key: Optional[str] = None,
) -> LLMProvider:
    """
    Returns the appropriate LLM provider based on configuration, requested provider, and available keys.
    Supports Bring Your Own Key (BYOK) and automatic multi-provider fallback between Gemini and Cohere.
    """
    mode = settings.PROVIDER_MODE.lower()
    name = (provider_name or settings.LLM_PROVIDER).lower()

    if mode == "mock" or name in ["mock", "test", "local"]:
        return MockLLMProvider()

    # 1. Custom User Keys (BYOK - Bring Your Own Key)
    if custom_api_key and name != "cohere":
        return GeminiProvider(api_key=custom_api_key, model=settings.LLM_MODEL)
    if custom_cohere_key or (custom_api_key and name == "cohere"):
        cohere_key = custom_cohere_key or custom_api_key
        return CohereProvider(api_key=cohere_key, model=settings.COHERE_MODEL)

    # 2. Explicit Provider Selection
    if name == "cohere":
        if settings.has_cohere_key:
            return CohereProvider(api_key=settings.COHERE_API_KEY, model=settings.COHERE_MODEL)
        elif mode == "live":
            raise ProviderAuthenticationError("COHERE_API_KEY is not configured in environment.")

    if name == "gemini":
        if settings.has_gemini_key:
            return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.LLM_MODEL)
        elif mode == "live":
            raise ProviderAuthenticationError("GEMINI_API_KEY is not configured in environment.")

    # 3. Multi-Provider Fallback Pool (Auto / Live)
    # If both keys are present, Gemini acts as primary and Cohere acts as automatic failover!
    if settings.has_gemini_key and settings.has_cohere_key:
        primary = GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.LLM_MODEL)
        secondary = CohereProvider(api_key=settings.COHERE_API_KEY, model=settings.COHERE_MODEL)
        return FallbackLLMProvider(primary=primary, secondary=secondary)

    # Single provider available
    if settings.has_gemini_key:
        return GeminiProvider(api_key=settings.GEMINI_API_KEY, model=settings.LLM_MODEL)

    if settings.has_cohere_key:
        return CohereProvider(api_key=settings.COHERE_API_KEY, model=settings.COHERE_MODEL)

    if mode == "live":
        raise ProviderAuthenticationError(
            "Neither GEMINI_API_KEY nor COHERE_API_KEY is configured. Set at least one API key."
        )

    return MockLLMProvider()
