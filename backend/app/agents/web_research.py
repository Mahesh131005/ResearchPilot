import uuid
from typing import List, Dict, Any, Optional
from app.services.tavily_search import TavilySearchService
from app.schemas.research import SubQuestion

class WebResearchAgent:
    """Specialized agent conducting web search, source verification, and deduplication via Tavily."""

    def __init__(self, search_service: Optional[TavilySearchService] = None):
        self.search_service = search_service or TavilySearchService()

    async def research(
        self,
        sub_questions: List[Dict[str, Any]],
        max_searches: int = 5,
    ) -> List[Dict[str, Any]]:
        evidence_items = []
        seen_urls = set()
        searches_performed = 0

        for sq in sub_questions:
            if searches_performed >= max_searches:
                break

            # Check if this sub-question targets web
            source_type = sq.get("source_type", "both")
            if source_type not in ["web", "both"]:
                continue

            # Prefer optimized search_query if available, else fallback to question
            q_text = sq.get("search_query") or sq.get("question", "")
            searches_performed += 1

            try:
                results = await self.search_service.search(q_text, max_results=3)
            except Exception:
                # Resilient degradation: skip failed query and continue with remaining searches
                results = []

            for item in results:
                url = item.get("url", "").strip()
                if not url:
                    continue
                # Normalize URL (strip trailing slash and fragment)
                normalized_url = url.split("#")[0].rstrip("/")
                if normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)

                content = (item.get("content") or "").strip()
                if not content:
                    continue

                evidence_items.append({
                    "id": str(uuid.uuid4()),
                    "source_type": "web",
                    "title": item.get("title", "Web Evidence").strip(),
                    "content": content,
                    "url": url,
                    "document_id": None,
                    "page_number": None,
                    "published_date": item.get("published_date"),
                    "relevance_score": float(item.get("score", 0.8)),
                    "sub_question_id": sq.get("id"),
                })

        return evidence_items

