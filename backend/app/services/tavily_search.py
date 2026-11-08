import os
import hashlib
from typing import List, Dict, Any, Optional
from tavily import TavilyClient

from app.core.config import settings
from app.services.usage_service import UsageService
from app.core.errors import (
    ProviderAuthenticationError,
    ProviderQuotaError,
    ProviderAPIError,
)

class TavilySearchService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.TAVILY_API_KEY
        self.client = TavilyClient(api_key=self.api_key) if (self.api_key and self.api_key.strip()) else None

    @property
    def is_live(self) -> bool:
        mode = settings.PROVIDER_MODE.lower()
        if mode == "mock":
            return False
        if mode == "live":
            return True
        return bool(self.client)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> List[Dict[str, Any]]:
        """
        Executes web search via Tavily API with source deduplication and URL validation.
        In mock mode or when TAVILY_API_KEY is not supplied in auto mode, returns clearly labeled mock sources.
        In live mode or when a key is provided, genuine authenticated searches are performed.
        If an authenticated live search fails (e.g. invalid key or quota exhausted), an error is raised.
        """
        mode = settings.PROVIDER_MODE.lower()

        # Strict Mock Mode
        if mode == "mock":
            results = self._mock_web_search(query)
            await self._record_search_usage(query, search_depth, len(results), is_live=False)
            return results

        # Strict Live Mode without Key
        if mode == "live" and not self.client:
            raise ProviderAuthenticationError(
                "PROVIDER_MODE is set to 'live' but TAVILY_API_KEY is not configured in backend/.env. "
                "Set a valid TAVILY_API_KEY or change PROVIDER_MODE to 'mock' or 'auto'."
            )

        # Auto Mode without Key -> Graceful Mock
        if not self.client:
            results = self._mock_web_search(query)
            await self._record_search_usage(query, search_depth, len(results), is_live=False)
            return results

        # Live Mode / Authenticated Call
        if not settings.BILLABLE_OPERATIONS_ENABLED and self.is_live:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Live billable operations are temporarily suspended by administrator "
                    "(BILLABLE_OPERATIONS_ENABLED=False). Live external web search is paused. "
                    "Switch to PROVIDER_MODE='mock' or enable billable operations to proceed."
                ),
            )

        try:
            response = self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_answer=False,
                include_raw_content=False,
            )
            raw_results = response.get("results", [])
            results = []
            seen_urls = set()

            for item in raw_results:
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                results.append({
                    "title": item.get("title", "Web Research Source"),
                    "url": url,
                    "content": item.get("content", ""),
                    "published_date": item.get("published_date") or None,
                    "score": item.get("score", 0.8),
                    "is_mock": False,
                })
            await self._record_search_usage(query, search_depth, len(results), is_live=True)
            return results

        except Exception as e:
            err_str = str(e)
            if "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower() or "401" in err_str or "403" in err_str:
                raise ProviderAuthenticationError(
                    f"Tavily API search failed: Invalid or unauthorized API key. Details: {err_str}"
                ) from e
            elif "429" in err_str or "rate limit" in err_str.lower() or "quota" in err_str.lower():
                raise ProviderQuotaError(
                    f"Tavily API search failed: Rate limit or credit quota exceeded. Details: {err_str}"
                ) from e
            else:
                raise ProviderAPIError(
                    f"Tavily API search failed: {err_str}"
                ) from e

    async def _record_search_usage(self, query: str, search_depth: str, count: int, is_live: bool):
        try:
            from app.core.usage_context import get_usage_context
            ctx = get_usage_context()
            scope = ctx.get("job_id") or ctx.get("user_id") or "global"
            q_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()[:16]
            await UsageService.record_from_context(
                provider="tavily",
                operation_type="web_search",
                request_count=1,
                search_depth=search_depth,
                is_estimated=not is_live,
                usage_metadata_available=True,
                idempotency_key=f"tavily:{scope}:{q_hash}",
                meta_info={"query": query[:120], "is_mock": not is_live, "result_count": count},
            )
        except Exception:
            pass

    def _mock_web_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Deterministic mock web research results used when running in mock mode.
        Clearly marked as [MOCK EVIDENCE] to ensure full transparency.
        """
        q_lower = query.lower()
        if "banking" in q_lower or "india" in q_lower or "rbi" in q_lower:
            return [
                {
                    "title": "[MOCK EVIDENCE] Reserve Bank of India - Report on Trend and Progress of Banking",
                    "url": "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Trend+and+Progress+of+Banking+in+India",
                    "content": "[SIMULATED WEB RESEARCH] Indian scheduled commercial banks are scaling artificial intelligence pilots across credit underwriting, algorithmic compliance monitoring, and customer service automation under supervisory guidance.",
                    "published_date": "2025-01-15",
                    "score": 0.92,
                    "is_mock": True,
                },
                {
                    "title": "[MOCK EVIDENCE] Bank for International Settlements - Financial Stability and AI",
                    "url": "https://www.bis.org/publ/bppdf/bispap135.htm",
                    "content": "[SIMULATED WEB RESEARCH] Emerging market economies face specific opportunities and tail risks from generative AI, including operational resilience vulnerabilities, data localization mandates, and third-party vendor concentration.",
                    "published_date": "2025-02-10",
                    "score": 0.88,
                    "is_mock": True,
                }
            ]
        else:
            return [
                {
                    "title": f"[MOCK EVIDENCE] Industry Analysis: {query[:40]}",
                    "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
                    "content": f"[SIMULATED WEB RESEARCH] Synthetic research overview covering technology developments and adoption risks regarding {query}.",
                    "published_date": "2025-03-01",
                    "score": 0.80,
                    "is_mock": True,
                }
            ]
