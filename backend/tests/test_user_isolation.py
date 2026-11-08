import io
import uuid
import pytest
from httpx import AsyncClient

@pytest.fixture
async def user_a_headers(async_client: AsyncClient):
    email = f"user_a_{uuid.uuid4().hex[:8]}@isolation.test"
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "UserAPassword2026!"}
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.fixture
async def user_b_headers(async_client: AsyncClient):
    email = f"user_b_{uuid.uuid4().hex[:8]}@isolation.test"
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "UserBPassword2026!"}
    )
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}

@pytest.mark.asyncio
async def test_document_cross_user_isolation_and_anti_enumeration(
    async_client: AsyncClient,
    sample_pdf_bytes: bytes,
    user_a_headers: dict,
    user_b_headers: dict,
):
    # 1. User A uploads a document
    files = {
        "file": ("user_a_confidential.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")
    }
    upload_resp = await async_client.post(
        "/api/v1/documents/upload",
        files=files,
        headers=user_a_headers
    )
    assert upload_resp.status_code == 201
    doc_a = upload_resp.json()
    doc_a_id = doc_a["id"]

    # 2. User A can see their own document
    list_a = await async_client.get("/api/v1/documents", headers=user_a_headers)
    assert list_a.status_code == 200
    assert any(d["id"] == doc_a_id for d in list_a.json())

    get_a = await async_client.get(f"/api/v1/documents/{doc_a_id}", headers=user_a_headers)
    assert get_a.status_code == 200

    chunks_a = await async_client.get(f"/api/v1/documents/{doc_a_id}/chunks", headers=user_a_headers)
    assert chunks_a.status_code == 200

    # 3. User B list documents DOES NOT contain User A's document
    list_b = await async_client.get("/api/v1/documents", headers=user_b_headers)
    assert list_b.status_code == 200
    assert not any(d["id"] == doc_a_id for d in list_b.json())

    # 4. Anti-Enumeration: User B accessing User A's document returns 404 Not Found (never 403)
    get_b = await async_client.get(f"/api/v1/documents/{doc_a_id}", headers=user_b_headers)
    assert get_b.status_code == 404, f"Expected 404 for foreign doc, got {get_b.status_code}"

    # 5. Anti-Enumeration: User B accessing User A's document chunks returns 404
    chunks_b = await async_client.get(f"/api/v1/documents/{doc_a_id}/chunks", headers=user_b_headers)
    assert chunks_b.status_code == 404

    # 6. Anti-Enumeration: User B attempting to delete User A's document returns 404
    del_b = await async_client.delete(f"/api/v1/documents/{doc_a_id}", headers=user_b_headers)
    assert del_b.status_code == 404

    # 7. Document still exists and is untouched for User A
    get_a_again = await async_client.get(f"/api/v1/documents/{doc_a_id}", headers=user_a_headers)
    assert get_a_again.status_code == 200

@pytest.mark.asyncio
async def test_research_job_cross_user_isolation(
    async_client: AsyncClient,
    sample_pdf_bytes: bytes,
    user_a_headers: dict,
    user_b_headers: dict,
):
    # 1. User A creates a research job
    create_job_resp = await async_client.post(
        "/api/v1/research/jobs",
        json={
            "query": "Analysis of quantum computing in pharmaceutical discovery",
            "depth": "quick",
            "enable_web": False,
            "enable_documents": False,
            "document_ids": [],
        },
        headers=user_a_headers
    )
    assert create_job_resp.status_code == 201
    job_a = create_job_resp.json()
    job_a_id = job_a["id"]

    # 2. User A can list and get the job
    list_a = await async_client.get("/api/v1/research/jobs", headers=user_a_headers)
    assert any(j["id"] == job_a_id for j in list_a.json())

    get_a = await async_client.get(f"/api/v1/research/jobs/{job_a_id}", headers=user_a_headers)
    assert get_a.status_code == 200

    # 3. User B cannot see User A's job in listing
    list_b = await async_client.get("/api/v1/research/jobs", headers=user_b_headers)
    assert not any(j["id"] == job_a_id for j in list_b.json())

    # 4. Anti-enumeration: User B accessing User A's job endpoints gets 404
    get_b = await async_client.get(f"/api/v1/research/jobs/{job_a_id}", headers=user_b_headers)
    assert get_b.status_code == 404

    events_b = await async_client.get(f"/api/v1/research/jobs/{job_a_id}/events", headers=user_b_headers)
    assert events_b.status_code == 404

    report_b = await async_client.get(f"/api/v1/research/jobs/{job_a_id}/report", headers=user_b_headers)
    assert report_b.status_code == 404

    del_b = await async_client.delete(f"/api/v1/research/jobs/{job_a_id}", headers=user_b_headers)
    assert del_b.status_code == 404

    # 5. User B cannot attach User A's document to a job
    # First, User A uploads doc
    files = {"file": ("user_a_doc.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    up = await async_client.post("/api/v1/documents/upload", files=files, headers=user_a_headers)
    doc_a_id = up.json()["id"]

    # User B tries to start job using User A's document ID -> returns 404
    unauth_job = await async_client.post(
        "/api/v1/research/jobs",
        json={
            "query": "Inquire about user A document",
            "depth": "quick",
            "enable_web": False,
            "enable_documents": True,
            "document_ids": [doc_a_id],
        },
        headers=user_b_headers
    )
    assert unauth_job.status_code == 404

@pytest.mark.asyncio
async def test_qa_and_search_cross_user_isolation(
    async_client: AsyncClient,
    sample_pdf_bytes: bytes,
    user_a_headers: dict,
    user_b_headers: dict,
):
    # User A uploads a document
    files = {"file": ("banking_ai_secret.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    up = await async_client.post("/api/v1/documents/upload", files=files, headers=user_a_headers)
    assert up.status_code == 201
    doc_a_id = up.json()["id"]

    # User B searches chunks without specifying document_id -> receives 0 results from User A's docs
    search_b = await async_client.post(
        "/api/v1/qa/search",
        json={"query": "Generative Artificial Intelligence Banking", "top_k": 5},
        headers=user_b_headers
    )
    assert search_b.status_code == 200
    assert len(search_b.json()) == 0

    # User B explicitly tries to search using User A's document_id -> 404 Not Found
    search_b_target = await async_client.post(
        "/api/v1/qa/search",
        json={"query": "Banking", "document_id": doc_a_id},
        headers=user_b_headers
    )
    assert search_b_target.status_code == 404

    # User B explicitly tries to query using User A's document_id -> 404 Not Found
    query_b_target = await async_client.post(
        "/api/v1/qa/query",
        json={"query": "What are the challenges?", "document_id": doc_a_id},
        headers=user_b_headers
    )
    assert query_b_target.status_code == 404

