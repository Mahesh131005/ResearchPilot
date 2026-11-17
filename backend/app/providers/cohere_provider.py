import json
import hashlib
import asyncio
from typing import Optional, Type, TypeVar, Dict, Any
from pydantic import BaseModel
import httpx

from app.core.config import settings
from app.core.errors import (
    ProviderAPIError,
    ProviderAuthenticationError,
    ProviderQuotaError,
)
from app.providers.base import LLMProvider
from app.services.usage_service import UsageService

T = TypeVar("T", bound=BaseModel)

COHERE_V2_CHAT_URL = "https://api.cohere.com/v2/chat"


class CohereProvider(LLMProvider):
    """
    High-performance LLM provider implementing Cohere v2 Chat & Structured Output API.
    Supports Command-R, Command-R+, and fast Command-R7B models.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.COHERE_API_KEY
        self.model = model or settings.COHERE_MODEL or "command-r-08-2024"
        if not self.api_key:
            raise ProviderAuthenticationError(
                "COHERE_API_KEY is not configured. Set COHERE_API_KEY in backend/.env or Render Dashboard, "
                "or provide your personal key in the extension settings."
            )

    @property
    def is_live(self) -> bool:
        return True

    def _handle_error(self, status_code: int, err_data: Any) -> Exception:
        err_msg = str(err_data)
        if isinstance(err_data, dict):
            err_msg = err_data.get("message") or str(err_data)

        if status_code in (401, 403) or "unauthorized" in err_msg.lower() or "invalid api key" in err_msg.lower():
            return ProviderAuthenticationError(f"Cohere API authentication failed: {err_msg}")
        elif status_code == 429 or "rate limit" in err_msg.lower() or "quota" in err_msg.lower():
            return ProviderQuotaError(f"Cohere API rate limit or quota exceeded: {err_msg}")
        return ProviderAPIError(f"Cohere API error (HTTP {status_code}): {err_msg}")

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(3):
                try:
                    res = await client.post(COHERE_V2_CHAT_URL, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        content = data.get("message", {}).get("content", [])
                        text = content[0].get("text", "") if content else ""

                        # Usage accounting
                        usage = data.get("usage", {}).get("tokens", {})
                        in_tok = int(usage.get("input_tokens") or 0)
                        out_tok = int(usage.get("output_tokens") or 0)

                        p_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()[:16]
                        from app.core.usage_context import get_usage_context
                        _ctx = get_usage_context()
                        _scope = _ctx.get("job_id") or _ctx.get("user_id") or "global" if _ctx else "global"

                        await UsageService.record_from_context(
                            provider="cohere",
                            operation_type="text_generation",
                            model_name=self.model,
                            input_tokens=in_tok,
                            output_tokens=out_tok,
                            total_tokens=in_tok + out_tok,
                            is_estimated=False,
                            usage_metadata_available=True,
                            idempotency_key=f"cohere:{_scope}:{self.model}:{p_hash}",
                            meta_info={"model": self.model},
                        )
                        return text

                    # Handle retryable transient errors (429 or 5xx)
                    if res.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue

                    err_body = res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text
                    raise self._handle_error(res.status_code, err_body)

                except httpx.RequestError as req_err:
                    if attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    raise ProviderAPIError(f"Cohere network connection failed: {req_err}") from req_err

        raise ProviderAPIError("Cohere API call failed after retries.")

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> T:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        # Cohere v2 native structured output schema
        json_schema = schema.model_json_schema()

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_object",
                "schema": json_schema,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(3):
                try:
                    res = await client.post(COHERE_V2_CHAT_URL, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        content = data.get("message", {}).get("content", [])
                        raw_json = content[0].get("text", "") if content else "{}"

                        # Validate directly against Pydantic schema
                        parsed = schema.model_validate_json(raw_json)

                        # Usage accounting
                        usage = data.get("usage", {}).get("tokens", {})
                        in_tok = int(usage.get("input_tokens") or 0)
                        out_tok = int(usage.get("output_tokens") or 0)

                        p_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()[:16]
                        from app.core.usage_context import get_usage_context
                        _ctx = get_usage_context()
                        _scope = _ctx.get("job_id") or _ctx.get("user_id") or "global" if _ctx else "global"

                        await UsageService.record_from_context(
                            provider="cohere",
                            operation_type="structured_generation",
                            model_name=self.model,
                            input_tokens=in_tok,
                            output_tokens=out_tok,
                            total_tokens=in_tok + out_tok,
                            is_estimated=False,
                            usage_metadata_available=True,
                            idempotency_key=f"cohere:{_scope}:{self.model}:{schema.__name__}:{p_hash}",
                            meta_info={"model": self.model, "schema": schema.__name__},
                        )
                        return parsed

                    # Retry on 429 or 5xx
                    if res.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue

                    err_body = res.json() if res.headers.get("content-type", "").startswith("application/json") else res.text
                    raise self._handle_error(res.status_code, err_body)

                except httpx.RequestError as req_err:
                    if attempt < 2:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    raise ProviderAPIError(f"Cohere network connection failed: {req_err}") from req_err

        raise ProviderAPIError("Cohere structured generation failed after retries.")

