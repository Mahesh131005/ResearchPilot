import pytest
import io
from app.providers.mock_provider import MockEmbeddingProvider, MockLLMProvider
from app.services.retrieval_service import RetrievalService
from app.services.document_qa_service import DocumentQAService
from app.schemas.qa import DocumentQueryRequest
from app.services.document_service import DocumentService
from fastapi import UploadFile

@pytest.mark.asyncio
async def test_mock_embedding_provider():
    provider = MockEmbeddingProvider(dim=768)
    vector = await provider.embed_query("artificial intelligence")
    assert len(vector) == 768
    assert any(v != 0.0 for v in vector)

    batch_vectors = await provider.embed_documents(["document one", "document two"])
    assert len(batch_vectors) == 2
    assert len(batch_vectors[0]) == 768
    assert len(batch_vectors[1]) == 768

@pytest.mark.asyncio
async def test_semantic_retrieval_and_qa_pipeline(async_client, sample_pdf_bytes):
    # 1. Upload sample document through API
    files = {
        "file": ("indian_banking_ai.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")
    }
    upload_res = await async_client.post("/api/v1/documents/upload", files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    try:
        # 2. Test Semantic Retrieval for RBI Guidelines (Should match Page 2)
        rbi_query = {
            "query": "Reserve Bank of India guidelines on regulatory compliance and explainability",
            "document_id": doc_id,
            "top_k": 3
        }
        search_res = await async_client.post("/api/v1/qa/search", json=rbi_query)
        assert search_res.status_code == 200
        results = search_res.json()
        assert len(results) > 0
        # The top result should be from Page 2
        top_match = results[0]
        assert top_match["page_number"] == 2
        assert "Reserve Bank of India" in top_match["content"]
        assert top_match["similarity_score"] > 0.0

        # 3. Test Semantic Retrieval for Banking AI Adoption (Should match Page 1)
        ai_query = {
            "query": "Generative artificial intelligence credit assessment and fraud detection in banks",
            "document_id": doc_id,
            "top_k": 3
        }
        search_res2 = await async_client.post("/api/v1/qa/search", json=ai_query)
        assert search_res2.status_code == 200
        results2 = search_res2.json()
        assert len(results2) > 0
        assert results2[0]["page_number"] == 1
        assert "Generative Artificial Intelligence" in results2[0]["content"]

        # 4. Test Document Q&A with Page-Level Citations
        qa_query = {
            "query": "What are the regulatory guidelines from the Reserve Bank of India?",
            "document_id": doc_id
        }
        qa_res = await async_client.post("/api/v1/qa/query", json=qa_query)
        assert qa_res.status_code == 200
        qa_data = qa_res.json()
        assert qa_data["has_sufficient_evidence"] is True
        assert len(qa_data["citations"]) > 0
        # Verify citation points to actual document page 2
        assert any(c["page_number"] == 2 for c in qa_data["citations"])
        assert "Reserve Bank of India" in qa_data["answer"]

        # 5. Test Missing Evidence Handling
        unrelated_query = {
            "query": "How do you prepare authentic Neapolitan pizza dough?",
            "document_id": doc_id,
            "threshold": 0.5 # High threshold that pizza recipe won't meet
        }
        unrelated_res = await async_client.post("/api/v1/qa/query", json=unrelated_query)
        assert unrelated_res.status_code == 200
        unrelated_data = unrelated_res.json()
        assert unrelated_data["has_sufficient_evidence"] is False
        assert "Insufficient evidence" in unrelated_data["answer"]
        assert len(unrelated_data["citations"]) == 0

    finally:
        # Clean up test document
        await async_client.delete(f"/api/v1/documents/{doc_id}")

