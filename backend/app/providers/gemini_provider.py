import os
import hashlib
from typing import List, Optional, Type, TypeVar
from pydantic import BaseModel
from google import genai
from google.genai import types, errors

from app.core.config import settings
from app.services.usage_service import UsageService
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
        import asyncio
        for attempt in range(3):
            try:
                config = types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM)
                response = self._client.models.embed_content(
                    model=self.model,
                    contents=texts,
                    config=config,
                )
                embeddings = [list(item.values) for item in response.embeddings]
                usage_meta = getattr(response, "usage_metadata", None)
                emb_tok = getattr(usage_meta, "total_token_count", None)
                has_meta = emb_tok is not None
                if not has_meta:
                    emb_tok = 0
                await UsageService.record_from_context(
                    provider="gemini",
                    operation_type="embedding",
                    model_name=self.model,
                    embedding_tokens=emb_tok,
                    is_estimated=not has_meta,
                    usage_metadata_available=has_meta,
                    meta_info={"text_count": len(texts), "limitation": "Gemini embed_content API does not return token count" if not has_meta else None},
                )
                return embeddings
            except Exception as e:
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in ["10053", "10054", "aborted", "reset", "timeout", "503", "unavailable", "high demand"])
                if attempt < 2 and is_transient:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                raise self._handle_error(e) from e

    async def embed_query(self, text: str) -> List[float]:
        if not text:
            raise ValueError("Query text cannot be empty.")
        import asyncio
        for attempt in range(3):
            try:
                config = types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM)
                response = self._client.models.embed_content(
                    model=self.model,
                    contents=[text],
                    config=config,
                )
                embedding = list(response.embeddings[0].values)
                usage_meta = getattr(response, "usage_metadata", None)
                emb_tok = getattr(usage_meta, "total_token_count", None)
                has_meta = emb_tok is not None
                if not has_meta:
                    emb_tok = 0
                await UsageService.record_from_context(
                    provider="gemini",
                    operation_type="embedding",
                    model_name=self.model,
                    embedding_tokens=emb_tok,
                    is_estimated=not has_meta,
                    usage_metadata_available=has_meta,
                    meta_info={"text_count": 1, "limitation": "Gemini embed_content API does not return token count" if not has_meta else None},
                )
                return embedding
            except Exception as e:
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in ["10053", "10054", "aborted", "reset", "timeout", "503", "unavailable", "high demand"])
                if attempt < 2 and is_transient:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
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
        for attempt in range(3):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                text = response.text or ""
                usage_meta = getattr(response, "usage_metadata", None)
                in_tok = getattr(usage_meta, "prompt_token_count", 0) or 0
                out_tok = getattr(usage_meta, "candidates_token_count", 0) or 0
                tot_tok = getattr(usage_meta, "total_token_count", 0) or (in_tok + out_tok)
                has_meta = usage_meta is not None and tot_tok > 0

                p_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()[:16]
                from app.core.usage_context import get_usage_context
                _ctx = get_usage_context()
                _scope = _ctx.get("job_id") or _ctx.get("user_id") or "global" if _ctx else "global"
                await UsageService.record_from_context(
                    provider="gemini",
                    operation_type="llm_generation",
                    model_name=self.model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    total_tokens=tot_tok,
                    is_estimated=not has_meta,
                    usage_metadata_available=has_meta,
                    idempotency_key=f"gemini:{_scope}:{self.model}:{p_hash}",
                    meta_info={"model": self.model, "has_actual_metadata": has_meta},
                )
                return text
            except Exception as e:
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in ["10053", "10054", "aborted", "reset", "timeout", "503", "unavailable", "high demand"])
                if attempt < 2 and is_transient:
                    await asyncio.sleep(2.0 * (attempt + 1))
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
        for attempt in range(3):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )
                parsed = schema.model_validate_json(response.text)
                usage_meta = getattr(response, "usage_metadata", None)
                in_tok = getattr(usage_meta, "prompt_token_count", 0) or 0
                out_tok = getattr(usage_meta, "candidates_token_count", 0) or 0
                tot_tok = getattr(usage_meta, "total_token_count", 0) or (in_tok + out_tok)
                has_meta = usage_meta is not None and tot_tok > 0

                p_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()[:16]
                from app.core.usage_context import get_usage_context
                _ctx = get_usage_context()
                _scope = _ctx.get("job_id") or _ctx.get("user_id") or "global" if _ctx else "global"
                await UsageService.record_from_context(
                    provider="gemini",
                    operation_type="structured_generation",
                    model_name=self.model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    total_tokens=tot_tok,
                    is_estimated=not has_meta,
                    usage_metadata_available=has_meta,
                    idempotency_key=f"gemini:{_scope}:{self.model}:{schema.__name__}:{p_hash}",
                    meta_info={"model": self.model, "schema": schema.__name__, "has_actual_metadata": has_meta},
                )
                return parsed
            except Exception as e:
                err_str = str(e).lower()
                is_transient = any(k in err_str for k in ["10053", "10054", "aborted", "reset", "timeout", "503", "unavailable", "high demand"])
                if attempt < 2 and is_transient:
                    await asyncio.sleep(2.0 * (attempt + 1))
                    continue
                raise self._handle_error(e) from e
