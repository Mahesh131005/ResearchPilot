from app.core.config import settings
from app.core.errors import ProviderAuthenticationError
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.gemini_provider import GeminiEmbeddingProvider, GeminiProvider
from app.providers.mock_provider import MockEmbeddingProvider, MockLLMProvider

def get_embedding_provider(provider_name: str = None) -> EmbeddingProvider:
    """
    Returns the appropriate dense embedding provider based on configuration and mode.
    """
    mode = settings.PROVIDER_MODE.lower()
    name = (provider_name or settings.EMBEDDING_PROVIDER).lower()

    if mode == "mock" or name in ["mock", "test", "local"]:
        return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM)

    if mode == "live":
        if not settings.has_gemini_key:
            raise ProviderAuthenticationError(
                "PROVIDER_MODE is set to 'live' but GEMINI_API_KEY is not configured in backend/.env. "
                "Set a valid GEMINI_API_KEY or change PROVIDER_MODE to 'mock' or 'auto'."
            )
        return GeminiEmbeddingProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.EMBEDDING_MODEL
        )

    # mode == "auto"
    if settings.has_gemini_key:
        return GeminiEmbeddingProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.EMBEDDING_MODEL
        )
    return MockEmbeddingProvider(dim=settings.EMBEDDING_DIM)


def get_llm_provider(provider_name: str = None) -> LLMProvider:
    """
    Returns the appropriate LLM provider based on configuration and mode.
    """
    mode = settings.PROVIDER_MODE.lower()
    name = (provider_name or settings.LLM_PROVIDER).lower()

    if mode == "mock" or name in ["mock", "test", "local"]:
        return MockLLMProvider()

    if mode == "live":
        if not settings.has_gemini_key:
            raise ProviderAuthenticationError(
                "PROVIDER_MODE is set to 'live' but GEMINI_API_KEY is not configured in backend/.env. "
                "Set a valid GEMINI_API_KEY or change PROVIDER_MODE to 'mock' or 'auto'."
            )
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.LLM_MODEL
        )

    # mode == "auto"
    if settings.has_gemini_key:
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.LLM_MODEL
        )
    return MockLLMProvider()
