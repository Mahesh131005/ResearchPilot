import pytest
import io

@pytest.mark.asyncio
async def test_health_check(async_client):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

@pytest.mark.asyncio
async def test_upload_and_inspect_pdf(async_client, sample_pdf_bytes):
    # 1. Upload valid PDF
    files = {
        "file": ("banking_ai_report.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")
    }
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 201
    doc = response.json()
    doc_id = doc["id"]
    assert doc["filename"] == "banking_ai_report.pdf"
    assert doc["status"] == "completed"
    assert doc["page_count"] == 2
    assert doc["total_chunks"] >= 2

    # 2. List documents
    list_resp = await async_client.get("/api/v1/documents")
    assert list_resp.status_code == 200
    docs = list_resp.json()
    assert any(d["id"] == doc_id for d in docs)

    # 3. Get single document
    get_resp = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == doc_id

    # 4. Get chunks with provenance
    chunks_resp = await async_client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert chunks_resp.status_code == 200
    chunks = chunks_resp.json()
    assert len(chunks) >= 2
    assert chunks[0]["page_number"] in [1, 2]
    assert "content" in chunks[0]

    # 5. Check status endpoint
    status_resp = await async_client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"

    # 6. Delete document
    del_resp = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 204

    # 7. Verify 404 after deletion
    after_del = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert after_del.status_code == 404

@pytest.mark.asyncio
async def test_reject_invalid_file_extension(async_client):
    files = {
        "file": ("malicious_script.sh", io.BytesIO(b"echo 'pwned'"), "text/plain")
    }
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]

@pytest.mark.asyncio
async def test_reject_corrupt_pdf(async_client):
    files = {
        "file": ("corrupt.pdf", io.BytesIO(b"%PDF-not-really-a-pdf-file"), "application/pdf")
    }
    response = await async_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 422
    assert "PDF parsing error" in response.json()["detail"]

