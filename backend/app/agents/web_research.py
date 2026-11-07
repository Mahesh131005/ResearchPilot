import uuid
from typing import List, Dict, Any, Optional
from app.services.tavily_search import TavilySearchService
from app.schemas.research import SubQuestion

class WebResearchAgent:
    """Specialized agent conducting web search, source verification, and deduplication via Tavily."""

    def __init__(self, search_service: Optional[TavilySearchService] = None):
        self.search_service = search_service or TavilySearchService()

    async def research(self, sub_questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        evidence_items = []
        seen_urls = set()

        for sq in sub_questions:
            # Check if this sub-question targets web
            source_type = sq.get("source_type", "both")
            if source_type not in ["web", "both"]:
                continue

            q_text = sq.get("question", "")
            results = await self.search_service.search(q_text, max_results=3)

            for item in results:
                url = item.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                evidence_items.append({
                    "id": str(uuid.uuid4()),
                    "source_type": "web",
                    "title": item.get("title", "Web Evidence"),
                    "content": item.get("content", ""),
                    "url": url,
                    "document_id": None,
                    "page_number": None,
                    "published_date": item.get("published_date"),
                    "relevance_score": item.get("score", 0.8),
                    "sub_question_id": sq.get("id"),
                })

        return evidence_items

