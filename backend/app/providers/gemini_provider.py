import os
from typing import List, Optional, Type, TypeVar
from pydantic import BaseModel
from google import genai
from google.genai import types, errors

from app.core.config import settings
from app.core.errors import (
    ProviderAuthenticationError,
    ProviderQuotaError,
    ProviderAPIError,
)
from app.providers.base import EmbeddingProvider, LLMProvider

T = TypeVar("T", bound=BaseModel)

class GeminiEmbeddingProvider(EmbeddingProvider):
    """Generates vector embeddings using Google's Gemini Embedding API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.model = model or settings.EMBEDDING_MODEL
        if not self.api_key:
            raise ProviderAuthenticationError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in backend/.env for live mode, "
                "or set PROVIDER_MODE=mock to run in offline simulation mode."
            )
        self._client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})

    @property
    def is_live(self) -> bool:
        return True

    def _handle_error(self, e: Exception) -> Exception:
        err_str = str(e)
        code = getattr(e, "code", None)
        if isinstance(e, errors.ClientError) or code in [400, 401, 403] or "API_KEY_INVALID" in err_str or "INVALID_ARGUMENT" in err_str or "PERMISSION_DENIED" in err_str:
            return ProviderAuthenticationError(
                f"Gemini Embedding API authentication failed: Invalid API key or unauthorized. Details: {err_str}"
            )
        elif code == 429 or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            return ProviderQuotaError(
                f"Gemini Embedding API rate limit or quota exceeded: {err_str}"
            )
        return ProviderAPIError(f"Gemini Embedding API call failed: {err_str}")

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            config = types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM)
            response = self._client.models.embed_content(
                model=self.model,
                contents=texts,
                config=config,
            )
            return [list(item.values) for item in response.embeddings]
        except Exception as e:
            raise self._handle_error(e) from e

    async def embed_query(self, text: str) -> List[float]:
        if not text:
            raise ValueError("Query text cannot be empty.")
        try:
            config = types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM)
            response = self._client.models.embed_content(
                model=self.model,
                contents=[text],
                config=config,
            )
            return list(response.embeddings[0].values)
        except Exception as e:
            raise self._handle_error(e) from e


class GeminiProvider(LLMProvider):
    """Text generation and structured output using Gemini models."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
        self.model = model or settings.LLM_MODEL
        if not self.api_key:
            raise ProviderAuthenticationError(
                "GEMINI_API_KEY is not configured. Set GEMINI_API_KEY in backend/.env for live mode, "
                "or set PROVIDER_MODE=mock to run in offline simulation mode."
            )
        self._client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})

    @property
    def is_live(self) -> bool:
        return True

    def _handle_error(self, e: Exception) -> Exception:
        err_str = str(e)
        code = getattr(e, "code", None)
        if isinstance(e, errors.ClientError) or code in [400, 401, 403] or "API_KEY_INVALID" in err_str or "INVALID_ARGUMENT" in err_str or "PERMISSION_DENIED" in err_str:
            return ProviderAuthenticationError(
                f"Gemini LLM API authentication failed: Invalid API key or unauthorized. Details: {err_str}"
            )
        elif code == 429 or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            return ProviderQuotaError(
                f"Gemini LLM API rate limit or quota exceeded: {err_str}"
            )
        return ProviderAPIError(f"Gemini LLM API call failed: {err_str}")

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        import asyncio
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction if system_instruction else None,
        )
        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                return response.text or ""
            except Exception as e:
                if attempt == 0 and any(k in str(e).lower() for k in ["10053", "10054", "aborted", "reset", "timeout"]):
                    await asyncio.sleep(1.5)
                    continue
                raise self._handle_error(e) from e

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> T:
        import asyncio
        config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system_instruction if system_instruction else None,
            response_mime_type="application/json",
            response_schema=schema,
        )
        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                return schema.model_validate_json(response.text)
            except Exception as e:
                if attempt == 0 and any(k in str(e).lower() for k in ["10053", "10054", "aborted", "reset", "timeout"]):
                    await asyncio.sleep(1.5)
                    continue
                raise self._handle_error(e) from e
